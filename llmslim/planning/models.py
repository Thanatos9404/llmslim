"""Provider-neutral data model for adaptive context planning.

All public records are frozen. Mutable caller-owned dictionaries and sequences
are copied at the boundary so a completed plan remains a stable audit record.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..core import ContextRole


def _frozen_mapping(value: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    return MappingProxyType(copy.deepcopy(dict(value or {})))


def _plain_mapping(value: Mapping[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(dict(value))


class ContextKind(str, Enum):
    """Logical context classes understood by the planner."""

    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"
    RAG_DOCUMENT = "rag_document"
    MEMORY = "memory"
    TOOL_SCHEMA = "tool_schema"
    GENERAL = "general"


class CandidateMethod(str, Enum):
    """Available representations for one logical context item."""

    RAW = "raw"
    EXTRACTIVE_COMPRESSED = "extractive_compressed"
    REWRITE_COMPRESSED = "rewrite_compressed"
    HYBRID_COMPRESSED = "hybrid_compressed"
    DROP = "drop"


class PlanStatus(str, Enum):
    """Whether a plan satisfies its hard input-token constraints."""

    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"


@dataclass(frozen=True)
class ContextItem:
    """One provenance-bearing logical unit considered by the planner."""

    item_id: str
    content: str
    kind: ContextKind = ContextKind.GENERAL
    role: ContextRole = ContextRole.GENERAL
    original_order: int = 0
    token_count: int = 0
    compressible: bool = True
    required: bool = False
    relevance: Optional[float] = None
    recency: float = 0.0
    priority: float = 0.0
    source: str = "caller"
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not self.item_id or not isinstance(self.item_id, str):
            raise ValueError("item_id must be a non-empty string")
        if not isinstance(self.content, str):
            raise TypeError("context item content must be a string")
        if self.token_count < 0:
            raise ValueError("token_count must be non-negative")
        if self.relevance is not None and not 0.0 <= self.relevance <= 1.0:
            raise ValueError("relevance must be between 0 and 1")
        if not 0.0 <= self.recency <= 1.0:
            raise ValueError("recency must be between 0 and 1")
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))

    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id": self.item_id,
            "kind": self.kind.value,
            "role": self.role.value,
            "original_order": self.original_order,
            "token_count": self.token_count,
            "compressible": self.compressible,
            "required": self.required,
            "relevance": self.relevance,
            "recency": self.recency,
            "priority": self.priority,
            "source": self.source,
            "metadata": _plain_mapping(self.metadata),
        }
        if include_content:
            result["content"] = self.content
        return result


@dataclass(frozen=True)
class ContextBundle:
    """A stable ordered collection of context items."""

    items: Tuple[ContextItem, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("context item IDs must be unique")


@dataclass(frozen=True)
class ContextBudget:
    """Resolved input budget, including output reservation and safety margin."""

    max_input_tokens: int
    reserve_output_tokens: int = 4096
    safety_margin_tokens: int = 256
    target_utilization: float = 1.0
    model_context_window: Optional[int] = None

    def __post_init__(self) -> None:
        if self.max_input_tokens <= 0:
            raise ValueError("max_input_tokens must be positive")
        if self.reserve_output_tokens < 0 or self.safety_margin_tokens < 0:
            raise ValueError("token reservations must be non-negative")
        if not 0.0 < self.target_utilization <= 1.0:
            raise ValueError("target_utilization must be in (0, 1]")
        if self.model_context_window is not None and self.model_context_window <= 0:
            raise ValueError("model_context_window must be positive")

    @property
    def available_input_tokens(self) -> int:
        limit = self.max_input_tokens
        if self.model_context_window is not None:
            context_input = self.model_context_window - self.reserve_output_tokens
            limit = min(limit, context_input)
        usable = max(0, limit - self.safety_margin_tokens)
        return max(0, int(usable * self.target_utilization))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_input_tokens": self.max_input_tokens,
            "reserve_output_tokens": self.reserve_output_tokens,
            "safety_margin_tokens": self.safety_margin_tokens,
            "target_utilization": self.target_utilization,
            "model_context_window": self.model_context_window,
            "available_input_tokens": self.available_input_tokens,
        }


@dataclass(frozen=True)
class ModelProfile:
    """Data-driven context and pricing metadata for a target model."""

    model_id: str
    provider: str
    context_window: int
    input_cost_per_million: Optional[float] = None
    cached_input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None
    currency: str = "INR"
    capabilities: Tuple[str, ...] = ()
    pricing_as_of: Optional[str] = None
    source: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not self.model_id or self.context_window <= 0:
            raise ValueError("model profile requires an ID and positive context window")
        prices = (
            self.input_cost_per_million,
            self.cached_input_cost_per_million,
            self.output_cost_per_million,
        )
        if any(price is not None and price < 0 for price in prices):
            raise ValueError("model profile prices must be non-negative")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "metadata", _frozen_mapping(self.metadata))

    def estimate_input_cost(self, tokens: int) -> Optional[float]:
        if tokens < 0:
            raise ValueError("token count must be non-negative")
        if self.input_cost_per_million is None:
            return None
        return tokens / 1_000_000.0 * self.input_cost_per_million

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "context_window": self.context_window,
            "input_cost_per_million": self.input_cost_per_million,
            "cached_input_cost_per_million": self.cached_input_cost_per_million,
            "output_cost_per_million": self.output_cost_per_million,
            "currency": self.currency,
            "capabilities": list(self.capabilities),
            "pricing_as_of": self.pricing_as_of,
            "source": self.source,
            "metadata": _plain_mapping(self.metadata),
        }


@dataclass(frozen=True)
class ContextCandidate:
    """One model-facing representation of a logical item."""

    item_id: str
    method: CandidateMethod
    content: str
    token_cost: int
    utility: float
    risk: float
    reason: str
    retention_ratio: float
    validation: Mapping[str, Any] = field(default_factory=dict, compare=False)
    provenance: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if self.token_cost < 0:
            raise ValueError("candidate token cost must be non-negative")
        if not 0.0 <= self.risk <= 1.0:
            raise ValueError("candidate risk must be between 0 and 1")
        object.__setattr__(self, "validation", _frozen_mapping(self.validation))
        object.__setattr__(self, "provenance", _frozen_mapping(self.provenance))


@dataclass(frozen=True)
class ContextDecision:
    """Explainable selected representation for one input item."""

    item: ContextItem
    selected: ContextCandidate
    candidate_count: int
    reason: str
    warnings: Tuple[str, ...] = ()

    @property
    def tokens_removed(self) -> int:
        return max(0, self.item.token_count - self.selected.token_cost)

    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        result = {
            "item": self.item.to_dict(include_content=include_content),
            "method": self.selected.method.value,
            "planned_tokens": self.selected.token_cost,
            "tokens_removed": self.tokens_removed,
            "utility": round(self.selected.utility, 6),
            "risk": self.selected.risk,
            "retention_ratio": self.selected.retention_ratio,
            "reason": self.reason,
            "candidate_count": self.candidate_count,
            "validation": _plain_mapping(self.selected.validation),
            "provenance": _plain_mapping(self.selected.provenance),
            "warnings": list(self.warnings),
        }
        if include_content:
            result["planned_content"] = self.selected.content
        return result


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class PlanValidationResult:
    passed: bool
    checks: Tuple[ValidationCheck, ...]
    warnings: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in self.checks
            ],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PlanMetrics:
    planner_version: str
    policy: str
    model: str
    total_candidates: int
    original_tokens: int
    planned_tokens: int
    budget_tokens: int
    mandatory_tokens: int
    utilization: float
    items_kept_raw: int
    items_compressed: int
    items_dropped: int
    tokens_by_kind: Mapping[str, int]
    planning_latency_ms: float
    transformation_latency_ms: float
    validation_latency_ms: float
    token_counter: str
    token_count_classification: str = "ESTIMATED"
    estimated_input_cost_before: Optional[float] = None
    estimated_input_cost_after: Optional[float] = None
    estimated_input_cost_saving: Optional[float] = None
    cost_currency: Optional[str] = None

    @property
    def tokens_removed(self) -> int:
        return max(0, self.original_tokens - self.planned_tokens)

    def to_dict(self) -> Dict[str, Any]:
        result = dict(self.__dict__)
        result["tokens_by_kind"] = dict(self.tokens_by_kind)
        result["tokens_removed"] = self.tokens_removed
        return result


@dataclass(frozen=True)
class ContextPlan:
    """Complete local planning result and audit record."""

    status: PlanStatus
    final_context: str
    final_messages: Tuple[Mapping[str, Any], ...]
    decisions: Tuple[ContextDecision, ...]
    budget: ContextBudget
    model_profile: ModelProfile
    metrics: PlanMetrics
    validation: PlanValidationResult
    warnings: Tuple[str, ...] = ()
    fallbacks: Tuple[str, ...] = ()

    @property
    def feasible(self) -> bool:
        return self.status is PlanStatus.FEASIBLE

    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "status": self.status.value,
            "feasible": self.feasible,
            "decisions": [
                decision.to_dict(include_content=include_content) for decision in self.decisions
            ],
            "budget": self.budget.to_dict(),
            "model_profile": self.model_profile.to_dict(),
            "metrics": self.metrics.to_dict(),
            "validation": self.validation.to_dict(),
            "warnings": list(self.warnings),
            "fallbacks": list(self.fallbacks),
        }
        if include_content:
            result["final_context"] = self.final_context
            result["final_messages"] = [dict(message) for message in self.final_messages]
        return result


class ContextPlanningError(RuntimeError):
    """Base class for planner failures."""


class InfeasibleContextError(ContextPlanningError):
    """Raised by strict callers when mandatory context exceeds the budget."""

    def __init__(self, plan: ContextPlan) -> None:
        self.plan = plan
        super().__init__(
            "mandatory context exceeds the available input budget: "
            f"{plan.metrics.planned_tokens} > {plan.metrics.budget_tokens} tokens"
        )


MessageSequence = Sequence[Mapping[str, Any]]
