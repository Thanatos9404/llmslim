"""A drop-in for Mem0's ``Memory`` class, backed by :class:`llmslim.memory.Memory`.

Switching is one import::

    # from mem0 import Memory
    from llmslim.memory.compat import Mem0Memory as Memory

    memory = Memory()                                   # or Memory("memory.db") for a SQLite file
    memory.add(messages, user_id="alice")
    hits = memory.search("Where does Alice live?", filters={"user_id": "alice"})
    for hit in hits["results"]:
        print(hit["memory"])

Method names, keyword arguments and return shapes follow Mem0 2.x. The differences are deliberate:

* Nothing is extracted. ``add`` stores each turn verbatim and makes no model call, so ``infer``, ``prompt`` and
  ``memory_type`` are accepted and ignored, and every returned event is ``"ADD"``.
* ``search`` selects the turns that answer the question within a token ``budget`` (an LLMSlim extension, default
  2,000) and returns them as results ranked by a lexical overlap ``score``. The selected turns, rendered for a prompt
  in date order, are also returned under ``"context"``. ``threshold`` and ``explain`` are ignored. ``rerank=True``
  uses LLMSlim's optional cross-encoder (``pip install "llmslim[semantic]"``).
* Filters match ``user_id``, ``agent_id`` and ``run_id`` exactly; other filter keys raise ``ValueError`` rather than
  being silently ignored. ``expiration_date`` and ``reference_date`` are not supported and raise as well.
* ``history`` returns the turn's current state only: turns are kept verbatim, so there is no extraction history.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from ._core import Memory
from ._types import MemoryItem
from .stores import MemoryStore

__all__ = ["Mem0Memory"]

_ENTITY_KEYS = ("user_id", "agent_id", "run_id")


def _result(item: MemoryItem, score: Optional[float] = None) -> Dict[str, Any]:
    data = item.to_dict()
    result = {
        "id": item.id,
        "memory": item.content,
        "role": item.role,
        "metadata": data["metadata"],
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "user_id": item.user_id,
        "agent_id": item.agent_id,
        "run_id": item.run_id,
    }
    if score is not None:
        result["score"] = score
    return result


def _entities(filters: Optional[Mapping[str, Any]]) -> Dict[str, Optional[str]]:
    filters = dict(filters or {})
    unsupported = sorted(key for key in filters if key not in _ENTITY_KEYS)
    if unsupported:
        raise ValueError(
            f"filters supports only {', '.join(_ENTITY_KEYS)} in llmslim; unsupported: {', '.join(unsupported)}"
        )
    entities = {key: filters.get(key) for key in _ENTITY_KEYS}
    if not any(entities.values()):
        raise ValueError("filters must contain at least one of user_id, agent_id, run_id")
    return entities


class Mem0Memory:
    """Mem0's ``Memory`` interface over LLMSlim's verbatim, read-time-selected memory. See the module docs."""

    def __init__(
        self,
        store: Union[MemoryStore, str, Path, None] = None,
        *,
        budget: int = 2000,
        **options: Any,
    ):
        self.memory = Memory(store, budget=budget, **options)

    @classmethod
    def from_config(cls, config: Optional[Mapping[str, Any]] = None) -> "Mem0Memory":
        """Mem0's constructor shape. LLM, embedder and vector-store settings do not apply and are ignored; a
        ``{"store": path}`` entry selects a SQLite file."""
        return cls((config or {}).get("store"))

    def add(
        self,
        messages: Any,
        *,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        timestamp: Any = None,
        expiration_date: Any = None,
        infer: bool = True,
        memory_type: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if expiration_date is not None:
            raise ValueError("expiration_date is not supported by llmslim memory")
        items = self.memory.add(
            messages,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            timestamp=timestamp,
            metadata=metadata,
        )
        return {
            "results": [{"id": item.id, "memory": item.content, "event": "ADD"} for item in items]
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        filters: Optional[Mapping[str, Any]] = None,
        threshold: float = 0.1,
        rerank: bool = False,
        explain: bool = False,
        reference_date: Any = None,
        show_expired: bool = False,
        budget: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if reference_date is not None:
            raise ValueError("reference_date is not supported by llmslim memory")
        stray = sorted(set(kwargs) & set(_ENTITY_KEYS))
        if stray:
            raise ValueError(f"pass {', '.join(stray)} inside filters, as Mem0 2.x requires")
        if kwargs:
            raise TypeError(f"unexpected arguments: {', '.join(sorted(kwargs))}")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        scope = _entities(filters)
        context = self.memory.search(
            query,
            budget=budget,
            relevance="semantic" if rerank else None,
            user_id=scope["user_id"],
            agent_id=scope["agent_id"],
            run_id=scope["run_id"],
        )
        ranked = sorted(
            context.turns, key=lambda turn: (-turn.score, turn.item.created_at, turn.item.seq)
        )
        return {
            "results": [_result(turn.item, turn.score) for turn in ranked[:top_k]],
            "context": context.text,
        }

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        item = self.memory.get(memory_id)
        return _result(item) if item else None

    def get_all(
        self,
        *,
        filters: Optional[Mapping[str, Any]] = None,
        top_k: int = 20,
        show_expired: bool = False,
        **kwargs: Any,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if kwargs:
            raise TypeError(f"unexpected arguments: {', '.join(sorted(kwargs))}")
        items = self.memory.get_all(**_entities(filters))
        newest = sorted(items, key=lambda item: (item.created_at, item.seq), reverse=True)[:top_k]
        return {"results": [_result(item) for item in newest]}

    def update(
        self,
        memory_id: str,
        text: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        expiration_date: Any = None,
        data: Optional[str] = None,
    ) -> Dict[str, str]:
        if expiration_date is not None:
            raise ValueError("expiration_date is not supported by llmslim memory")
        if (
            self.memory.update(memory_id, text if text is not None else data, metadata=metadata)
            is None
        ):
            raise ValueError(f"memory {memory_id} not found")
        return {"message": "Memory updated successfully!"}

    def delete(self, memory_id: str) -> Dict[str, str]:
        if not self.memory.delete(memory_id):
            raise ValueError(f"memory {memory_id} not found")
        return {"message": "Memory deleted successfully!"}

    def delete_all(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, str]:
        self.memory.delete_all(user_id=user_id, agent_id=agent_id, run_id=run_id)
        return {"message": "Memories deleted successfully!"}

    def history(self, memory_id: str) -> List[Dict[str, Any]]:
        item = self.memory.get(memory_id)
        return [] if item is None else [{**_result(item), "event": "ADD"}]

    def reset(self) -> None:
        raise NotImplementedError(
            "reset() would delete every user's memory; use delete_all(user_id=...) for one scope"
        )
