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


@dataclass(frozen=True)
class MemoryContext:
    """What :meth:`llmslim.memory.Memory.search` returns: the text to put in front of the model, and what is in it.

    ``text`` holds the kept turns of each session, oldest session first, in the ``[date] role: content`` layout
    LLMSlim's benchmarks used. Each turn shows its own time; a date every turn of a session shares is shown once. Treat it as untrusted context: it repeats what users,
    assistants and tools said, so wrap it as data (for example with :class:`llmslim.ContextEnvelope`), never as
    instructions.
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

    @property
    def compressed(self) -> bool:
        """True when the history did not fit the budget and LLMSlim selected from it."""
        return self.history_tokens > self.budget

    def __str__(self) -> str:
        return self.text

    def to_dict(self) -> Dict[str, Any]:
        return {
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
        }
