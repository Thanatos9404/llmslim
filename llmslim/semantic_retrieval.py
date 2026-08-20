"""Optional, offline-only dense and hybrid tool retrieval.

This module has no import-time ML dependency and does not download models.  It
is strictly a model-facing ranking aid; authoritative tool schemas remain in
``llmslim.tools`` and are never changed, executed, or authorized here.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .tool_retrieval import RetrievalHit, catalog_fingerprint, normalize_text, retrieval_document
from .tools import ToolSchema, _coerce_tool

SEMANTIC_MODEL_ID = "intfloat/multilingual-e5-small"
SEMANTIC_MODEL_REVISION = "0e60b8d9d2166d80387f86e3b48ec9ced55f4d15"
SEMANTIC_REPRESENTATION_VERSION = "semantic_tool_text_v1"
SEMANTIC_NORMALIZATION = "l2_cosine_v1"


class SemanticDependencyError(RuntimeError):
    """Raised when the explicit optional semantic feature is unavailable."""


@dataclass(frozen=True)
class SemanticModelConfig:
    model_id: str = SEMANTIC_MODEL_ID
    revision: str = SEMANTIC_MODEL_REVISION
    representation_version: str = SEMANTIC_REPRESENTATION_VERSION
    normalization: str = SEMANTIC_NORMALIZATION
    device: str = "cpu"

    @property
    def identity(self) -> str:
        return "|".join(
            (
                self.model_id,
                self.revision,
                self.representation_version,
                self.normalization,
                self.device,
            )
        )


def _normalized(values: Sequence[float]) -> Tuple[float, ...]:
    length = math.sqrt(sum(value * value for value in values))
    if not length:
        return tuple(0.0 for _ in values)
    return tuple(value / length for value in values)


def semantic_tool_text(tool: ToolSchema) -> str:
    """Build bounded structured text without annotations, metadata, or raw blobs."""
    fields = [
        "namespace: " + " ".join(normalize_text(tool.namespace or ""))[:16],
        "tool: " + " ".join(normalize_text(tool.name))[:32],
        "title: " + " ".join(normalize_text(tool.title or ""))[:48],
        "description: " + " ".join(normalize_text((tool.description or "")[:4_096]))[:160],
        "parameters: " + " ".join(retrieval_document(tool))[:120],
    ]
    return "passage: " + " ".join(part for part in fields if not part.endswith(": "))


def semantic_query_text(query: str) -> str:
    """Use E5's retrieval query prefix with bounded Unicode-safe content."""
    return "query: " + " ".join(normalize_text(query)[:256])


class SentenceTransformerBackend:
    """Explicit local-cache SentenceTransformers backend; never contacts a hub."""

    def __init__(self, config: SemanticModelConfig = SemanticModelConfig()) -> None:
        self.config = config
        self._model: Any | None = None

    @property
    def identity(self) -> str:
        return self.config.identity

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise SemanticDependencyError(
                "Semantic retrieval is optional; install llmslim[semantic] and explicitly cache the pinned model."
            ) from exc
        try:
            self._model = SentenceTransformer(
                self.config.model_id,
                revision=self.config.revision,
                device=self.config.device,
                trust_remote_code=False,
                local_files_only=True,
            )
        except OSError as exc:
            raise SemanticDependencyError(
                "Pinned semantic model is not in the local Hugging Face cache; run the documented explicit setup command."
            ) from exc
        return self._model

    def encode(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        model = self._load()
        raw = model.encode(
            list(texts), normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        return tuple(_normalized(tuple(float(value) for value in row)) for row in raw)


class DenseToolRetriever:
    """Optional normalized-cosine retriever with safe, identity-keyed caching."""

    strategy = "dense_e5_small_v1"
    _cache: Dict[str, "DenseToolRetriever"] = {}

    def __init__(
        self,
        tools: Sequence[Union[ToolSchema, Mapping[str, object]]],
        backend: SentenceTransformerBackend,
    ) -> None:
        self.tools = tuple(_coerce_tool(tool) for tool in tools)
        if len({tool.tool_id for tool in self.tools}) != len(self.tools):
            raise ValueError("tool retrieval requires unique stable tool identities")
        self.backend = backend
        self.documents = tuple(semantic_tool_text(tool) for tool in self.tools)
        self.catalog_fingerprint = catalog_fingerprint(self.tools)
        self.cache_key = "|".join((self.strategy, self.catalog_fingerprint, backend.identity))
        started = time.perf_counter()
        self.embeddings = backend.encode(self.documents)
        self._query_vectors: Dict[str, Tuple[float, ...]] = {}
        try:
            import numpy as np

            self._matrix: object | None = np.asarray(self.embeddings, dtype="float32")
        except ImportError:  # numpy is a base dependency, retained as a safe fallback.
            self._matrix = None
        self.index_build_ms = (time.perf_counter() - started) * 1000
        self.embedding_dimension = len(self.embeddings[0]) if self.embeddings else 0
        self.embedding_memory_bytes = len(self.embeddings) * self.embedding_dimension * 8

    @classmethod
    def cached(
        cls,
        tools: Sequence[Union[ToolSchema, Mapping[str, object]]],
        backend: SentenceTransformerBackend,
    ) -> "DenseToolRetriever":
        probe = tuple(_coerce_tool(tool) for tool in tools)
        key = "|".join((cls.strategy, catalog_fingerprint(probe), backend.identity))
        if key not in cls._cache:
            cls._cache[key] = cls(probe, backend)
        return cls._cache[key]

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()

    def score(self, query: str) -> Sequence[float]:
        normalized_query = semantic_query_text(query)
        vector = self._query_vectors.get(normalized_query)
        if vector is None:
            vector = self.backend.encode((normalized_query,))[0]
            self._query_vectors[normalized_query] = vector
        if self._matrix is not None:
            import numpy as np

            return [float(value) for value in self._matrix @ np.asarray(vector, dtype="float32")]
        return [
            sum(left * right for left, right in zip(vector, document))
            for document in self.embeddings
        ]

    def rank(self, query: str, limit: Optional[int] = None) -> Tuple[RetrievalHit, ...]:
        scored = list(zip(self.tools, self.score(query)))
        scored.sort(key=lambda item: (-item[1], item[0].tool_id))
        if limit is not None:
            scored = scored[: max(0, limit)]
        return tuple(
            RetrievalHit(tool, float(score), rank + 1) for rank, (tool, score) in enumerate(scored)
        )


class HybridRRFToolRetriever:
    """Deterministic BM25+dense Reciprocal Rank Fusion without score mixing."""

    strategy = "bm25_dense_rrf_v1"

    def __init__(self, bm25: Any, dense: DenseToolRetriever, rrf_k: int = 60) -> None:
        self.bm25, self.dense, self.rrf_k = bm25, dense, rrf_k
        self.tools = dense.tools
        bm25_ids = tuple(tool.tool_id for tool in bm25.tools)
        dense_ids = tuple(tool.tool_id for tool in dense.tools)
        if bm25_ids != dense_ids:
            raise ValueError("hybrid fusion requires identically ordered catalogs")
        self.catalog_fingerprint = dense.catalog_fingerprint

    def score(self, query: str) -> Sequence[float]:
        ranks: List[Dict[str, int]] = []
        for retriever in (self.bm25, self.dense):
            ranks.append({hit.tool.tool_id: hit.rank for hit in retriever.rank(query)})
        return [
            sum(1.0 / (self.rrf_k + rank_map[tool.tool_id]) for rank_map in ranks)
            for tool in self.tools
        ]

    def rank(self, query: str, limit: Optional[int] = None) -> Tuple[RetrievalHit, ...]:
        scored = list(zip(self.tools, self.score(query)))
        scored.sort(key=lambda item: (-item[1], item[0].tool_id))
        if limit is not None:
            scored = scored[: max(0, limit)]
        return tuple(
            RetrievalHit(tool, float(score), rank + 1) for rank, (tool, score) in enumerate(scored)
        )


__all__ = [
    "DenseToolRetriever",
    "HybridRRFToolRetriever",
    "SEMANTIC_MODEL_ID",
    "SEMANTIC_MODEL_REVISION",
    "SEMANTIC_NORMALIZATION",
    "SEMANTIC_REPRESENTATION_VERSION",
    "SemanticDependencyError",
    "SemanticModelConfig",
    "SentenceTransformerBackend",
    "semantic_query_text",
    "semantic_tool_text",
]
