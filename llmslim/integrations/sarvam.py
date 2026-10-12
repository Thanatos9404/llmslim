"""Optional official-SDK Sarvam integrations.

* :class:`SarvamProvider` / :class:`AsyncSarvamProvider`: bounded chat and
  rewrite providers for ``sarvam-105b`` and ``sarvam-105b-conversations``.
* :class:`SarvamLanguageTools` / :class:`AsyncSarvamLanguageTools` and the
  :func:`annotate_languages` / :func:`normalize_scripts` context helpers
  (:mod:`llmslim.integrations.sarvam_text`).
* :class:`SarvamDocumentSource` / :class:`AsyncSarvamDocumentSource`
  (:mod:`llmslim.integrations.sarvam_documents`).

The module imports without the optional dependency. Constructing a live client
requires ``llmslim[sarvam]`` and an explicitly supplied key, or an explicit
``from_env()`` call. Paid calls go through a :class:`UsageGuard`; failed calls
are never retried automatically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, List, NoReturn, Optional, Type, TypeVar, Union

from ..planning.models import ModelProfile
from ..planning.profiles import BUILTIN_MODEL_PROFILES
from ..rewrite import BaseRewriteProvider, RewriteRequest
from ._guard import (
    RateLimitExceeded,
    UsageCapExceeded,
    UsageGuard,
    UsageLimitExceeded,
    UsageLimits,
    UsageReservation,
)
from ._sarvam_common import (
    SARVAM_PRICES,
    SarvamAuthenticationError,
    SarvamInvalidRequestError,
    SarvamJobError,
    SarvamJobTimeoutError,
    SarvamMalformedResponseError,
    SarvamPaymentRequiredError,
    SarvamPriceTable,
    SarvamProviderError,
    SarvamRateLimitError,
    SarvamServerError,
    SarvamServiceUsage,
    SarvamTimeoutError,
    async_client,
    env_key,
    fail_call,
    map_sarvam_error,
    read_field,
    sync_client,
)
from .sarvam_documents import (
    DEFAULT_DOCUMENT_LIMITS,
    DOCUMENT_GUARD_PREFIX,
    AsyncSarvamDocumentSource,
    SarvamDocumentResult,
    SarvamDocumentSource,
)
from .sarvam_text import (
    DEFAULT_TEXT_LIMITS,
    TEXT_GUARD_PREFIX,
    AsyncSarvamLanguageTools,
    SarvamLanguageIdentification,
    SarvamLanguageTools,
    SarvamTextResult,
    aannotate_languages,
    annotate_languages,
    anormalize_scripts,
    normalize_scripts,
    split_for_sarvam,
)

CHAT_GUARD_PREFIX = "sarvam_chat"
DEFAULT_CHAT_LIMITS = UsageLimits(
    requests_per_minute=60, max_requests=1000, max_units=200.0, unit="inr"
)
# Per-message allowance for role markers and separators in the reservation bound.
_MESSAGE_OVERHEAD_TOKENS = 16
_ROLES = frozenset({"system", "developer", "user", "assistant", "tool"})


class _EnvGuard:
    """Sentinel: ``from_env`` builds the guard from ``LLMSLIM_SARVAM_CHAT_*``."""

    def __repr__(self) -> str:
        return "<guard from LLMSLIM_SARVAM_CHAT_*>"


_ENV_GUARD = _EnvGuard()
_ProviderT = TypeVar("_ProviderT", bound="_SarvamChatCore")


@dataclass(frozen=True)
class SarvamUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    classification: str = "PROVIDER_REPORTED"
    cached_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def _optional_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _parse_usage(response: Any) -> Optional[SarvamUsage]:
    usage = read_field(response, "usage")
    if usage is None:
        return None
    prompt_details = read_field(usage, "prompt_tokens_details")
    completion_details = read_field(usage, "completion_tokens_details")
    return SarvamUsage(
        prompt_tokens=_optional_int(read_field(usage, "prompt_tokens")),
        completion_tokens=_optional_int(read_field(usage, "completion_tokens")),
        total_tokens=_optional_int(read_field(usage, "total_tokens")),
        # Sarvam omits prompt_tokens_details on a cache miss; "not reported" stays None.
        cached_tokens=(
            _optional_int(read_field(prompt_details, "cached_tokens"))
            if prompt_details is not None
            else None
        ),
        reasoning_tokens=(
            _optional_int(read_field(completion_details, "reasoning_tokens"))
            if completion_details is not None
            else None
        ),
    )


def _response_content(response: Any) -> str:
    choices = read_field(response, "choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or not choices:
        raise SarvamMalformedResponseError("Sarvam returned a response without assistant content")
    content = read_field(read_field(choices[0], "message"), "content")
    if not isinstance(content, str) or not content.strip():
        raise SarvamMalformedResponseError("Sarvam returned empty assistant content")
    return content


def _normalize_messages(messages: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    if not messages:
        raise ValueError("messages must not be empty")
    normalized = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in _ROLES:
            raise ValueError("messages contain an unsupported role")
        if not isinstance(content, str) or not content:
            raise ValueError("messages must contain non-empty string content")
        normalized.append({"role": role, "content": content})
    return normalized


def sarvam_chat_cost_inr(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    cached_tokens: Optional[int] = None,
    profile: Optional[ModelProfile] = None,
) -> float:
    """INR cost of one chat call at the dated profile prices; cached input uses the cached rate."""

    resolved = profile or BUILTIN_MODEL_PROFILES[model]
    input_rate = float(resolved.input_cost_per_million or 0.0)
    cached_rate = resolved.cached_input_cost_per_million
    output_rate = float(resolved.output_cost_per_million or 0.0)
    cached = min(max(cached_tokens or 0, 0), prompt_tokens)
    cached_cost = cached * (input_rate if cached_rate is None else float(cached_rate))
    return (
        (prompt_tokens - cached) * input_rate + cached_cost + completion_tokens * output_rate
    ) / 1_000_000.0


class _SarvamChatCore:
    """Validation, usage and guard accounting shared by the sync and async providers."""

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
        guard: Optional[UsageGuard] = None,
    ) -> None:
        if model not in self.supported_models:
            raise ValueError("unsupported Sarvam chat model: " + model)
        if timeout_seconds <= 0 or max_tokens <= 0:
            raise ValueError("timeout_seconds and max_tokens must be positive")
        if guard is not None and not isinstance(guard, UsageGuard):
            raise TypeError("guard must be a UsageGuard or None")
        if client is None:
            client = self._make_client(api_key, timeout_seconds)
        self._client = client
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.guard = guard
        self._profile = BUILTIN_MODEL_PROFILES[model]
        self._usage: ContextVar[Optional[SarvamUsage]] = ContextVar(
            "llmslim_sarvam_usage", default=None
        )

    def _make_client(self, api_key: Optional[str], timeout_seconds: float) -> Any:
        return sync_client(api_key, timeout_seconds, type(self).__name__)

    @classmethod
    def from_env(
        cls: Type[_ProviderT],
        env_var: str = "SARVAM_API_KEY",
        *,
        guard: Union[UsageGuard, None, _EnvGuard] = _ENV_GUARD,
        **kwargs: Any,
    ) -> _ProviderT:
        """Explicitly load one named key variable and construct a guarded provider.

        The guard reads ``LLMSLIM_SARVAM_CHAT_REQUESTS_PER_MINUTE``, ``_MAX_REQUESTS``
        and ``_MAX_UNITS`` (INR); pass ``guard=None`` to opt out or your own guard.
        """

        api_key = env_key(env_var)
        resolved = (
            UsageGuard.from_env(CHAT_GUARD_PREFIX, DEFAULT_CHAT_LIMITS)
            if isinstance(guard, _EnvGuard)
            else guard
        )
        return cls(api_key=api_key, guard=resolved, **kwargs)

    @property
    def last_usage(self) -> Optional[SarvamUsage]:
        """Provider-reported usage for the current execution context, if returned."""

        return self._usage.get()

    def is_available(self) -> bool:
        return self._client is not None

    def _request(
        self, messages: Sequence[Mapping[str, str]], max_tokens: Optional[int]
    ) -> Dict[str, Any]:
        normalized = _normalize_messages(messages)
        output_limit = self.max_tokens if max_tokens is None else max_tokens
        if isinstance(output_limit, bool) or not isinstance(output_limit, int) or output_limit <= 0:
            raise ValueError("max_tokens must be a positive integer")
        return {
            "model": self.model,
            "messages": normalized,
            "max_tokens": output_limit,
            "reasoning_effort": self.reasoning_effort,
            "stream": False,
        }

    def _reserve(self, request: Mapping[str, Any]) -> Optional[UsageReservation]:
        if self.guard is None:
            return None
        # UTF-8 bytes bound any byte-level tokenizer; the context window bounds the prompt.
        prompt_bound = sum(
            len(message["content"].encode("utf-8")) + _MESSAGE_OVERHEAD_TOKENS
            for message in request["messages"]
        )
        prompt_bound = min(prompt_bound, self._profile.context_window)
        return self.guard.acquire(
            sarvam_chat_cost_inr(
                self.model, prompt_bound, request["max_tokens"], profile=self._profile
            )
        )

    def _fail(self, reservation: Optional[UsageReservation], exc: BaseException) -> NoReturn:
        self._usage.set(None)
        fail_call(self.guard, reservation, exc)

    def _finish(self, response: Any, reservation: Optional[UsageReservation]) -> str:
        usage = _parse_usage(response)
        self._usage.set(usage)
        if (
            self.guard is not None
            and reservation is not None
            and usage is not None
            and usage.prompt_tokens is not None
            and usage.completion_tokens is not None
        ):
            self.guard.settle(
                reservation,
                sarvam_chat_cost_inr(
                    self.model,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    cached_tokens=usage.cached_tokens,
                    profile=self._profile,
                ),
            )
        # Without reported usage the conservative reservation stays charged.
        return _response_content(response)

    @staticmethod
    def _messages_for(request: RewriteRequest) -> List[Dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt or request.text})
        return messages

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(model={self.model!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, credentials=<redacted>)"
        )


class SarvamProvider(_SarvamChatCore, BaseRewriteProvider):
    """Synchronous rewrite provider backed by the official ``sarvamai`` SDK.

    ``guard=None`` (the default for direct construction) applies no local limit,
    which keeps callers that enforce their own spend ledger, such as
    :mod:`llmslim.hosted`, unchanged. :meth:`from_env` attaches a guard.
    """

    def rewrite(self, request: RewriteRequest) -> str:
        return self.chat(self._messages_for(request))

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Create one bounded chat completion and retain sanitized usage metadata."""

        request = self._request(messages, max_tokens)
        reservation = self._reserve(request)
        try:
            response = self._client.chat.completions(**request)
        except Exception as exc:
            self._fail(reservation, exc)
        return self._finish(response, reservation)


class AsyncSarvamProvider(_SarvamChatCore):
    """Asyncio chat provider backed by ``AsyncSarvamAI`` with the sync provider's semantics.

    ``last_usage`` lives in a :class:`~contextvars.ContextVar`, so concurrent
    tasks each see the usage of their own most recent call.
    """

    def _make_client(self, api_key: Optional[str], timeout_seconds: float) -> Any:
        return async_client(api_key, timeout_seconds, type(self).__name__)

    async def arewrite(self, request: RewriteRequest) -> str:
        return await self.chat(self._messages_for(request))

    async def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        max_tokens: Optional[int] = None,
    ) -> str:
        request = self._request(messages, max_tokens)
        reservation = self._reserve(request)
        try:
            response = await self._client.chat.completions(**request)
        except Exception as exc:
            self._fail(reservation, exc)
        return self._finish(response, reservation)


__all__ = [
    "CHAT_GUARD_PREFIX",
    "DEFAULT_CHAT_LIMITS",
    "DEFAULT_DOCUMENT_LIMITS",
    "DEFAULT_TEXT_LIMITS",
    "DOCUMENT_GUARD_PREFIX",
    "RateLimitExceeded",
    "SARVAM_PRICES",
    "TEXT_GUARD_PREFIX",
    "AsyncSarvamDocumentSource",
    "AsyncSarvamLanguageTools",
    "AsyncSarvamProvider",
    "SarvamAuthenticationError",
    "SarvamDocumentResult",
    "SarvamDocumentSource",
    "SarvamInvalidRequestError",
    "SarvamJobError",
    "SarvamJobTimeoutError",
    "SarvamLanguageIdentification",
    "SarvamLanguageTools",
    "SarvamMalformedResponseError",
    "SarvamPaymentRequiredError",
    "SarvamPriceTable",
    "SarvamProvider",
    "SarvamProviderError",
    "SarvamRateLimitError",
    "SarvamServerError",
    "SarvamServiceUsage",
    "SarvamTextResult",
    "SarvamTimeoutError",
    "SarvamUsage",
    "UsageCapExceeded",
    "UsageGuard",
    "UsageLimitExceeded",
    "UsageLimits",
    "aannotate_languages",
    "annotate_languages",
    "anormalize_scripts",
    "map_sarvam_error",
    "normalize_scripts",
    "sarvam_chat_cost_inr",
    "split_for_sarvam",
]
