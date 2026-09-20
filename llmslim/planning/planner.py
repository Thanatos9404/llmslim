"""Adaptive deterministic planning over mixed LLM context."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from ..core import ContextRole
from ..rewrite import BaseRewriteProvider
from ..tokens import count_tokens, get_active_token_counter_name
from ..tools import ToolSchema, canonical_json, fingerprint_tool_schema
from .budget import allocate_candidates
from .candidates import CandidateSet, generate_candidates, render_context_item, rendered_token_count
from .models import (
    CandidateMethod,
    ContextBudget,
    ContextDecision,
    ContextItem,
    ContextKind,
    ContextPlan,
    InfeasibleContextError,
    ModelProfile,
    PlanMetrics,
    PlanStatus,
)
from .policy import PlannerPolicy, PolicyPreset, resolve_policy
from .profiles import ModelProfileRegistry
from .scoring import method_safety_order
from .validation import validate_selection

PLANNER_VERSION = "0.6.0"

_MESSAGE_KIND = {
    "system": ContextKind.SYSTEM,
    "developer": ContextKind.DEVELOPER,
    "user": ContextKind.USER,
    "assistant": ContextKind.ASSISTANT,
    "tool": ContextKind.TOOL_RESULT,
}

_MESSAGE_ROLE = {
    "system": ContextRole.SYSTEM,
    "developer": ContextRole.DEVELOPER,
    "user": ContextRole.USER,
    "assistant": ContextRole.ASSISTANT,
    "tool": ContextRole.TOOL,
}


def _stable_id(prefix: str, index: int, content: str, supplied: Optional[str] = None) -> str:
    if supplied:
        return f"{prefix}:{supplied}"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{index}:{digest}"


def _text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _document_item(
    value: Union[str, Mapping[str, Any], ContextItem],
    *,
    index: int,
    order: int,
    kind: ContextKind,
    prefix: str,
) -> ContextItem:
    if isinstance(value, ContextItem):
        return replace(value, original_order=order)
    if isinstance(value, str):
        content = value
        supplied_id = None
        source = "caller"
        metadata: Mapping[str, Any] = {}
        priority = 0.0
        relevance = None
        required = False
    elif isinstance(value, Mapping):
        raw_content = value.get("content", value.get("text", ""))
        content = _text_content(raw_content)
        supplied_id = str(value["id"]) if value.get("id") is not None else None
        source = str(value.get("source", "caller"))
        raw_metadata = value.get("metadata", {})
        metadata = raw_metadata if isinstance(raw_metadata, Mapping) else {}
        priority = float(value.get("priority", 0.0))
        raw_relevance = value.get("relevance")
        relevance = float(raw_relevance) if raw_relevance is not None else None
        required = bool(value.get("required", False))
    else:
        raise TypeError(f"{prefix} entries must be strings, mappings, or ContextItem objects")
    role = (
        ContextRole.RAG
        if kind in {ContextKind.RAG_DOCUMENT, ContextKind.MEMORY}
        else ContextRole.GENERAL
    )
    return ContextItem(
        item_id=_stable_id(prefix, index, content, supplied_id),
        content=content,
        kind=kind,
        role=role,
        original_order=order,
        compressible=True,
        required=required,
        relevance=relevance,
        priority=priority,
        source=source,
        metadata=metadata,
    )


def _tool_raw(value: Union[ToolSchema, Mapping[str, Any]]) -> Mapping[str, Any]:
    if isinstance(value, ToolSchema):
        return value.raw
    if not isinstance(value, Mapping):
        raise TypeError("tool entries must be ToolSchema objects or mappings")
    return value


class AdaptiveContextPlanner:
    """Provider-neutral, deterministic adaptive context planner.

    The default path is fully local. A rewrite provider is considered only
    when the caller explicitly supplies one; LLMSlim never executes tools.
    """

    def __init__(
        self,
        *,
        policy: Union[PlannerPolicy, PolicyPreset, str, None] = None,
        provider: Optional[BaseRewriteProvider] = None,
        model_profiles: Iterable[ModelProfile] = (),
    ) -> None:
        self.policy = resolve_policy(policy)
        self.provider = provider
        self.model_profiles = ModelProfileRegistry(model_profiles)

    def _normalize(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        documents: Sequence[Union[str, Mapping[str, Any], ContextItem]],
        tools: Sequence[Union[ToolSchema, Mapping[str, Any]]],
        memories: Sequence[Union[str, Mapping[str, Any], ContextItem]],
        query: str,
        policy: PlannerPolicy,
    ) -> Tuple[ContextItem, ...]:
        items: List[ContextItem] = []
        order = 0
        message_count = len(messages)
        if any(not isinstance(message, Mapping) for message in messages):
            raise TypeError("messages must contain mappings")
        last_user_index = max(
            (
                index
                for index, message in enumerate(messages)
                if str(message.get("role", "")).lower() == "user"
            ),
            default=-1,
        )
        for index, message in enumerate(messages):
            role_name = str(message.get("role", "general")).lower()
            content = _text_content(message.get("content", ""))
            kind = _MESSAGE_KIND.get(role_name, ContextKind.GENERAL)
            role = _MESSAGE_ROLE.get(role_name, ContextRole.GENERAL)
            trusted = role in {ContextRole.SYSTEM, ContextRole.DEVELOPER}
            is_current_user = index == last_user_index and role is ContextRole.USER
            latest_boundary = max(0, message_count - policy.preserve_latest_turns)
            extra = {
                key: copy.deepcopy(value)
                for key, value in message.items()
                if key not in {"content", "role"}
            }
            item = ContextItem(
                item_id=_stable_id("message", index, content, str(message.get("id", "")) or None),
                content=content,
                kind=kind,
                role=role,
                original_order=order,
                compressible=not trusted,
                required=trusted or is_current_user,
                recency=(index + 1) / max(1, message_count),
                source="messages",
                metadata={
                    "message_role": role_name,
                    "message_extra": extra,
                    "no_drop": index >= latest_boundary,
                },
            )
            items.append(item)
            order += 1

        if query.strip():
            # With an existing user turn, ``query`` is a relevance signal and
            # must not duplicate that turn merely because punctuation or
            # phrasing differs. Without messages it is the actual current turn.
            has_user_turn = any(item.kind is ContextKind.USER for item in items)
            if not has_user_turn:
                items.append(
                    ContextItem(
                        item_id=_stable_id("query", 0, query),
                        content=query,
                        kind=ContextKind.USER,
                        role=ContextRole.USER,
                        original_order=order,
                        compressible=False,
                        required=True,
                        recency=1.0,
                        priority=5.0,
                        source="query",
                        metadata={"message_role": "user", "message_extra": {}, "no_drop": True},
                    )
                )
                order += 1

        for index, document in enumerate(documents):
            items.append(
                _document_item(
                    document,
                    index=index,
                    order=order,
                    kind=ContextKind.RAG_DOCUMENT,
                    prefix="document",
                )
            )
            order += 1

        for index, memory in enumerate(memories):
            items.append(
                _document_item(
                    memory,
                    index=index,
                    order=order,
                    kind=ContextKind.MEMORY,
                    prefix="memory",
                )
            )
            order += 1

        for index, tool in enumerate(tools):
            raw = _tool_raw(tool)
            content = canonical_json(raw)
            supplied_id = None
            if isinstance(tool, ToolSchema):
                supplied_id = tool.tool_id
            elif isinstance(raw.get("name"), str):
                supplied_id = str(raw["name"])
            items.append(
                ContextItem(
                    item_id=_stable_id("tool", index, content, supplied_id),
                    content=content,
                    kind=ContextKind.TOOL_SCHEMA,
                    role=ContextRole.TOOL,
                    original_order=order,
                    compressible=False,
                    required=not policy.experimental_selective_tools,
                    recency=1.0,
                    source="tools",
                    metadata={
                        "tool_fingerprint": fingerprint_tool_schema(raw),
                        "no_drop": not policy.experimental_selective_tools,
                    },
                )
            )
            order += 1

        # Planning token_count includes the exact provenance wrapper used by
        # final_context, preventing small serialization overheads from causing
        # a nominally feasible plan to exceed its budget.
        prepared = [
            replace(item, token_count=rendered_token_count(item, item.content)) for item in items
        ]
        ids = [item.item_id for item in prepared]
        if len(ids) != len(set(ids)):
            raise ValueError("normalized context item IDs must be unique")
        return tuple(prepared)

    def _profile_and_budget(
        self,
        *,
        model: str,
        model_profile: Optional[ModelProfile],
        max_input_tokens: Optional[int],
        reserve_output_tokens: int,
        safety_margin_tokens: int,
        budget: Optional[Union[int, ContextBudget]],
        policy: PlannerPolicy,
    ) -> Tuple[ModelProfile, ContextBudget]:
        if model_profile is not None:
            profile = model_profile
        else:
            profile = self.model_profiles.get(model)  # type: ignore[assignment]
            if profile is None:
                if max_input_tokens is None and not isinstance(budget, (int, ContextBudget)):
                    self.model_profiles.require(model)
                explicit = (
                    budget.available_input_tokens
                    if isinstance(budget, ContextBudget)
                    else int(budget)
                    if isinstance(budget, int)
                    else int(max_input_tokens or 0)
                )
                profile = ModelProfile(
                    model_id=model,
                    provider="caller",
                    context_window=explicit + reserve_output_tokens + safety_margin_tokens,
                    source="caller-supplied token budget",
                )
        if isinstance(budget, ContextBudget):
            return profile, budget
        if isinstance(budget, int):
            if max_input_tokens is not None and max_input_tokens != budget:
                raise ValueError("budget and max_input_tokens disagree")
            max_input_tokens = budget
        input_limit = (
            max_input_tokens
            if max_input_tokens is not None
            else profile.context_window - reserve_output_tokens
        )
        resolved = ContextBudget(
            max_input_tokens=input_limit,
            reserve_output_tokens=reserve_output_tokens,
            safety_margin_tokens=safety_margin_tokens,
            target_utilization=policy.target_utilization,
            model_context_window=profile.context_window,
        )
        if resolved.available_input_tokens <= 0:
            raise ValueError("output reservation and safety margin leave no input-token budget")
        return profile, resolved

    @staticmethod
    def _safe_fallbacks(
        groups: Sequence[CandidateSet],
        selected: Sequence[Any],
        capacity: int,
    ) -> Tuple[Tuple[Any, ...], Tuple[str, ...]]:
        chosen = list(selected)
        fallbacks: List[str] = []
        total = sum(candidate.token_cost for candidate in chosen)
        for index, (group, candidate) in enumerate(zip(groups, chosen)):
            if bool(candidate.validation.get("passed", True)):
                continue
            alternatives = sorted(
                (
                    option
                    for option in group.candidates
                    if bool(option.validation.get("passed", True))
                    and method_safety_order(option.method) > method_safety_order(candidate.method)
                ),
                key=lambda option: (method_safety_order(option.method), -option.token_cost),
            )
            for alternative in alternatives:
                replacement_total = total - candidate.token_cost + alternative.token_cost
                if replacement_total <= capacity:
                    chosen[index] = alternative
                    total = replacement_total
                    fallbacks.append(
                        f"{candidate.item_id}: {candidate.method.value} -> {alternative.method.value}"
                    )
                    break
        return tuple(chosen), tuple(fallbacks)

    def plan(
        self,
        *,
        messages: Sequence[Mapping[str, Any]] = (),
        documents: Sequence[Union[str, Mapping[str, Any], ContextItem]] = (),
        tools: Sequence[Union[ToolSchema, Mapping[str, Any]]] = (),
        memories: Sequence[Union[str, Mapping[str, Any], ContextItem]] = (),
        query: str = "",
        model: str = "generic-128k",
        max_input_tokens: Optional[int] = None,
        reserve_output_tokens: int = 4096,
        safety_margin_tokens: int = 256,
        budget: Optional[Union[int, ContextBudget]] = None,
        policy: Union[PlannerPolicy, PolicyPreset, str, None] = None,
        provider: Optional[BaseRewriteProvider] = None,
        model_profile: Optional[ModelProfile] = None,
        raise_on_infeasible: bool = False,
    ) -> ContextPlan:
        """Plan the highest-value safe context within a finite model budget."""

        started = time.perf_counter()
        resolved_policy = resolve_policy(policy) if policy is not None else self.policy
        profile, resolved_budget = self._profile_and_budget(
            model=model,
            model_profile=model_profile,
            max_input_tokens=max_input_tokens,
            reserve_output_tokens=reserve_output_tokens,
            safety_margin_tokens=safety_margin_tokens,
            budget=budget,
            policy=resolved_policy,
        )
        items = self._normalize(
            messages=messages,
            documents=documents,
            tools=tools,
            memories=memories,
            query=query,
            policy=resolved_policy,
        )
        active_provider = provider if provider is not None else self.provider
        groups = tuple(
            generate_candidates(
                item,
                query=query,
                policy=resolved_policy,
                provider=active_provider,
            )
            for item in items
        )
        allocation = allocate_candidates(groups, resolved_budget.available_input_tokens)
        selected, fallbacks = self._safe_fallbacks(
            groups, allocation.selected, resolved_budget.available_input_tokens
        )
        final_context = "".join(
            render_context_item(item, candidate.content)
            for item, candidate in zip(items, selected)
            if candidate.method is not CandidateMethod.DROP
        ).rstrip()
        final_tokens = count_tokens(final_context)

        validation_started = time.perf_counter()
        validation = validate_selection(items, selected, resolved_budget, final_tokens)
        validation_ms = (time.perf_counter() - validation_started) * 1000.0
        feasible = allocation.feasible and final_tokens <= resolved_budget.available_input_tokens
        status = PlanStatus.FEASIBLE if feasible else PlanStatus.INFEASIBLE

        decisions = tuple(
            ContextDecision(
                item=item,
                selected=candidate,
                candidate_count=len(group.candidates),
                reason=(
                    candidate.reason + f"; value signals: relevance={group.score.relevance:.3f}, "
                    f"recency={group.score.recency:.3f}, provenance={group.score.provenance:.3f}"
                ),
                warnings=group.warnings,
            )
            for item, group, candidate in zip(items, groups, selected)
        )

        final_messages: List[Mapping[str, Any]] = []
        for item, candidate in zip(items, selected):
            message_role = item.metadata.get("message_role")
            if not message_role or candidate.method is CandidateMethod.DROP:
                continue
            extra = item.metadata.get("message_extra", {})
            message = dict(extra) if isinstance(extra, Mapping) else {}
            message["role"] = str(message_role)
            message["content"] = candidate.content
            final_messages.append(message)

        original_tokens = sum(group.candidates[0].token_cost for group in groups)
        mandatory_tokens = sum(
            min(candidate.token_cost for candidate in group.candidates)
            for group in groups
            if all(candidate.method is not CandidateMethod.DROP for candidate in group.candidates)
        )
        by_kind: Dict[str, int] = defaultdict(int)
        for item, candidate in zip(items, selected):
            by_kind[item.kind.value] += candidate.token_cost
        before_cost = profile.estimate_input_cost(original_tokens)
        after_cost = profile.estimate_input_cost(final_tokens)
        metrics = PlanMetrics(
            planner_version=PLANNER_VERSION,
            policy=resolved_policy.name,
            model=profile.model_id,
            total_candidates=sum(len(group.candidates) for group in groups),
            original_tokens=original_tokens,
            planned_tokens=final_tokens,
            budget_tokens=resolved_budget.available_input_tokens,
            mandatory_tokens=mandatory_tokens,
            utilization=(final_tokens / resolved_budget.available_input_tokens)
            if resolved_budget.available_input_tokens
            else 0.0,
            items_kept_raw=sum(c.method is CandidateMethod.RAW for c in selected),
            items_compressed=sum(
                c.method
                in {
                    CandidateMethod.EXTRACTIVE_COMPRESSED,
                    CandidateMethod.REWRITE_COMPRESSED,
                    CandidateMethod.HYBRID_COMPRESSED,
                }
                for c in selected
            ),
            items_dropped=sum(c.method is CandidateMethod.DROP for c in selected),
            tokens_by_kind=dict(sorted(by_kind.items())),
            planning_latency_ms=(time.perf_counter() - started) * 1000.0,
            transformation_latency_ms=sum(group.transformation_latency_ms for group in groups),
            validation_latency_ms=validation_ms,
            token_counter=get_active_token_counter_name(),
            token_count_classification="ESTIMATED",
            estimated_input_cost_before=before_cost,
            estimated_input_cost_after=after_cost,
            estimated_input_cost_saving=(before_cost - after_cost)
            if before_cost is not None and after_cost is not None
            else None,
            cost_currency=profile.currency if before_cost is not None else None,
        )
        warnings = [warning for group in groups for warning in group.warnings]
        warnings.extend(validation.warnings)
        if resolved_policy.experimental_selective_tools and tools:
            warnings.append(
                "EXPERIMENTAL: selective tool exposure is context selection, not authorization or execution"
            )
        if not feasible:
            warnings.append(
                "infeasible plan: mandatory/minimum-safe context exceeds the available budget; trusted content was not truncated"
            )
        plan = ContextPlan(
            status=status,
            final_context=final_context,
            final_messages=tuple(final_messages),
            decisions=decisions,
            budget=resolved_budget,
            model_profile=profile,
            metrics=metrics,
            validation=validation,
            warnings=tuple(dict.fromkeys(warnings)),
            fallbacks=fallbacks,
        )
        if raise_on_infeasible and not plan.feasible:
            raise InfeasibleContextError(plan)
        return plan

    async def aplan(
        self,
        *,
        context_sources: Sequence[Any] = (),
        source_limit: int = 10,
        fail_open_sources: bool = False,
        documents: Sequence[Union[str, Mapping[str, Any], ContextItem]] = (),
        query: str = "",
        **kwargs: Any,
    ) -> ContextPlan:
        """Retrieve explicit context sources and then run the synchronous planner.

        External I/O is asynchronous; CPU-only deterministic planning remains
        synchronous. Source failures are fail-closed unless explicitly opted out.
        """

        from ..context import collect_context_sources

        source_result = await collect_context_sources(
            context_sources,
            query,
            limit_per_source=source_limit,
            fail_open=fail_open_sources,
        )
        plan = self.plan(
            documents=tuple(documents) + source_result.items,
            query=query,
            **kwargs,
        )
        if not source_result.failures:
            return plan
        source_warnings = tuple(
            f"context source {failure.source_id} failed with {failure.error_type}; explicit fail-open used"
            for failure in source_result.failures
        )
        return replace(plan, warnings=plan.warnings + source_warnings)


def plan_context(
    *,
    messages: Sequence[Mapping[str, Any]] = (),
    documents: Sequence[Union[str, Mapping[str, Any], ContextItem]] = (),
    tools: Sequence[Union[ToolSchema, Mapping[str, Any]]] = (),
    memories: Sequence[Union[str, Mapping[str, Any], ContextItem]] = (),
    query: str = "",
    model: str = "generic-128k",
    max_input_tokens: Optional[int] = None,
    reserve_output_tokens: int = 4096,
    safety_margin_tokens: int = 256,
    budget: Optional[Union[int, ContextBudget]] = None,
    policy: Union[PlannerPolicy, PolicyPreset, str, None] = None,
    provider: Optional[BaseRewriteProvider] = None,
    model_profile: Optional[ModelProfile] = None,
    raise_on_infeasible: bool = False,
) -> ContextPlan:
    """Convenience API for one-shot adaptive context planning."""

    return AdaptiveContextPlanner(policy=policy, provider=provider).plan(
        messages=messages,
        documents=documents,
        tools=tools,
        memories=memories,
        query=query,
        model=model,
        max_input_tokens=max_input_tokens,
        reserve_output_tokens=reserve_output_tokens,
        safety_margin_tokens=safety_margin_tokens,
        budget=budget,
        model_profile=model_profile,
        raise_on_infeasible=raise_on_infeasible,
    )


__all__ = ["AdaptiveContextPlanner", "PLANNER_VERSION", "plan_context"]
