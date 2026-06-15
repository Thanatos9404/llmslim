"""Comprehensive test suite for context-compressor.

Tests cover the public API surface, core algorithm correctness, edge
cases, and all pipeline helpers.  The suite is designed to run with only
core dependencies (numpy + scikit-learn) — no sentence-transformers or
tiktoken required.
"""

from __future__ import annotations

import re
from typing import Dict, List

import numpy as np
import pytest

from context_compressor import (
    CompressionResult,
    ContextCompressor,
    CostEstimate,
    MODEL_PRICING,
    compress,
    compress_chat_messages,
    compress_documents,
    count_tokens,
    count_tokens_batch,
    estimate_cost_savings,
    list_supported_models,
)
from context_compressor.chunking import Chunk, semantic_chunk
from context_compressor.embeddings import (
    EmbeddingBackend,
    TfidfEmbeddingBackend,
    get_default_backend,
    reset_default_backend,
)
from context_compressor.ranking import (
    DEFAULT_WEIGHTS,
    score_chunk_sentences,
)
from context_compressor.tokenization import split_paragraphs, split_sentences


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

LONG_TEXT = (
    "Machine learning is a subset of artificial intelligence that focuses on "
    "building systems that learn from data. These systems improve their "
    "performance over time without being explicitly programmed. "
    "Supervised learning uses labeled data to train models. "
    "Unsupervised learning finds hidden patterns in unlabeled data. "
    "Reinforcement learning trains agents through reward signals. "
    "Deep learning uses neural networks with many layers. "
    "Convolutional neural networks are widely used for image recognition tasks. "
    "Recurrent neural networks are effective for sequential data processing. "
    "Transfer learning allows models to leverage knowledge from related tasks. "
    "You must always validate your model on a held-out test set. "
    "Never deploy a model without monitoring its predictions in production. "
    "Ensure that training data is representative of the target population."
)

SHORT_TEXT = "Hello world."

INSTRUCTION_TEXT = (
    "You must respond in JSON format. "
    "Never include personal data in your output. "
    "Always cite your sources. "
    "The API endpoint is https://api.example.com/v1/chat. "
    "Ensure all responses are under 500 tokens."
)


class DeterministicBackend(EmbeddingBackend):
    """A test-only embedding backend that returns reproducible vectors."""

    name = "deterministic-test"

    def encode(self, texts):
        rng = np.random.RandomState(42)
        return rng.randn(len(texts), 16).astype(np.float32)


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------


class TestTokenCounting:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_nonempty_string(self):
        assert count_tokens("hello world") >= 1

    def test_batch(self):
        results = count_tokens_batch(["hello", "world", "foo bar baz"])
        assert len(results) == 3
        assert all(r >= 1 for r in results)


# ---------------------------------------------------------------------------
# Sentence / paragraph splitting
# ---------------------------------------------------------------------------


class TestTokenization:
    def test_split_paragraphs(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        paras = split_paragraphs(text)
        assert len(paras) == 3

    def test_split_sentences_basic(self):
        text = "First sentence. Second sentence. Third sentence."
        sentences = split_sentences(text)
        assert len(sentences) >= 3

    def test_code_blocks_preserved(self):
        text = "Here is code:\n```python\nprint('hello')\n```\nEnd."
        sentences = split_sentences(text)
        code_found = any("```" in s for s in sentences)
        assert code_found, "Code block should be preserved as a single unit"

    def test_empty_text(self):
        assert split_sentences("") == []
        assert split_paragraphs("") == []

    def test_markdown_heading_preserved(self):
        text = "# Heading\nSome content here."
        sentences = split_sentences(text)
        assert any(s.startswith("#") for s in sentences)


# ---------------------------------------------------------------------------
# Semantic chunking
# ---------------------------------------------------------------------------


class TestChunking:
    def test_empty_input(self):
        assert semantic_chunk([], np.zeros((0, 16))) == []

    def test_single_sentence(self):
        chunks = semantic_chunk(["Hello."], np.ones((1, 16)))
        assert len(chunks) == 1
        assert len(chunks[0]) == 1

    def test_creates_multiple_chunks(self):
        sentences = [f"Sentence {i} about topic." for i in range(20)]
        rng = np.random.RandomState(0)
        embeddings = rng.randn(20, 16).astype(np.float32)
        chunks = semantic_chunk(
            sentences, embeddings, max_chunk_tokens=30, similarity_threshold=0.5
        )
        assert len(chunks) >= 2
        # Every sentence must be covered
        all_indices = sorted(idx for c in chunks for idx in c.sentence_indices)
        assert all_indices == list(range(20))

    def test_chunk_attributes(self):
        sentences = ["One.", "Two.", "Three."]
        embs = np.ones((3, 8))
        chunks = semantic_chunk(sentences, embs, max_chunk_tokens=9999)
        chunk = chunks[0]
        assert hasattr(chunk, "sentence_indices")
        assert hasattr(chunk, "sentences")
        assert hasattr(chunk, "token_counts")
        assert hasattr(chunk, "total_tokens")
        assert len(chunk) == len(chunk.sentences)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    def _make_chunk(self, sentences: List[str]) -> Chunk:
        token_counts = [count_tokens(s) for s in sentences]
        indices = list(range(len(sentences)))
        return Chunk(indices, list(sentences), token_counts)

    def test_basic_scoring(self):
        sentences = ["Important first sentence.", "Filler.", "Another important point."]
        chunk = self._make_chunk(sentences)
        rng = np.random.RandomState(1)
        embeddings = rng.randn(3, 16).astype(np.float32)
        scored = score_chunk_sentences(chunk, embeddings)
        assert len(scored) == 3
        assert all("score" in s for s in scored)
        assert all("must_keep" in s for s in scored)

    def test_instruction_boosted(self):
        sentences = [
            "You must always validate inputs.",
            "The weather is nice today.",
        ]
        chunk = self._make_chunk(sentences)
        embs = np.ones((2, 8))
        scored = score_chunk_sentences(chunk, embs)
        assert scored[0]["score"] > scored[1]["score"], (
            "Instruction sentence should score higher"
        )

    def test_must_keep_for_critical(self):
        sentences = [
            "Never share API keys publicly.",
            "Cats are cute animals.",
        ]
        chunk = self._make_chunk(sentences)
        embs = np.ones((2, 8))
        scored = score_chunk_sentences(chunk, embs)
        assert scored[0]["must_keep"] is True
        assert scored[1]["must_keep"] is False

    def test_query_relevance(self):
        sentences = ["Python is a programming language.", "Cats sleep a lot."]
        chunk = self._make_chunk(sentences)
        rng = np.random.RandomState(7)
        embs = rng.randn(2, 16).astype(np.float32)
        query_emb = embs[0]  # Same direction as first sentence
        scored = score_chunk_sentences(chunk, embs, query_embedding=query_emb)
        assert scored[0]["query_similarity"] is not None

    def test_preserve_patterns(self):
        sentences = ["Regular sentence.", "Contains SECRET_TOKEN value."]
        chunk = self._make_chunk(sentences)
        embs = np.ones((2, 8))
        scored = score_chunk_sentences(
            chunk, embs, preserve_patterns=[r"SECRET_TOKEN"]
        )
        assert scored[1]["must_keep"] is True

    def test_default_weights_keys(self):
        expected_keys = {"centrality", "position", "entity", "instruction", "query", "length_penalty"}
        assert set(DEFAULT_WEIGHTS.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------------------


class TestEmbeddings:
    def test_tfidf_backend(self):
        backend = TfidfEmbeddingBackend()
        result = backend.encode(["hello world", "foo bar"])
        assert isinstance(result, np.ndarray)
        assert result.shape[0] == 2

    def test_tfidf_single_text(self):
        backend = TfidfEmbeddingBackend()
        result = backend.encode(["only one text"])
        assert result.shape[0] == 1

    def test_get_default_backend(self):
        reset_default_backend()
        backend = get_default_backend()
        assert hasattr(backend, "encode")
        assert hasattr(backend, "name")
        reset_default_backend()


# ---------------------------------------------------------------------------
# Core compress() function
# ---------------------------------------------------------------------------


class TestCompress:
    def test_basic_compression(self):
        result = compress(LONG_TEXT, target_ratio=0.5)
        assert isinstance(result, CompressionResult)
        assert len(result.compressed_text) > 0
        assert result.compressed_tokens < result.original_tokens
        assert 0 < result.actual_ratio <= 1.0
        assert result.reduction_percent > 0

    def test_returns_original_for_short_text(self):
        result = compress(SHORT_TEXT, target_ratio=0.5)
        assert result.compressed_text == SHORT_TEXT
        assert result.reduction_percent == 0

    def test_target_ratio_validation(self):
        with pytest.raises(ValueError, match="target_ratio"):
            compress(LONG_TEXT, target_ratio=0.0)
        with pytest.raises(ValueError, match="target_ratio"):
            compress(LONG_TEXT, target_ratio=1.5)

    def test_ratio_one_returns_everything(self):
        result = compress(LONG_TEXT, target_ratio=1.0)
        # With ratio=1.0 the compressor should keep (almost) everything
        assert result.actual_ratio >= 0.85

    def test_aggressive_compression(self):
        result = compress(LONG_TEXT, target_ratio=0.3)
        assert result.reduction_percent >= 30

    def test_instruction_preservation(self):
        result = compress(INSTRUCTION_TEXT, target_ratio=0.5)
        compressed = result.compressed_text.lower()
        # Critical directives should survive compression
        assert "must" in compressed or "never" in compressed or "ensure" in compressed

    def test_query_aware_compression(self):
        result = compress(LONG_TEXT, target_ratio=0.5, query="neural networks")
        assert isinstance(result, CompressionResult)
        assert result.compressed_tokens < result.original_tokens

    def test_compression_result_summary(self):
        result = compress(LONG_TEXT, target_ratio=0.5)
        summary = result.summary()
        assert "Original tokens" in summary
        assert "Compressed tokens" in summary
        assert "Reduction" in summary

    def test_str_returns_compressed_text(self):
        result = compress(LONG_TEXT, target_ratio=0.5)
        assert str(result) == result.compressed_text

    def test_tokens_saved_property(self):
        result = compress(LONG_TEXT, target_ratio=0.5)
        assert result.tokens_saved == result.original_tokens - result.compressed_tokens

    def test_custom_kwargs(self):
        result = compress(
            LONG_TEXT,
            target_ratio=0.5,
            max_chunk_tokens=100,
            similarity_threshold=0.2,
        )
        assert isinstance(result, CompressionResult)


# ---------------------------------------------------------------------------
# ContextCompressor class
# ---------------------------------------------------------------------------


class TestContextCompressor:
    def test_custom_backend(self):
        compressor = ContextCompressor(embedding_backend=DeterministicBackend())
        result = compressor.compress(LONG_TEXT, target_ratio=0.5)
        assert result.backend == "deterministic-test"

    def test_custom_weights(self):
        compressor = ContextCompressor(
            weights={"centrality": 0.5, "instruction": 0.5}
        )
        result = compressor.compress(LONG_TEXT, target_ratio=0.5)
        assert isinstance(result, CompressionResult)

    def test_preserve_patterns(self):
        compressor = ContextCompressor(preserve_patterns=[r"API_KEY_\w+"])
        text = (
            "Some filler text that is not important at all. "
            "Configure API_KEY_PRIMARY in your environment. "
            "More filler text to pad the content out a bit longer. "
            "Even more text about unrelated topics and ideas. "
            "Additional sentences to make this long enough for compression. "
            "The system processes data in batches of variable size. "
            "Performance metrics are collected every five minutes."
        )
        result = compressor.compress(text, target_ratio=0.5)
        assert "API_KEY_PRIMARY" in result.compressed_text

    def test_min_tokens_threshold(self):
        compressor = ContextCompressor(min_tokens_for_compression=9999)
        result = compressor.compress(LONG_TEXT, target_ratio=0.5)
        assert result.compressed_text == LONG_TEXT


# ---------------------------------------------------------------------------
# Chat message compression
# ---------------------------------------------------------------------------


class TestChatCompression:
    def test_basic_chat(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": LONG_TEXT},
        ]
        compressed = compress_chat_messages(messages, target_ratio=0.5)
        assert len(compressed) == 2
        # System prompt should be preserved
        assert compressed[0]["content"] == "You are helpful."
        # User message should be compressed
        assert len(compressed[1]["content"]) <= len(LONG_TEXT)

    def test_preserves_roles(self):
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": LONG_TEXT},
            {"role": "assistant", "content": LONG_TEXT},
        ]
        compressed = compress_chat_messages(messages)
        assert [m["role"] for m in compressed] == ["system", "user", "assistant"]

    def test_short_messages_untouched(self):
        messages = [
            {"role": "user", "content": "Hi"},
        ]
        compressed = compress_chat_messages(messages, min_tokens=100)
        assert compressed[0]["content"] == "Hi"

    def test_does_not_mutate_input(self):
        messages = [{"role": "user", "content": LONG_TEXT}]
        original_content = messages[0]["content"]
        compress_chat_messages(messages, target_ratio=0.5)
        assert messages[0]["content"] == original_content


# ---------------------------------------------------------------------------
# Document compression (RAG pipeline)
# ---------------------------------------------------------------------------


class TestDocumentCompression:
    def test_basic_batch(self):
        docs = [LONG_TEXT, LONG_TEXT]
        results = compress_documents(docs, target_ratio=0.5)
        assert len(results) == 2
        assert all(isinstance(r, CompressionResult) for r in results)

    def test_query_aware(self):
        results = compress_documents(
            [LONG_TEXT], query="neural networks", target_ratio=0.5
        )
        assert len(results) == 1
        assert results[0].compressed_tokens < results[0].original_tokens

    def test_empty_list(self):
        assert compress_documents([]) == []


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_basic_estimate(self):
        est = estimate_cost_savings(1000, 500, model="gpt-5", requests_per_day=1000)
        assert isinstance(est, CostEstimate)
        assert est.tokens_saved == 500
        assert est.daily_savings_usd > 0
        assert est.monthly_savings_usd > est.daily_savings_usd
        assert est.annual_savings_usd > est.monthly_savings_usd

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model"):
            estimate_cost_savings(1000, 500, model="nonexistent-model")

    def test_zero_savings(self):
        est = estimate_cost_savings(1000, 1000, model="gpt-5")
        assert est.tokens_saved == 0
        assert est.daily_savings_usd == 0

    def test_summary_format(self):
        est = estimate_cost_savings(2000, 1000, model="gpt-5", requests_per_day=500)
        summary = est.summary()
        assert "gpt-5" in summary
        assert "$" in summary

    def test_list_supported_models(self):
        models = list_supported_models()
        assert len(models) > 0
        assert "gpt-5" in models

    def test_all_models_valid(self):
        for model in list_supported_models():
            est = estimate_cost_savings(1000, 500, model=model)
            assert est.model == model


# ---------------------------------------------------------------------------
# Integration: end-to-end pipeline
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_compress_then_cost(self):
        """Full workflow: compress text, then estimate savings."""
        result = compress(LONG_TEXT, target_ratio=0.5)
        est = estimate_cost_savings(
            result.original_tokens,
            result.compressed_tokens,
            model="gpt-5",
            requests_per_day=10_000,
        )
        assert est.tokens_saved == result.tokens_saved
        assert est.annual_savings_usd > 0

    def test_multiple_ratios(self):
        """Compression should increase as ratio decreases."""
        results = [compress(LONG_TEXT, target_ratio=r) for r in [0.7, 0.5, 0.3]]
        # More aggressive ratio → fewer tokens (approximately)
        assert results[2].compressed_tokens <= results[0].compressed_tokens

    def test_chunk_results_populated(self):
        result = compress(LONG_TEXT, target_ratio=0.5)
        if result.num_chunks > 0:
            assert len(result.chunk_results) == result.num_chunks
            for cr in result.chunk_results:
                assert cr.compressed_tokens <= cr.original_tokens
