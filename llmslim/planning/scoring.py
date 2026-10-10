"""Deterministic, interpretable utility scoring for context items."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, FrozenSet, Optional, Set

from ..analysis import analyze
from ..core import ContextRole
from .models import CandidateMethod, ContextItem, ContextKind
from .policy import PlannerPolicy

_TERM_RE = re.compile(r"[^\W_]+", re.UNICODE)

_PROVENANCE_SIGNAL: Dict[ContextRole, float] = {
    ContextRole.SYSTEM: 1.00,
    ContextRole.DEVELOPER: 0.96,
    ContextRole.USER: 0.78,
    ContextRole.TOOL: 0.58,
    ContextRole.ASSISTANT: 0.52,
    ContextRole.RAG: 0.46,
    ContextRole.GENERAL: 0.44,
}

_KIND_SIGNAL: Dict[ContextKind, float] = {
    ContextKind.SYSTEM: 1.00,
    ContextKind.DEVELOPER: 0.96,
    ContextKind.USER: 0.82,
    ContextKind.TOOL_SCHEMA: 0.78,
    ContextKind.TOOL_RESULT: 0.60,
    ContextKind.MEMORY: 0.58,
    ContextKind.RAG_DOCUMENT: 0.54,
    ContextKind.ASSISTANT: 0.50,
    ContextKind.GENERAL: 0.46,
}

# Imperative wording is a value signal only for trusted or semi-trusted
# instructions. In retrieved/tool/assistant content it is at best neutral and
# at worst an indirect prompt-injection payload, so it never raises the value
# of untrusted evidence (mirrors the untrusted priority cap in ranking.py).
_UNTRUSTED_INSTRUCTION_ROLES: FrozenSet[ContextRole] = frozenset(
    {ContextRole.RAG, ContextRole.TOOL, ContextRole.ASSISTANT}
)

# Retrieved evidence kinds whose caller metadata may mark them superseded.
_SUPERSEDABLE_KINDS: FrozenSet[ContextKind] = frozenset(
    {ContextKind.RAG_DOCUMENT, ContextKind.MEMORY, ContextKind.TOOL_RESULT}
)

#: Multiplier applied to the value of evidence the caller marked superseded
#: (``metadata["superseded"]``/``metadata["superseded_by"]``) or whose
#: ``metadata["valid_until"]`` has passed. Superseded evidence is still kept
#: when the budget allows, but it is the first optional evidence to go.
SUPERSEDED_VALUE_FACTOR = 0.05

_TRUE_STRINGS = frozenset({"true", "yes", "1"})

_METHOD_RISK: Dict[CandidateMethod, float] = {
    CandidateMethod.RAW: 0.0,
    CandidateMethod.EXTRACTIVE_COMPRESSED: 0.16,
    CandidateMethod.HYBRID_COMPRESSED: 0.24,
    CandidateMethod.REWRITE_COMPRESSED: 0.30,
    CandidateMethod.DROP: 1.0,
}


def lexical_terms(text: str) -> Set[str]:
    return {
        match.group(0).casefold() for match in _TERM_RE.finditer(text) if len(match.group(0)) > 1
    }


def lexical_relevance(query: str, content: str) -> float:
    """Return a bounded query/content overlap score without opaque model calls."""

    query_terms = lexical_terms(query)
    if not query_terms:
        return 0.5
    content_terms = lexical_terms(content)
    if not content_terms:
        return 0.0
    overlap = len(query_terms & content_terms)
    recall = overlap / len(query_terms)
    precision = overlap / min(len(content_terms), max(len(query_terms) * 4, 1))
    phrase_bonus = 0.15 if query.casefold() in content.casefold() else 0.0
    return min(1.0, 0.72 * recall + 0.28 * min(1.0, precision) + phrase_bonus)


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in _TRUE_STRINGS
    return False


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 string, ``datetime`` or ``date`` as an aware UTC instant.

    Naive values are interpreted as UTC. Returns ``None`` for unparseable values.
    """

    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, date):
        stamp = datetime(value.year, value.month, value.day)
    elif isinstance(value, str) and value.strip():
        try:
            # Python 3.9/3.10 fromisoformat() does not accept a trailing "Z".
            stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def supersession_reason(item: ContextItem, now: Optional[datetime] = None) -> Optional[str]:
    """Return why caller metadata marks retrieved evidence as superseded, else ``None``.

    Recognised metadata on documents, memories and tool results:

    - ``superseded``: truthy (``True``, non-zero, ``"true"``/``"yes"``/``"1"``);
    - ``superseded_by``: any non-empty value (for example the replacing document ID);
    - ``valid_until``: an ISO-8601 timestamp/date at or before ``now`` (UTC).

    Unparseable ``valid_until`` values are ignored, not treated as expired.
    """

    if item.kind not in _SUPERSEDABLE_KINDS:
        return None
    metadata = item.metadata
    if _flag(metadata.get("superseded")):
        return "metadata.superseded is set"
    superseded_by = metadata.get("superseded_by")
    if superseded_by not in (None, "", False):
        return f"metadata.superseded_by={superseded_by}"
    expiry = parse_timestamp(metadata.get("valid_until"))
    if expiry is not None:
        instant = now if now is not None else datetime.now(timezone.utc)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        if expiry <= instant:
            return "metadata.valid_until has passed"
    return None


@dataclass(frozen=True)
class ScoreBreakdown:
    relevance: float
    recency: float
    provenance: float
    density: float
    priority: float
    kind: float
    required_bonus: float
    total: float
    #: 1.0 for current content; ``SUPERSEDED_VALUE_FACTOR`` for superseded evidence.
    freshness: float = 1.0

    @property
    def superseded(self) -> bool:
        return self.freshness < 1.0

    def to_dict(self) -> Dict[str, float]:
        return {key: round(value, 6) for key, value in self.__dict__.items()}


def score_item(
    item: ContextItem,
    query: str,
    policy: PlannerPolicy,
    *,
    now: Optional[datetime] = None,
) -> ScoreBreakdown:
    """Score one logical item using named, testable components.

    - Instruction density only adds value for trusted/semi-trusted roles;
      imperative wording in RAG, tool or assistant content never raises its
      value (it may be a prompt-injection payload).
    - Retrieved evidence that caller metadata marks superseded (see
      :func:`supersession_reason`) has its total multiplied by
      :data:`SUPERSEDED_VALUE_FACTOR`, so it is dropped before current evidence
      under budget pressure. ``now`` defaults to the current UTC time.
    """

    profile = analyze(item.content)
    relevance = (
        item.relevance if item.relevance is not None else lexical_relevance(query, item.content)
    )
    provenance = _PROVENANCE_SIGNAL[item.role]
    kind = _KIND_SIGNAL[item.kind]
    instruction_density = (
        0.0 if item.role in _UNTRUSTED_INSTRUCTION_ROLES else profile.instruction_density
    )
    density = min(1.0, 0.58 * instruction_density + 0.42 * profile.entity_density)
    priority = 1.0 / (1.0 + math.exp(-item.priority / 2.0))
    required_bonus = 5.0 if item.required else 0.0
    weighted = (
        policy.relevance_weight * relevance
        + policy.recency_weight * item.recency
        + policy.provenance_weight * provenance
        + policy.density_weight * density
        + policy.priority_weight * priority
    )
    # Kind is a small tie-breaking signal rather than a hidden allocation quota.
    total = 100.0 * (0.90 * weighted + 0.10 * kind) + required_bonus
    freshness = SUPERSEDED_VALUE_FACTOR if supersession_reason(item, now) is not None else 1.0
    total *= freshness
    return ScoreBreakdown(
        relevance=relevance,
        recency=item.recency,
        provenance=provenance,
        density=density,
        priority=priority,
        kind=kind,
        required_bonus=required_bonus,
        total=total,
        freshness=freshness,
    )


def candidate_utility(
    base: ScoreBreakdown,
    method: CandidateMethod,
    retention_ratio: float,
    policy: PlannerPolicy,
) -> tuple[float, float]:
    """Convert item value into representation value and explicit risk."""

    risk = min(1.0, _METHOD_RISK[method] + max(0.0, 1.0 - retention_ratio) * 0.22)
    if method is CandidateMethod.DROP:
        return 0.0, risk
    # Diminishing loss: retaining half the tokens normally retains more than
    # half the item's useful evidence, but raw remains strictly preferred.
    retention_value = retention_ratio**0.62
    if method is CandidateMethod.RAW:
        retention_value = 1.0
    utility = base.total * retention_value * (1.0 - policy.risk_penalty * risk)
    return max(0.0, utility), risk


def method_safety_order(method: CandidateMethod) -> int:
    """Higher values are safer fallbacks when validation is uncertain."""

    order = {
        CandidateMethod.DROP: 0,
        CandidateMethod.REWRITE_COMPRESSED: 1,
        CandidateMethod.HYBRID_COMPRESSED: 2,
        CandidateMethod.EXTRACTIVE_COMPRESSED: 3,
        CandidateMethod.RAW: 4,
    }
    return order[method]


__all__ = [
    "SUPERSEDED_VALUE_FACTOR",
    "ScoreBreakdown",
    "candidate_utility",
    "lexical_relevance",
    "lexical_terms",
    "method_safety_order",
    "parse_timestamp",
    "score_item",
    "supersession_reason",
]
