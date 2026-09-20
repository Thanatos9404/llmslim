"""Shared context-source and explicit persistence abstractions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable

from .planning.models import ContextItem
from .planning.scoring import lexical_relevance


class ContextSourceError(RuntimeError):
    """A context source failed before producing an authoritative result set."""


@runtime_checkable
class ContextSource(Protocol):
    """Read-only retrieval boundary; sources never decide model-context priority."""

    source_id: str

    async def search(self, query: str, limit: int = 10) -> Sequence[ContextItem]:
        """Return bounded, provenance-bearing candidates."""


@runtime_checkable
class ContextStore(Protocol):
    """Explicit persistence boundary; planning never writes automatically."""

    async def save(self, item: ContextItem, namespace: str = "default") -> None:
        """Persist an explicitly approved context item."""

    async def get(self, item_id: str, namespace: str = "default") -> Optional[ContextItem]:
        """Return one item when present."""

    async def search(
        self, query: str, limit: int = 10, namespace: str = "default"
    ) -> Sequence[ContextItem]:
        """Retrieve bounded candidates from explicit persistent state."""

    async def delete(self, item_id: str, namespace: str = "default") -> bool:
        """Delete an explicitly addressed item and report whether it existed."""


@dataclass(frozen=True)
class ContextSourceFailure:
    source_id: str
    error_type: str


@dataclass(frozen=True)
class ContextSourceResult:
    items: Tuple[ContextItem, ...]
    failures: Tuple[ContextSourceFailure, ...] = ()


class InMemoryContextSource:
    """Deterministic local source useful for applications and tests."""

    def __init__(self, items: Sequence[ContextItem], source_id: str = "in-memory") -> None:
        self.source_id = source_id
        self._items = tuple(items)

    async def search(self, query: str, limit: int = 10) -> Sequence[ContextItem]:
        if not 1 <= limit <= 100:
            raise ValueError("context source limit must be between 1 and 100")
        ranked = sorted(
            self._items,
            key=lambda item: (
                -lexical_relevance(query, item.content),
                item.original_order,
                item.item_id,
            ),
        )
        return tuple(ranked[:limit])


class InMemoryContextStore:
    """Process-local explicit context store with no automatic ingestion."""

    def __init__(self) -> None:
        self._namespaces: Dict[str, Dict[str, ContextItem]] = {}
        # The protected operations are synchronous dictionary mutations with
        # no await points. A thread lock keeps them atomic without binding the
        # store to whichever event loop happened to exist at construction.
        self._lock = Lock()

    async def save(self, item: ContextItem, namespace: str = "default") -> None:
        if not namespace:
            raise ValueError("namespace must be non-empty")
        with self._lock:
            self._namespaces.setdefault(namespace, {})[item.item_id] = item

    async def get(self, item_id: str, namespace: str = "default") -> Optional[ContextItem]:
        with self._lock:
            return self._namespaces.get(namespace, {}).get(item_id)

    async def search(
        self, query: str, limit: int = 10, namespace: str = "default"
    ) -> Sequence[ContextItem]:
        if not 1 <= limit <= 100:
            raise ValueError("context store limit must be between 1 and 100")
        with self._lock:
            items = tuple(self._namespaces.get(namespace, {}).values())
        return await InMemoryContextSource(items, source_id="in-memory-store").search(query, limit)

    async def delete(self, item_id: str, namespace: str = "default") -> bool:
        with self._lock:
            values = self._namespaces.get(namespace, {})
            return values.pop(item_id, None) is not None


async def collect_context_sources(
    sources: Sequence[ContextSource],
    query: str,
    *,
    limit_per_source: int = 10,
    fail_open: bool = False,
) -> ContextSourceResult:
    """Collect sources concurrently while making every failure explicit.

    The default is fail-closed. ``fail_open=True`` is an explicit availability
    choice and returns source IDs plus exception class names, never exception
    messages that could contain credentials or customer data.
    """

    if not 1 <= limit_per_source <= 100:
        raise ValueError("limit_per_source must be between 1 and 100")
    outcomes = await asyncio.gather(
        *(source.search(query, limit_per_source) for source in sources),
        return_exceptions=True,
    )
    items: List[ContextItem] = []
    failures: List[ContextSourceFailure] = []
    for source, outcome in zip(sources, outcomes):
        if isinstance(outcome, BaseException):
            failure = ContextSourceFailure(source.source_id, type(outcome).__name__)
            failures.append(failure)
            if not fail_open:
                raise ContextSourceError(
                    f"context source '{source.source_id}' failed with {failure.error_type}"
                ) from None
            continue
        items.extend(outcome)
    return ContextSourceResult(tuple(items), tuple(failures))


__all__ = [
    "ContextSource",
    "ContextSourceError",
    "ContextSourceFailure",
    "ContextSourceResult",
    "ContextStore",
    "InMemoryContextSource",
    "InMemoryContextStore",
    "collect_context_sources",
]
