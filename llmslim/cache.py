"""Cache planning metadata. Providers own prompt/KV storage; LLMSlim owns no tensors.

The estimates in this module are deliberately distinct from provider usage.
No cache hit is asserted until a provider reports one.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from threading import RLock
from typing import Any, Mapping, Optional, Tuple

from .planning.models import CandidateMethod, ContextKind, ContextPlan
from .tokens import count_tokens

RENDER_VERSION = "llmslim-cache-render-1"


class CacheStatus(str, Enum):
    DISABLED = "disabled"
    COLD = "cold"
    ESTIMATED_REUSE = "estimated_reuse"
    REPORTED_HIT = "reported_hit"
    REPORTED_MISS = "reported_miss"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class CacheCapabilities:
    provider: str
    automatic_prefix_cache: bool = False
    explicit_prefix_cache: bool = False
    explicit_cached_object: bool = False
    conversation_state: bool = False
    client_managed_kv_cache: bool = False
    cache_usage_reporting: bool = False
    configurable_ttl: bool = False
    cache_prewarm: bool = False
    cache_breakpoints: bool = False
    verified: bool = True


PROVIDER_CAPABILITIES: Mapping[str, CacheCapabilities] = {
    "openai": CacheCapabilities(
        "openai",
        automatic_prefix_cache=True,
        explicit_prefix_cache=True,
        conversation_state=True,
        cache_usage_reporting=True,
        configurable_ttl=True,
        cache_breakpoints=True,
        cache_prewarm=True,
    ),
    "anthropic": CacheCapabilities(
        "anthropic",
        automatic_prefix_cache=True,
        explicit_prefix_cache=True,
        cache_usage_reporting=True,
        configurable_ttl=True,
        cache_breakpoints=True,
    ),
    "gemini": CacheCapabilities(
        "gemini",
        automatic_prefix_cache=True,
        explicit_cached_object=True,
        cache_usage_reporting=True,
        configurable_ttl=True,
    ),
    "sarvam": CacheCapabilities("sarvam", verified=False),
    "vllm": CacheCapabilities("vllm", automatic_prefix_cache=True),
    "transformers": CacheCapabilities("transformers", client_managed_kv_cache=True),
    "generic": CacheCapabilities("generic", verified=False),
}


@dataclass(frozen=True)
class CachePolicy:
    mode: str = "disabled"  # disabled, provider_memory, explicit, auto
    provider: str = "generic"
    tenant_id: Optional[str] = None
    conversation_mode: str = "stateless"  # stateless, provider_stateful
    ttl_seconds: Optional[int] = None
    cached_input_rate: Optional[float] = None  # currency per million tokens
    uncached_input_rate: Optional[float] = None
    cache_write_rate: Optional[float] = None
    rendering_version: str = RENDER_VERSION
    request_settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in {"disabled", "provider_memory", "explicit", "auto"}:
            raise ValueError("unknown cache mode")
        if self.conversation_mode not in {"stateless", "provider_stateful"}:
            raise ValueError("unknown conversation mode")
        if self.mode != "disabled" and not self.tenant_id:
            raise ValueError("cache-aware mode requires a tenant_id")
        if self.conversation_mode == "provider_stateful" and self.mode == "disabled":
            raise ValueError("provider state requires an enabled cache policy")
        if self.ttl_seconds is not None and not 0 < self.ttl_seconds <= 86400:
            raise ValueError("cache TTL must be between 1 and 86400 seconds")
        for rate in (self.cached_input_rate, self.uncached_input_rate, self.cache_write_rate):
            if rate is not None and rate < 0:
                raise ValueError("cache token rates must be non-negative")
        if not isinstance(self.request_settings, Mapping):
            raise TypeError("request_settings must be a mapping")
        allowed = {"temperature", "top_p", "tool_choice", "response_format", "max_output_tokens"}
        if set(self.request_settings) - allowed:
            raise ValueError("cache settings contain unsupported or sensitive fields")
        # Detached serialization ensures caller mutation cannot change a fingerprint later.
        frozen = json.loads(json.dumps(dict(self.request_settings), sort_keys=True))
        object.__setattr__(self, "request_settings", frozen)

    @property
    def capabilities(self) -> CacheCapabilities:
        return PROVIDER_CAPABILITIES.get(
            self.provider, CacheCapabilities(self.provider, verified=False)
        )

    def validate_capabilities(self) -> None:
        cap = self.capabilities
        if self.conversation_mode == "provider_stateful" and not cap.conversation_state:
            raise ValueError(f"{self.provider} conversation state is unsupported or unverified")
        if self.mode == "explicit" and not (
            cap.explicit_prefix_cache or cap.explicit_cached_object
        ):
            raise ValueError(
                f"{self.provider} explicit prompt caching is unsupported or unverified"
            )
        if self.mode == "provider_memory" and not cap.automatic_prefix_cache:
            raise ValueError(f"{self.provider} provider caching is unsupported or unverified")
        if self.ttl_seconds is not None and not cap.configurable_ttl:
            raise ValueError(f"{self.provider} cache TTL is unsupported or unverified")


@dataclass(frozen=True)
class CacheSegment:
    item_hash: str
    kind: str
    stability: str
    tokens: int
    digest: str
    position: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_hash": self.item_hash,
            "kind": self.kind,
            "stability": self.stability,
            "tokens": self.tokens,
            "position": self.position,
        }


@dataclass(frozen=True)
class CachePlan:
    provider: str
    mode: str
    conversation_mode: str
    segments: Tuple[CacheSegment, ...]
    prefix_fingerprint: str
    stable_prefix_tokens: int
    semi_stable_tokens: int
    dynamic_suffix_tokens: int
    logical_context_tokens: int
    transmitted_input_bytes: int
    generation: int = 1
    status: CacheStatus = CacheStatus.COLD
    invalidation_reason: Optional[str] = None
    estimated_cache_read_tokens: int = 0
    estimated_cache_saving: Optional[float] = None
    estimated_effective_input_cost: Optional[float] = None
    provider_state_referenced_tokens: int = 0
    stateful_suffix_start: Optional[int] = None
    explanation: str = "Provider cache usage has not been reported."
    message_digests: Tuple[str, ...] = field(default=(), repr=False)
    previous_response_id: Optional[str] = field(default=None, repr=False)
    provider_cache_reference: Optional[str] = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "conversation_mode": self.conversation_mode,
            "segments": [part.to_dict() for part in self.segments],
            "prefix_fingerprint": self.prefix_fingerprint[:16],
            "stable_prefix_tokens": self.stable_prefix_tokens,
            "semi_stable_tokens": self.semi_stable_tokens,
            "dynamic_suffix_tokens": self.dynamic_suffix_tokens,
            "logical_context_tokens": self.logical_context_tokens,
            "transmitted_input_bytes": self.transmitted_input_bytes,
            "generation": self.generation,
            "status": self.status.value,
            "invalidation_reason": self.invalidation_reason,
            "estimated_cache_read_tokens": self.estimated_cache_read_tokens,
            "estimated_cache_saving": self.estimated_cache_saving,
            "estimated_effective_input_cost": self.estimated_effective_input_cost,
            "provider_state_referenced_tokens": self.provider_state_referenced_tokens,
            "stateful_suffix_start": self.stateful_suffix_start,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class CacheTelemetry:
    source: str = "estimated"  # estimated or provider_reported
    input_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    provider_cache_hit: Optional[bool] = None
    transmitted_input_bytes: Optional[int] = None
    time_to_first_token_ms: Optional[float] = None
    full_latency_ms: Optional[float] = None

    def __post_init__(self) -> None:
        if self.source not in {"estimated", "provider_reported"}:
            raise ValueError("invalid telemetry source")
        for value in (
            self.input_tokens,
            self.cache_read_tokens,
            self.cache_write_tokens,
            self.output_tokens,
            self.transmitted_input_bytes,
        ):
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError("cache telemetry counts must be non-negative integers")
        if (
            self.input_tokens is not None
            and self.cache_read_tokens is not None
            and self.cache_read_tokens > self.input_tokens
        ):
            raise ValueError("cache reads exceed input tokens")
        if (
            self.input_tokens is not None
            and self.cache_read_tokens is not None
            and self.cache_write_tokens is not None
            and self.cache_read_tokens + self.cache_write_tokens > self.input_tokens
        ):
            raise ValueError("cache reads and writes exceed input tokens")

    @property
    def uncached_input_tokens(self) -> Optional[int]:
        if self.input_tokens is None or self.cache_read_tokens is None:
            return None
        return self.input_tokens - self.cache_read_tokens

    @property
    def cache_hit_ratio(self) -> Optional[float]:
        if not self.input_tokens or self.cache_read_tokens is None:
            return None
        return self.cache_read_tokens / self.input_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "uncached_input_tokens": self.uncached_input_tokens,
            "cache_hit_ratio": self.cache_hit_ratio,
        }


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def cache_item_digest(item: Any, content: str) -> str:
    return _digest(
        {"kind": item.kind.value, "content": content, "role": item.metadata.get("message_role")}
    )


def cache_item_key(item: Any) -> str:
    return _digest(item.item_id)[:16]


def classify_stability(item: Any) -> str:
    """Use provenance and explicit caller hints, never textual instructions."""
    if item.kind in {ContextKind.SYSTEM, ContextKind.DEVELOPER, ContextKind.TOOL_SCHEMA}:
        return "stable"
    if item.kind in {ContextKind.USER, ContextKind.ASSISTANT, ContextKind.TOOL_RESULT}:
        return "dynamic"
    hint = item.metadata.get("cache_stability")
    if hint == "stable" and item.metadata.get("cache_authorized") is True:
        return "stable"
    if hint == "dynamic":
        return "dynamic"
    if item.kind is ContextKind.MEMORY or hint == "semi_stable":
        return "semi_stable"
    return "dynamic"


def compile_cache_plan(
    plan: ContextPlan,
    model_input: Any,
    policy: CachePolicy,
    material_settings: Optional[Mapping[str, Any]] = None,
) -> CachePlan:
    """Fingerprint the provider-visible leading prefix without changing model semantics."""
    policy.validate_capabilities()
    segments = []
    for index, decision in enumerate(plan.decisions):
        if decision.selected.method is CandidateMethod.DROP:
            continue
        item = decision.item
        segments.append(
            CacheSegment(
                item_hash=cache_item_key(item),
                kind=item.kind.value,
                stability=classify_stability(item),
                tokens=decision.selected.token_cost,
                digest=cache_item_digest(item, decision.selected.content),
                position=index,
            )
        )
    # Tools are a separate provider request field and precede messages for
    # Anthropic. Preserve caller order because tool ordering may be material.
    tools = [dict(tool) for tool in model_input.tools]
    leading = []
    stabilities = model_input.message_stabilities or tuple(
        "stable" if message.get("role") in {"system", "developer"} else "dynamic"
        for message in model_input.messages
    )
    for message, stability in zip(model_input.messages, stabilities):
        if stability == "stable":
            leading.append(dict(message))
        else:
            break
    prefix = {
        "provider": policy.provider,
        "model": model_input.model,
        "render": policy.rendering_version,
        "settings": policy.request_settings,
        "runtime_settings": material_settings or {},
        "tools": tools,
        "messages": leading,
        "tenant": policy.tenant_id,
    }
    fingerprint = _digest(prefix)
    prefix_tokens = sum(count_tokens(str(msg.get("content", ""))) for msg in leading)
    prefix_tokens += sum(count_tokens(json.dumps(tool, sort_keys=True)) for tool in tools)
    # The prefix count is an estimate; the model-specific tokenizer may differ.
    logical = plan.metrics.planned_tokens
    semi = sum(part.tokens for part in segments if part.stability == "semi_stable")
    transmitted = len(
        json.dumps(
            {
                "model": model_input.model,
                "messages": [dict(message) for message in model_input.messages],
                "tools": tools,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    message_digests = tuple(_digest(dict(message)) for message in model_input.messages)
    return CachePlan(
        provider=policy.provider,
        mode=policy.mode,
        conversation_mode=policy.conversation_mode,
        segments=tuple(segments),
        prefix_fingerprint=fingerprint,
        stable_prefix_tokens=prefix_tokens,
        semi_stable_tokens=semi,
        dynamic_suffix_tokens=max(0, logical - prefix_tokens - semi),
        logical_context_tokens=logical,
        transmitted_input_bytes=transmitted,
        status=CacheStatus.DISABLED if policy.mode == "disabled" else CacheStatus.COLD,
        message_digests=message_digests,
    )


@dataclass
class _CacheEntry:
    fingerprint: str
    generation: int
    prefix_tokens: int
    model: str
    rendering_version: str
    settings_digest: str
    stable_digests: Mapping[str, str]
    message_digests: Tuple[str, ...]
    logical_tokens: int
    created_at: float
    last_used_at: float
    expires_at: Optional[float]
    previous_response_id: Optional[str] = None
    provider_cache_reference: Optional[str] = None


class CacheManager:
    """Tenant-scoped in-memory metadata only; no prompt bodies or KV tensors."""

    def __init__(self, *, max_entries: int = 1024) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries: dict[tuple[str, str, str, str], _CacheEntry] = {}
        self._lock = RLock()

    @staticmethod
    def _key(
        policy: CachePolicy, session_id: Optional[str], model: str
    ) -> tuple[str, str, str, str]:
        return (policy.tenant_id or "", session_id or "", policy.provider, model)

    def observe(
        self, cache_plan: CachePlan, policy: CachePolicy, session_id: Optional[str], model: str
    ) -> CachePlan:
        if policy.mode == "disabled" or not session_id:
            return cache_plan
        now = time.monotonic()
        key = self._key(policy, session_id, model)
        with self._lock:
            prior = self._entries.get(key)
            expired = prior is not None and prior.expires_at is not None and prior.expires_at <= now
            if expired:
                del self._entries[key]
                prior = None
            hit = prior is not None and prior.fingerprint == cache_plan.prefix_fingerprint
            provider_cache_supported = policy.capabilities.verified and (
                policy.capabilities.automatic_prefix_cache
                or policy.capabilities.explicit_prefix_cache
                or policy.capabilities.explicit_cached_object
                or policy.capabilities.client_managed_kv_cache
            )
            append_only = bool(
                prior is not None
                and hit
                and cache_plan.message_digests[: len(prior.message_digests)]
                == prior.message_digests
            )
            rewritten = bool(hit and not append_only)
            generation = (
                (prior.generation if hit and not rewritten else prior.generation + 1)
                if prior
                else 1
            )
            reason = None
            if expired:
                reason = "cache expired"
            elif prior and not hit:
                reason = "stable prefix or cache settings changed"
            elif rewritten:
                reason = "conversation prefix rewritten"
            status = (
                CacheStatus.INVALIDATED
                if reason
                else CacheStatus.ESTIMATED_REUSE
                if hit and provider_cache_supported
                else CacheStatus.COLD
            )
            read = (
                min(
                    prior.prefix_tokens,
                    cache_plan.stable_prefix_tokens,
                    cache_plan.logical_context_tokens,
                )
                if prior is not None and hit and provider_cache_supported
                else 0
            )
            if (
                prior is not None
                and append_only
                and provider_cache_supported
                and policy.mode != "explicit"
            ):
                read = min(prior.logical_tokens, cache_plan.logical_context_tokens)
            effective = estimate_cache_cost(cache_plan.logical_context_tokens, read, 0, policy)
            no_cache = estimate_cache_cost(cache_plan.logical_context_tokens, 0, 0, policy)
            state_start = None
            if (
                prior is not None
                and append_only
                and prior.previous_response_id
                and policy.conversation_mode == "provider_stateful"
                and len(cache_plan.message_digests) == len(prior.message_digests) + 1
                and cache_plan.message_digests[: len(prior.message_digests)]
                == prior.message_digests
            ):
                state_start = len(prior.message_digests)
            result = replace(
                cache_plan,
                generation=generation,
                status=status,
                invalidation_reason=reason,
                estimated_cache_read_tokens=read,
                estimated_cache_saving=(
                    no_cache - effective if effective is not None and no_cache is not None else None
                ),
                estimated_effective_input_cost=effective,
                stateful_suffix_start=state_start,
                provider_state_referenced_tokens=(
                    prior.logical_tokens if prior is not None and state_start is not None else 0
                ),
                previous_response_id=prior.previous_response_id
                if prior is not None and append_only
                else None,
                provider_cache_reference=prior.provider_cache_reference
                if prior is not None and hit
                else None,
                explanation=(
                    "Provider cache support is unverified; no reuse is estimated."
                    if not provider_cache_supported
                    else "Stable prefix metadata matches; provider hit remains unverified."
                    if hit
                    else "New prefix generation; provider cache use is unverified."
                ),
            )
            if len(self._entries) >= self.max_entries and key not in self._entries:
                oldest = min(self._entries, key=lambda item: self._entries[item].last_used_at)
                del self._entries[oldest]
            self._entries[key] = _CacheEntry(
                fingerprint=cache_plan.prefix_fingerprint,
                generation=generation,
                prefix_tokens=cache_plan.stable_prefix_tokens,
                model=model,
                rendering_version=policy.rendering_version,
                settings_digest=_digest(policy.request_settings),
                stable_digests={
                    part.item_hash: part.digest
                    for part in cache_plan.segments
                    if part.stability == "stable"
                },
                message_digests=cache_plan.message_digests,
                logical_tokens=cache_plan.logical_context_tokens,
                created_at=prior.created_at if prior is not None and hit else now,
                last_used_at=now,
                expires_at=(now + policy.ttl_seconds if policy.ttl_seconds else None),
                previous_response_id=(
                    prior.previous_response_id
                    if prior is not None
                    and append_only
                    and prior.message_digests == cache_plan.message_digests
                    else None
                ),
                provider_cache_reference=prior.provider_cache_reference
                if prior is not None and hit
                else None,
            )
            return result

    def cached_stable_digests(
        self, policy: CachePolicy, session_id: Optional[str], model: str
    ) -> Mapping[str, str]:
        if policy.mode == "disabled" or not session_id:
            return {}
        with self._lock:
            entry = self._entries.get(self._key(policy, session_id, model))
            if entry is None or (
                entry.expires_at is not None and entry.expires_at <= time.monotonic()
            ):
                return {}
            return dict(entry.stable_digests)

    def record_provider_reference(
        self,
        policy: CachePolicy,
        session_id: str,
        model: str,
        fingerprint: str,
        *,
        previous_response_id: Optional[str] = None,
        provider_cache_reference: Optional[str] = None,
    ) -> None:
        if policy.mode == "disabled":
            raise ValueError("cannot record a provider reference for a disabled cache")
        with self._lock:
            entry = self._entries.get(self._key(policy, session_id, model))
            if entry is None or entry.fingerprint != fingerprint:
                raise ValueError("provider reference does not match the active prefix")
            if previous_response_id is not None:
                if (
                    policy.conversation_mode != "provider_stateful"
                    or not policy.capabilities.conversation_state
                ):
                    raise ValueError("provider conversation state is not enabled")
                if not isinstance(previous_response_id, str) or len(previous_response_id) > 256:
                    raise ValueError("invalid response reference")
                entry.previous_response_id = previous_response_id
            if provider_cache_reference is not None:
                if policy.mode != "explicit" or not policy.capabilities.explicit_cached_object:
                    raise ValueError("explicit provider cache is not enabled")
                if (
                    not isinstance(provider_cache_reference, str)
                    or len(provider_cache_reference) > 512
                ):
                    raise ValueError("invalid cache reference")
                entry.provider_cache_reference = provider_cache_reference
            entry.last_used_at = time.monotonic()

    def clear(self, *, tenant_id: str, session_id: Optional[str] = None) -> None:
        with self._lock:
            for key in list(self._entries):
                if key[0] == tenant_id and (session_id is None or key[1] == session_id):
                    del self._entries[key]


def estimate_cache_cost(
    input_tokens: int, read_tokens: int, write_tokens: int, policy: CachePolicy
) -> Optional[float]:
    """Rates are caller-supplied per million; read/write subsets never add twice."""
    if policy.uncached_input_rate is None or policy.cached_input_rate is None:
        return None
    if not 0 <= read_tokens <= input_tokens or not 0 <= write_tokens <= input_tokens - read_tokens:
        raise ValueError("cache token accounting exceeds input tokens")
    write_rate = (
        policy.cache_write_rate
        if policy.cache_write_rate is not None
        else policy.uncached_input_rate
    )
    remaining = input_tokens - read_tokens - write_tokens
    return (
        remaining * policy.uncached_input_rate
        + read_tokens * policy.cached_input_rate
        + write_tokens * write_rate
    ) / 1_000_000


def cache_cost_breakdown(
    original_tokens: int, planned_tokens: int, telemetry: CacheTelemetry, policy: CachePolicy
) -> dict[str, Optional[float]]:
    """Disjoint compression and caching savings against the same raw baseline."""
    if original_tokens < 0 or planned_tokens < 0:
        raise ValueError("token counts must be non-negative")
    base = estimate_cache_cost(original_tokens, 0, 0, policy)
    planned_uncached = estimate_cache_cost(planned_tokens, 0, 0, policy)
    actual = None
    if telemetry.input_tokens is not None and telemetry.cache_read_tokens is not None:
        actual = estimate_cache_cost(
            telemetry.input_tokens,
            telemetry.cache_read_tokens,
            telemetry.cache_write_tokens or 0,
            policy,
        )
    return {
        "estimated_original_input_cost": base,
        "estimated_planned_uncached_input_cost": planned_uncached,
        "provider_usage_input_cost": actual,
        "compression_saving": (
            base - planned_uncached if base is not None and planned_uncached is not None else None
        ),
        "cache_saving": (
            planned_uncached - actual
            if planned_uncached is not None
            and actual is not None
            and telemetry.input_tokens == planned_tokens
            else None
        ),
        "combined_saving": (
            base - actual
            if base is not None and actual is not None and telemetry.input_tokens == planned_tokens
            else None
        ),
    }


__all__ = [
    "CacheCapabilities",
    "CachePolicy",
    "CachePlan",
    "CacheTelemetry",
    "CacheSegment",
    "CacheStatus",
    "CacheManager",
    "PROVIDER_CAPABILITIES",
    "compile_cache_plan",
    "classify_stability",
    "cache_item_digest",
    "cache_item_key",
    "estimate_cache_cost",
    "cache_cost_breakdown",
]
