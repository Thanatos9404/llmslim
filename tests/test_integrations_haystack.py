"""LLMSlimDocumentCompressor with real Haystack objects. Skipped when haystack-ai is not installed."""

from __future__ import annotations

import inspect
from typing import List

import pytest

pytest.importorskip("haystack")

from haystack import Document, Pipeline
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from llmslim import count_tokens
from llmslim.integrations._documents import COMPRESSED_TOKENS_KEY, ORIGINAL_TOKENS_KEY
from llmslim.integrations.haystack import LLMSlimDocumentCompressor
from tests._integration_corpus import (
    ANSWER,
    BUDGET,
    CORPUS,
    NON_EMPTY,
    QUERY,
    TARGET_RATIO,
    PreferringScorer,
)


def _documents() -> List[Document]:
    return [
        Document(id=doc_id, content=text, meta={"source": source}, score=1.0 - i / 10)
        for i, (doc_id, source, text) in enumerate(CORPUS)
    ]


def test_keeps_the_relevant_document_within_the_budget():
    documents = _documents() + [Document(id="no-text", content=None, meta={"source": "blob"})]
    result = LLMSlimDocumentCompressor(target_ratio=TARGET_RATIO).run(
        documents=documents, query=QUERY
    )
    assert list(result) == ["documents"]
    out = result["documents"]
    assert [d.id for d in out] == ["refunds"]
    (kept,) = out
    assert ANSWER in kept.content
    assert sum(count_tokens(d.content) for d in out) <= BUDGET
    assert kept.score == pytest.approx(0.8)
    assert kept.meta["source"] == "refunds.md"
    assert kept.meta[ORIGINAL_TOKENS_KEY] == count_tokens(CORPUS[2][2])
    assert kept.meta[COMPRESSED_TOKENS_KEY] == count_tokens(kept.content)
    # The input documents are not modified.
    assert documents[2].meta == {"source": "refunds.md"}
    assert documents[2].content == CORPUS[2][2]


def test_without_a_query_compresses_each_document_and_drops_empty_ones():
    out = LLMSlimDocumentCompressor(target_ratio=TARGET_RATIO).run(documents=_documents())
    assert [d.id for d in out["documents"]] == NON_EMPTY


def test_token_counts_are_optional():
    out = LLMSlimDocumentCompressor(record_token_counts=False).run(
        documents=_documents(), query=QUERY
    )
    assert [d.meta for d in out["documents"]] == [{"source": "refunds.md"}]


def test_custom_relevance_and_options():
    scorer = PreferringScorer("company")
    compressor = LLMSlimDocumentCompressor(
        relevance=scorer, additional_compress_kwargs={"mode": "rag"}
    )
    out = compressor.run(documents=_documents(), query=QUERY)
    assert scorer.calls
    assert "about" in [d.id for d in out["documents"]]
    with pytest.raises(ValueError):
        compressor.to_dict()  # a callable cannot be written to YAML


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_ratio": 0},
        {"target_ratio": 2},
        {"relevance": "psychic"},
        {"selection": "random"},
        {"additional_compress_kwargs": {"context_role": "user"}},
    ],
)
def test_invalid_options_fail_at_construction(kwargs):
    with pytest.raises(ValueError):
        LLMSlimDocumentCompressor(**kwargs)


def test_pipeline_after_a_retriever_and_serialization():
    store = InMemoryDocumentStore()
    store.write_documents([d for d in _documents() if d.content and d.content.strip()])
    pipeline = Pipeline()
    pipeline.add_component("retriever", InMemoryBM25Retriever(document_store=store, top_k=5))
    pipeline.add_component(
        "compressor", LLMSlimDocumentCompressor(target_ratio=TARGET_RATIO, selection="focus")
    )
    pipeline.connect("retriever.documents", "compressor.documents")

    result = pipeline.run({"retriever": {"query": QUERY}, "compressor": {"query": QUERY}})
    out = result["compressor"]["documents"]
    assert [d.id for d in out] == ["refunds"]
    assert ANSWER in out[0].content

    # Haystack 3 only deserializes classes from allowlisted modules.
    allow = {}
    if "allowed_modules" in inspect.signature(Pipeline.loads).parameters:
        allow["allowed_modules"] = ["llmslim.integrations.haystack"]
    restored = Pipeline.loads(pipeline.dumps(), **allow)
    compressor = restored.get_component("compressor")
    assert isinstance(compressor, LLMSlimDocumentCompressor)
    assert compressor.target_ratio == TARGET_RATIO and compressor.selection == "focus"
    assert compressor.context_role == "rag"
