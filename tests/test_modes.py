"""Tests for llmslim.modes — optimisation mode definitions and resolution."""

from __future__ import annotations

import pytest

from llmslim.analysis import ContentProfile, ContentType
from llmslim.modes import (
    MODE_AGGRESSIVE,
    MODE_BALANCED,
    MODE_CODE,
    MODE_QUALITY,
    MODE_SYSTEM,
    OptimizationMode,
    get_mode,
    list_modes,
    resolve_mode,
)

# =====================================================================
# Built-in modes
# =====================================================================


class TestBuiltInModes:
    """Verify built-in mode properties."""

    def test_mode_count(self):
        assert len(list_modes()) == 8

    def test_mode_names(self):
        expected = sorted(
            [
                "balanced",
                "quality",
                "aggressive",
                "rag",
                "chat",
                "system",
                "code",
                "documentation",
            ]
        )
        assert list_modes() == expected

    def test_all_modes_frozen(self):
        for name in list_modes():
            mode = get_mode(name)
            with pytest.raises(AttributeError):
                mode.name = "mutated"  # type: ignore[misc]

    def test_target_ratios_valid(self):
        for name in list_modes():
            mode = get_mode(name)
            assert 0.0 < mode.target_ratio_default <= 1.0

    def test_boost_values_positive(self):
        for name in list_modes():
            mode = get_mode(name)
            assert mode.instruction_priority_boost > 0
            assert mode.entity_priority_boost > 0

    def test_balanced_is_neutral(self):
        assert MODE_BALANCED.instruction_priority_boost == 1.0
        assert MODE_BALANCED.entity_priority_boost == 1.0
        assert MODE_BALANCED.ranking_weights == {}

    def test_aggressive_low_ratio(self):
        assert MODE_AGGRESSIVE.target_ratio_default < MODE_BALANCED.target_ratio_default

    def test_quality_high_ratio(self):
        assert MODE_QUALITY.target_ratio_default > MODE_BALANCED.target_ratio_default

    def test_system_high_instruction_boost(self):
        assert MODE_SYSTEM.instruction_priority_boost >= 2.0

    def test_code_high_entity_boost(self):
        assert MODE_CODE.entity_priority_boost >= 2.0


# =====================================================================
# get_mode
# =====================================================================


class TestGetMode:
    def test_known_mode(self):
        mode = get_mode("balanced")
        assert mode.name == "balanced"

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown mode"):
            get_mode("nonexistent")


# =====================================================================
# resolve_mode
# =====================================================================


class TestResolveMode:
    def test_none_returns_balanced(self):
        mode = resolve_mode(None)
        assert mode.name == "balanced"

    def test_explicit_name(self):
        mode = resolve_mode("aggressive")
        assert mode.name == "aggressive"

    def test_auto_without_profile_returns_balanced(self):
        mode = resolve_mode("auto")
        assert mode.name == "balanced"

    def test_auto_with_code_profile(self):
        profile = ContentProfile(
            content_type=ContentType.PYTHON,
            confidence=0.85,
            language_hint="python",
            estimated_tokens=500,
        )
        mode = resolve_mode("auto", profile)
        assert mode.name == "code"

    def test_auto_with_chat_profile(self):
        profile = ContentProfile(
            content_type=ContentType.CHAT_CONVERSATION,
            confidence=0.9,
            estimated_tokens=200,
        )
        mode = resolve_mode("auto", profile)
        assert mode.name == "chat"

    def test_auto_with_system_prompt_profile(self):
        profile = ContentProfile(
            content_type=ContentType.SYSTEM_PROMPT,
            confidence=0.8,
            estimated_tokens=150,
        )
        mode = resolve_mode("auto", profile)
        assert mode.name == "system"

    def test_auto_with_rag_profile(self):
        profile = ContentProfile(
            content_type=ContentType.RAG_CONTEXT,
            confidence=0.75,
            estimated_tokens=1000,
        )
        mode = resolve_mode("auto", profile)
        assert mode.name == "rag"

    def test_auto_with_markdown_profile(self):
        profile = ContentProfile(
            content_type=ContentType.MARKDOWN,
            confidence=0.7,
            has_structure=True,
            estimated_tokens=800,
        )
        mode = resolve_mode("auto", profile)
        assert mode.name == "documentation"

    def test_auto_with_log_profile(self):
        profile = ContentProfile(
            content_type=ContentType.LOG_FILE,
            confidence=0.9,
            estimated_tokens=2000,
        )
        mode = resolve_mode("auto", profile)
        assert mode.name == "aggressive"

    def test_auto_with_general_text(self):
        profile = ContentProfile(
            content_type=ContentType.GENERAL_TEXT,
            confidence=1.0,
            estimated_tokens=500,
        )
        mode = resolve_mode("auto", profile)
        assert mode.name == "balanced"


# =====================================================================
# OptimizationMode dataclass
# =====================================================================


class TestOptimizationMode:
    def test_default_weights_is_empty_dict(self):
        mode = OptimizationMode(name="test", description="test mode")
        assert mode.ranking_weights == {}

    def test_custom_weights(self):
        mode = OptimizationMode(
            name="custom",
            description="test",
            ranking_weights={"centrality": 0.5},
        )
        assert mode.ranking_weights == {"centrality": 0.5}


# =====================================================================
# Integration: compress() with mode
# =====================================================================

# Import the actual compress function to test mode integration
from llmslim import compress

_LONG_TEXT = (
    "Machine learning is a subset of artificial intelligence. "
    "It uses statistical methods to learn from data. "
    "Deep learning is a further subset using neural networks. "
    "These networks have multiple layers of processing. "
    "Training requires large datasets and significant compute. "
    "The results can be applied to many domains. "
    "Natural language processing uses ML for text analysis. "
    "Computer vision applies deep learning to images. "
    "Reinforcement learning trains agents through rewards. "
    "Transfer learning reuses models trained on one task. "
) * 5  # Repeat to ensure it's long enough for compression


class TestCompressWithMode:
    def test_compress_without_mode_unchanged(self):
        """Default compress() should produce same output as v0.2."""
        result = compress(_LONG_TEXT, target_ratio=0.5)
        assert result.content_type is None
        assert result.mode is None
        assert result.elapsed_ms is None

    def test_compress_with_mode(self):
        result = compress(_LONG_TEXT, target_ratio=0.5, mode="quality")
        assert result.mode == "quality"
        assert result.content_type is None  # detect_content not set

    def test_compress_with_detect(self):
        result = compress(_LONG_TEXT, target_ratio=0.5, detect_content=True)
        assert result.content_type is not None
        assert result.content_confidence is not None
        assert result.mode is not None  # auto-resolved from balanced

    def test_compress_with_mode_and_detect(self):
        result = compress(_LONG_TEXT, target_ratio=0.5, mode="aggressive", detect_content=True)
        assert result.mode == "aggressive"
        assert result.content_type is not None

    def test_compress_auto_mode(self):
        result = compress(_LONG_TEXT, target_ratio=0.5, mode="auto", detect_content=True)
        assert result.mode is not None
        assert result.content_type is not None

    def test_compress_with_mode_has_telemetry(self):
        result = compress(_LONG_TEXT, target_ratio=0.5, mode="balanced")
        assert result.elapsed_ms is not None
        assert result.instructions_found is not None
        assert result.entities_found is not None

    def test_compress_result_to_dict(self):
        result = compress(_LONG_TEXT, target_ratio=0.5, mode="balanced")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "original_tokens" in d
        assert "mode" in d
        assert d["mode"] == "balanced"

    def test_compress_result_detailed_summary(self):
        result = compress(_LONG_TEXT, target_ratio=0.5, mode="balanced", detect_content=True)
        summary = result.detailed_summary()
        assert "balanced" in summary
        assert "Content type" in summary

    def test_aggressive_mode_compresses_more(self):
        result_balanced = compress(_LONG_TEXT, target_ratio=0.5, mode="balanced")
        result_aggressive = compress(_LONG_TEXT, mode="aggressive")
        # Aggressive should compress more (lower actual_ratio)
        assert result_aggressive.actual_ratio <= result_balanced.actual_ratio + 0.15
