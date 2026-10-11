"""LLMSlimCompressor with real LangChain objects. Skipped when langchain-core is not installed."""

from __future__ import annotations

import asyncio
import importlib
from typing import List

import pytest

pytest.importorskip("langchain_core")

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.retrievers import BaseRetriever

from llmslim import count_tokens
from llmslim.integrations._documents import COMPRESSED_TOKENS_KEY, ORIGINAL_TOKENS_KEY
from llmslim.integrations.langchain import LLMSlimCompressor
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
        Document(page_content=text, metadata={"source": source, "rank": i}, id=doc_id)
        for i, (doc_id, source, text) in enumerate(CORPUS)
    ]


class _FixedRetriever(BaseRetriever):
    documents: List[Document]

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        return list(self.documents)


def _contextual_compression_retriever():
    # langchain-classic (LangChain 1.x) or langchain < 1.0, whichever is installed.
    for module in (
        "langchain_classic.retrievers.contextual_compression",
        "langchain.retrievers.contextual_compression",
    ):
        try:
            return importlib.import_module(module).ContextualCompressionRetriever
        except ImportError:
            continue
    pytest.skip("ContextualCompressionRetriever needs langchain-classic")


def test_is_a_document_compressor():
    assert isinstance(LLMSlimCompressor(), BaseDocumentCompressor)
    assert LLMSlimCompressor().target_ratio == 0.25


def test_keeps_the_relevant_document_within_the_budget():
    documents = _documents()
    out = LLMSlimCompressor(target_ratio=TARGET_RATIO).compress_documents(documents, QUERY)
    assert [d.id for d in out] == ["refunds"]
    (kept,) = out
    assert ANSWER in kept.page_content
    assert sum(count_tokens(d.page_content) for d in out) <= BUDGET
    assert kept.metadata["source"] == "refunds.md" and kept.metadata["rank"] == 2
    assert kept.metadata[ORIGINAL_TOKENS_KEY] == count_tokens(documents[2].page_content)
    assert kept.metadata[COMPRESSED_TOKENS_KEY] == count_tokens(kept.page_content)
    # The input documents are not modified.
    assert documents[2].metadata == {"source": "refunds.md", "rank": 2}
    assert documents[2].page_content == CORPUS[2][2]


def test_without_a_query_compresses_each_document_and_drops_empty_ones():
    documents = _documents()
    out = LLMSlimCompressor(target_ratio=TARGET_RATIO).compress_documents(documents, "")
    assert [d.id for d in out] == NON_EMPTY
    for doc in out:
        assert doc.metadata[COMPRESSED_TOKENS_KEY] <= doc.metadata[ORIGINAL_TOKENS_KEY]


def test_token_counts_are_optional():
    out = LLMSlimCompressor(record_token_counts=False).compress_documents(_documents(), QUERY)
    assert [d.metadata for d in out] == [{"source": "refunds.md", "rank": 2}]


def test_custom_relevance_and_options():
    scorer = PreferringScorer("company")
    compressor = LLMSlimCompressor(relevance=scorer, additional_compress_kwargs={"mode": "rag"})
    out = compressor.compress_documents(_documents(), QUERY)
    assert scorer.calls
    assert "about" in [d.id for d in out]
    proportional = LLMSlimCompressor(selection="proportional").compress_documents(
        _documents(), QUERY
    )
    assert [d.id for d in proportional] == NON_EMPTY


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_ratio": 0},
        {"target_ratio": 2},
        {"relevance": "psychic"},
        {"selection": "random"},
        {"additional_compress_kwargs": {"query": "q"}},
    ],
)
def test_invalid_options_fail_at_construction(kwargs):
    with pytest.raises(ValueError):
        LLMSlimCompressor(**kwargs)


def test_async_compression():
    out = asyncio.run(LLMSlimCompressor().acompress_documents(_documents(), QUERY))
    assert [d.id for d in out] == ["refunds"]


def test_drop_in_for_contextual_compression_retriever():
    retriever_cls = _contextual_compression_retriever()
    retriever = retriever_cls(
        base_compressor=LLMSlimCompressor(target_ratio=TARGET_RATIO),
        base_retriever=_FixedRetriever(documents=_documents()),
    )
    out = retriever.invoke(QUERY)
    assert [d.id for d in out] == ["refunds"]
    assert ANSWER in out[0].page_content
    assert out[0].metadata["source"] == "refunds.md"
