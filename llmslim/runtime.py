"""Provider-neutral agent context runtime. The host still executes the model and tools."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from threading import Lock
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .context import ContextSource, collect_context_sources
from .context_graph import ContextGraph
from .context_policy import ContextPolicy
from .core import ContextRole
from .envelope import ContextEnvelope
from .planning.candidates import render_context_item, rendered_token_count
from .planning.models import CandidateMethod, ContextKind, ContextPlan, ModelProfile
from .planning.progressive import plan_context_v2
from .quality import QualityReport

_SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _safe_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ModelInput:
    """Provider-neutral request parts; no credentials or executable callbacks."""

    model: str
    messages: Tuple[Mapping[str, Any], ...]
    tools: Tuple[Mapping[str, Any], ...]
    context: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": [dict(message) for message in self.messages],
            "tools": [dict(tool) for tool in self.tools],
            "context": self.context,
        }


@dataclass(frozen=True)
class ContextTrace:
    """Local diagnostics. Item IDs are hashed; prompt bodies are absent."""

    trace_id: str
    session_hash: Optional[str]
    planner_version: str
    model: str
    original_tokens: int
    planned_tokens: int
    budget_tokens: int
    decisions: Tuple[Mapping[str, Any], ...]
    quality: QualityReport
    dependency_edges: int
    planning_latency_ms: float
    transformation_latency_ms: float
    validation_latency_ms: float
    estimated_cost_before: Optional[float]
    estimated_cost_after: Optional[float]
    cost_currency: Optional[str]
    warnings: Tuple[str, ...] = ()

    @classmethod
    def from_plan(
        cls,
        envelope: ContextEnvelope,
        plan: ContextPlan,
        quality: QualityReport,
        graph: ContextGraph,
        exclusions: Sequence[str],
    ) -> "ContextTrace":
        decisions = tuple(
            {
                "item_hash": _safe_id(decision.item.item_id),
                "kind": decision.item.kind.value,
                "method": decision.selected.method.value,
                "original_tokens": decision.item.token_count,
                "planned_tokens": decision.selected.token_cost,
                "reason": (
                    "mandatory or budget-compatible raw context"
                    if decision.selected.method is CandidateMethod.RAW
                    else "quality-validated reduction under budget pressure"
                ),
            }
            for decision in plan.decisions
        )
        return cls(
            trace_id="trace_" + _safe_id(envelope.envelope_id + plan.metrics.planner_version),
            session_hash=_safe_id(envelope.session_id) if envelope.session_id else None,
            planner_version=plan.metrics.planner_version,
            model=plan.model_profile.model_id,
            original_tokens=plan.metrics.original_tokens,
            planned_tokens=plan.metrics.planned_tokens,
            budget_tokens=plan.metrics.budget_tokens,
            decisions=decisions,
            quality=quality,
            dependency_edges=graph.to_dict()["dependency_edges"],
            planning_latency_ms=plan.metrics.planning_latency_ms,
            transformation_latency_ms=plan.metrics.transformation_latency_ms,
            validation_latency_ms=plan.metrics.validation_latency_ms,
            estimated_cost_before=plan.metrics.estimated_input_cost_before,
            estimated_cost_after=plan.metrics.estimated_input_cost_after,
            cost_currency=plan.metrics.cost_currency,
            warnings=tuple("policy excluded an optional item" for _ in exclusions)
            + tuple("planning constraint was infeasible" for _ in plan.warnings if not plan.feasible),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "session_hash": self.session_hash,
            "planner_version": self.planner_version,
            "model": self.model,
            "original_tokens": self.original_tokens,
            "planned_tokens": self.planned_tokens,
            "tokens_avoided": max(0, self.original_tokens - self.planned_tokens),
            "budget_tokens": self.budget_tokens,
            "decisions": [dict(value) for value in self.decisions],
            "quality": self.quality.to_dict(),
            "dependency_edges": self.dependency_edges,
            "planning_latency_ms": self.planning_latency_ms,
            "transformation_latency_ms": self.transformation_latency_ms,
            "validation_latency_ms": self.validation_latency_ms,
            "estimated_cost_before": self.estimated_cost_before,
            "estimated_cost_after": self.estimated_cost_after,
            "cost_currency": self.cost_currency,
            "warnings": list(self.warnings),
        }

    def explain(self) -> str:
        return (
            f"{self.planner_version}: {self.original_tokens} estimated input tokens "
            f"became {self.planned_tokens}; {len(self.decisions)} items considered; "
            f"quality gates {'passed' if self.quality.passed else 'failed'}."
        )


@dataclass(frozen=True)
class PreparedContext:
    envelope: ContextEnvelope
    graph: ContextGraph
    plan: ContextPlan
    quality: QualityReport
    model_input: ModelInput
    trace: ContextTrace

    @property
    def feasible(self) -> bool:
        return self.plan.feasible

    @property
    def cost(self) -> Mapping[str, Any]:
        metrics = self.plan.metrics
        return {
            "original_estimated_input_cost": metrics.estimated_input_cost_before,
            "planned_estimated_input_cost": metrics.estimated_input_cost_after,
            "estimated_saving": metrics.estimated_input_cost_saving,
            "currency": metrics.cost_currency,
        }

    @property
    def explanation(self) -> str:
        return self.trace.explain()


def _model_input(plan: ContextPlan) -> ModelInput:
    messages = []
    tools = []
    current_user = None
    for decision in plan.decisions:
        item, candidate = decision.item, decision.selected
        if candidate.method is CandidateMethod.DROP:
            continue
        if item.kind is ContextKind.TOOL_SCHEMA:
            tools.append(json.loads(candidate.content))
            continue
        role = item.metadata.get("message_role")
        if item.kind in {
            ContextKind.SYSTEM, ContextKind.DEVELOPER, ContextKind.USER, ContextKind.ASSISTANT
        } and role in {"system", "developer", "user", "assistant"}:
            message: Mapping[str, Any] = {"role": role, "content": candidate.content}
            if item.required and role == "user":
                current_user = message
            else:
                messages.append(message)
        else:
            messages.append(
                {"role": "user", "content": render_context_item(item, candidate.content)}
            )
    if current_user is not None:
        messages.append(current_user)
    return ModelInput(plan.model_profile.model_id, tuple(messages), tuple(tools), plan.final_context)


class ContextRuntime:
    """Construct one model-visible context; never calls the model or executes tools."""

    def __init__(
        self,
        *,
        model: str = "generic-128k",
        objective: str = "balanced",
        quality_floor: float = 0.80,
        max_input_tokens: Optional[int] = None,
        reserve_output_tokens: int = 4096,
        safety_margin_tokens: int = 256,
        policy: Optional[ContextPolicy] = None,
        model_profile: Optional[ModelProfile] = None,
        max_session_messages: int = 100,
    ) -> None:
        if not 1 <= max_session_messages <= 256:
            raise ValueError("max_session_messages must be between 1 and 256")
        self.model = model
        self.objective = objective
        self.quality_floor = quality_floor
        self.max_input_tokens = max_input_tokens
        self.reserve_output_tokens = reserve_output_tokens
        self.safety_margin_tokens = safety_margin_tokens
        self.policy = policy
        self.model_profile = model_profile
        self.max_session_messages = max_session_messages
        self._sessions: Dict[str, RuntimeSession] = {}
        self._session_lock = Lock()

    def prepare_sync(
        self,
        *,
        session_id: Optional[str] = None,
        user_input: str = "",
        messages: Sequence[Mapping[str, Any]] = (),
        documents: Sequence[Any] = (),
        memories: Sequence[Any] = (),
        tool_results: Sequence[Any] = (),
        tools: Sequence[Any] = (),
    ) -> PreparedContext:
        if session_id is not None and not _SESSION_RE.fullmatch(session_id):
            raise ValueError("session_id contains unsafe characters")
        supplied_messages = tuple(messages)
        if user_input and (
            not supplied_messages
            or supplied_messages[-1].get("role") != "user"
            or supplied_messages[-1].get("content") != user_input
        ):
            supplied_messages += ({"role": "user", "content": user_input},)
        envelope = ContextEnvelope.from_inputs(
            messages=supplied_messages,
            documents=documents,
            memories=memories,
            tool_results=tool_results,
            tools=tools,
            current_query=user_input,
            session_id=session_id,
            model=self.model,
        )
        plan, quality, graph, exclusions = plan_context_v2(
            envelope,
            max_input_tokens=self.max_input_tokens,
            reserve_output_tokens=self.reserve_output_tokens,
            safety_margin_tokens=self.safety_margin_tokens,
            quality_floor=self.quality_floor,
            objective=self.objective,
            context_policy=self.policy,
            model_profile=self.model_profile,
        )
        trace = ContextTrace.from_plan(envelope, plan, quality, graph, exclusions)
        return PreparedContext(envelope, graph, plan, quality, _model_input(plan), trace)

    async def prepare(
        self,
        *,
        context_sources: Sequence[ContextSource] = (),
        source_limit: int = 10,
        fail_open_sources: bool = False,
        user_input: str = "",
        documents: Sequence[Any] = (),
        **kwargs: Any,
    ) -> PreparedContext:
        result = await collect_context_sources(
            context_sources,
            user_input,
            limit_per_source=source_limit,
            fail_open=fail_open_sources,
        )
        external = []
        for item in result.items:
            # Retrieval can rank evidence, never grant system/developer authority.
            safe_metadata = {
                key: value for key, value in item.metadata.items()
                if key in {"created_at", "entity_ids", "record_id"}
            }
            demoted = replace(
                item,
                kind=ContextKind.RAG_DOCUMENT,
                role=ContextRole.RAG,
                required=False,
                compressible=True,
                source="external:" + item.source,
                metadata=safe_metadata,
            )
            external.append(replace(demoted, token_count=rendered_token_count(demoted, demoted.content)))
        prepared = self.prepare_sync(
            user_input=user_input,
            documents=tuple(documents) + tuple(external),
            **kwargs,
        )
        if result.failures:
            safe_warnings = tuple(
                f"source failure: {failure.error_type}" for failure in result.failures
            )
            return replace(prepared, trace=replace(
                prepared.trace, warnings=prepared.trace.warnings + safe_warnings
            ))
        return prepared

    def session(self, session_id: str) -> "RuntimeSession":
        if not _SESSION_RE.fullmatch(session_id):
            raise ValueError("session_id contains unsafe characters")
        with self._session_lock:
            return self._sessions.setdefault(session_id, RuntimeSession(self, session_id))

    def clear_session(self, session_id: str) -> None:
        with self._session_lock:
            self._sessions.pop(session_id, None)


@dataclass
class RuntimeSession:
    runtime: ContextRuntime
    session_id: str
    _messages: list[Mapping[str, Any]] = field(default_factory=list, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def __aenter__(self) -> "RuntimeSession":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    def record(self, role: str, content: str) -> None:
        if role not in {"user", "assistant", "system", "developer"}:
            raise ValueError("unsupported session message role")
        if not isinstance(content, str):
            raise TypeError("session message content must be text")
        self._messages.append({"role": role, "content": content})
        trusted = [entry for entry in self._messages if entry["role"] in {"system", "developer"}]
        if len(trusted) > self.runtime.max_session_messages:
            self._messages.pop()
            raise ValueError("trusted session messages exceed retention limit")
        recent = [entry for entry in self._messages if entry["role"] not in {"system", "developer"}]
        slots = self.runtime.max_session_messages - len(trusted)
        self._messages = trusted + (recent[-slots:] if slots else [])

    async def prepare(self, user_input: str, **kwargs: Any) -> PreparedContext:
        async with self._lock:
            prepared = await self.runtime.prepare(
                session_id=self.session_id,
                user_input=user_input,
                messages=tuple(self._messages),
                **kwargs,
            )
            if prepared.feasible:
                self.record("user", user_input)
            return prepared


__all__ = ["ContextRuntime", "RuntimeSession", "PreparedContext", "ModelInput", "ContextTrace"]
