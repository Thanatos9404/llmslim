"""Framework-free tests for the shared core of the LangChain, LlamaIndex and Haystack adapters.

These run in every environment; the framework-specific tests skip when a framework is missing.
"""

from __future__ import annotations

import importlib
import sys

import pytest

from llmslim import compress_documents, count_tokens
from llmslim.integrations._documents import (
    COMPRESSED_TOKENS_KEY,
    ORIGINAL_TOKENS_KEY,
    compress_texts,
    token_metadata,
    validate_options,
)
from tests._integration_corpus import (
    ANSWER,
    BUDGET,
    CORPUS,
    QUERY,
    TARGET_RATIO,
    TEXTS,
    PreferringScorer,
)


def test_query_shares_one_budget_and_keeps_the_relevant_document():
    results = compress_texts(TEXTS, QUERY, target_ratio=TARGET_RATIO)
    assert len(results) == len(TEXTS)
    kept = {CORPUS[i][0]: r for i, r in enumerate(results) if r is not None}
    assert "refunds" in kept
    assert ANSWER in kept["refunds"].compressed_text
    assert sum(count_tokens(r.compressed_text) for r in kept.values()) <= BUDGET
    assert all(r.selection == "focus" for r in kept.values())


def test_matches_compress_documents_on_the_non_empty_texts():
    non_empty = [t for t in TEXTS if t.strip()]
    expected = [r.compressed_text for r in compress_documents(non_empty, QUERY, TARGET_RATIO)]
    ours = [r.compressed_text for r in compress_texts(TEXTS, QUERY, target_ratio=TARGET_RATIO) if r]
    assert ours == [text for text in expected if text.strip()]


def test_empty_and_whitespace_texts_are_dropped():
    results = compress_texts(["", None, "   \n "], QUERY, target_ratio=0.5)
    assert results == [None, None, None]
    results = compress_texts(TEXTS, None, target_ratio=TARGET_RATIO)
    assert [r is None for r in results] == [not t.strip() for t in TEXTS]


def test_without_a_query_each_text_is_compressed_on_its_own():
    for query in (None, "", "   "):
        results = compress_texts(TEXTS, query, target_ratio=TARGET_RATIO)
        for text, result in zip(TEXTS, results):
            if text.strip():
                assert result is not None and result.selection != "focus"
                assert result.compressed_tokens <= result.original_tokens


def test_options_are_forwarded_to_compress_documents():
    scorer = PreferringScorer("company")
    results = compress_texts(TEXTS, QUERY, target_ratio=TARGET_RATIO, relevance=scorer)
    assert scorer.calls
    kept = [CORPUS[i][0] for i, r in enumerate(results) if r is not None]
    assert "about" in kept
    assert all(r.backend == "bm25+rerank" for r in results if r)

    proportional = compress_texts(TEXTS, QUERY, target_ratio=TARGET_RATIO, selection="proportional")
    assert all(r.selection != "focus" for r in proportional if r)

    # Preserve patterns apply to trusted text only, so they need a role other than the default rag.
    preserve = {"preserve_patterns": [r"rooftop garden"]}
    untrusted = compress_texts(
        TEXTS, QUERY, target_ratio=TARGET_RATIO, additional_compress_kwargs=preserve
    )
    assert not any("rooftop garden" in r.compressed_text for r in untrusted if r)
    trusted = compress_texts(
        TEXTS,
        QUERY,
        target_ratio=TARGET_RATIO,
        context_role="general",
        additional_compress_kwargs=preserve,
    )
    assert any("rooftop garden" in r.compressed_text for r in trusted if r)

    mode = compress_texts(
        TEXTS,
        None,
        target_ratio=0.5,
        additional_compress_kwargs={"min_tokens_for_compression": 1000},
    )
    assert [r.compressed_text for r in mode if r] == [t for t in TEXTS if t.strip()]


def test_token_metadata():
    (result,) = compress_documents([TEXTS[2]], None, 0.5)
    assert token_metadata(result) == {
        ORIGINAL_TOKENS_KEY: result.original_tokens,
        COMPRESSED_TOKENS_KEY: result.compressed_tokens,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_ratio": 0.0},
        {"target_ratio": 1.5},
        {"target_ratio": True},
        {"relevance": "psychic"},
        {"selection": "random"},
        {"additional_compress_kwargs": {"target_ratio": 0.5}},
        {"additional_compress_kwargs": {"query": "q"}},
    ],
)
def test_invalid_options_are_rejected(kwargs):
    options = {
        "target_ratio": 0.25,
        "relevance": "lexical",
        "selection": "auto",
        "additional_compress_kwargs": None,
    }
    options.update(kwargs)
    with pytest.raises(ValueError):
        validate_options(**options)


def test_valid_options_pass():
    validate_options(1.0, "semantic", "focus", {"mode": "rag"})
    validate_options(0.1, PreferringScorer("x"), "proportional", None)


@pytest.mark.parametrize(
    "module, framework, extra",
    [
        ("llmslim.integrations.langchain", "langchain_core.callbacks", "llmslim[langchain]"),
        (
            "llmslim.integrations.llama_index",
            "llama_index.core.postprocessor.types",
            "llmslim[llamaindex]",
        ),
        ("llmslim.integrations.haystack", "haystack", "llmslim[haystack]"),
    ],
)
def test_missing_framework_names_the_extra(monkeypatch, module, framework, extra):
    # None in sys.modules makes the adapter's first framework import fail, installed or not.
    monkeypatch.setitem(sys.modules, framework, None)
    monkeypatch.delitem(sys.modules, module, raising=False)
    with pytest.raises(ImportError, match=extra.replace("[", r"\[").replace("]", r"\]")):
        importlib.import_module(module)
