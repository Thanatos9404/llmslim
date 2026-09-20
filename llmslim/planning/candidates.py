"""Candidate representation generation for the adaptive planner."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core import ContextRole, compress
from ..rewrite import BaseRewriteProvider
from ..rewrite.validation import RewriteValidator
from ..tokens import count_tokens
from .models import CandidateMethod, ContextCandidate, ContextItem, ContextKind
from .policy import PlannerPolicy
from .scoring import ScoreBreakdown, candidate_utility, score_item

_TRUSTED_ROLES = {ContextRole.SYSTEM, ContextRole.DEVELOPER}
_UNTRUSTED_KINDS = {
    ContextKind.ASSISTANT,
    ContextKind.TOOL_RESULT,
    ContextKind.RAG_DOCUMENT,
    ContextKind.MEMORY,
}


def trusted_role(role: ContextRole) -> bool:
    return role in _TRUSTED_ROLES


def render_context_item(item: ContextItem, content: str) -> str:
    """Render one item with an explicit provenance boundary."""

    trusted = "true" if trusted_role(item.role) else "false"
    header = (
        f'<llmslim_context id="{item.item_id}" kind="{item.kind.value}" '
        f'role="{item.role.value}" trusted="{trusted}">'
    )
    return f"{header}\n{content}\n</llmslim_context>\n\n"


def rendered_token_count(item: ContextItem, content: str) -> int:
    return count_tokens(render_context_item(item, content))


@dataclass(frozen=True)
class CandidateSet:
    item: ContextItem
    candidates: Tuple[ContextCandidate, ...]
    score: ScoreBreakdown
    transformation_latency_ms: float
    warnings: Tuple[str, ...] = ()


def _validation_payload(result: Any) -> Dict[str, Any]:
    return {
        "passed": bool(result.passed),
        "similarity": result.similarity_score,
        "instruction_retention": result.instruction_retention,
        "entity_retention": result.entity_retention,
        "keyword_retention": result.keyword_retention,
        "failure_reasons": list(result.failure_reasons),
    }


def _build_candidate(
    item: ContextItem,
    method: CandidateMethod,
    content: str,
    score: ScoreBreakdown,
    policy: PlannerPolicy,
    reason: str,
    validation: Optional[Dict[str, Any]] = None,
) -> ContextCandidate:
    content_tokens = count_tokens(content)
    raw_content_tokens = max(1, count_tokens(item.content))
    retention = min(1.0, content_tokens / raw_content_tokens) if content else 0.0
    utility, risk = candidate_utility(score, method, retention, policy)
    cost = 0 if method is CandidateMethod.DROP else rendered_token_count(item, content)
    return ContextCandidate(
        item_id=item.item_id,
        method=method,
        content=content,
        token_cost=cost,
        utility=utility,
        risk=risk,
        reason=reason,
        retention_ratio=retention,
        validation=validation or {"passed": True, "method": "identity"},
        provenance={
            "role": item.role.value,
            "source": item.source,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "score": score.to_dict(),
        },
    )


def _required_keywords(item: ContextItem) -> List[str]:
    value = item.metadata.get("required_keywords", ())
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(entry) for entry in value]
    return []


def _allow_drop(item: ContextItem, policy: PlannerPolicy) -> bool:
    if not policy.allow_drop or item.required or bool(item.metadata.get("no_drop")):
        return False
    if trusted_role(item.role):
        return False
    if item.kind is ContextKind.TOOL_SCHEMA:
        return policy.experimental_selective_tools
    return True


def _provider_candidate(
    item: ContextItem,
    method: CandidateMethod,
    ratio: float,
    provider: BaseRewriteProvider,
    score: ScoreBreakdown,
    policy: PlannerPolicy,
) -> Optional[ContextCandidate]:
    strategy = "rewrite" if method is CandidateMethod.REWRITE_COMPRESSED else "hybrid"
    result = compress(
        item.content,
        target_ratio=ratio,
        query=None,
        strategy=strategy,
        provider=provider,
        required_keywords=_required_keywords(item),
        context_role=item.role,
        min_tokens_for_compression=0,
    )
    if result.compressed_text == item.content or result.compressed_tokens >= result.original_tokens:
        return None
    metadata = result.rewrite_metadata
    accepted = bool(getattr(metadata, "accepted", False))
    if not accepted:
        return None
    validation = {
        "passed": True,
        "similarity": getattr(metadata, "similarity_score", None),
        "instruction_retention": getattr(metadata, "instruction_retention", None),
        "entity_retention": getattr(metadata, "entity_retention", None),
        "fallback_used": getattr(metadata, "fallback_used", False),
    }
    return _build_candidate(
        item,
        method,
        result.compressed_text,
        score,
        policy,
        f"explicit provider produced a validated {strategy} representation at ratio {ratio:.2f}",
        validation,
    )


def generate_candidates(
    item: ContextItem,
    *,
    query: str,
    policy: PlannerPolicy,
    provider: Optional[BaseRewriteProvider] = None,
) -> CandidateSet:
    """Generate safe representations for one item, raw first and deterministically."""

    started = time.perf_counter()
    score = score_item(item, query, policy)
    warnings: List[str] = []
    candidates = [
        _build_candidate(
            item,
            CandidateMethod.RAW,
            item.content,
            score,
            policy,
            "raw content preserves the complete caller-provided representation",
        )
    ]
    raw_cost = candidates[0].token_cost
    seen = {item.content}

    can_transform = (
        item.compressible
        and not item.required
        and not trusted_role(item.role)
        and item.kind is not ContextKind.TOOL_SCHEMA
        and count_tokens(item.content) >= 12
    )
    if can_transform:
        validator = RewriteValidator(
            min_similarity=0.20,
            min_instruction_retention=policy.minimum_instruction_retention,
            min_entity_retention=policy.minimum_entity_retention,
        )
        for ratio in policy.compression_ratios:
            result = compress(
                item.content,
                target_ratio=ratio,
                query=query or None,
                strategy="extractive",
                context_role=item.role,
                min_tokens_for_compression=0,
            )
            transformed = result.compressed_text
            if transformed in seen or not transformed.strip():
                continue
            validation_result = validator.validate(
                item.content,
                transformed,
                required_keywords=_required_keywords(item),
            )
            payload = _validation_payload(validation_result)
            if not validation_result.passed:
                warnings.append(
                    f"rejected extractive candidate {ratio:.2f} for {item.item_id}: "
                    + "; ".join(validation_result.failure_reasons)
                )
                continue
            candidate = _build_candidate(
                item,
                CandidateMethod.EXTRACTIVE_COMPRESSED,
                transformed,
                score,
                policy,
                f"deterministic extractive compression retained validated evidence at ratio {ratio:.2f}",
                payload,
            )
            if candidate.token_cost < raw_cost:
                candidates.append(candidate)
                seen.add(transformed)

        if provider is not None:
            middle_ratio = policy.compression_ratios[len(policy.compression_ratios) // 2]
            provider_methods = []
            if policy.allow_rewrite:
                provider_methods.append(CandidateMethod.REWRITE_COMPRESSED)
            if policy.allow_hybrid:
                provider_methods.append(CandidateMethod.HYBRID_COMPRESSED)
            for method in provider_methods:
                try:
                    provider_candidate = _provider_candidate(
                        item, method, middle_ratio, provider, score, policy
                    )
                except Exception as exc:
                    # The provider boundary is optional. Preserve only the exception
                    # class; provider messages can contain request or credential data.
                    warnings.append(
                        f"{method.value} unavailable for {item.item_id}: {type(exc).__name__}"
                    )
                    continue
                if provider_candidate is not None and provider_candidate.content not in seen:
                    candidates.append(provider_candidate)
                    seen.add(provider_candidate.content)
                elif provider_candidate is None:
                    warnings.append(
                        f"{method.value} unavailable for {item.item_id}: "
                        "provider produced no validated token reduction"
                    )

    if _allow_drop(item, policy):
        candidates.append(
            _build_candidate(
                item,
                CandidateMethod.DROP,
                "",
                score,
                policy,
                "safe-to-drop optional context is available only when the budget requires it",
            )
        )

    # Stable ordering makes tie resolution deterministic. Raw remains first;
    # transformations then progress from least to most aggressive; DROP last.
    method_order = {
        CandidateMethod.RAW: 0,
        CandidateMethod.EXTRACTIVE_COMPRESSED: 1,
        CandidateMethod.HYBRID_COMPRESSED: 2,
        CandidateMethod.REWRITE_COMPRESSED: 3,
        CandidateMethod.DROP: 4,
    }
    candidates.sort(key=lambda candidate: (method_order[candidate.method], -candidate.token_cost))
    return CandidateSet(
        item=item,
        candidates=tuple(candidates),
        score=score,
        transformation_latency_ms=(time.perf_counter() - started) * 1000.0,
        warnings=tuple(warnings),
    )


__all__ = [
    "CandidateSet",
    "generate_candidates",
    "render_context_item",
    "rendered_token_count",
    "trusted_role",
]
