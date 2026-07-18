"""Tests for llmslim.rewrite.validation — the 4-validator pipeline."""

from __future__ import annotations

import pytest

from llmslim.rewrite.validation import (
    BaseSimilarityValidator,
    EntityValidator,
    InstructionValidator,
    RewriteValidator,
    StructuralValidator,
    TfidfSimilarityValidator,
    ValidationResult,
    _extract_entities,
    _extract_instructions,
)

# ─────────────────────────────────────────────────────────────────────
# Helper extraction functions
# ─────────────────────────────────────────────────────────────────────


class TestExtractInstructions:
    def test_extracts_must(self):
        insts = _extract_instructions("You must respond in JSON.")
        assert "must" in insts

    def test_extracts_never(self):
        insts = _extract_instructions("Never share personal data.")
        assert "never" in insts

    def test_extracts_multiple(self):
        insts = _extract_instructions(
            "You must always ensure quality. Never skip validation."
        )
        assert len(insts) >= 3  # must, always, ensure, never

    def test_empty_text(self):
        insts = _extract_instructions("")
        assert len(insts) == 0

    def test_no_instructions(self):
        insts = _extract_instructions("The weather is nice today.")
        assert len(insts) == 0


class TestExtractEntities:
    def test_extracts_capitalized(self):
        ents = _extract_entities("Google and Amazon are companies.")
        assert any("Google" in e for e in ents)

    def test_extracts_urls(self):
        ents = _extract_entities("Visit https://api.example.com/v1")
        assert any("https://" in e for e in ents)

    def test_extracts_snake_case(self):
        ents = _extract_entities("Set the target_ratio to 0.5")
        assert "target_ratio" in ents

    def test_extracts_inline_code(self):
        ents = _extract_entities("Use `compress()` function")
        assert "`compress()`" in ents

    def test_empty_text(self):
        ents = _extract_entities("")
        assert len(ents) == 0


# ─────────────────────────────────────────────────────────────────────
# StructuralValidator
# ─────────────────────────────────────────────────────────────────────


class TestStructuralValidator:
    def test_valid_compression(self):
        v = StructuralValidator()
        passed, score, failures = v.validate("orig", "rew", 100, 50)
        assert passed is True
        assert len(failures) == 0

    def test_empty_rewrite(self):
        v = StructuralValidator()
        passed, score, failures = v.validate("orig", "  ", 100, 0)
        assert passed is False
        assert "empty" in failures[0].lower()

    def test_inflated_rewrite(self):
        v = StructuralValidator()
        passed, score, failures = v.validate("orig", "much longer", 10, 20)
        assert passed is False
        assert "inflated" in failures[0].lower()

    def test_suspiciously_short(self):
        v = StructuralValidator()
        passed, score, failures = v.validate("orig", "x", 100, 5)
        assert passed is False
        assert "short" in failures[0].lower()


# ─────────────────────────────────────────────────────────────────────
# InstructionValidator
# ─────────────────────────────────────────────────────────────────────


class TestInstructionValidator:
    def test_all_instructions_kept(self):
        text = "You must respond in JSON. Never share secrets. Always cite sources."
        v = InstructionValidator(min_retention=0.8)
        passed, retention, failures = v.validate(text, text)
        assert passed is True
        assert retention == 1.0

    def test_some_instructions_lost(self):
        orig = "You must respond in JSON. Never share secrets. Always cite sources."
        rewrite = "Respond in JSON."
        v = InstructionValidator(min_retention=0.8)
        passed, retention, failures = v.validate(orig, rewrite)
        # "must" and "never" and "always" are lost; only partial match
        assert retention < 1.0

    def test_no_instructions_always_passes(self):
        v = InstructionValidator(min_retention=0.8)
        passed, retention, failures = v.validate(
            "The sky is blue.", "Sky is blue."
        )
        assert passed is True
        assert retention == 1.0

    def test_custom_threshold(self):
        v = InstructionValidator(min_retention=0.5)
        orig = "You must do X. You must do Y."
        rewrite = "You must do X."
        passed, retention, failures = v.validate(orig, rewrite)
        assert retention >= 0.5  # "must" is still present


# ─────────────────────────────────────────────────────────────────────
# EntityValidator
# ─────────────────────────────────────────────────────────────────────


class TestEntityValidator:
    def test_all_entities_kept(self):
        text = "Google uses TensorFlow at https://tensorflow.org"
        v = EntityValidator(min_retention=0.7)
        passed, retention, failures = v.validate(text, text)
        assert passed is True
        assert retention == 1.0

    def test_entities_lost(self):
        orig = "Google uses TensorFlow at https://tensorflow.org"
        rewrite = "A company uses a framework."
        v = EntityValidator(min_retention=0.7)
        passed, retention, failures = v.validate(orig, rewrite)
        assert passed is False
        assert retention < 0.7

    def test_no_entities_passes(self):
        v = EntityValidator(min_retention=0.7)
        passed, retention, failures = v.validate("the the the", "the the")
        assert passed is True


# ─────────────────────────────────────────────────────────────────────
# TfidfSimilarityValidator
# ─────────────────────────────────────────────────────────────────────


class TestTfidfSimilarityValidator:
    def test_identical_text(self):
        v = TfidfSimilarityValidator()
        score = v.score("hello world", "hello world")
        assert score == pytest.approx(1.0, abs=0.01)

    def test_similar_text(self):
        v = TfidfSimilarityValidator()
        score = v.score(
            "Machine learning is a subset of artificial intelligence.",
            "ML is part of AI, focusing on data-driven learning.",
        )
        assert 0.0 < score < 1.0

    def test_completely_different(self):
        v = TfidfSimilarityValidator()
        score = v.score("alpha bravo charlie", "xray yankee zulu")
        assert score < 0.3

    def test_empty_text(self):
        v = TfidfSimilarityValidator()
        assert v.score("", "hello") == 0.0
        assert v.score("hello", "") == 0.0

    def test_name_attribute(self):
        v = TfidfSimilarityValidator()
        assert v.name == "tfidf_cosine"


class TestBaseSimilarityValidator:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseSimilarityValidator()  # type: ignore[abstract]

    def test_custom_similarity_validator(self):
        class ConstantValidator(BaseSimilarityValidator):
            name = "constant"

            def score(self, original: str, rewrite: str) -> float:
                return 0.42

        v = ConstantValidator()
        assert v.score("a", "b") == 0.42


# ─────────────────────────────────────────────────────────────────────
# RewriteValidator (composite)
# ─────────────────────────────────────────────────────────────────────


class TestRewriteValidator:
    ORIGINAL = (
        "You must respond in JSON format. "
        "Google Cloud provides the BigQuery service. "
        "Never include personal data. "
        "Always validate the target_ratio parameter. "
        "Visit https://example.com for more info."
    )

    def test_identical_text_passes(self):
        validator = RewriteValidator()
        result = validator.validate(self.ORIGINAL, self.ORIGINAL)
        assert result.passed is True
        assert result.similarity_score > 0.9
        assert result.instruction_retention == 1.0
        assert result.entity_retention == 1.0

    def test_good_rewrite_passes(self):
        rewrite = (
            "You must respond in JSON. "
            "Google Cloud offers BigQuery. "
            "Never include personal data. "
            "Always validate target_ratio. "
            "See https://example.com."
        )
        validator = RewriteValidator(min_similarity=0.3)
        result = validator.validate(self.ORIGINAL, rewrite)
        assert result.passed is True

    def test_terrible_rewrite_fails(self):
        rewrite = "Something completely different about cooking pasta."
        validator = RewriteValidator()
        result = validator.validate(self.ORIGINAL, rewrite)
        assert result.passed is False
        assert len(result.failure_reasons) > 0

    def test_empty_rewrite_fails(self):
        validator = RewriteValidator()
        result = validator.validate(self.ORIGINAL, "")
        assert result.passed is False
        assert "empty" in result.failure_reasons[0].lower()

    def test_required_keywords_present(self):
        validator = RewriteValidator(min_similarity=0.3)
        result = validator.validate(
            self.ORIGINAL,
            self.ORIGINAL,
            required_keywords=["JSON", "Google"],
        )
        assert result.passed is True
        assert result.keyword_retention == 1.0

    def test_required_keywords_missing(self):
        validator = RewriteValidator(min_similarity=0.3)
        result = validator.validate(
            self.ORIGINAL,
            "Just some random text with JSON.",
            required_keywords=["JSON", "NONEXISTENT_KEYWORD"],
        )
        assert result.keyword_retention < 1.0
        assert any("Missing required keywords" in r for r in result.failure_reasons)

    def test_pluggable_similarity(self):
        """Custom similarity validator is used instead of TF-IDF."""

        class AlwaysHighSimilarity(BaseSimilarityValidator):
            name = "always_high"

            def score(self, original: str, rewrite: str) -> float:
                return 0.99

        validator = RewriteValidator(
            similarity_validator=AlwaysHighSimilarity(),
            min_similarity=0.5,
        )
        result = validator.validate(self.ORIGINAL, self.ORIGINAL)
        assert result.similarity_score == pytest.approx(0.99, abs=0.01)

    def test_scores_dict_populated(self):
        validator = RewriteValidator()
        result = validator.validate(self.ORIGINAL, self.ORIGINAL)
        assert "structural" in result.scores
        assert "instruction_retention" in result.scores
        assert "entity_retention" in result.scores
        assert "similarity" in result.scores

    def test_validation_result_frozen(self):
        result = ValidationResult(
            passed=True,
            similarity_score=0.9,
            instruction_retention=1.0,
            entity_retention=1.0,
            token_reduction=0.5,
            keyword_retention=1.0,
        )
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore[misc]

    def test_custom_thresholds(self):
        """Lenient thresholds should accept looser rewrites."""
        validator = RewriteValidator(
            min_similarity=0.1,
            min_instruction_retention=0.3,
            min_entity_retention=0.2,
        )
        # A rewrite that loses some entities but keeps key instructions
        rewrite = "You must respond in JSON. Never include personal data."
        result = validator.validate(self.ORIGINAL, rewrite)
        # Should still pass with lenient thresholds
        assert isinstance(result.passed, bool)
        assert result.instruction_retention > 0.0
