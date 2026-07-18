"""Tests for llmslim.rewrite.engine and core integration with strategy/provider."""

from __future__ import annotations

import pytest

from llmslim import CompressionResult, compress
from llmslim.rewrite import (
    CallableProvider,
    RewriteEngine,
    RewriteMetadata,
    RewriteRequest,
    RewriteResult,
)


class MockProvider(CallableProvider):
    def __init__(self, output_prefix=""):
        def _fn(req: RewriteRequest) -> str:
            prefix = output_prefix + " " if output_prefix else ""
            return (
                f"{prefix}Machine learning is a subset of artificial intelligence that focuses on "
                "building systems learning from data. Supervised, Unsupervised, and Reinforcement learning. "
                "You must always validate your model on a held-out test set."
            )

        super().__init__(_fn, name="mock_provider")


class FailingProvider(CallableProvider):
    def __init__(self):
        def _fn(req: RewriteRequest) -> str:
            raise RuntimeError("Provider API down")

        super().__init__(_fn, name="failing_provider")


LONG_TEXT = (
    "Machine learning is a subset of artificial intelligence that focuses on "
    "building systems that learn from data. Supervised learning uses labeled data. "
    "Unsupervised learning finds hidden patterns. Reinforcement learning trains agents. "
    "You must always validate your model on a held-out test set."
)


class TestRewriteEngine:
    def test_engine_init(self):
        prov = MockProvider()
        engine = RewriteEngine(provider=prov)
        assert engine.provider.name == "mock_provider"

    def test_engine_init_type_error(self):
        with pytest.raises(TypeError, match="Expected a BaseRewriteProvider"):
            RewriteEngine(provider="not a provider")  # type: ignore[arg-type]

    def test_successful_rewrite(self):
        prov = MockProvider()
        engine = RewriteEngine(provider=prov)
        res = engine.rewrite(LONG_TEXT, target_ratio=0.5)

        assert isinstance(res, RewriteResult)
        assert res.accepted is True
        assert res.fallback_used is False
        assert res.provider_used == "mock_provider"
        assert res.template_used == "general"

    def test_failed_validation_fallback(self):
        # Return text that completely loses instructions & meaning
        prov = CallableProvider(lambda req: "pasta pizza spaghetti", name="bad_mock")
        engine = RewriteEngine(provider=prov)
        res = engine.rewrite(LONG_TEXT, target_ratio=0.5)

        assert res.accepted is False
        assert res.fallback_used is True
        assert res.rewritten_text == LONG_TEXT  # fell back to original

    def test_provider_exception_handled(self):
        prov = FailingProvider()
        engine = RewriteEngine(provider=prov)
        res = engine.rewrite(LONG_TEXT, target_ratio=0.5)

        assert res.accepted is False
        assert res.fallback_used is True
        assert res.rewritten_text == LONG_TEXT
        assert "Provider API down" in (res.error_message or "")


class TestCoreCompressStrategies:
    def test_strategy_extractive_default(self):
        res = compress(LONG_TEXT, target_ratio=0.5)
        assert isinstance(res, CompressionResult)
        assert res.rewrite_metadata is None

    def test_strategy_rewrite_without_provider_raises(self):
        with pytest.raises(ValueError, match="Strategy 'rewrite' requires a provider"):
            compress(LONG_TEXT, strategy="rewrite")

    def test_strategy_hybrid_without_provider_raises(self):
        with pytest.raises(ValueError, match="Strategy 'hybrid' requires a provider"):
            compress(LONG_TEXT, strategy="hybrid")

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy 'unknown'"):
            compress(LONG_TEXT, strategy="unknown", provider=lambda r: r.text)

    def test_strategy_rewrite_with_callable_provider(self):
        def my_provider(req: RewriteRequest) -> str:
            return (
                "Machine learning is a subset of artificial intelligence focusing on "
                "systems learning from data. Supervised, Unsupervised, and Reinforcement. "
                "You must always validate your model on a held-out test set."
            )

        res = compress(
            LONG_TEXT,
            strategy="rewrite",
            provider=my_provider,
            target_ratio=0.5,
        )

        assert isinstance(res, CompressionResult)
        assert res.rewrite_metadata is not None
        assert isinstance(res.rewrite_metadata, RewriteMetadata)
        assert res.rewrite_metadata.strategy == "rewrite"
        assert res.rewrite_metadata.accepted is True
        assert "rewrite_metadata" in res.to_dict()
        assert "Optimization     : strategy=rewrite" in res.detailed_summary()

    def test_strategy_hybrid_execution(self):
        def my_provider(req: RewriteRequest) -> str:
            return (
                "Machine learning is a subset of artificial intelligence focusing on "
                "systems learning from data. Supervised, Unsupervised, and Reinforcement. "
                "You must always validate your model on a held-out test set."
            )

        res = compress(
            LONG_TEXT,
            strategy="hybrid",
            provider=my_provider,
            target_ratio=0.5,
        )

        assert isinstance(res, CompressionResult)
        assert res.rewrite_metadata is not None
        assert res.rewrite_metadata.strategy == "hybrid"
        assert res.rewrite_metadata.accepted is True

    def test_rewrite_validation_failure_fallback_in_core(self):
        def bad_provider(req: RewriteRequest) -> str:
            return "nonsense garbage text"

        res = compress(
            LONG_TEXT,
            strategy="rewrite",
            provider=bad_provider,
            target_ratio=0.5,
        )

        assert res.rewrite_metadata is not None
        assert res.rewrite_metadata.accepted is False
        assert res.rewrite_metadata.fallback_used is True
        assert res.compressed_text == LONG_TEXT  # fell back to original
