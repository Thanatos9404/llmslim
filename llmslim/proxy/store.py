"""The proxy's memory of what it compressed: one SQLite file, so later requests replay the same bytes.

Losing this file mid-session would make the proxy send an earlier tool output uncompressed while the model's later
turns were produced against the compressed version. So entries are kept for ``keep_days`` after their last use, not
pruned by size.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from .rewrite import RewriteReport

__all__ = ["ProxyStore"]

SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProxyStore:
    """First-sight decisions and per-request savings, in SQLite. Safe across threads in one process."""

    def __init__(self, path: Union[str, Path] = ":memory:", *, keep_days: int = 30) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS proxy_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proxy_blocks (
                    key TEXT PRIMARY KEY,
                    tool TEXT NOT NULL,
                    tokens_before INTEGER NOT NULL,
                    tokens_after INTEGER NOT NULL,
                    compressed TEXT NOT NULL,
                    original TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    used_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proxy_requests (
                    at TEXT NOT NULL,
                    compressed INTEGER NOT NULL,
                    replayed INTEGER NOT NULL,
                    tokens_before INTEGER NOT NULL,
                    tokens_after INTEGER NOT NULL
                );
                """
            )
            row = self._conn.execute(
                "SELECT value FROM proxy_meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO proxy_meta (key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            elif int(row[0]) > SCHEMA_VERSION:
                self._conn.close()
                raise RuntimeError(
                    f"{self.path} was written by a newer llmslim; upgrade llmslim to use it"
                )
            cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
            self._conn.execute("DELETE FROM proxy_blocks WHERE used_at < ?", (cutoff,))

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ BlockCache

    def get(self, key: str) -> Optional[Tuple[str, int, int]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT compressed, tokens_before, tokens_after FROM proxy_blocks WHERE key = ?",
                (key,),
            ).fetchone()
            if row is not None:
                self._conn.execute(
                    "UPDATE proxy_blocks SET used_at = ? WHERE key = ?", (_now(), key)
                )
        return (row[0], row[1], row[2]) if row else None

    def put(
        self, key: str, *, tool: str, original: str, compressed: str, before: int, after: int
    ) -> None:
        now = _now()
        with self._lock:
            # First decision wins: a concurrent request for the same block must not change bytes already sent.
            self._conn.execute(
                "INSERT OR IGNORE INTO proxy_blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (key, tool, before, after, compressed, original, now, now),
            )

    def original(self, key: str) -> Optional[str]:
        """The full output behind a compressed block."""
        with self._lock:
            row = self._conn.execute(
                "SELECT original FROM proxy_blocks WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------------ savings

    def record(self, report: RewriteReport) -> None:
        if not report.changed:
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO proxy_requests VALUES (?, ?, ?, ?, ?)",
                (
                    _now(),
                    report.compressed,
                    report.replayed,
                    report.tokens_before,
                    report.tokens_after,
                ),
            )

    def stats(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Totals over the requests the proxy changed (since ``since``, if given)."""
        where, params = (
            ("WHERE at >= ?", (since.astimezone(timezone.utc).isoformat(),)) if since else ("", ())
        )
        with self._lock:
            requests, compressed, replayed, before, after = self._conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(compressed), 0), COALESCE(SUM(replayed), 0), "
                f"COALESCE(SUM(tokens_before), 0), COALESCE(SUM(tokens_after), 0) FROM proxy_requests {where}",
                params,
            ).fetchone()
            blocks = self._conn.execute("SELECT COUNT(*) FROM proxy_blocks").fetchone()[0]
        return {
            "requests_changed": requests,
            "outputs_compressed": compressed,
            "outputs_replayed": replayed,
            "tokens_before": before,
            "tokens_after": after,
            "tokens_saved": before - after,
            "blocks_stored": blocks,
        }
