"""LLMSlimPostprocessor with real LlamaIndex objects. Skipped when llama-index-core is not installed."""

from __future__ import annotations

from typing import List

import pytest

pytest.importorskip("llama_index.core")

from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import MetadataMode, NodeWithScore, QueryBundle, TextNode

from llmslim import count_tokens
from llmslim.integrations._documents import COMPRESSED_TOKENS_KEY, ORIGINAL_TOKENS_KEY
from llmslim.integrations.llama_index import LLMSlimPostprocessor
from tests._integration_corpus import (
    ANSWER,
    BUDGET,
    CORPUS,
    NON_EMPTY,
    QUERY,
    TARGET_RATIO,
    PreferringScorer,
)


def _text_nodes() -> List[TextNode]:
    return [
        TextNode(text=text, metadata={"source": source}, id_=doc_id)
        for doc_id, source, text in CORPUS
    ]


def _nodes() -> List[NodeWithScore]:
    return [NodeWithScore(node=node, score=1.0 - i / 10) for i, node in enumerate(_text_nodes())]


def test_is_a_node_postprocessor():
    assert isinstance(LLMSlimPostprocessor(), BaseNodePostprocessor)
    assert LLMSlimPostprocessor.class_name() == "LLMSlimPostprocessor"
    assert LLMSlimPostprocessor().target_ratio == 0.25


def test_keeps_the_relevant_node_with_its_score_and_metadata():
    nodes = _nodes()
    out = LLMSlimPostprocessor(target_ratio=TARGET_RATIO).postprocess_nodes(nodes, query_str=QUERY)
    assert [n.node.node_id for n in out] == ["refunds"]
    (kept,) = out
    text = kept.node.get_content(metadata_mode=MetadataMode.NONE)
    assert ANSWER in text
    assert sum(count_tokens(n.node.get_content()) for n in out) <= BUDGET
    assert kept.score == pytest.approx(0.8)
    assert kept.node.metadata["source"] == "refunds.md"
    assert kept.node.metadata[ORIGINAL_TOKENS_KEY] == count_tokens(CORPUS[2][2])
    assert kept.node.metadata[COMPRESSED_TOKENS_KEY] == count_tokens(text)
    # The token counts stay out of what the LLM and the embedder see.
    for mode in (MetadataMode.LLM, MetadataMode.EMBED):
        rendered = kept.node.get_content(metadata_mode=mode)
        assert "source: refunds.md" in rendered and "llmslim_" not in rendered
    # The input nodes are not modified.
    original = nodes[2].node
    assert original.metadata == {"source": "refunds.md"}
    assert original.excluded_llm_metadata_keys == []
    assert original.get_content() == CORPUS[2][2]


def test_query_bundle_is_used():
    out = LLMSlimPostprocessor().postprocess_nodes(_nodes(), query_bundle=QueryBundle(QUERY))
    assert [n.node.node_id for n in out] == ["refunds"]


def test_without_a_query_compresses_each_node_and_drops_empty_ones():
    out = LLMSlimPostprocessor(target_ratio=TARGET_RATIO).postprocess_nodes(_nodes())
    assert [n.node.node_id for n in out] == NON_EMPTY
    for item in out:
        assert item.node.metadata[COMPRESSED_TOKENS_KEY] <= item.node.metadata[ORIGINAL_TOKENS_KEY]


def test_token_counts_are_optional():
    out = LLMSlimPostprocessor(record_token_counts=False).postprocess_nodes(
        _nodes(), query_str=QUERY
    )
    assert [n.node.metadata for n in out] == [{"source": "refunds.md"}]
    assert out[0].node.excluded_llm_metadata_keys == []


def test_custom_relevance_and_options():
    scorer = PreferringScorer("company")
    postprocessor = LLMSlimPostprocessor(
        relevance=scorer, additional_compress_kwargs={"mode": "rag"}
    )
    out = postprocessor.postprocess_nodes(_nodes(), query_str=QUERY)
    assert scorer.calls
    assert "about" in [n.node.node_id for n in out]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_ratio": 0},
        {"target_ratio": 2},
        {"relevance": "psychic"},
        {"selection": "random"},
        {"additional_compress_kwargs": {"target_ratio": 0.5}},
    ],
)
def test_invalid_options_fail_at_construction(kwargs):
    with pytest.raises(ValueError):
        LLMSlimPostprocessor(**kwargs)


def test_drop_in_for_a_query_engine():
    from llama_index.core import VectorStoreIndex
    from llama_index.core.embeddings import MockEmbedding
    from llama_index.core.llms import MockLLM

    index = VectorStoreIndex(_text_nodes(), embed_model=MockEmbedding(embed_dim=8))
    query_engine = index.as_query_engine(
        llm=MockLLM(),
        similarity_top_k=len(CORPUS),
        node_postprocessors=[LLMSlimPostprocessor(target_ratio=TARGET_RATIO)],
    )
    response = query_engine.query(QUERY)
    assert [n.node.node_id for n in response.source_nodes] == ["refunds"]
    assert ANSWER in response.source_nodes[0].node.get_content()
