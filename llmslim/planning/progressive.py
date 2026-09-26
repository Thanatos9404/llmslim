"""v0.7 progressive, quality-gated planner over a ContextEnvelope.

The v0.6 planner remains untouched and continues to serve plan_context().
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

from ..context_graph import ContextGraph
from ..context_policy import ContextPolicy
from ..envelope import ContextEnvelope
from ..quality import QualityReport, assess_quality
from ..tokens import count_tokens, get_active_token_counter_name
from .candidates import CandidateSet, generate_candidates, render_context_item
from .models import (
    CandidateMethod,
    ContextCandidate,
    ContextDecision,
    ContextItem,
    ContextPlan,
    ModelProfile,
    PlanMetrics,
    PlanStatus,
)
from .planner import AdaptiveContextPlanner
from .policy import PlannerPolicy, PolicyPreset, resolve_policy
from .scoring import score_item
from .validation import validate_selection

PLANNER_VERSION = "0.7.0"
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")


def _raw(item: ContextItem, query: str, policy: PlannerPolicy) -> ContextCandidate:
    score = score_item(item, query, policy)
    return ContextCandidate(
        item_id=item.item_id,
        method=CandidateMethod.RAW,
        content=item.content,
        token_cost=item.token_count,
        utility=score.total,
        risk=0.0,
        reason="raw context fits or is required for the safest feasible plan",
        retention_ratio=1.0,
        validation={"passed": True, "method": "identity"},
        provenance={"role": item.role.value, "source": item.source},
    )


def _candidate_allowed(
    item: ContextItem, candidate: ContextCandidate, quality_floor: float, relevance: float, query: str
) -> bool:
    if candidate.method is CandidateMethod.RAW:
        return True
    if not bool(candidate.validation.get("passed", False)):
        return False
    if candidate.method is CandidateMethod.DROP:
        # Python's \w splits Indic letters at combining marks, so use
        # whitespace tokens for this conservative inflection check.
        punctuation = ".,;:!?()[]{}…।"
        query_words = [part.strip(punctuation) for part in query.casefold().split()]
        content_words = [part.strip(punctuation) for part in item.content.casefold().split()]
        inflected_match = any(
            query_word != content_word
            and min(len(query_word), len(content_word)) >= 5
            and any(ord(char) > 127 for char in query_word)
            and (query_word in content_word or content_word in query_word)
            for query_word in query_words for content_word in content_words
        )
        return (
            not item.required
            and not item.metadata.get("required_keywords")
            and relevance <= max(0.0, 1.0 - quality_floor)
            and not inflected_match
        )
    for key in ("similarity", "instruction_retention", "entity_retention", "keyword_retention"):
        value = candidate.validation.get(key)
        if isinstance(value, (int, float)) and value < quality_floor:
            return False
    if not set(_NUMBER_RE.findall(item.content)) <= set(_NUMBER_RE.findall(candidate.content)):
        return False
    return True


def plan_context_v2(
    envelope: ContextEnvelope,
    *,
    max_input_tokens: Optional[int] = None,
    reserve_output_tokens: int = 4096,
    safety_margin_tokens: int = 256,
    quality_floor: float = 0.80,
    objective: str = "balanced",
    context_policy: Optional[ContextPolicy] = None,
    model_profile: Optional[ModelProfile] = None,
) -> Tuple[ContextPlan, QualityReport, ContextGraph, Tuple[str, ...]]:
    """Reduce context only under budget pressure, preserving known dependencies.

    If no quality-safe step can satisfy the budget, return an explicit
    infeasible plan. The selected content is never silently truncated.
    """
    if not 0.0 <= quality_floor <= 1.0:
        raise ValueError("quality_floor must be between 0 and 1")
    if objective not in {"balanced", "quality", "cost", "latency", "minimize_tokens"}:
        raise ValueError("unknown planning objective")
    started = time.perf_counter()
    local_policy = context_policy or ContextPolicy()
    items, exclusions = local_policy.apply(envelope.items, envelope.current_query)
    if len(items) > 256:
        raise ValueError("progressive planner exceeds the 256-item safety limit")
    evidence = [item for item in items if item.kind.value in {"rag_document", "memory", "tool_result"}]
    if len(evidence) == 1 and envelope.current_query:
        sole_id = evidence[0].item_id
        items = tuple(
            replace(item, metadata={**item.metadata, "no_drop": True})
            if item.item_id == sole_id else item
            for item in items
        )
    graph = ContextGraph.from_items(items)
    preset = {
        "balanced": PolicyPreset.BALANCED,
        "quality": PolicyPreset.QUALITY_FIRST,
        "cost": PolicyPreset.COST_FIRST,
        "latency": PolicyPreset.LATENCY_FIRST,
        "minimize_tokens": PolicyPreset.COST_FIRST,
    }[objective]
    policy = resolve_policy(preset)
    planner = AdaptiveContextPlanner(policy=policy)
    profile, budget = planner._profile_and_budget(
        model=envelope.model,
        model_profile=model_profile,
        max_input_tokens=max_input_tokens,
        reserve_output_tokens=reserve_output_tokens,
        safety_margin_tokens=safety_margin_tokens,
        budget=None,
        policy=policy,
    )
    selected: List[ContextCandidate] = [
        _raw(item, envelope.current_query, policy) for item in items
    ]
    raw_tokens = sum(candidate.token_cost for candidate in selected)
    envelope_tokens = sum(item.token_count for item in envelope.items)
    groups: Sequence[CandidateSet] = ()
    warnings: List[str] = []
    transformation_ms = 0.0
    # Generating extraction frontiers is the expensive operation. Skip it
    # entirely for a context that already fits.
    if raw_tokens > budget.available_input_tokens:
        groups = tuple(
            generate_candidates(item, query=envelope.current_query, policy=policy)
            for item in items
        )
        transformation_ms = sum(group.transformation_latency_ms for group in groups)
        warnings.extend(warning for group in groups for warning in group.warnings)
        # One step per item and frontier level. This also bounds work on
        # adversarial inputs without relying on a solver with unbounded states.
        max_steps = sum(min(8, len(group.candidates)) for group in groups)
        for _ in range(max_steps):
            current_tokens = sum(candidate.token_cost for candidate in selected)
            if current_tokens <= budget.available_input_tokens:
                break
            alternatives = []
            alive = {
                candidate.item_id
                for candidate in selected
                if candidate.method is not CandidateMethod.DROP
            }
            locked = frozenset(
                target for source in alive for target in graph.dependencies(source)
            )
            for index, (item, group) in enumerate(zip(items, groups)):
                current = selected[index]
                for candidate in group.candidates[:8]:
                    saving = current.token_cost - candidate.token_cost
                    if saving <= 0 or candidate.token_cost >= current.token_cost:
                        continue
                    if item.item_id in locked and candidate.method is not CandidateMethod.RAW:
                        continue
                    if not _candidate_allowed(
                        item, candidate, quality_floor, group.score.relevance, envelope.current_query
                    ):
                        continue
                    loss = max(0.0, current.utility - candidate.utility)
                    if objective in {"cost", "minimize_tokens"}:
                        key = (-float(saving), loss, 0.0, item.original_order, candidate.method.value)
                    elif objective == "latency":
                        key = (loss / saving, -float(saving), 0.0, item.original_order, candidate.method.value)
                    else:
                        key = (loss / saving, loss, -float(saving), item.original_order, candidate.method.value)
                    alternatives.append((key, index, candidate))
            if not alternatives:
                break
            _, index, candidate = min(alternatives, key=lambda entry: entry[0])
            selected[index] = candidate

    final_context = "".join(
        render_context_item(item, candidate.content)
        for item, candidate in zip(items, selected)
        if candidate.method is not CandidateMethod.DROP
    ).rstrip()
    final_tokens = count_tokens(final_context)
    validation_started = time.perf_counter()
    validation = validate_selection(items, selected, budget, final_tokens)
    quality = assess_quality(items, selected, graph, quality_floor, envelope.current_query)
    validation_ms = (time.perf_counter() - validation_started) * 1000.0
    feasible = final_tokens <= budget.available_input_tokens and validation.passed and quality.passed
    decisions = tuple(
        ContextDecision(
            item=item,
            selected=candidate,
            candidate_count=len(groups[index].candidates) if groups else 1,
            reason=(
                "retained raw because it fits the budget or is required by policy/dependency"
                if candidate.method is CandidateMethod.RAW
                else candidate.reason + "; selected after quality and dependency checks"
            ),
        )
        for index, (item, candidate) in enumerate(zip(items, selected))
    )
    final_messages = []
    for item, candidate in zip(items, selected):
        role = item.metadata.get("message_role")
        if role and candidate.method is not CandidateMethod.DROP:
            extra = item.metadata.get("message_extra", {})
            message = dict(extra) if isinstance(extra, dict) else dict(extra) if extra else {}
            message.update({"role": str(role), "content": candidate.content})
            final_messages.append(message)
    by_kind: Dict[str, int] = defaultdict(int)
    for item, candidate in zip(items, selected):
        by_kind[item.kind.value] += candidate.token_cost
    before_cost = profile.estimate_input_cost(envelope_tokens)
    after_cost = profile.estimate_input_cost(final_tokens)
    metrics = PlanMetrics(
        planner_version=PLANNER_VERSION,
        policy=objective,
        model=profile.model_id,
        total_candidates=sum(len(group.candidates) for group in groups) if groups else len(items),
        original_tokens=envelope_tokens,
        planned_tokens=final_tokens,
        budget_tokens=budget.available_input_tokens,
        mandatory_tokens=sum(item.token_count for item in items if item.required),
        utilization=final_tokens / budget.available_input_tokens,
        items_kept_raw=sum(c.method is CandidateMethod.RAW for c in selected),
        items_compressed=sum(c.method not in {CandidateMethod.RAW, CandidateMethod.DROP} for c in selected),
        items_dropped=sum(c.method is CandidateMethod.DROP for c in selected),
        tokens_by_kind=dict(sorted(by_kind.items())),
        planning_latency_ms=(time.perf_counter() - started) * 1000.0,
        transformation_latency_ms=transformation_ms,
        validation_latency_ms=validation_ms,
        token_counter=get_active_token_counter_name(),
        token_count_classification="HEURISTIC_ESTIMATE",
        estimated_input_cost_before=before_cost,
        estimated_input_cost_after=after_cost,
        estimated_input_cost_saving=(before_cost - after_cost) if before_cost is not None and after_cost is not None else None,
        cost_currency=profile.currency if before_cost is not None else None,
    )
    if not feasible:
        warnings.append("infeasible: quality-safe context exceeds the available input budget")
    plan = ContextPlan(
        status=PlanStatus.FEASIBLE if feasible else PlanStatus.INFEASIBLE,
        final_context=final_context,
        final_messages=tuple(final_messages),
        decisions=decisions,
        budget=budget,
        model_profile=profile,
        metrics=metrics,
        validation=validation,
        warnings=tuple(warnings),
    )
    return plan, quality, graph, exclusions


__all__ = ["plan_context_v2", "PLANNER_VERSION"]
