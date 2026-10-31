"""Bring chat history into :class:`llmslim.memory.Memory`: :func:`import_history`, behind ``llmslim import``."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

from ._core import Memory, storage_target
from ._import_sources import READERS, RawSession, Tally, detect, parse_time
from ._import_types import (
    FORMAT_NAMES,
    FORMATS,
    HistoryImportError,
    ImportedSession,
    ImportLimits,
    ImportReport,
)
from ._redact import redact as redact_text
from ._types import MemoryItem, Scope
from .postgres import PostgresStore, is_postgres_url
from .stores import MemoryStore, SQLiteStore

DEFAULT_USER = "default"  # the user ``llmslim mcp`` serves when none is named
_ID_VERSION = "llmslim-import/1"
_BATCH = 500

Lookup = Callable[[List[str]], Set[str]]
Writer = Callable[[List[MemoryItem]], None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _item_id(fmt: str, user_id: str, agent_id: Optional[str], parts: Iterable[str]) -> str:
    """A turn id derived from where it came from, so importing the same history again finds the same ids. The scope
    is part of it: the same file imported for two users gives two sets of turns."""
    text = "\x1f".join((_ID_VERSION, fmt, user_id, agent_id or "", *parts))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _content_digest(role: str, raw_time: str, text: str) -> str:
    return hashlib.sha256("\x1f".join((role, raw_time, text)).encode("utf-8")).hexdigest()


def _bound(value: Any, name: str) -> Optional[datetime]:
    if value is None:
        return None
    moment = parse_time(value)
    if moment is None:
        raise ValueError(
            f"{name} must be a datetime, epoch seconds or ISO-8601 text such as 2025-01-31, not {value!r}"
        )
    return moment


def _times(session: RawSession, now: datetime) -> List[datetime]:
    """Each turn's time. A turn without one takes the time of the turn before it in its session (so the order holds);
    leading ones take the session's start or its first known time; a session with no time at all takes ``now``."""
    known = [turn.time for turn in session.turns]
    first = next((moment for moment in known if moment is not None), None)
    if first is not None and session.start is not None:
        lead = min(first, session.start)
    else:
        lead = first or session.start or now
    out: List[datetime] = []
    last: Optional[datetime] = None
    for moment in known:
        if moment is not None:
            last = moment
        out.append(last or lead)
    return out


# --------------------------------------------------------------------------- where the turns go


def _nothing() -> None:
    return None


def _nothing_stored(ids: List[str]) -> Set[str]:
    return set()


def _store_lookup(store: MemoryStore) -> Lookup:
    def lookup(ids: List[str]) -> Set[str]:
        return {item_id for item_id in ids if store.get(item_id) is not None}

    return lookup


def _read_only_lookup(path: Path) -> Tuple[Lookup, Callable[[], None]]:
    """Which ids a SQLite memory file already holds, read without writing anything (for a dry run).

    A file no other process has open is read as immutable, which creates no ``-wal`` or ``-shm`` file beside it. One
    in use (``llmslim mcp`` running, say) already has them, and is read normally so its latest writes are seen."""
    in_use = path.with_name(path.name + "-wal").exists()
    options = "mode=ro" if in_use else "mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?{options}", uri=True)
    except sqlite3.Error as error:
        raise HistoryImportError(f"can't open {path} read-only: {error}") from error

    def lookup(ids: List[str]) -> Set[str]:
        found: Set[str] = set()
        try:
            for start in range(0, len(ids), _BATCH):
                chunk = ids[start : start + _BATCH]
                marks = ", ".join("?" for _ in chunk)
                rows = conn.execute(
                    f"SELECT id FROM llmslim_memory WHERE id IN ({marks})", chunk
                ).fetchall()
                found.update(row[0] for row in rows)
        except sqlite3.Error as error:
            raise HistoryImportError(f"can't read {path} as an LLMSlim memory: {error}") from error
        return found

    return lookup, conn.close


def _target(
    memory: Union[Memory, MemoryStore, str, os.PathLike[str], None], dry_run: bool
) -> Tuple[Lookup, Optional[Writer], Callable[[], None]]:
    """How to check for turns already stored, how to store new ones (None in a dry run) and how to close what was
    opened here."""
    nothing = _nothing
    empty = _nothing_stored

    if memory is None:
        if not dry_run:
            raise ValueError("memory is required unless dry_run=True")
        return empty, None, nothing
    if isinstance(memory, Memory):
        store: Any = memory.store
        return _store_lookup(store), (None if dry_run else store.add), nothing
    if isinstance(memory, (str, os.PathLike)):
        target = os.fspath(memory)
        if is_postgres_url(target):
            store = PostgresStore(target)
            return _store_lookup(store), (None if dry_run else store.add), store.close
        path = Path(target).expanduser()
        if dry_run:
            if not path.exists():
                return empty, None, nothing  # nothing stored yet, and a dry run creates nothing
            lookup, close = _read_only_lookup(path)
            return lookup, None, close
        store = SQLiteStore(storage_target(target))
        return _store_lookup(store), store.add, store.close
    if all(hasattr(memory, name) for name in ("add", "get", "list")):
        return _store_lookup(memory), (None if dry_run else memory.add), nothing
    raise TypeError(
        "memory must be a Memory, a MemoryStore, a SQLite path or a postgresql:// URL, "
        f"not {type(memory).__name__}"
    )


def _write(write: Writer, lookup: Lookup, items: List[MemoryItem]) -> Tuple[List[MemoryItem], int]:
    """Store ``items`` in batches. Returns what was stored and how many turns turned out to be there already (another
    import running at the same time)."""
    stored: List[MemoryItem] = []
    raced = 0
    for start in range(0, len(items), _BATCH):
        batch = items[start : start + _BATCH]
        try:
            write(batch)
            stored.extend(batch)
            continue
        except (
            Exception
        ):  # a duplicate id from a concurrent import, or a real failure: retry one by one
            pass
        for item in batch:
            try:
                write([item])
                stored.append(item)
            except Exception as error:
                if lookup([item.id]):
                    raced += 1
                    continue
                raise HistoryImportError(f"could not store an imported turn: {error}") from error
    return stored, raced


# --------------------------------------------------------------------------- the import


def import_history(
    source: Union[str, os.PathLike[str]],
    memory: Union[Memory, MemoryStore, str, os.PathLike[str], None],
    *,
    format: str = "auto",
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    since: Any = None,
    until: Any = None,
    limit: Optional[int] = None,
    include_tool_output: bool = False,
    dry_run: bool = False,
    strict: bool = False,
    redact: bool = True,
    limits: Optional[ImportLimits] = None,
    on_session: Optional[Callable[[ImportedSession], None]] = None,
) -> ImportReport:
    """Import chat history from another tool into memory, verbatim, as ``llmslim import`` does.

    Reads Claude Code transcripts (``~/.claude/projects``), a ChatGPT or Claude.ai data export (the zip as
    downloaded, its folder, or ``conversations.json``), a Mem0 export (``get_all`` output or a list of memories) or
    generic JSONL (one ``{"role", "content", "timestamp"?, "session_id"?, "user_id"?}`` per line). Each session
    becomes a ``run_id`` and each message a turn with its original time. Only what the user and the assistant said is
    imported: reasoning ("thinking") never is, and tool calls and results only with ``include_tool_output``.

    Importing is idempotent: each turn's id is derived from its source id (or, without one, from its content and
    position in its session), so importing the same history again stores only what is new. Every file is untrusted
    and read within ``limits``; see ``docs/IMPORT.md``. No model is called and nothing leaves the machine.

    Args:
        source: The file or folder to read. ``~`` is expanded.
        memory: Where the turns go: a :class:`~llmslim.memory.Memory`, a store, a SQLite path or a
            ``postgresql://`` URL. ``None`` only with ``dry_run``.
        format: ``"claude-code"``, ``"chatgpt"``, ``"claude-ai"``, ``"mem0"``, ``"jsonl"`` or ``"auto"``, which
            tells them apart from what the file holds (not its name).
        user_id: The user every turn is stored under. When ``None``, a record's own ``user_id`` (Mem0, JSONL) is
            kept, else ``"default"``, the user ``llmslim mcp`` serves when none is named.
        agent_id: The agent every turn is stored under; when ``None``, a record's own ``agent_id``, if any.
        since: Import only turns at or after this time (a datetime, epoch seconds or ISO-8601 text).
        until: Import only turns before this time.
        limit: Stop after this many new turns.
        include_tool_output: Also import tool calls and their results, as ``tool`` turns. Off by default: tool
            output (shell output, file contents) is where secrets usually are.
        dry_run: Read and count everything, store nothing. A SQLite file is opened read-only, and one that does not
            exist is not created.
        strict: Stop with :class:`HistoryImportError` at the first malformed or oversized record, instead of
            skipping and counting it.
        redact: Replace obvious credentials (API keys, AWS keys, private key blocks, bearer tokens, passwords in
            URLs) with ``[REDACTED:<kind>]`` before anything is stored. Best-effort; see ``docs/IMPORT.md``.
        limits: Size and nesting bounds on what is read; :class:`ImportLimits` has the defaults.
        on_session: Called with each :class:`ImportedSession` as it is done, for progress.

    Returns:
        An :class:`ImportReport` with what was imported, skipped (by reason), malformed and redacted.

    Raises:
        HistoryImportError: The source can't be read at all, its format can't be told, a size limit is exceeded,
            a zip archive is unsafe, or (with ``strict``) a record is malformed. A file that fails part way through
            is listed in the report's ``errors`` instead, with what was imported before it kept.
        ValueError: An unknown ``format``, an unreadable ``since`` or ``until``, or a ``limit`` below 1.

    Example:
        >>> from llmslim.memory import Memory, import_history
        >>> memory = Memory("memory.db")
        >>> report = import_history("~/.claude/projects", memory, format="claude-code")
        >>> print(report.imported, "turns imported,", report.duplicates, "already there")
    """
    if format != "auto" and format not in FORMATS:
        raise ValueError(f"format must be 'auto' or one of {', '.join(FORMATS)}, not {format!r}")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be a positive number of turns")
    if user_id is not None or agent_id is not None:
        Scope(user_id, agent_id)  # raises for an empty id
    start, end = _bound(since, "since"), _bound(until, "until")
    limits = limits or ImportLimits()
    path = Path(os.fspath(source)).expanduser()
    fmt = detect(path, limits) if format == "auto" else format
    lookup, write, close = _target(memory, dry_run)
    tally = Tally(limits, strict=strict, include_tool_output=include_tool_output)
    errors: List[str] = []
    sessions: List[ImportedSession] = []
    redactions: Counter = Counter()
    seen: Set[str] = set()
    imported = duplicates = produced = 0
    limited = False
    now = _utcnow()
    try:
        reader = READERS[fmt](path, tally, errors)
        while not limited:
            try:
                raw = next(reader)
            except StopIteration:
                break
            except HistoryImportError as error:
                # Strict, or nothing read yet: the import failed. Part way through a file: keep what was imported
                # and list the error in the report.
                if strict or (produced == 0 and not errors):
                    raise
                errors.append(str(error))
                break
            produced += 1
            if not raw.turns:
                continue
            owner = user_id or raw.user_id or DEFAULT_USER
            agent = agent_id or raw.agent_id
            title = raw.title
            if redact and title:
                title, found = redact_text(title)
                redactions.update(found)
            base: Dict[str, Any] = {"source": fmt, "session": raw.key, **raw.metadata}
            if title:
                base["title"] = title
            candidates: List[MemoryItem] = []
            occurrences: Counter = Counter()
            left_out = 0
            for turn, moment in zip(raw.turns, _times(raw, now)):
                if len(turn.text) > limits.max_turn_chars:
                    if strict:
                        raise HistoryImportError(
                            f"a {turn.role} turn in {FORMAT_NAMES[fmt]} session {raw.key} is "
                            f"{len(turn.text):,} characters, over the {limits.max_turn_chars:,} limit "
                            "(max_turn_chars); --strict stops here"
                        )
                    tally.skip("too_large")
                    left_out += 1
                    continue
                text = turn.text
                if redact:
                    text, found = redact_text(text)
                    redactions.update(found)
                if not text.strip():
                    tally.skip("empty")
                    left_out += 1
                    continue
                if (start is not None and moment < start) or (end is not None and moment >= end):
                    tally.skip("outside_window")
                    left_out += 1
                    continue
                if turn.source_id is not None:
                    parts: Tuple[str, ...] = (raw.id_scope, "id", turn.source_id)
                else:
                    digest = _content_digest(turn.role, turn.raw_time, text)
                    occurrences[digest] += 1
                    parts = (raw.id_scope, "content", digest, str(occurrences[digest]))
                metadata = dict(base)
                if turn.source_id is not None:
                    metadata["source_id"] = turn.source_id
                candidates.append(
                    MemoryItem(
                        id=_item_id(fmt, owner, agent, parts),
                        role=turn.role,
                        content=text,
                        created_at=moment,
                        user_id=owner,
                        agent_id=agent,
                        run_id=raw.run_id,
                        metadata=metadata,
                    )
                )
            stored_before = set(lookup([item.id for item in candidates if item.id not in seen]))
            fresh: List[MemoryItem] = []
            repeated = 0
            for item in candidates:
                if item.id in seen or item.id in stored_before:
                    repeated += 1
                    continue
                if limit is not None and imported + len(fresh) >= limit:
                    limited = True
                    break
                seen.add(item.id)
                fresh.append(item)
            if write is not None and fresh:
                stored, raced = _write(write, lookup, fresh)
                fresh, repeated = stored, repeated + raced
            imported += len(fresh)
            duplicates += repeated
            done = ImportedSession(
                format=fmt,
                session_id=raw.key,
                title=title,
                run_id=raw.run_id,
                user_id=owner,
                turns=len(raw.turns),
                imported=len(fresh),
                duplicates=repeated,
                skipped=left_out,
            )
            sessions.append(done)
            if on_session is not None:
                on_session(done)
    finally:
        close()
    return ImportReport(
        format=fmt,
        source=str(path),
        dry_run=dry_run,
        files=tally.files,
        sessions=tuple(sessions),
        imported=imported,
        duplicates=duplicates,
        malformed=tally.malformed,
        skipped=dict(tally.skipped),
        redactions=dict(redactions),
        errors=tuple(errors),
        limited=limited,
    )
