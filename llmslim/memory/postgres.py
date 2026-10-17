"""A Postgres store for :class:`llmslim.memory.Memory`, through psycopg 3.

``pip install "llmslim[postgres]"``. Works with any Postgres 12 or newer: self-hosted, Supabase, Neon, RDS, Cloud SQL,
Azure. ``Memory("postgresql://...")`` uses it, and so do ``llmslim serve --db postgresql://...`` and
``llmslim mcp --db postgresql://...``.
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from ._types import MemoryItem, Scope

__all__ = ["PostgresStore", "is_postgres_url"]

SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,50}$")
_COLUMNS = (
    "id",
    "seq",
    "role",
    "content",
    "created_at",
    "updated_at",
    "user_id",
    "agent_id",
    "run_id",
    "metadata",
)


def is_postgres_url(value: Any) -> bool:
    """Whether ``value`` is a Postgres connection URL (``postgresql://`` or ``postgres://``)."""
    return isinstance(value, str) and value.startswith(("postgresql://", "postgres://"))


def _missing_driver() -> ImportError:
    return ImportError('The Postgres memory store needs psycopg 3: pip install "llmslim[postgres]"')


class PostgresStore:
    """Turns in one Postgres table.

    Pass a connection URL (``postgresql://user:password@host:5432/db``), in which case the store opens its own
    connection pool and closes it in :meth:`close`; a ``psycopg_pool.ConnectionPool``; or a single
    ``psycopg.Connection`` in autocommit mode. The store is safe to use from several threads.

    The table (``llmslim_memory`` by default) and its ``<table>_meta`` table are created if they don't exist. Creation
    runs under an advisory lock, so several processes can start at once. The schema is versioned: a table written by
    a newer llmslim is refused rather than misread.

    Args:
        conninfo: A connection URL, a ``ConnectionPool`` or an autocommit ``Connection``.
        table: Table name: letters, digits and underscores. Use one per application or tenant if you like.
        max_size: Most connections in the pool the store opens for a URL.
    """

    def __init__(self, conninfo: Any, *, table: str = "llmslim_memory", max_size: int = 10) -> None:
        try:
            import psycopg
            from psycopg import sql
        except ImportError as error:  # pragma: no cover - exercised only without the extra
            raise _missing_driver() from error
        if not _IDENTIFIER.match(table):
            raise ValueError(
                "table must be letters, digits and underscores, starting with a letter or underscore"
            )
        self.table = table
        self._sql = sql
        self._psycopg = psycopg
        self._lock = threading.Lock()
        self._owned_pool: Any = None
        self._single: Any = None
        if isinstance(conninfo, str):
            try:
                from psycopg_pool import ConnectionPool
            except ImportError as error:  # pragma: no cover - exercised only without the extra
                raise _missing_driver() from error
            self._owned_pool = ConnectionPool(
                conninfo, min_size=1, max_size=max_size, kwargs={"autocommit": True}, open=True
            )
            self._pool: Any = self._owned_pool
        elif isinstance(conninfo, psycopg.Connection):
            if not conninfo.autocommit:
                raise ValueError(
                    "pass a Connection in autocommit mode: psycopg.connect(url, autocommit=True)"
                )
            self._single, self._pool = conninfo, None
        elif hasattr(conninfo, "connection"):
            self._pool = conninfo
        else:
            raise TypeError(
                "conninfo must be a postgresql:// URL, a psycopg_pool.ConnectionPool or a psycopg.Connection"
            )
        self._t = sql.Identifier(table)
        self._meta = sql.Identifier(f"{table}_meta")
        self._columns = sql.SQL(", ").join(sql.Identifier(column) for column in _COLUMNS)
        try:
            self._create_schema()
        except BaseException:
            self.close()
            raise

    # ------------------------------------------------------------------ connections

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self._single is not None:
            # One connection serves one statement at a time; the lock keeps transactions from interleaving.
            with self._lock:
                yield self._single
        else:
            with self._pool.connection() as conn:
                yield conn

    def close(self) -> None:
        """Close the pool the store opened for a URL. A pool or connection you passed in stays open."""
        if self._owned_pool is not None:
            self._owned_pool.close()

    def __enter__(self) -> "PostgresStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _create_schema(self) -> None:
        sql = self._sql
        with self._connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"llmslim:{self.table}",))
            conn.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {} (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                ).format(self._meta)
            )
            conn.execute(
                sql.SQL(
                    """CREATE TABLE IF NOT EXISTS {} (
                        id TEXT PRIMARY KEY,
                        seq BIGINT GENERATED ALWAYS AS IDENTITY,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ,
                        user_id TEXT,
                        agent_id TEXT,
                        run_id TEXT,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    )"""
                ).format(self._t)
            )
            for column in ("user_id", "agent_id", "run_id"):
                conn.execute(
                    sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} ({}, created_at, seq)").format(
                        sql.Identifier(f"{self.table}_{column}"), self._t, sql.Identifier(column)
                    )
                )
            row = conn.execute(
                sql.SQL("SELECT value FROM {} WHERE key = 'schema_version'").format(self._meta)
            ).fetchone()
            if row is None:
                conn.execute(
                    sql.SQL("INSERT INTO {} (key, value) VALUES ('schema_version', %s)").format(
                        self._meta
                    ),
                    (str(SCHEMA_VERSION),),
                )
            elif int(row[0]) > SCHEMA_VERSION:
                raise RuntimeError(
                    f"table {self.table} uses memory schema {row[0]}; this llmslim reads up to {SCHEMA_VERSION}. "
                    "Upgrade llmslim."
                )

    # ------------------------------------------------------------------ MemoryStore

    def add(self, items: Sequence[MemoryItem]) -> None:
        if not items:
            return
        from psycopg.types.json import Jsonb

        sql = self._sql
        insert = sql.SQL(
            "INSERT INTO {} (id, role, content, created_at, updated_at, user_id, agent_id, run_id, metadata) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ).format(self._t)
        rows = [
            (
                item.id,
                item.role,
                item.content,
                item.created_at,
                item.updated_at,
                item.user_id,
                item.agent_id,
                item.run_id,
                Jsonb(dict(item.metadata)),
            )
            for item in items
        ]
        try:
            with self._connection() as conn, conn.transaction(), conn.cursor() as cursor:
                # One row at a time, in order, so seq follows the order the turns were given in.
                for row in rows:
                    cursor.execute(insert, row)
        except self._psycopg.errors.UniqueViolation as error:
            raise ValueError("memory id already exists") from error

    def list(
        self, scope: Scope, *, since: Optional[datetime] = None, until: Optional[datetime] = None
    ) -> List[MemoryItem]:
        sql = self._sql
        where, params = self._scope_sql(scope)
        if since is not None:
            where.append(sql.SQL("created_at >= %s"))
            params.append(since)
        if until is not None:
            where.append(sql.SQL("created_at < %s"))
            params.append(until)
        query = sql.SQL("SELECT {} FROM {} WHERE {} ORDER BY created_at, seq").format(
            self._columns, self._t, sql.SQL(" AND ").join(where)
        )
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_item(row) for row in rows]

    def get(self, item_id: str) -> Optional[MemoryItem]:
        query = self._sql.SQL("SELECT {} FROM {} WHERE id = %s").format(self._columns, self._t)
        with self._connection() as conn:
            row = conn.execute(query, (item_id,)).fetchone()
        return _row_item(row) if row else None

    def update(
        self,
        item_id: str,
        *,
        content: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        from psycopg.types.json import Jsonb

        sql = self._sql
        sets = [sql.SQL("updated_at = %s")]
        params: List[Any] = [datetime.now(timezone.utc)]
        if content is not None:
            sets.append(sql.SQL("content = %s"))
            params.append(content)
        if metadata is not None:
            sets.append(sql.SQL("metadata = %s"))
            params.append(Jsonb(dict(metadata)))
        query = sql.SQL("UPDATE {} SET {} WHERE id = %s RETURNING {}").format(
            self._t, sql.SQL(", ").join(sets), self._columns
        )
        with self._connection() as conn:
            row = conn.execute(query, [*params, item_id]).fetchone()
        return _row_item(row) if row else None

    def delete(self, item_id: str) -> bool:
        query = self._sql.SQL("DELETE FROM {} WHERE id = %s").format(self._t)
        with self._connection() as conn:
            return conn.execute(query, (item_id,)).rowcount > 0

    def delete_scope(self, scope: Scope) -> int:
        where, params = self._scope_sql(scope)
        query = self._sql.SQL("DELETE FROM {} WHERE {}").format(
            self._t, self._sql.SQL(" AND ").join(where)
        )
        with self._connection() as conn:
            return conn.execute(query, params).rowcount

    def _scope_sql(self, scope: Scope) -> Tuple[List[Any], List[Any]]:
        clauses: List[Any] = []
        params: List[Any] = []
        for name in ("user_id", "agent_id", "run_id"):
            value = getattr(scope, name)
            if value is not None:
                clauses.append(self._sql.SQL("{} = %s").format(self._sql.Identifier(name)))
                params.append(value)
        return clauses, params


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    return value.astimezone(timezone.utc) if value is not None else None


def _row_item(row: Sequence[Any]) -> MemoryItem:
    metadata: Dict[str, Any] = row[9] or {}
    return MemoryItem(
        id=row[0],
        seq=row[1],
        role=row[2],
        content=row[3],
        created_at=_utc(row[4]),  # type: ignore[arg-type]
        updated_at=_utc(row[5]),
        user_id=row[6],
        agent_id=row[7],
        run_id=row[8],
        metadata=metadata,
    )
