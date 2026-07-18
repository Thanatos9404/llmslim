"""Rewrite engine — optional LLM-powered prompt optimization.

This sub-package provides the abstraction layer, prompt templates,
validation pipeline, and execution engine for semantic rewriting.
All components are optional — the core ``compress()`` function works
fully offline without any of this.

Public API
----------
.. autoclass:: BaseRewriteProvider
.. autoclass:: CallableProvider
.. autoclass:: RewriteRequest
.. autoclass:: RewriteEngine
.. autoclass:: RewriteResult
.. autoclass:: RewriteMetadata
.. autoclass:: RewriteTemplate
.. autoclass:: TemplateResolver
.. autoclass:: RewriteValidator
.. autoclass:: ValidationResult
"""

from .base import BaseRewriteProvider, CallableProvider, RewriteRequest
from .engine import RewriteEngine, RewriteMetadata, RewriteResult
from .templates import RewriteTemplate, TemplateResolver
from .validation import (
    BaseSimilarityValidator,
    RewriteValidator,
    TfidfSimilarityValidator,
    ValidationResult,
)

__all__ = [
    "BaseRewriteProvider",
    "CallableProvider",
    "RewriteRequest",
    "RewriteEngine",
    "RewriteResult",
    "RewriteMetadata",
    "RewriteTemplate",
    "TemplateResolver",
    "RewriteValidator",
    "ValidationResult",
    "BaseSimilarityValidator",
    "TfidfSimilarityValidator",
]
