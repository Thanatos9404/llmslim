"""Optional explicit MongoDB context persistence and retrieval.

Uses PyMongo's native async API (not Motor). Construction never reads
``MONGODB_URI`` implicitly and planning never writes automatically.
"""

from __future__ import annotations

import inspect
import json
import os
import re
from dataclasses import replace
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Sequence, Union

from ..core import ContextRole
from ..planning.models import ContextItem, ContextKind, ContextPlan

EmbeddingProvider = Callable[[str], Union[Sequence[float], Awaitable[Sequence[float]]]]

_SENSITIVE_KEY_RE = re.compile(
    r"(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|mongodb[_-]?uri)",
    re.IGNORECASE,
)
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class MongoDBIntegrationError(RuntimeError):
    """Sanitized MongoDB integration error."""


class MongoDBContextStore:
    """Explicit async PyMongo context store with bounded retrieval."""

    def __init__(
        self,
        *,
        uri: Optional[str] = None,
        client: Optional[Any] = None,
        database: str = "llmslim",
        collection: str = "context_items",
        atlas_search_index: Optional[str] = None,
        server_selection_timeout_ms: int = 5000,
        connect_timeout_ms: int = 5000,
        socket_timeout_ms: int = 10000,
        max_content_bytes: int = 2_000_000,
    ) -> None:
        if bool(uri) == bool(client):
            raise ValueError("provide exactly one of uri or client")
        _validated_name(database, "database")
        _validated_name(collection, "collection")
        if atlas_search_index is not None:
            _validated_name(atlas_search_index, "Atlas Search index")
        if min(server_selection_timeout_ms, connect_timeout_ms, socket_timeout_ms) <= 0:
            raise ValueError("MongoDB timeouts must be positive")
        if max_content_bytes <= 0:
            raise ValueError("max_content_bytes must be positive")
        self._owns_client = client is None
        if client is None:
            try:
                from pymongo import AsyncMongoClient
                from pymongo.server_api import ServerApi
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    'MongoDBContextStore requires the optional extra: pip install "llmslim[mongodb]"'
                ) from exc
            client = AsyncMongoClient(
                uri,
                server_api=ServerApi("1"),
                serverSelectionTimeoutMS=server_selection_timeout_ms,
                connectTimeoutMS=connect_timeout_ms,
                socketTimeoutMS=socket_timeout_ms,
                appname="llmslim",
            )
        self._client = client
        self._collection = client[database][collection]
        self.database = database
        self.collection = collection
        self.atlas_search_index = atlas_search_index
        self.max_content_bytes = max_content_bytes

    @classmethod
    def from_env(cls, env_var: str = "MONGODB_URI", **kwargs: Any) -> "MongoDBContextStore":
        """Explicitly load one named environment variable and construct a store."""

        uri = os.environ.get(env_var)
        if not uri:
            raise ValueError(f"environment variable {env_var} is not set")
        return cls(uri=uri, **kwargs)

    async def save(self, item: ContextItem, namespace: str = "default") -> None:
        namespace = _validated_namespace(namespace)
        if len(item.content.encode("utf-8")) > self.max_content_bytes:
            raise ValueError("context item exceeds max_content_bytes")
        document = _item_to_document(item, namespace)
        try:
            await self._collection.replace_one({"_id": document["_id"]}, document, upsert=True)
        except Exception as exc:
            _raise_sanitized("save", exc)

    async def get(self, item_id: str, namespace: str = "default") -> Optional[ContextItem]:
        namespace = _validated_namespace(namespace)
        document_id = _document_id(namespace, item_id)
        try:
            document = await self._collection.find_one({"_id": document_id})
        except Exception as exc:
            _raise_sanitized("get", exc)
        return _document_to_item(document) if document else None

    async def search(
        self, query: str, limit: int = 10, namespace: str = "default"
    ) -> Sequence[ContextItem]:
        namespace = _validated_namespace(namespace)
        bounded = _bounded_limit(limit)
        query = _bounded_query(query)
        try:
            if self.atlas_search_index:
                pipeline: Sequence[Mapping[str, Any]] = [
                    {
                        "$search": {
                            "index": self.atlas_search_index,
                            "text": {"query": query, "path": "content"},
                        }
                    },
                    {"$match": {"namespace": namespace, "record_type": "context_item"}},
                    {"$limit": bounded},
                ]
                cursor = await _maybe_await(self._collection.aggregate(pipeline))
            else:
                cursor = self._collection.find(
                    {
                        "namespace": namespace,
                        "record_type": "context_item",
                        "content": {"$regex": re.escape(query), "$options": "i"},
                    },
                    max_time_ms=5000,
                ).limit(bounded)
            documents = await cursor.to_list(length=bounded)
        except Exception as exc:
            _raise_sanitized("search", exc)
        return tuple(_document_to_item(document) for document in documents)

    async def search_vector(
        self,
        query_vector: Sequence[float],
        *,
        index_name: str,
        path: str = "embedding",
        limit: int = 10,
        num_candidates: int = 100,
        namespace: str = "default",
        filters: Optional[Mapping[str, Any]] = None,
    ) -> Sequence[ContextItem]:
        """Run an explicit Atlas ``$vectorSearch`` query with caller embeddings."""

        _validated_name(index_name, "Atlas Vector Search index")
        _validated_name(path, "embedding path")
        namespace = _validated_namespace(namespace)
        bounded = _bounded_limit(limit)
        if not query_vector or not all(isinstance(value, (int, float)) for value in query_vector):
            raise ValueError("query_vector must contain numeric values")
        if not bounded <= num_candidates <= 10_000:
            raise ValueError("num_candidates must be between limit and 10000")
        prefilter: Dict[str, Any] = {"namespace": namespace, "record_type": "context_item"}
        if filters:
            prefilter.update(_json_safe(filters))
        pipeline: Sequence[Mapping[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": index_name,
                    "path": path,
                    "queryVector": [float(value) for value in query_vector],
                    "numCandidates": num_candidates,
                    "limit": bounded,
                    "filter": prefilter,
                }
            },
            {"$limit": bounded},
        ]
        try:
            cursor = await _maybe_await(self._collection.aggregate(pipeline))
            documents = await cursor.to_list(length=bounded)
        except Exception as exc:
            _raise_sanitized("vector search", exc)
        return tuple(_document_to_item(document) for document in documents)

    async def delete(self, item_id: str, namespace: str = "default") -> bool:
        namespace = _validated_namespace(namespace)
        document_id = _document_id(namespace, item_id)
        try:
            result = await self._collection.delete_one({"_id": document_id})
        except Exception as exc:
            _raise_sanitized("delete", exc)
        return bool(result.deleted_count)

    async def save_record(
        self,
        record_id: str,
        record_type: str,
        payload: Mapping[str, Any],
        namespace: str = "default",
    ) -> None:
        """Explicitly store sanitized traces or evaluation feedback."""

        namespace = _validated_namespace(namespace)
        _validated_name(record_type, "record type")
        document = {
            "_id": _document_id(namespace, record_id),
            "namespace": namespace,
            "record_type": record_type,
            "payload": _scrub_sensitive(payload),
        }
        try:
            await self._collection.replace_one({"_id": document["_id"]}, document, upsert=True)
        except Exception as exc:
            _raise_sanitized("save record", exc)

    async def save_plan_trace(
        self,
        plan_id: str,
        plan: ContextPlan,
        *,
        namespace: str = "default",
        include_content: bool = False,
    ) -> None:
        """Persist an explicit plan trace; prompt content is excluded by default."""

        await self.save_record(
            plan_id,
            "plan_trace",
            plan.to_dict(include_content=include_content),
            namespace,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

    def __repr__(self) -> str:
        return (
            f"MongoDBContextStore(database={self.database!r}, collection={self.collection!r}, "
            "uri=<redacted>)"
        )


class MongoDBContextSource:
    """ContextSource facade over a MongoDB store's text or vector retrieval."""

    source_id = "mongodb:context"

    def __init__(
        self,
        store: MongoDBContextStore,
        *,
        namespace: str = "default",
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_index: Optional[str] = None,
        vector_path: str = "embedding",
        num_candidates: int = 100,
        preserve_caller_trust: bool = False,
    ) -> None:
        self.store = store
        self.namespace = _validated_namespace(namespace)
        self.embedding_provider = embedding_provider
        self.vector_index = vector_index
        self.vector_path = vector_path
        self.num_candidates = num_candidates
        self.preserve_caller_trust = preserve_caller_trust
        if bool(embedding_provider) != bool(vector_index):
            raise ValueError("embedding_provider and vector_index must be configured together")

    async def search(self, query: str, limit: int = 10) -> Sequence[ContextItem]:
        bounded = _bounded_limit(limit)
        if self.embedding_provider is None:
            items = await self.store.search(query, bounded, self.namespace)
        else:
            vector_result = self.embedding_provider(query)
            vector = await vector_result if inspect.isawaitable(vector_result) else vector_result
            assert self.vector_index is not None
            items = await self.store.search_vector(
                vector,
                index_name=self.vector_index,
                path=self.vector_path,
                limit=bounded,
                num_candidates=max(bounded, self.num_candidates),
                namespace=self.namespace,
            )
        if self.preserve_caller_trust:
            return tuple(items)
        return tuple(
            replace(
                item,
                role=ContextRole.RAG,
                kind=ContextKind.MEMORY
                if item.kind is ContextKind.MEMORY
                else ContextKind.RAG_DOCUMENT,
                source=self.source_id,
                required=False,
            )
            for item in items
        )

    def __repr__(self) -> str:
        return f"MongoDBContextSource(namespace={self.namespace!r}, credentials=<redacted>)"


def _item_to_document(item: ContextItem, namespace: str) -> Dict[str, Any]:
    return {
        "_id": _document_id(namespace, item.item_id),
        "namespace": namespace,
        "record_type": "context_item",
        "item_id": item.item_id,
        "content": item.content,
        "kind": item.kind.value,
        "role": item.role.value,
        "original_order": item.original_order,
        "compressible": item.compressible,
        "required": item.required,
        "relevance": item.relevance,
        "recency": item.recency,
        "priority": item.priority,
        "source": item.source,
        "metadata": _scrub_sensitive(item.metadata),
    }


def _document_to_item(document: Mapping[str, Any]) -> ContextItem:
    try:
        return ContextItem(
            item_id=str(document["item_id"]),
            content=str(document.get("content", "")),
            kind=ContextKind(str(document.get("kind", ContextKind.GENERAL.value))),
            role=ContextRole(str(document.get("role", ContextRole.RAG.value))),
            original_order=int(document.get("original_order", 0)),
            compressible=bool(document.get("compressible", True)),
            required=bool(document.get("required", False)),
            relevance=float(document["relevance"])
            if document.get("relevance") is not None
            else None,
            recency=float(document.get("recency", 0.0)),
            priority=float(document.get("priority", 0.0)),
            source=str(document.get("source", "mongodb:store")),
            metadata=document.get("metadata", {})
            if isinstance(document.get("metadata", {}), Mapping)
            else {},
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MongoDBIntegrationError(
            f"MongoDB context document is malformed ({type(exc).__name__})"
        ) from None


def _scrub_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "<redacted>" if _SENSITIVE_KEY_RE.search(str(key)) else _scrub_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub_sensitive(item) for item in value]
    return _json_safe(value)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _validated_name(value: str, label: str) -> str:
    if not value or not _NAME_RE.fullmatch(value) or value.startswith("system."):
        raise ValueError(f"invalid MongoDB {label}")
    return value


def _validated_namespace(value: str) -> str:
    if not value or len(value) > 200 or "\x00" in value:
        raise ValueError("invalid MongoDB context namespace")
    return value


def _document_id(namespace: str, item_id: str) -> str:
    if not item_id or len(item_id) > 500 or "\x00" in item_id:
        raise ValueError("invalid MongoDB context item ID")
    return namespace + ":" + item_id


def _bounded_limit(value: int) -> int:
    if not 1 <= value <= 100:
        raise ValueError("MongoDB retrieval limit must be between 1 and 100")
    return value


def _bounded_query(value: str) -> str:
    if not value.strip() or len(value) > 500:
        raise ValueError("MongoDB retrieval query must contain 1-500 characters")
    return value


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _raise_sanitized(operation: str, exc: Exception) -> None:
    raise MongoDBIntegrationError(f"MongoDB {operation} failed ({type(exc).__name__})") from None


__all__ = [
    "MongoDBContextSource",
    "MongoDBContextStore",
    "MongoDBIntegrationError",
]
