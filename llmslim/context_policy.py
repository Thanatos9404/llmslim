"""Caller-owned local context rules applied before optimization."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable, FrozenSet, Optional, Sequence, Tuple

from .core import ContextRole
from .planning.candidates import rendered_token_count
from .planning.models import ContextItem, ContextKind
from .planning.scoring import lexical_relevance

Redactor = Callable[[ContextItem], str]


@dataclass(frozen=True)
class ContextPolicy:
    never_drop_roles: FrozenSet[ContextRole] = field(
        default_factory=lambda: frozenset({ContextRole.SYSTEM, ContextRole.DEVELOPER})
    )
    max_memory_tokens: Optional[int] = None
    max_rag_tokens: Optional[int] = None
    stale_tool_result_seconds: Optional[int] = None
    allowed_sources: Optional[FrozenSet[str]] = None
    denied_sources: FrozenSet[str] = field(default_factory=frozenset)
    redactor: Optional[Redactor] = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if any(
            value is not None and value < 0
            for value in (self.max_memory_tokens, self.max_rag_tokens, self.stale_tool_result_seconds)
        ):
            raise ValueError("context policy limits must be non-negative")
        if not {ContextRole.SYSTEM, ContextRole.DEVELOPER} <= self.never_drop_roles:
            raise ValueError("trusted instruction roles must remain mandatory")

    def apply(
        self, items: Sequence[ContextItem], query: str, *, now: Optional[datetime] = None
    ) -> Tuple[Tuple[ContextItem, ...], Tuple[str, ...]]:
        """Return retained items and safe decision reasons. Mandatory items fail closed."""
        instant = now or datetime.now(timezone.utc)
        retained = []
        excluded = []
        for item in items:
            reason = None
            if item.kind in {ContextKind.MEMORY, ContextKind.RAG_DOCUMENT, ContextKind.TOOL_RESULT}:
                if self.allowed_sources is not None and item.source not in self.allowed_sources:
                    reason = "source is outside the caller allowlist"
                elif item.source in self.denied_sources:
                    reason = "source is on the caller denylist"
            if item.kind is ContextKind.TOOL_RESULT and self.stale_tool_result_seconds is not None:
                stamp = item.metadata.get("created_at")
                if isinstance(stamp, str):
                    try:
                        timestamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                        age = (instant - timestamp.astimezone(timezone.utc)).total_seconds()
                        if age > self.stale_tool_result_seconds:
                            reason = "tool result exceeded the caller freshness limit"
                    except ValueError:
                        reason = "tool result has an invalid timestamp"
            if reason:
                if item.required or item.role in self.never_drop_roles:
                    raise ValueError("context policy conflicts with mandatory context")
                excluded.append(f"{item.item_id}: {reason}")
                continue
            if self.redactor is not None and item.role not in self.never_drop_roles:
                redacted = self.redactor(item)
                if not isinstance(redacted, str):
                    raise TypeError("context policy redactor must return text")
                if redacted != item.content:
                    item = replace(item, content=redacted)
                    item = replace(item, token_count=rendered_token_count(item, redacted))
            retained.append(item)

        for kind, cap in (
            (ContextKind.MEMORY, self.max_memory_tokens),
            (ContextKind.RAG_DOCUMENT, self.max_rag_tokens),
        ):
            if cap is None:
                continue
            category = [item for item in retained if item.kind is kind]
            ranked = sorted(
                category,
                key=lambda item: (
                    -int(item.required),
                    -lexical_relevance(query, item.content),
                    -item.priority,
                    item.original_order,
                    item.item_id,
                ),
            )
            total = 0
            keep_ids = set()
            for item in ranked:
                if total + item.token_count <= cap:
                    keep_ids.add(item.item_id)
                    total += item.token_count
                elif item.required:
                    raise ValueError("mandatory context exceeds a category token cap")
                else:
                    excluded.append(f"{item.item_id}: {kind.value} token cap")
            retained = [
                item for item in retained if item.kind is not kind or item.item_id in keep_ids
            ]
        return tuple(retained), tuple(excluded)
