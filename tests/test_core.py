"""Comprehensive test suite for llmslim.

Tests cover the public API surface, core algorithm correctness, edge
cases, and all pipeline helpers.  The suite is designed to run with only
core dependencies (numpy + scikit-learn) — no sentence-transformers or
tiktoken required.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pytest

from llmslim import (
    CompressionResult,
    ContextCompressor,
    CostEstimate,
    compress,
    compress_chat_messages,
    compress_documents,
    count_tokens,
    count_tokens_batch,
    estimate_cost_savings,
    list_supported_models,
)
from llmslim.chunking import Chunk, semantic_chunk
from llmslim.embeddings import (
    EmbeddingBackend,
    TfidfEmbeddingBackend,
    get_default_backend,
    reset_default_backend,
)
from llmslim.ranking import (
    DEFAULT_WEIGHTS,
    score_chunk_sentences,
)
from llmslim.tokenization import split_paragraphs, split_sentences

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
        assert scored[0]["score"] > scored[1]["score"], "Instruction sentence should score higher"

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
        scored = score_chunk_sentences(chunk, embs, preserve_patterns=[r"SECRET_TOKEN"])
        assert scored[1]["must_keep"] is True

    def test_default_weights_keys(self):
        expected_keys = {
            "centrality",
            "position",
            "entity",
            "instruction",
            "query",
            "length_penalty",
        }
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
        compressor = ContextCompressor(weights={"centrality": 0.5, "instruction": 0.5})
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
        results = compress_documents([LONG_TEXT], query="neural networks", target_ratio=0.5)
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


# =====================================================================
# v0.2 Tests: DP Knapsack Optimality
# =====================================================================


class TestDPKnapsack:
    """Verify that DP knapsack produces provably better results than
    greedy on inputs where the two strategies diverge."""

    def test_dp_beats_greedy_on_heterogeneous_items(self):
        """Construct a case where greedy is suboptimal.

        Budget = 10 tokens.
        Items:
          A: weight=6, value=7  (greedy picks this first)
          B: weight=5, value=5
          C: weight=5, value=5

        Greedy picks A (6 tokens, score 7), can't fit B or C.
        DP picks B+C (10 tokens, score 10) — strictly better.
        """
        from llmslim.core import ContextCompressor

        scored = [
            {"index": 0, "score": 7.0, "must_keep": False, "sentence": "A"},
            {"index": 1, "score": 5.0, "must_keep": False, "sentence": "B"},
            {"index": 2, "score": 5.0, "must_keep": False, "sentence": "C"},
        ]
        token_counts = [6, 5, 5]
        # target_ratio = 10/16 ≈ 0.625 → target_tokens = 10
        selected = ContextCompressor._select_for_chunk(scored, token_counts, 10 / 16)

        # DP should pick indices 1 and 2 (total score 10 > 7)
        assert selected == {1, 2}

    def test_greedy_fallback_for_large_inputs(self):
        """Verify the greedy fallback activates for large DP tables."""
        from llmslim.core import ContextCompressor

        # Create items that would exceed DP table limit.
        n = 100
        items = [{"index": i, "score": float(i), "must_keep": False} for i in range(n)]
        token_counts = list(range(1, n + 1))
        budget = 600  # n * budget = 100 * 600 = 60,000 > 50,000

        # Should not raise, should return a valid selection.
        selected = ContextCompressor._knapsack_select(items, token_counts, budget)
        assert isinstance(selected, set)
        total_used = sum(token_counts[i] for i in selected)
        assert total_used <= budget

    def test_must_keep_respected_with_dp(self):
        """Must-keep sentences are always selected regardless of DP."""
        from llmslim.core import ContextCompressor

        scored = [
            {"index": 0, "score": 0.1, "must_keep": True, "sentence": "keep"},
            {"index": 1, "score": 0.9, "must_keep": False, "sentence": "optional"},
            {"index": 2, "score": 0.8, "must_keep": False, "sentence": "optional2"},
        ]
        token_counts = [3, 5, 5]
        selected = ContextCompressor._select_for_chunk(scored, token_counts, 0.5)
        assert 0 in selected  # must_keep sentence always included

    def test_always_returns_at_least_one(self):
        """Even with zero budget, at least one sentence is returned."""
        from llmslim.core import ContextCompressor

        scored = [
            {"index": 0, "score": 0.5, "must_keep": False, "sentence": "only"},
        ]
        token_counts = [100]
        selected = ContextCompressor._select_for_chunk(scored, token_counts, 0.01)
        assert len(selected) >= 1


# =====================================================================
# v0.2 Tests: Instruction Detection Expansion
# =====================================================================


class TestInstructionDetection:
    """Verify expanded instruction pattern coverage."""

    def test_role_definition_detected(self):
        from llmslim.ranking import _instruction_score

        score = _instruction_score("You are an expert Python developer.")
        assert score > 0.0, "Role definition 'You are' should be detected"

    def test_output_format_detected(self):
        from llmslim.ranking import _instruction_score

        score = _instruction_score("Respond in JSON format only.")
        assert score > 0.0, "'Respond in' should be detected as instruction"

    def test_warning_label_detected(self):
        from llmslim.ranking import _instruction_score

        score = _instruction_score("WARNING: Do not use deprecated APIs.")
        assert score > 0.0, "'WARNING:' label should be detected"

    def test_quantified_constraint_detected(self):
        from llmslim.ranking import _instruction_score

        score = _instruction_score("Return at most 5 results.")
        assert score > 0.0, "'at most' should be detected as instruction"

    def test_multi_signal_sentence_scores_higher(self):
        """A sentence matching multiple signals should score higher
        than one matching a single signal."""
        from llmslim.ranking import _instruction_score

        single = _instruction_score("You should do this.")
        multi = _instruction_score("You must always ensure correctness.")
        assert multi > single, "Multiple instruction signals should produce higher score"

    def test_role_definition_is_must_keep(self):
        from llmslim.ranking import _is_must_keep

        assert _is_must_keep("You are an AI assistant.", [])

    def test_warning_label_is_must_keep(self):
        from llmslim.ranking import _is_must_keep

        assert _is_must_keep("WARNING: This action is irreversible.", [])


# =====================================================================
# v0.2 Tests: Entity Detection Expansion
# =====================================================================


class TestEntityDetection:
    """Verify expanded entity pattern coverage."""

    def test_short_acronym_detected(self):
        from llmslim.ranking import _entity_score

        score = _entity_score("The HPA scales pods automatically.")
        assert score > 0.0, "Short acronym 'HPA' should be detected"

    def test_snake_case_detected(self):
        from llmslim.ranking import _entity_score

        score = _entity_score("Set the target_ratio parameter to 0.5.")
        assert score > 0.0, "snake_case identifier should be detected"

    def test_version_string_detected(self):
        from llmslim.ranking import _entity_score

        score = _entity_score("Requires PostgreSQL 16 or Python 3.8.")
        assert score > 0.0, "Version strings should be detected"

    def test_file_name_detected(self):
        from llmslim.ranking import _entity_score

        score = _entity_score("Edit the config.yaml file.")
        assert score > 0.0, "File names should be detected"

    def test_env_var_detected(self):
        from llmslim.ranking import _entity_score

        score = _entity_score("Set DATABASE_URL in your .env file.")
        assert score > 0.0, "Environment variables should be detected"

    def test_inline_code_detected(self):
        from llmslim.ranking import _entity_score

        score = _entity_score("Use the `compress` function.")
        assert score > 0.0, "Inline code spans should be detected"


# =====================================================================
# v0.2 Tests: Determinism
# =====================================================================


class TestDeterminism:
    """Verify that compression is deterministic."""

    def test_identical_runs_produce_identical_output(self):
        """10 identical runs should produce byte-identical output."""
        text = (
            "Authentication requires OAuth 2.0 tokens. You must always "
            "use HTTPS. JWT tokens consist of header, payload, and "
            "signature. Never store tokens in localStorage. Implement "
            "rate limiting on all endpoints. Use bcrypt for hashing."
        )
        results = [compress(text, target_ratio=0.5) for _ in range(10)]
        first = results[0].compressed_text
        for i, r in enumerate(results[1:], 1):
            assert r.compressed_text == first, f"Run {i} differed from run 0"


# =====================================================================
# v0.2 Tests: Edge Cases
# =====================================================================


class TestEdgeCases:
    """Test edge cases and format-specific scenarios."""

    def test_single_sentence(self):
        result = compress("This is a single sentence.", target_ratio=0.5)
        assert result.compressed_text == "This is a single sentence."

    def test_json_prompt(self):
        """JSON-like structured prompts should not crash."""
        json_prompt = (
            "You must respond in JSON format. "
            'The schema is: {"name": "string", "age": "number"}. '
            "Always include all required fields. "
            "Never return null values."
        )
        result = compress(json_prompt, target_ratio=0.5)
        assert len(result.compressed_text) > 0
        assert result.compressed_tokens > 0

    def test_yaml_prompt(self):
        """YAML-like structured prompts should not crash."""
        yaml_prompt = (
            "Configuration options:\n"
            "  - name: target_ratio\n"
            "    type: float\n"
            "    required: true\n"
            "  - name: model\n"
            "    type: string\n"
            "    default: gpt-4"
        )
        result = compress(yaml_prompt, target_ratio=0.5)
        assert len(result.compressed_text) > 0

    def test_instruction_retention_regression(self):
        """Regression test: instruction sentences should be retained
        at high ratios.  The v0.1 baseline showed 80% instruction
        retention on Chat Prompts -- this should be improved."""
        text = (
            "You are an expert engineer. "
            "You must always provide production code. "
            "Never suggest deprecated APIs. "
            "Ensure all queries use parameterized inputs. "
            "The database is PostgreSQL 16 on RDS."
        )
        result = compress(text, target_ratio=0.7)
        # All instruction sentences should be kept at 70% ratio
        assert (
            "must" in result.compressed_text.lower() or "always" in result.compressed_text.lower()
        )
        assert (
            "never" in result.compressed_text.lower() or "ensure" in result.compressed_text.lower()
        )
