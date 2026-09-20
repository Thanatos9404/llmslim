"""Post-planning hard-constraint and integrity validation."""

from __future__ import annotations

import json
from typing import List, Sequence

from ..core import ContextRole
from ..tools import fingerprint_tool_schema
from .models import (
    CandidateMethod,
    ContextBudget,
    ContextCandidate,
    ContextItem,
    ContextKind,
    PlanValidationResult,
    ValidationCheck,
)


def validate_selection(
    items: Sequence[ContextItem],
    selected: Sequence[ContextCandidate],
    budget: ContextBudget,
    final_tokens: int,
) -> PlanValidationResult:
    """Validate budget, retention, ordering, provenance and tool contracts."""

    checks: List[ValidationCheck] = []
    warnings: List[str] = []
    by_id = {candidate.item_id: candidate for candidate in selected}

    within_budget = final_tokens <= budget.available_input_tokens
    checks.append(
        ValidationCheck(
            "token_budget",
            within_budget,
            f"planned {final_tokens} tokens against {budget.available_input_tokens} available",
        )
    )

    missing_required = [
        item.item_id
        for item in items
        if item.required
        and (
            item.item_id not in by_id
            or by_id[item.item_id].method is CandidateMethod.DROP
            or by_id[item.item_id].content != item.content
        )
    ]
    checks.append(
        ValidationCheck(
            "required_context_retention",
            not missing_required,
            "all required items retained exactly"
            if not missing_required
            else "missing or transformed required items: " + ", ".join(missing_required),
        )
    )

    trusted_changed = [
        item.item_id
        for item in items
        if item.role in {ContextRole.SYSTEM, ContextRole.DEVELOPER}
        and (
            item.item_id not in by_id
            or by_id[item.item_id].method is not CandidateMethod.RAW
            or by_id[item.item_id].content != item.content
        )
    ]
    checks.append(
        ValidationCheck(
            "trusted_instruction_retention",
            not trusted_changed,
            "system/developer content retained byte-for-byte"
            if not trusted_changed
            else "trusted items changed: " + ", ".join(trusted_changed),
        )
    )

    selected_order = [
        item.original_order
        for item in items
        if item.item_id in by_id and by_id[item.item_id].method is not CandidateMethod.DROP
    ]
    order_valid = selected_order == sorted(selected_order)
    checks.append(
        ValidationCheck(
            "stable_ordering",
            order_valid,
            "selected content preserves original order"
            if order_valid
            else "selected content is out of original order",
        )
    )

    bad_candidates = [
        candidate.item_id
        for candidate in selected
        if candidate.method not in {CandidateMethod.RAW, CandidateMethod.DROP}
        and not bool(candidate.validation.get("passed", False))
    ]
    checks.append(
        ValidationCheck(
            "candidate_validation",
            not bad_candidates,
            "all transformed representations passed validation"
            if not bad_candidates
            else "unvalidated representations selected: " + ", ".join(bad_candidates),
        )
    )

    tool_errors: List[str] = []
    for item in items:
        if item.kind is not ContextKind.TOOL_SCHEMA:
            continue
        candidate = by_id.get(item.item_id)
        if candidate is None or candidate.method is CandidateMethod.DROP:
            # Experimental selective exposure may omit a tool, but a selected
            # schema can never be rewritten or fingerprint-mismatched.
            continue
        if candidate.method is not CandidateMethod.RAW:
            tool_errors.append(item.item_id + ": non-raw representation")
            continue
        expected = item.metadata.get("tool_fingerprint")
        if expected:
            try:
                actual = fingerprint_tool_schema(json.loads(candidate.content))
            except (TypeError, ValueError, json.JSONDecodeError):
                tool_errors.append(item.item_id + ": malformed authoritative schema")
                continue
            if actual != expected:
                tool_errors.append(item.item_id + ": fingerprint mismatch")
    checks.append(
        ValidationCheck(
            "tool_schema_integrity",
            not tool_errors,
            "selected tool contracts remain authoritative and fingerprint-valid"
            if not tool_errors
            else "; ".join(tool_errors),
        )
    )

    external_elevation = [
        item.item_id
        for item in items
        if item.source.split(":", 1)[0] in {"zoho", "mongodb"}
        and item.role in {ContextRole.SYSTEM, ContextRole.DEVELOPER}
    ]
    checks.append(
        ValidationCheck(
            "external_provenance_boundary",
            not external_elevation,
            "external source content remains untrusted"
            if not external_elevation
            else "external items gained trusted provenance: " + ", ".join(external_elevation),
        )
    )

    warnings.append(
        "token counts are planner estimates unless a provider separately reports authoritative usage"
    )
    return PlanValidationResult(
        passed=all(check.passed for check in checks),
        checks=tuple(checks),
        warnings=tuple(warnings),
    )


__all__ = ["validate_selection"]
