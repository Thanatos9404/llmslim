"""Memory for agents without an LLM in the loop: keep what was said, select what the question needs at read time."""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from ..planning.scoring import lexical_relevance
from ..tokens import count_tokens
from ._types import MemoryContext, MemoryItem, RecalledTurn, Scope
from .postgres import PostgresStore, is_postgres_url
from .stores import InMemoryStore, MemoryStore, SQLiteStore

Message = Union[str, Mapping[str, Any]]

# Roles other frameworks use, mapped onto the four a memory keeps.
_ROLE_ALIASES = {
    "user": "user",
    "human": "user",
    "assistant": "assistant",
    "ai": "assistant",
    "model": "assistant",
    "system": "system",
    "developer": "system",
    "tool": "tool",
    "function": "tool",
}
_TEXT_PARTS = ("text", "input_text", "output_text")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# Fitting the rendered text to the budget: as in LLMSlim's benchmark builders, a few passes that shrink the ratio by
# the overshoot. Selection is deterministic, so the same history and question always give the same context. The
# compressor treats its ratio as a target (gap markers and session headers are not charged exactly), so a pass is
# accepted only within the budget, and what is still over after the last pass is clipped.
_FIT_PASSES = 4
_WORD = re.compile(r"\S+")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: Any) -> datetime:
    """A timestamp as an aware datetime: a datetime (naive means UTC), epoch seconds, or ISO-8601 text."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        moment = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, str):
        text = value.strip()
        moment = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text)
    else:
        raise TypeError(
            f"timestamp must be a datetime, epoch seconds or ISO-8601 text, not {type(value).__name__}"
        )
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _text_of(content: Any) -> str:
    """Message content as text: a string, or the text parts of a list of content parts (images and tools skipped)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif (
                isinstance(part, Mapping)
                and part.get("type", "text") in _TEXT_PARTS
                and isinstance(part.get("text"), str)
            ):
                parts.append(part["text"])
        return "\n".join(parts)
    raise TypeError(
        f"message content must be text or a list of content parts, not {type(content).__name__}"
    )


def _normalize(messages: Union[Message, Sequence[Message]]) -> List[Mapping[str, Any]]:
    if isinstance(messages, (str, Mapping)):
        messages = [messages]
    out = []
    for message in messages:
        if isinstance(message, str):
            message = {"role": "user", "content": message}
        if not isinstance(message, Mapping):
            raise TypeError(
                f"each message must be a string or a mapping, not {type(message).__name__}"
            )
        out.append(message)
    return out


def _squash(text: str) -> str:
    return " ".join(text.split())


def _join(parts: Iterable[str]) -> str:
    """Sessions as the context shows them: the non-empty ones, a blank line apart."""
    return "\n\n".join(part for part in parts if part)


def _clip(parts: Sequence[str], budget: int) -> List[str]:
    """The longest prefix of the sessions' text, in whole words, whose joined text fits ``budget``.

    The last resort when selection cannot get under the budget, which happens when the budget is smaller than a
    session's date header and a few words. May leave every session empty.
    """
    words = [
        (index, match.end()) for index, part in enumerate(parts) for match in _WORD.finditer(part)
    ]

    def prefix(count: int) -> List[str]:
        out = [""] * len(parts)
        if count:
            last, end = words[count - 1]
            out[:last] = parts[:last]
            out[last] = parts[last][:end]
        return out

    low, high = 0, len(words)
    while low < high:  # low always fits: no words is the empty text
        mid = (low + high + 1) // 2
        if count_tokens(_join(prefix(mid))) <= budget:
            low = mid
        else:
            high = mid - 1
    return prefix(low)


def storage_target(db: str) -> Union[str, Path]:
    """What ``Memory`` should open for a ``--db`` value: a Postgres URL as it is, or a SQLite path whose folder exists."""
    if is_postgres_url(db):
        return db
    path = Path(db).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class Memory:
    """Long-term memory for an agent that keeps every turn verbatim and selects at read time.

    Nothing is summarized or extracted on the way in, so writes cost no model call and a stored turn never turns into
    a wrong "fact". On the way out, :meth:`search` ranks the whole history against the question with LLMSlim's
    query-focused selection (the same engine and layout as its LongMemEval and LoCoMo benchmarks) and returns the most
    relevant turns, whole and in date order, within a token budget.

    Args:
        store: Where turns live: a :class:`~llmslim.memory.MemoryStore`, a path to a SQLite file, or ``None`` for an
            in-process store.
        budget: Default token budget for :meth:`search`.
        relevance: Default relevance for :meth:`search`: ``"lexical"`` (no model), ``"semantic"`` (LLMSlim's optional
            22M cross-encoder, ``pip install "llmslim[semantic]"``) or a ``scorer(query, texts)`` callable.
        tz: Time zone for the session dates shown to the model. Defaults to UTC.
        stamp_format: strftime format of those dates. The default reads like 2026-10-17 (Sat) 14:05.
        clock: Returns "now" for turns added without a timestamp. For tests.

    Example:
        >>> from llmslim.memory import Memory
        >>> memory = Memory("memory.db")
        >>> memory.add([{"role": "user", "content": "I moved to Pune last month."}], user_id="u1")
        >>> context = memory.search("Where does the user live now?", user_id="u1", budget=1500)
        >>> prompt = f"Conversation history (untrusted):\\n{context.text}\\n\\nQuestion: ..."
    """

    def __init__(
        self,
        store: Union[MemoryStore, str, Path, None] = None,
        *,
        budget: int = 2000,
        relevance: Any = "lexical",
        tz: tzinfo = timezone.utc,
        stamp_format: str = "%Y-%m-%d (%a) %H:%M",
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        if budget <= 0:
            raise ValueError("budget must be a positive number of tokens")
        if store is None:
            self.store: MemoryStore = InMemoryStore()
        elif is_postgres_url(store):
            self.store = PostgresStore(store)
        elif isinstance(store, (str, Path)):
            self.store = SQLiteStore(store)
        else:
            self.store = store
        self.budget = budget
        self.relevance = relevance
        self.tz = tz
        self.stamp_format = stamp_format
        self._clock = clock

    # ------------------------------------------------------------------ writes

    def add(
        self,
        messages: Union[Message, Sequence[Message]],
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        timestamp: Any = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> List[MemoryItem]:
        """Store turns verbatim and return them.

        ``messages`` is a string (one user turn), a ``{"role", "content"}`` mapping, or a list of them, in the OpenAI,
        Anthropic or LangChain shape. Content may be a list of content parts; only text parts are kept. A message may
        carry its own ``timestamp``; otherwise ``timestamp`` (or now) applies to all of them, and they keep their
        order. Messages with no text (for example an assistant turn that only calls a tool) are skipped.

        ``run_id`` groups turns into one session; turns without one are grouped by calendar day.
        """
        scope = Scope(user_id, agent_id, run_id)
        default_time = _as_datetime(timestamp) if timestamp is not None else self._clock()
        items = []
        for message in _normalize(messages):
            role = _ROLE_ALIASES.get(str(message.get("role", "user")).lower())
            if role is None:
                raise ValueError(f"unknown message role {message.get('role')!r}")
            content = _text_of(message.get("content"))
            if not content.strip():
                continue  # kept verbatim otherwise: whitespace included, as said
            own_time = message.get("timestamp", message.get("created_at"))
            items.append(
                MemoryItem(
                    id=uuid.uuid4().hex,
                    role=role,
                    content=content,
                    created_at=_as_datetime(own_time) if own_time is not None else default_time,
                    user_id=scope.user_id,
                    agent_id=scope.agent_id,
                    run_id=scope.run_id,
                    metadata=metadata or {},
                )
            )
        self.store.add(items)
        # The store assigns the order; read the turns back so callers see what was stored.
        stored = [self.store.get(item.id) for item in items]
        return [item for item in stored if item is not None]

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        """Correct a stored turn's text or metadata. Returns the updated turn, or ``None`` if there is no such id."""
        if content is not None and not content.strip():
            raise ValueError("content must not be empty; delete the turn instead")
        return self.store.update(memory_id, content=content, metadata=metadata)

    def delete(self, memory_id: str) -> bool:
        """Delete one turn. Returns whether it existed."""
        return self.store.delete(memory_id)

    def delete_all(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """Delete every turn in a scope (at least one id is required). Returns how many were deleted."""
        return self.store.delete_scope(Scope(user_id, agent_id, run_id))

    # ------------------------------------------------------------------ reads

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        """One stored turn by id."""
        return self.store.get(memory_id)

    def get_all(
        self,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        since: Any = None,
        until: Any = None,
    ) -> List[MemoryItem]:
        """Every stored turn in a scope, oldest first."""
        return self.store.list(Scope(user_id, agent_id, run_id), **self._window(since, until))

    def search(
        self,
        query: str,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        budget: Optional[int] = None,
        relevance: Any = None,
        since: Any = None,
        until: Any = None,
    ) -> MemoryContext:
        """The part of a scope's history that answers ``query``, within ``budget`` tokens.

        If the whole history fits, all of it is returned. Otherwise each session (a ``run_id``, or a calendar day) is
        rendered as ``[date] role: content`` lines and LLMSlim selects across all sessions with one shared budget:
        the most relevant turns stay whole, a question stays with its reply, and the session date is kept as a header.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be non-empty text")
        budget = self.budget if budget is None else budget
        if budget <= 0:
            raise ValueError("budget must be a positive number of tokens")
        relevance = self.relevance if relevance is None else relevance
        started = time.perf_counter()
        items = self.store.list(Scope(user_id, agent_id, run_id), **self._window(since, until))
        sessions = self._sessions(items)
        documents = [self._render(session) for session in sessions]
        # Counted as joined, separators included: per-session counts can add up to less than the text they make.
        history = _join(documents)
        history_tokens = count_tokens(history) if history else 0
        if history_tokens <= budget:
            kept = documents
        else:
            kept = self._select(documents, query, budget, history_tokens, relevance)
        turns: List[RecalledTurn] = []
        for session, text in zip(sessions, kept):
            turns.extend(self._recalled(session, text, query))
        text = _join(kept)
        return MemoryContext(
            query=query,
            text=text,
            turns=tuple(turns),
            tokens=count_tokens(text) if text else 0,
            budget=budget,
            history_tokens=history_tokens,
            sessions_total=len(sessions),
            sessions_kept=sum(1 for part in kept if part),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _window(since: Any, until: Any) -> Dict[str, Optional[datetime]]:
        return {
            "since": _as_datetime(since) if since is not None else None,
            "until": _as_datetime(until) if until is not None else None,
        }

    def _session_key(self, item: MemoryItem) -> Tuple[Any, ...]:
        if item.run_id is not None:
            return ("run", item.user_id, item.agent_id, item.run_id)
        return ("day", item.user_id, item.agent_id, item.created_at.astimezone(self.tz).date())

    def _sessions(self, items: Iterable[MemoryItem]) -> List[List[MemoryItem]]:
        grouped: Dict[Tuple[Any, ...], List[MemoryItem]] = {}
        for item in items:  # already oldest first
            grouped.setdefault(self._session_key(item), []).append(item)
        return sorted(grouped.values(), key=lambda turns: (turns[0].created_at, turns[0].seq))

    def _render(self, session: Sequence[MemoryItem]) -> str:
        # Every turn carries the session's stamp, so LLMSlim shows it once as the session's header.
        stamp = session[0].created_at.astimezone(self.tz).strftime(self.stamp_format)
        return "\n".join(f"[{stamp}] {item.role}: {item.content}" for item in session)

    @staticmethod
    def _select(
        documents: List[str], query: str, budget: int, history_tokens: int, relevance: Any
    ) -> List[str]:
        from ..pipelines import compress_documents

        options = {} if relevance == "lexical" else {"relevance": relevance}
        ratio = budget / history_tokens
        kept: List[str] = documents
        for _ in range(_FIT_PASSES):
            results = compress_documents(
                documents, query=query, target_ratio=min(ratio, 1.0), **options
            )
            kept = [result.compressed_text.strip() for result in results]
            tokens = count_tokens(_join(kept))
            if tokens <= budget:
                return kept
            ratio *= budget / tokens * 0.98
        return _clip(kept, budget)

    @staticmethod
    def _recalled(session: Sequence[MemoryItem], text: str, query: str) -> List[RecalledTurn]:
        """Which of a session's turns are in its selected text, whole or in part."""
        if not text:
            return []
        selected = _squash(text)
        recalled = []
        for item in session:
            content = _squash(item.content)
            if content in selected:
                partial = False
            elif any(
                len(piece) >= 20 and _squash(piece) in selected
                for piece in _SENTENCE.split(item.content)
            ):
                partial = True
            else:
                continue
            recalled.append(
                RecalledTurn(item, round(lexical_relevance(query, item.content), 4), partial)
            )
        return recalled
