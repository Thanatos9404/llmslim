"""v0.3.0 Regression and backward compatibility test suite."""

from __future__ import annotations

import pytest

from llmslim import (
    BaseRewriteProvider,
    CallableProvider,
    CompressionResult,
    RewriteEngine,
    RewriteMetadata,
    RewriteRequest,
    RewriteValidator,
    ValidationResult,
    compress,
)

SAMPLE_TEXT = (
    "Machine learning is a branch of artificial intelligence. "
    "Supervised learning uses labeled dataset for training models. "
    "Unsupervised learning discovers hidden patterns in unlabeled data. "
    "You must always validate your model on a test dataset."
)


class TestV03Regression:
    def test_default_compress_unaffected(self):
        res = compress(SAMPLE_TEXT, target_ratio=0.5)
        assert isinstance(res, CompressionResult)
        assert res.rewrite_metadata is None

    def test_top_level_exports_exist(self):
        assert BaseRewriteProvider is not None
        assert CallableProvider is not None
        assert RewriteRequest is not None
        assert RewriteEngine is not None
        assert RewriteMetadata is not None
        assert RewriteValidator is not None
        assert ValidationResult is not None

    def test_strategy_rewrite_validation_pipeline(self):
        def _prov(req: RewriteRequest) -> str:
            return (
                "Machine learning is artificial intelligence using Supervised "
                "and Unsupervised learning. You must always validate your model on a test dataset."
            )

        res = compress(
            SAMPLE_TEXT,
            strategy="rewrite",
            provider=_prov,
            target_ratio=0.5,
        )

        assert res.rewrite_metadata is not None
        assert res.rewrite_metadata.accepted is True
        assert res.rewrite_metadata.strategy == "rewrite"

    def test_missing_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="requires a provider"):
            compress(SAMPLE_TEXT, strategy="rewrite")

    def test_invalid_strategy_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            compress(SAMPLE_TEXT, strategy="invalid_strat", provider=lambda r: r.text)
