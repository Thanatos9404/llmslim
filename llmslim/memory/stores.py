"""Where :class:`llmslim.memory.Memory` keeps turns.

A store only persists and lists turns; it never ranks, summarizes or calls a model. Two ship with Core:

* :class:`InMemoryStore`: a process-local list, for tests and short-lived agents.
* :class:`SQLiteStore`: one SQLite file (Python's built-in ``sqlite3``, no extra dependency). The default when
  :class:`~llmslim.memory.Memory` is given a path.

Any object with the :class:`MemoryStore` methods works, so other databases can be added without touching selection;
:class:`~llmslim.memory.PostgresStore` and :class:`~llmslim.memory.MongoStore` are two.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
    runtime_checkable,
)

from ._types import MemoryItem, Scope

__all__ = ["InMemoryStore", "MemoryStore", "SQLiteStore"]

SCHEMA_VERSION = 1


@runtime_checkable
class MemoryStore(Protocol):
    """Persistence for memory turns. Implementations must be safe to call from several threads."""

    def add(self, items: Sequence[MemoryItem]) -> None:
        """Store new turns. Their ``id`` values are new; their ``seq`` values are ignored and assigned by the store."""

    def list(
        self, scope: Scope, *, since: Optional[datetime] = None, until: Optional[datetime] = None
    ) -> List[MemoryItem]:
        """Turns in ``scope`` with ``since <= created_at < until``, oldest first (ties in the order they were added)."""

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """One turn by id, or ``None``."""

    def update(
        self,
        item_id: str,
        *,
        content: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        """Replace a turn's content and/or metadata; return the updated turn, or ``None`` if there is no such id."""

    def delete(self, item_id: str) -> bool:
        """Delete one turn; return whether it existed."""

    def delete_scope(self, scope: Scope) -> int:
        """Delete every turn in ``scope``; return how many were deleted."""


def _in_window(item: MemoryItem, since: Optional[datetime], until: Optional[datetime]) -> bool:
    return (since is None or item.created_at >= since) and (
        until is None or item.created_at < until
    )


class InMemoryStore:
    """Turns in a list in this process. Nothing survives a restart."""

    def __init__(self) -> None:
        self._items: Dict[str, MemoryItem] = {}
        self._seq = 0
        self._lock = threading.Lock()

    def add(self, items: Sequence[MemoryItem]) -> None:
        with self._lock:
            for item in items:
                if item.id in self._items:
                    raise ValueError(f"memory id already exists: {item.id}")
                self._seq += 1
                self._items[item.id] = replace(item, seq=self._seq)

    def list(
        self, scope: Scope, *, since: Optional[datetime] = None, until: Optional[datetime] = None
    ) -> List[MemoryItem]:
        with self._lock:
            found = [
                item
                for item in self._items.values()
                if scope.matches(item.user_id, item.agent_id, item.run_id)
                and _in_window(item, since, until)
            ]
        return sorted(found, key=lambda item: (item.created_at, item.seq))

    def get(self, item_id: str) -> Optional[MemoryItem]:
        with self._lock:
            return self._items.get(item_id)

    def update(
        self,
        item_id: str,
        *,
        content: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                return None
            changes: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
            if content is not None:
                changes["content"] = content
            if metadata is not None:
                changes["metadata"] = metadata
            self._items[item_id] = updated = replace(item, **changes)
            return updated

    def delete(self, item_id: str) -> bool:
        with self._lock:
            return self._items.pop(item_id, None) is not None

    def delete_scope(self, scope: Scope) -> int:
        with self._lock:
            doomed = [
                key
                for key, item in self._items.items()
                if scope.matches(item.user_id, item.agent_id, item.run_id)
            ]
            for key in doomed:
                del self._items[key]
            return len(doomed)


_COLUMNS = "id, seq, role, content, created_at, updated_at, user_id, agent_id, run_id, metadata"


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def _row_item(row: Sequence[Any]) -> MemoryItem:
    return MemoryItem(
        id=row[0],
        seq=row[1],
        role=row[2],
        content=row[3],
        created_at=datetime.fromisoformat(row[4]),
        updated_at=datetime.fromisoformat(row[5]) if row[5] else None,
        user_id=row[6],
        agent_id=row[7],
        run_id=row[8],
        metadata=json.loads(row[9]),
    )


def _scope_sql(scope: Scope) -> Tuple[str, List[Any]]:
    clauses, params = [], []
    for name in ("user_id", "agent_id", "run_id"):
        value = getattr(scope, name)
        if value is not None:
            clauses.append(f"{name} = ?")
            params.append(value)
    return " AND ".join(clauses), params


class SQLiteStore:
    """Turns in one SQLite file, through Python's built-in ``sqlite3``.

    Pass a file path, or ``":memory:"`` for a private in-memory database. One connection is shared behind a lock, so
    the store is safe to use from several threads in one process. Timestamps are stored as UTC ISO-8601 text, which
    sorts in time order. The schema is versioned in ``llmslim_meta``; a file written by a newer schema is refused rather
    than misread.
    """

    def __init__(self, path: Union[str, Path] = "llmslim_memory.db") -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")  # readers do not block the writer
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS llmslim_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS llmslim_memory (
                    id TEXT PRIMARY KEY,
                    seq INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    user_id TEXT,
                    agent_id TEXT,
                    run_id TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS llmslim_memory_scope
                    ON llmslim_memory (user_id, agent_id, run_id, created_at, seq);
                """
            )
            row = self._conn.execute(
                "SELECT value FROM llmslim_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO llmslim_meta (key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            elif int(row[0]) > SCHEMA_VERSION:
                self._conn.close()
                raise RuntimeError(
                    f"{self.path} uses memory schema {row[0]}; this llmslim reads up to {SCHEMA_VERSION}. Upgrade llmslim."
                )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def add(self, items: Sequence[MemoryItem]) -> None:
        if not items:
            return
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                (start,) = self._conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) FROM llmslim_memory"
                ).fetchone()
                self._conn.executemany(
                    f"INSERT INTO llmslim_memory ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            item.id,
                            start + offset,
                            item.role,
                            item.content,
                            _iso(item.created_at),
                            _iso(item.updated_at),
                            item.user_id,
                            item.agent_id,
                            item.run_id,
                            json.dumps(dict(item.metadata), ensure_ascii=False, sort_keys=True),
                        )
                        for offset, item in enumerate(items, start=1)
                    ],
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def list(
        self, scope: Scope, *, since: Optional[datetime] = None, until: Optional[datetime] = None
    ) -> List[MemoryItem]:
        where, params = _scope_sql(scope)
        if since is not None:
            where += " AND created_at >= ?"
            params.append(_iso(since))
        if until is not None:
            where += " AND created_at < ?"
            params.append(_iso(until))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_COLUMNS} FROM llmslim_memory WHERE {where} ORDER BY created_at, seq",
                params,
            ).fetchall()
        return [_row_item(row) for row in rows]

    def get(self, item_id: str) -> Optional[MemoryItem]:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM llmslim_memory WHERE id = ?", (item_id,)
            ).fetchone()
        return _row_item(row) if row else None

    def update(
        self,
        item_id: str,
        *,
        content: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        sets, params = ["updated_at = ?"], [_iso(datetime.now(timezone.utc))]
        if content is not None:
            sets.append("content = ?")
            params.append(content)
        if metadata is not None:
            sets.append("metadata = ?")
            params.append(json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True))
        with self._lock:
            cursor = self._conn.execute(
                f"UPDATE llmslim_memory SET {', '.join(sets)} WHERE id = ?", [*params, item_id]
            )
            if cursor.rowcount == 0:
                return None
        return self.get(item_id)

    def delete(self, item_id: str) -> bool:
        with self._lock:
            return (
                self._conn.execute("DELETE FROM llmslim_memory WHERE id = ?", (item_id,)).rowcount
                > 0
            )

    def delete_scope(self, scope: Scope) -> int:
        where, params = _scope_sql(scope)
        with self._lock:
            return self._conn.execute(f"DELETE FROM llmslim_memory WHERE {where}", params).rowcount
