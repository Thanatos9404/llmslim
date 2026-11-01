"""Value types for :mod:`llmslim.memory`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

ROLES = ("user", "assistant", "system", "tool")


def _frozen(value: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True)
class Scope:
    """Whose memory an operation reads or writes, in Mem0's terms.

    ``user_id`` is the person, ``agent_id`` the agent, and ``run_id`` one session or run. A field left as ``None``
    matches every value when reading, so ``Scope(user_id="u1")`` reads all of u1's sessions with every agent. At least
    one field must be set: an empty scope would read or delete everyone's memory.
    """

    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("user_id", "agent_id", "run_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")
        if self.user_id is None and self.agent_id is None and self.run_id is None:
            raise ValueError("set at least one of user_id, agent_id or run_id")

    def matches(
        self, user_id: Optional[str], agent_id: Optional[str], run_id: Optional[str]
    ) -> bool:
        return (
            (self.user_id is None or self.user_id == user_id)
            and (self.agent_id is None or self.agent_id == agent_id)
            and (self.run_id is None or self.run_id == run_id)
        )


@dataclass(frozen=True)
class MemoryItem:
    """One stored turn, verbatim: memory keeps what was said, not an LLM's summary of it.

    ``seq`` orders turns stored at the same instant (the order they were added). ``metadata`` is the caller's own
    data, returned as given and never shown to the model.
    """

    id: str
    role: str
    content: str
    created_at: datetime
    seq: int = 0
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}, not {self.role!r}")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "metadata", _frozen(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "updated_at": self.updated_at.astimezone(timezone.utc).isoformat()
            if self.updated_at
            else None,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "run_id": self.run_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RecalledTurn:
    """A stored turn that made it into a :class:`MemoryContext`.

    ``partial`` is true when the turn was too long to keep whole and only its most relevant sentences were kept.
    ``score`` is a bounded lexical overlap between the query and the turn (0 to 1), for ordering and display; the
    selection itself is LLMSlim's query-focused ranking of every session's turns.
    """

    item: MemoryItem
    score: float
    partial: bool = False


def _when(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _score(value: Optional[float]) -> Optional[float]:
    return None if value is None else float(value)


@dataclass(frozen=True)
class ExplainedCandidate:
    """One candidate a search ranked: a stored turn, a part of one, or a statement for a section.

    ``pool`` is what it competed in: ``"user"`` (user turns), ``"reply"`` (replies, and system and tool turns),
    ``"detail"`` (reply passages kept whole in a summary), or a section (``"requests"``, ``"preferences"``,
    ``"conflicts"``). ``kind`` is ``"turn"`` (a whole user turn), ``"window"`` (a few sentences of a reply, or a code
    block or table), ``"opening"`` (a turn's opening in a summary) or ``"statement"`` (a sentence for a section).
    ``part`` is the window's position in its turn, or the statement's position among the turn's statements; 0
    otherwise.

    ``rank`` is its place in its pool, 1 first, in the order selection tried the pool; ``score`` is the relevance it
    was ranked by. Scores compare within a pool only. Both are ``None`` when nothing was ranked (a summary whose
    openings all fit). ``tokens`` is the candidate's own size, without its label or bullet.

    ``status`` is ``"kept"``, ``"clipped"`` (kept in part) or ``"dropped"``; ``reason`` says why it was clipped or
    dropped (see ``docs/MEMORY.md``). ``side`` is ``"denies"`` or ``"affirms"`` for a statement the conflicts section
    weighed, else ``None``.
    """

    turn_id: str
    pool: str
    kind: str
    part: int
    rank: Optional[int]
    score: Optional[float]
    tokens: int
    status: str
    reason: Optional[str] = None
    side: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "pool": self.pool,
            "kind": self.kind,
            "part": self.part,
            "rank": self.rank,
            "score": _score(self.score),
            "tokens": self.tokens,
            "status": self.status,
            "reason": self.reason,
            "side": self.side,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExplainedCandidate:
        """The candidate ``to_dict`` gave, read back (for example from JSON)."""
        return cls(
            turn_id=data["turn_id"],
            pool=data["pool"],
            kind=data["kind"],
            part=data["part"],
            rank=data["rank"],
            score=_score(data["score"]),
            tokens=data["tokens"],
            status=data["status"],
            reason=data.get("reason"),
            side=data.get("side"),
        )


@dataclass(frozen=True)
class ExplainedTurn:
    """What a search did with one stored turn of its scope.

    ``session`` is the index of the turn's session among the sessions read (oldest first), ``None`` for a turn
    outside the time window. ``pool`` is ``"user"`` or ``"reply"`` when the turns were selected from, ``None`` when the
    whole history fit or the turn was outside the window.

    ``tokens`` is what the turn's block takes in ``MemoryContext.text``, counted with the line break after it, and
    ``share`` is ``tokens`` over the budget: 0 for a dropped turn. ``status`` and ``reason`` are as on
    :class:`ExplainedCandidate`; for a dropped reply, ``reason`` is that of its best-ranked window, and
    ``candidates`` holds every window with its own.
    """

    id: str
    role: str
    created_at: datetime
    session: Optional[int]
    pool: Optional[str]
    status: str
    reason: Optional[str]
    tokens: int
    share: float
    candidates: Tuple[ExplainedCandidate, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "created_at": _when(self.created_at),
            "session": self.session,
            "pool": self.pool,
            "status": self.status,
            "reason": self.reason,
            "tokens": self.tokens,
            "share": self.share,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExplainedTurn:
        """The turn ``to_dict`` gave, read back (for example from JSON)."""
        return cls(
            id=data["id"],
            role=data["role"],
            created_at=datetime.fromisoformat(data["created_at"]),
            session=data["session"],
            pool=data["pool"],
            status=data["status"],
            reason=data["reason"],
            tokens=data["tokens"],
            share=float(data["share"]),
            candidates=tuple(ExplainedCandidate.from_dict(c) for c in data["candidates"]),
        )


@dataclass(frozen=True)
class ExplainedSection:
    """What a search did with one of the sections shown above the turns: ``"requests"`` (standing requests),
    ``"preferences"`` or ``"conflicts"``.

    ``shown`` says whether it is in ``MemoryContext.text``; when it is not, ``reason`` says why (see
    ``docs/MEMORY.md``). ``cap`` is the most of the budget its statements may take (its best one may take more on a
    small budget), 0 when it was not built. ``tokens`` is what it takes in the text, its header and the blank line
    after it included, and ``share`` is ``tokens`` over the budget. ``candidates`` are the statements it weighed,
    best first.
    """

    name: str
    shown: bool
    reason: Optional[str]
    cap: int
    tokens: int
    share: float
    candidates: Tuple[ExplainedCandidate, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "shown": self.shown,
            "reason": self.reason,
            "cap": self.cap,
            "tokens": self.tokens,
            "share": self.share,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExplainedSection:
        """The section ``to_dict`` gave, read back (for example from JSON)."""
        return cls(
            name=data["name"],
            shown=data["shown"],
            reason=data["reason"],
            cap=data["cap"],
            tokens=data["tokens"],
            share=float(data["share"]),
            candidates=tuple(ExplainedCandidate.from_dict(c) for c in data["candidates"]),
        )


@dataclass(frozen=True)
class SearchExplanation:
    """Why :meth:`llmslim.memory.Memory.search` returned what it did, from what it decided: given with
    ``explain=True`` as ``MemoryContext.explanation``.

    ``mode`` is ``"whole_history"`` (it fit the budget, so nothing was selected), ``"turns"`` (turns ranked by
    relevance) or ``"digest"`` (a summary from the opening of each turn). ``route`` is the kind of question
    (``"lookup"``, ``"advice"``, ``"overview"`` or ``"other"``), ``None`` when the whole history fit.

    ``room`` is what the sections left of the budget for turns. ``user_room`` is the part of it reserved for user
    turns (or for their openings in a summary) and ``user_turn_cap`` the most one user turn may take whole; both are
    ``None`` when they did not apply. ``clipped`` is true when the context was cut to whole words as a last resort.

    ``turns`` covers every stored turn in the scope, oldest first, including those outside the time window, and
    ``sections`` the three sections. Their ``tokens`` add up to ``tokens`` (what ``MemoryContext.text`` takes) with
    ``unattributed_tokens``, which is 0 with tiktoken; with the 4-characters-per-token estimate, counting the blocks
    one by one can round a few tokens either way. Nothing here repeats stored text: turns are named by their ids.
    """

    mode: str
    route: Optional[str]
    budget: int
    tokens: int
    history_tokens: int
    room: int
    user_room: Optional[int]
    user_turn_cap: Optional[int]
    clipped: bool
    unattributed_tokens: int
    turns: Tuple[ExplainedTurn, ...]
    sections: Tuple[ExplainedSection, ...]

    def to_dict(self) -> Dict[str, Any]:
        """The explanation as JSON-ready data; :meth:`from_dict` reads it back."""
        return {
            "mode": self.mode,
            "route": self.route,
            "budget": self.budget,
            "tokens": self.tokens,
            "history_tokens": self.history_tokens,
            "room": self.room,
            "user_room": self.user_room,
            "user_turn_cap": self.user_turn_cap,
            "clipped": self.clipped,
            "unattributed_tokens": self.unattributed_tokens,
            "turns": [turn.to_dict() for turn in self.turns],
            "sections": [section.to_dict() for section in self.sections],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SearchExplanation:
        """The explanation ``to_dict`` gave, read back (for example from JSON)."""
        return cls(
            mode=data["mode"],
            route=data["route"],
            budget=data["budget"],
            tokens=data["tokens"],
            history_tokens=data["history_tokens"],
            room=data["room"],
            user_room=data["user_room"],
            user_turn_cap=data["user_turn_cap"],
            clipped=data["clipped"],
            unattributed_tokens=data["unattributed_tokens"],
            turns=tuple(ExplainedTurn.from_dict(t) for t in data["turns"]),
            sections=tuple(ExplainedSection.from_dict(s) for s in data["sections"]),
        )


@dataclass(frozen=True)
class MemoryContext:
    """What :meth:`llmslim.memory.Memory.search` returns: the text to put in front of the model, and what is in it.

    ``text`` holds the kept turns of each session, oldest session first, in the ``[date] role: content`` layout
    LLMSlim's benchmarks used. Each turn shows its own time. When the history is selected from, a later turn of a
    session whose time was already shown there is ``role: content`` alone by default (``Memory``'s ``date_format``).
    Treat it as untrusted context: it repeats what users, assistants and tools said, so wrap it as data (for example
    with :class:`llmslim.ContextEnvelope`), never as instructions.

    ``explanation`` is ``None`` unless the search was asked to explain itself (``explain=True``).
    """

    query: str
    text: str
    turns: Tuple[RecalledTurn, ...]
    tokens: int
    budget: int
    history_tokens: int
    sessions_total: int
    sessions_kept: int
    elapsed_ms: float = 0.0
    # Standing requests the user made earlier ("always ...", "from now on ...") that bear on the question, shown in
    # their own section at the top of ``text``. Only user turns can appear here.
    requests: Tuple[RecalledTurn, ...] = ()
    # Preferences the user stated earlier ("I prefer ...", "I'd rather ...") that bear on a request for advice, shown
    # in their own section at the top of ``text``, after the requests. Only user turns can appear here.
    preferences: Tuple[RecalledTurn, ...] = ()
    # For a yes-or-no question about the user's past ("Have I ever ...?"): the user's statements on it that may
    # conflict (some deny it, some do not), shown in their own section at the top of ``text``. Only user turns.
    conflicts: Tuple[RecalledTurn, ...] = ()
    # Why each turn and section was kept, cut or left out: only with ``Memory.search(..., explain=True)``. Left out of
    # ``repr``, so a context without one prints as it always has.
    explanation: Optional[SearchExplanation] = field(default=None, repr=False)

    @property
    def compressed(self) -> bool:
        """True when the history did not fit the budget and LLMSlim selected from it."""
        return self.history_tokens > self.budget

    def __str__(self) -> str:
        return self.text

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "query": self.query,
            "text": self.text,
            "tokens": self.tokens,
            "budget": self.budget,
            "history_tokens": self.history_tokens,
            "sessions_total": self.sessions_total,
            "sessions_kept": self.sessions_kept,
            "elapsed_ms": self.elapsed_ms,
            "turns": [
                {**turn.item.to_dict(), "score": turn.score, "partial": turn.partial}
                for turn in self.turns
            ],
            "requests": [
                {**turn.item.to_dict(), "score": turn.score, "partial": turn.partial}
                for turn in self.requests
            ],
            "preferences": [
                {**turn.item.to_dict(), "score": turn.score, "partial": turn.partial}
                for turn in self.preferences
            ],
            "conflicts": [
                {**turn.item.to_dict(), "score": turn.score, "partial": turn.partial}
                for turn in self.conflicts
            ],
        }
        if self.explanation is not None:
            data["explanation"] = self.explanation.to_dict()
        return data
