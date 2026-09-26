"""Small deterministic dependency graph over context item identities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Sequence, Set, Tuple

from .planning.models import ContextItem


class EdgeType(str, Enum):
    REPLIES_TO = "replies_to"
    REFERENCES = "references"
    SAME_ENTITY = "same_entity"
    SUPPORTS = "supports"
    DERIVED_FROM = "derived_from"
    TOOL_CALL_RESULT = "tool_call_result"
    MEMORY_SOURCE = "memory_source"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"


_DEPENDENCY_TYPES = {
    EdgeType.DEPENDS_ON,
    EdgeType.DERIVED_FROM,
    EdgeType.TOOL_CALL_RESULT,
    EdgeType.MEMORY_SOURCE,
}


@dataclass(frozen=True, order=True)
class ContextEdge:
    source_id: str
    target_id: str
    kind: EdgeType

    def to_dict(self) -> dict[str, str]:
        return {"source_id": self.source_id, "target_id": self.target_id, "kind": self.kind.value}


class ContextGraph:
    """Edges provide interpretation dependencies; they never grant trust or authority."""

    def __init__(self, item_ids: Iterable[str], edges: Iterable[ContextEdge] = ()) -> None:
        self.item_ids = frozenset(item_ids)
        if len(self.item_ids) > 512:
            raise ValueError("context graph exceeds the 512-node safety limit")
        unique = set(edges)
        if len(unique) > 4096:
            raise ValueError("context graph exceeds the 4096-edge safety limit")
        for edge in unique:
            if edge.source_id not in self.item_ids or edge.target_id not in self.item_ids:
                raise ValueError("context graph edge references an unknown item")
            if edge.source_id == edge.target_id:
                raise ValueError("context graph self edges are not allowed")
        self.edges: Tuple[ContextEdge, ...] = tuple(sorted(unique))
        dependencies: Dict[str, Set[str]] = {key: set() for key in self.item_ids}
        for edge in self.edges:
            if edge.kind in _DEPENDENCY_TYPES:
                dependencies[edge.source_id].add(edge.target_id)
        self._dependencies = dependencies

    @classmethod
    def from_items(cls, items: Sequence[ContextItem]) -> "ContextGraph":
        ids = {item.item_id for item in items}
        edges: Set[ContextEdge] = set()
        tool_calls: Dict[str, str] = {}
        entities: Dict[str, str] = {}
        for item in items:
            metadata: Mapping[str, Any] = item.metadata
            extra = metadata.get("message_extra")
            if isinstance(extra, Mapping):
                calls = extra.get("tool_calls", ())
                if isinstance(calls, (tuple, list)):
                    for call in calls[:32]:
                        if isinstance(call, Mapping) and isinstance(call.get("id"), str):
                            tool_calls[call["id"]] = item.item_id
                if item.kind.value == "assistant":
                    call_id = extra.get("call_id")
                    if isinstance(call_id, str):
                        tool_calls[call_id] = item.item_id
            entity_ids = metadata.get("entity_ids", ())
            if isinstance(entity_ids, (tuple, list)):
                for entity in entity_ids[:32]:
                    if not isinstance(entity, str) or not entity:
                        continue
                    prior = entities.setdefault(entity, item.item_id)
                    if prior != item.item_id:
                        edges.add(ContextEdge(item.item_id, prior, EdgeType.SAME_ENTITY))
            for field_name, kind in (
                ("depends_on", EdgeType.DEPENDS_ON),
                ("derived_from", EdgeType.DERIVED_FROM),
                ("reply_to", EdgeType.REPLIES_TO),
                ("memory_source_id", EdgeType.MEMORY_SOURCE),
            ):
                targets = metadata.get(field_name, ())
                if isinstance(targets, str):
                    targets = (targets,)
                if not isinstance(targets, (tuple, list)):
                    raise ValueError(f"{field_name} must contain item IDs")
                for target in targets:
                    if not isinstance(target, str) or target not in ids:
                        raise ValueError(f"{field_name} references an unknown item")
                    edges.add(ContextEdge(item.item_id, target, kind))
        for item in items:
            extra = item.metadata.get("message_extra", {})
            call_id = item.metadata.get("tool_call_id")
            if call_id is None and isinstance(extra, Mapping):
                call_id = extra.get("tool_call_id")
            if isinstance(call_id, str) and call_id in tool_calls:
                edges.add(ContextEdge(item.item_id, tool_calls[call_id], EdgeType.TOOL_CALL_RESULT))
        return cls(ids, edges)

    def dependencies(self, item_id: str) -> frozenset[str]:
        if item_id not in self.item_ids:
            raise KeyError(item_id)
        return frozenset(self._dependencies[item_id])

    def closure(self, selected_ids: Iterable[str]) -> frozenset[str]:
        found = set(selected_ids)
        if not found <= self.item_ids:
            raise ValueError("dependency closure contains unknown items")
        pending = list(found)
        while pending:
            for target in self._dependencies[pending.pop()]:
                if target not in found:
                    found.add(target)
                    pending.append(target)
        return frozenset(found)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": sorted(self.item_ids),
            "edges": [edge.to_dict() for edge in self.edges],
            "dependency_edges": sum(edge.kind in _DEPENDENCY_TYPES for edge in self.edges),
        }
