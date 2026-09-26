"""Named quality gates for a selected context representation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

from .context_graph import ContextGraph
from .core import ContextRole
from .planning.models import CandidateMethod, ContextCandidate, ContextItem, ContextKind
from .planning.scoring import lexical_relevance

_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")


@dataclass(frozen=True)
class QualityReport:
    passed: bool
    quality_floor: float
    metrics: Mapping[str, float]
    failures: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "quality_floor": self.quality_floor,
            "metrics": dict(self.metrics),
            "failures": list(self.failures),
        }


def assess_quality(
    items: Sequence[ContextItem],
    selected: Sequence[ContextCandidate],
    graph: ContextGraph,
    quality_floor: float,
    query: str = "",
) -> QualityReport:
    by_id = {candidate.item_id: candidate for candidate in selected}
    alive = {key for key, candidate in by_id.items() if candidate.method is not CandidateMethod.DROP}
    failures = []
    trusted = []
    required = []
    numbers = []
    entities = []
    similarities = []
    structure = []
    for item in items:
        candidate = by_id[item.item_id]
        is_alive = candidate.method is not CandidateMethod.DROP
        if item.role in {ContextRole.SYSTEM, ContextRole.DEVELOPER}:
            trusted.append(float(is_alive and candidate.content == item.content))
        required_terms = item.metadata.get("required_keywords", ())
        if isinstance(required_terms, str):
            required_terms = (required_terms,)
        if item.required or required_terms:
            terms = required_terms if isinstance(required_terms, (tuple, list)) else ()
            required.append(
                float(is_alive and all(str(term) in candidate.content for term in terms))
            )
        if is_alive:
            source_numbers = set(_NUMBER_RE.findall(item.content))
            if source_numbers:
                numbers.append(float(source_numbers <= set(_NUMBER_RE.findall(candidate.content))))
            value = candidate.validation.get("entity_retention")
            if isinstance(value, (int, float)):
                entities.append(float(value))
            similarity = candidate.validation.get("similarity")
            if isinstance(similarity, (int, float)):
                similarities.append(float(similarity))
            structure.append(float(bool(candidate.validation.get("passed", True))))
    dependencies = float(graph.closure(alive) == alive)
    tool_contract = float(
        all(
            by_id[item.item_id].method is CandidateMethod.RAW
            for item in items
            if item.kind is ContextKind.TOOL_SCHEMA and item.item_id in alive
        )
    )
    current_user = [item for item in items if item.kind is ContextKind.USER and item.required]
    coherence = float(all(item.item_id in alive for item in current_user))
    original_relevance = max(
        (lexical_relevance(query, item.content) for item in items if not item.required),
        default=0.0,
    )
    selected_relevance = max(
        (lexical_relevance(query, by_id[item.item_id].content)
         for item in items if not item.required and item.item_id in alive),
        default=0.0,
    )
    relevance_retention = (
        min(1.0, selected_relevance / original_relevance) if original_relevance else 1.0
    )
    metrics = {
        "trusted_instruction_retention": min(trusted, default=1.0),
        "required_fact_retention": min(required, default=1.0),
        "numerical_fact_retention": min(numbers, default=1.0),
        "entity_retention": min(entities, default=1.0),
        "semantic_similarity": min(similarities, default=1.0),
        "conversation_coherence": coherence,
        "structural_validity": min(structure, default=1.0),
        "dependency_integrity": dependencies,
        "tool_contract_integrity": tool_contract,
        "query_relevance_retention": relevance_retention,
    }
    for name, value in metrics.items():
        if name != "query_relevance_retention" and value < quality_floor:
            failures.append(f"{name} below quality floor")
    return QualityReport(not failures, quality_floor, metrics, tuple(failures))
