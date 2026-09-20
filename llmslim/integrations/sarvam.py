"""Optional official-SDK Sarvam rewrite provider.

The module imports without the optional dependency. Constructing a live
provider requires ``llmslim[sarvam]`` and an explicitly supplied key, or an
explicit call to :meth:`SarvamProvider.from_env`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..rewrite import BaseRewriteProvider, RewriteRequest


class SarvamProviderError(RuntimeError):
    """Sanitized base error for Sarvam provider failures."""


class SarvamAuthenticationError(SarvamProviderError):
    pass


class SarvamRateLimitError(SarvamProviderError):
    pass


class SarvamTimeoutError(SarvamProviderError):
    pass


class SarvamMalformedResponseError(SarvamProviderError):
    pass


@dataclass(frozen=True)
class SarvamUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    classification: str = "PROVIDER_REPORTED"

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


class SarvamProvider(BaseRewriteProvider):
    """Synchronous rewrite provider backed by the official ``sarvamai`` SDK."""

    name = "sarvam"
    supported_models = ("sarvam-105b", "sarvam-105b-conversations")

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        model: str = "sarvam-105b",
        timeout_seconds: float = 30.0,
        max_tokens: int = 2048,
        reasoning_effort: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        if model not in self.supported_models:
            raise ValueError("unsupported Sarvam chat model: " + model)
        if timeout_seconds <= 0 or max_tokens <= 0:
            raise ValueError("timeout_seconds and max_tokens must be positive")
        if client is None:
            if not api_key:
                raise ValueError(
                    "SarvamProvider requires api_key; use from_env() for explicit environment lookup"
                )
            try:
                from sarvamai import SarvamAI
            except ImportError as exc:  # pragma: no cover - clean-extra test exercises this.
                raise ImportError(
                    'SarvamProvider requires the optional extra: pip install "llmslim[sarvam]"'
                ) from exc
            client = SarvamAI(api_subscription_key=api_key, timeout=timeout_seconds)
        self._client = client
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self._usage: ContextVar[Optional[SarvamUsage]] = ContextVar(
            "llmslim_sarvam_usage", default=None
        )

    @classmethod
    def from_env(cls, env_var: str = "SARVAM_API_KEY", **kwargs: Any) -> "SarvamProvider":
        """Explicitly load one named environment variable and construct a provider."""

        api_key = os.environ.get(env_var)
        if not api_key:
            raise ValueError(f"environment variable {env_var} is not set")
        return cls(api_key=api_key, **kwargs)

    @property
    def last_usage(self) -> Optional[SarvamUsage]:
        """Provider-reported usage for the current execution context, if returned."""

        return self._usage.get()

    def is_available(self) -> bool:
        return self._client is not None

    def rewrite(self, request: RewriteRequest) -> str:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt or request.text})
        return self.chat(messages)

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Create one bounded chat completion and retain sanitized usage metadata."""

        if not messages:
            raise ValueError("messages must not be empty")
        normalized = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "developer", "user", "assistant", "tool"}:
                raise ValueError("messages contain an unsupported role")
            if not isinstance(content, str) or not content:
                raise ValueError("messages must contain non-empty string content")
            normalized.append({"role": role, "content": content})
        output_limit = self.max_tokens if max_tokens is None else max_tokens
        if isinstance(output_limit, bool) or not isinstance(output_limit, int) or output_limit <= 0:
            raise ValueError("max_tokens must be a positive integer")
        try:
            response = self._client.chat.completions(
                model=self.model,
                messages=normalized,
                max_tokens=output_limit,
                reasoning_effort=self.reasoning_effort,
                stream=False,
            )
        except Exception as exc:
            self._usage.set(None)
            self._raise_sanitized(exc)
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            raise SarvamMalformedResponseError(
                "Sarvam returned a response without assistant content"
            ) from None
        if not isinstance(content, str) or not content.strip():
            raise SarvamMalformedResponseError("Sarvam returned empty assistant content")
        usage = getattr(response, "usage", None)
        self._usage.set(
            SarvamUsage(
                prompt_tokens=_optional_int(getattr(usage, "prompt_tokens", None)),
                completion_tokens=_optional_int(getattr(usage, "completion_tokens", None)),
                total_tokens=_optional_int(getattr(usage, "total_tokens", None)),
            )
            if usage is not None
            else None
        )
        return content

    @staticmethod
    def _raise_sanitized(exc: Exception) -> None:
        name = type(exc).__name__.lower()
        if "unauthorized" in name or "forbidden" in name or "authentication" in name:
            error: SarvamProviderError = SarvamAuthenticationError("Sarvam authentication failed")
        elif "toomanyrequests" in name or "ratelimit" in name:
            error = SarvamRateLimitError("Sarvam rate limit exceeded")
        elif "timeout" in name:
            error = SarvamTimeoutError("Sarvam request timed out")
        else:
            error = SarvamProviderError(f"Sarvam request failed ({type(exc).__name__})")
        raise error from None

    def __repr__(self) -> str:
        return (
            f"SarvamProvider(model={self.model!r}, timeout_seconds={self.timeout_seconds!r}, "
            "credentials=<redacted>)"
        )


def _optional_int(value: Any) -> Optional[int]:
    return int(value) if value is not None else None


__all__ = [
    "SarvamAuthenticationError",
    "SarvamMalformedResponseError",
    "SarvamProvider",
    "SarvamProviderError",
    "SarvamRateLimitError",
    "SarvamTimeoutError",
    "SarvamUsage",
]
