"""Immutable boundary for the context available to one model turn."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence, Tuple

from .planning.models import ContextBundle, ContextItem
from .planning.planner import AdaptiveContextPlanner

_SECRET_KEYS = ("api_key", "apikey", "authorization", "password", "secret", "credential", "access_token", "refresh_token")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9_.:/-]{1,128}$")


def _check_metadata(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if any(secret in str(key).casefold() for secret in _SECRET_KEYS):
                raise ValueError("credentials cannot be included in a ContextEnvelope")
            _check_metadata(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_metadata(child)


@dataclass(frozen=True)
class ContextEnvelope:
    """Stable, provenance-bearing input set. Secrets are never accepted as metadata."""

    items: Tuple[ContextItem, ...]
    current_query: str = ""
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    model: str = "generic-128k"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    envelope_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.current_query, str):
            raise TypeError("current_query must be a string")
        if self.session_id is not None and (not self.session_id or len(self.session_id) > 128):
            raise ValueError("session_id must contain 1 to 128 characters")
        if not _SAFE_MODEL.fullmatch(self.model):
            raise ValueError("model identifier contains unsafe characters")
        if len(self.items) > 512:
            raise ValueError("context envelope exceeds the 512-item safety limit")
        items = tuple(
            replace(item, metadata=copy.deepcopy(dict(item.metadata))) for item in self.items
        )
        ContextBundle(items)  # validates identity uniqueness
        for item in items:
            if not _SAFE_ID.fullmatch(item.item_id):
                raise ValueError("context item ID contains unsafe characters")
            _check_metadata(item.metadata)
        object.__setattr__(self, "items", items)
        if not self.envelope_id:
            digest = hashlib.sha256()
            digest.update((self.session_id or "").encode())
            digest.update(self.current_query.encode())
            for item in items:
                digest.update(item.item_id.encode())
                digest.update(item.content.encode())
            object.__setattr__(self, "envelope_id", "ctx_" + digest.hexdigest()[:20])

    @classmethod
    def from_bundle(cls, bundle: ContextBundle, **kwargs: Any) -> "ContextEnvelope":
        return cls(items=bundle.items, **kwargs)

    @classmethod
    def from_messages(
        cls, messages: Sequence[Mapping[str, Any]], *, current_query: str = "", **kwargs: Any
    ) -> "ContextEnvelope":
        return cls.from_inputs(messages=messages, current_query=current_query, **kwargs)

    @classmethod
    def from_inputs(
        cls,
        *,
        messages: Sequence[Mapping[str, Any]] = (),
        documents: Sequence[Any] = (),
        memories: Sequence[Any] = (),
        tool_results: Sequence[Any] = (),
        tools: Sequence[Any] = (),
        current_query: str = "",
        **kwargs: Any,
    ) -> "ContextEnvelope":
        planner = AdaptiveContextPlanner()
        from .core import ContextRole
        from .planning.models import ContextKind

        safe_documents = tuple(
            replace(value, kind=ContextKind.RAG_DOCUMENT, role=ContextRole.RAG)
            if isinstance(value, ContextItem) else value
            for value in documents
        )
        safe_memories = tuple(
            replace(value, kind=ContextKind.MEMORY, role=ContextRole.RAG)
            if isinstance(value, ContextItem) else value
            for value in memories
        )
        items = planner._normalize(
            messages=messages,
            documents=safe_documents,
            memories=safe_memories,
            tools=tools,
            query=current_query,
            policy=planner.policy,
        )
        if tool_results:
            from .planning.candidates import rendered_token_count

            additional = []
            for index, value in enumerate(tool_results):
                if not isinstance(value, Mapping):
                    raise TypeError("tool_results must contain mappings")
                content = value.get("content")
                if not isinstance(content, str):
                    raise TypeError("tool result content must be a string")
                metadata = value.get("metadata", {})
                if not isinstance(metadata, Mapping):
                    raise TypeError("tool result metadata must be a mapping")
                item = ContextItem(
                    item_id="tool_result:" + str(value.get("id", index)),
                    content=content,
                    kind=ContextKind.TOOL_RESULT,
                    role=ContextRole.TOOL,
                    original_order=len(items) + index,
                    source=str(value.get("source", "tool_results")),
                    metadata=metadata,
                )
                additional.append(replace(item, token_count=rendered_token_count(item, content)))
            items += tuple(additional)
        return cls(items=items, current_query=current_query, **kwargs)

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        item_records = (
            [item.to_dict(include_content=True) for item in self.items]
            if include_content
            else [
                {
                    "id_hash": hashlib.sha256(item.item_id.encode()).hexdigest()[:16],
                    "kind": item.kind.value,
                    "role": item.role.value,
                    "token_count": item.token_count,
                }
                for item in self.items
            ]
        )
        return {
            "envelope_id": self.envelope_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "item_count": len(self.items),
            "items": item_records,
            **({"current_query": self.current_query} if include_content else {}),
        }
