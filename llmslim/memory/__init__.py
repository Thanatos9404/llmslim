"""Agent memory with no LLM in the loop.

:class:`Memory` keeps every turn verbatim (no extraction model on the way in) and, at read time, selects the part of
the history that answers a question within a token budget, with the query-focused selection LLMSlim benchmarks
against Mem0 and Zep. Turns live in a :class:`MemoryStore`: in this process (:class:`InMemoryStore`), in a SQLite
file (:class:`SQLiteStore`) or in Postgres (:class:`PostgresStore`, ``pip install "llmslim[postgres]"``).

Coming from Mem0? :class:`llmslim.memory.compat.Mem0Memory` has Mem0's method names and return shapes.
"""

from ._core import Memory
from ._types import MemoryContext, MemoryItem, RecalledTurn, Scope
from .postgres import PostgresStore
from .stores import InMemoryStore, MemoryStore, SQLiteStore

__all__ = [
    "InMemoryStore",
    "Memory",
    "MemoryContext",
    "MemoryItem",
    "MemoryStore",
    "PostgresStore",
    "RecalledTurn",
    "SQLiteStore",
    "Scope",
]
