"""Rewrite engine — execution of prompt rewriting with automatic validation and fallback.

The RewriteEngine has a single responsibility: given a provider, a template
resolver, and a validator, it formats the request, calls the provider,
validates the result, and returns a RewriteResult. If provider execution
fails or validation fails, it indicates fallback.

Public API
----------
.. autoclass:: RewriteResult
.. autoclass:: RewriteMetadata
.. autoclass:: RewriteEngine
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import BaseRewriteProvider, RewriteRequest
from .templates import TemplateResolver
from .validation import RewriteValidator, ValidationResult


@dataclass
class RewriteResult:
    """Outcome of a rewrite operation from the RewriteEngine."""

    rewritten_text: str
    accepted: bool
    validation: ValidationResult
    fallback_used: bool
    template_used: str
    provider_used: str
    rewrite_latency_ms: float
    error_message: Optional[str] = None


@dataclass
class RewriteMetadata:
    """Grouped metadata for rewrite telemetry within CompressionResult.

    Grouped object to keep CompressionResult clean as features evolve.
    """

    strategy: str
    accepted: bool
    fallback_used: bool
    provider_name: str
    template_name: str
    similarity_score: float
    instruction_retention: float
    entity_retention: float
    rewrite_latency_ms: float
    validation_scores: Dict[str, float] = field(default_factory=dict)
    failure_reasons: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to plain dictionary."""
        return {
            "strategy": self.strategy,
            "accepted": self.accepted,
            "fallback_used": self.fallback_used,
            "provider_name": self.provider_name,
            "template_name": self.template_name,
            "similarity_score": self.similarity_score,
            "instruction_retention": self.instruction_retention,
            "entity_retention": self.entity_retention,
            "rewrite_latency_ms": self.rewrite_latency_ms,
            "validation_scores": self.validation_scores,
            "failure_reasons": self.failure_reasons,
            "error_message": self.error_message,
        }


class RewriteEngine:
    """Executes prompt rewrites using a provider, template resolver, and validator.

    Responsibility: Execution only. Does not pick templates itself (delegates to
    TemplateResolver) nor does it perform validation directly (delegates to RewriteValidator).
    """

    def __init__(
        self,
        provider: BaseRewriteProvider,
        resolver: Optional[TemplateResolver] = None,
        validator: Optional[RewriteValidator] = None,
    ) -> None:
        if not isinstance(provider, BaseRewriteProvider):
            raise TypeError(
                f"Expected a BaseRewriteProvider instance, got {type(provider).__name__}"
            )
        self.provider = provider
        self.resolver = resolver or TemplateResolver()
        self.validator = validator or RewriteValidator()

    def rewrite(
        self,
        text: str,
        target_ratio: float = 0.5,
        content_type: Optional[str] = None,
        template_name: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        required_keywords: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RewriteResult:
        """Execute rewrite pipeline: format prompt -> call provider -> validate -> return result."""
        t0 = time.perf_counter()
        constraint_list = list(constraints or [])
        formatted_constraints = (
            "\n".join(f"- {c}" for c in constraint_list) if constraint_list else ""
        )

        template = self.resolver.resolve(name=template_name, content_type=content_type)
        user_prompt = template.format_user_prompt(
            text=text,
            target_ratio=target_ratio,
            constraints=formatted_constraints,
        )

        req = RewriteRequest(
            text=text,
            target_ratio=target_ratio,
            content_type=content_type,
            constraints=constraint_list,
            template_name=template.name,
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
            metadata=dict(metadata or {}),
        )

        try:
            if not self.provider.is_available():
                raise RuntimeError(f"Provider '{self.provider.name}' is not available.")

            rewritten = self.provider.rewrite(req)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            if not isinstance(rewritten, str):
                raise TypeError(f"Provider returned {type(rewritten).__name__}, expected str")

            val_result = self.validator.validate(
                original=text,
                rewrite=rewritten,
                required_keywords=required_keywords,
            )

            return RewriteResult(
                rewritten_text=rewritten if val_result.passed else text,
                accepted=val_result.passed,
                validation=val_result,
                fallback_used=not val_result.passed,
                template_used=template.name,
                provider_used=self.provider.name,
                rewrite_latency_ms=latency_ms,
            )

        except Exception as err:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            fallback_val = self.validator.validate(original=text, rewrite=text)
            return RewriteResult(
                rewritten_text=text,
                accepted=False,
                validation=fallback_val,
                fallback_used=True,
                template_used=template.name,
                provider_used=getattr(self.provider, "name", "unknown"),
                rewrite_latency_ms=latency_ms,
                error_message=str(err),
            )
