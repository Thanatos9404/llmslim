"""Deterministic, experimental lexical retrieval for model-facing tool plans.

This module is intentionally separate from :mod:`llmslim.tools`.  It never
changes a tool contract, does not dereference schema references, and does not
use annotations or ``_meta`` as retrieval evidence.  A returned ranking is an
advisory model-facing view; callers must hydrate the authoritative raw schema
before execution.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .tools import ToolSchema, _coerce_tool, fingerprint_tool_schema

_TOKEN_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)
_MAX_DESCRIPTION_TOKENS = 160
_MAX_SCHEMA_TOKENS = 120
_MAX_RETRIEVAL_FIELD_CHARS = 4_096


@dataclass(frozen=True)
class RetrievalHit:
    """A deterministic experimental rank, with an immutable tool reference."""

    tool: ToolSchema
    score: float
    rank: int


@dataclass(frozen=True)
class RetrievalIndexInfo:
    strategy: str
    catalog_fingerprint: str
    tool_count: int
    cache_hit: bool
    fields: Tuple[str, ...]
    metadata_policy: str


def normalize_text(text: str) -> Tuple[str, ...]:
    """NFKC/casefold lexical normalization with identifier-boundary splitting."""
    bounded = unicodedata.normalize("NFKC", text)
    bounded = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", bounded)
    bounded = re.sub(r"[_./:-]+", " ", bounded).casefold()
    return tuple(_TOKEN_RE.findall(bounded))


def _schema_terms(value: object) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            # Schema-only text is bounded.  ``examples`` and arbitrary vendor
            # extensions often contain untrusted payloads and are not evidence.
            if key in {"title", "description", "properties", "required", "enum", "type", "format"}:
                yield from normalize_text(str(key))
                if isinstance(item, str):
                    yield from normalize_text(item[:_MAX_RETRIEVAL_FIELD_CHARS])
                elif key == "properties" and isinstance(item, Mapping):
                    for name, schema in item.items():
                        yield from normalize_text(str(name))
                        yield from _schema_terms(schema)
                elif isinstance(item, (Mapping, list)):
                    yield from _schema_terms(item)
            elif isinstance(item, (Mapping, list)):
                yield from _schema_terms(item)
    elif isinstance(value, list):
        for item in value:
            yield from _schema_terms(item)


def retrieval_document(tool: ToolSchema) -> Tuple[str, ...]:
    """Return bounded, non-authoritative index text from safe descriptive fields."""
    tokens: List[str] = []
    for value, limit in ((tool.name, 32), (tool.namespace or "", 16), (tool.title or "", 48)):
        tokens.extend(normalize_text(value)[:limit])
    # Descriptions are useful but capped so an unusually long description cannot
    # dominate the index.  _meta and annotations are always excluded.
    tokens.extend(
        normalize_text((tool.description or "")[:_MAX_RETRIEVAL_FIELD_CHARS])[
            :_MAX_DESCRIPTION_TOKENS
        ]
    )
    tokens.extend(list(_schema_terms(tool.input_schema or {}))[:_MAX_SCHEMA_TOKENS])
    return tuple(tokens)


def catalog_fingerprint(tools: Sequence[Union[ToolSchema, Mapping[str, object]]]) -> str:
    catalog = [_coerce_tool(tool) for tool in tools]
    payload = "\n".join(
        sorted("%s:%s" % (tool.tool_id, fingerprint_tool_schema(tool)) for tool in catalog)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LexicalToolRetriever:
    """Base class for deterministic, cacheable lexical tool retrievers."""

    strategy = "lexical"
    _cache: Dict[Tuple[str, str], "LexicalToolRetriever"] = {}

    def __init__(self, tools: Sequence[Union[ToolSchema, Mapping[str, object]]]) -> None:
        self.tools = tuple(_coerce_tool(tool) for tool in tools)
        if len({tool.tool_id for tool in self.tools}) != len(self.tools):
            raise ValueError("tool retrieval requires unique stable tool identities")
        self.documents = tuple(retrieval_document(tool) for tool in self.tools)
        self.info = RetrievalIndexInfo(
            self.strategy,
            catalog_fingerprint(self.tools),
            len(self.tools),
            False,
            ("name", "namespace", "title", "description", "input_schema"),
            "annotations_and_meta_excluded; bounded_descriptions_and_schema_text",
        )

    @classmethod
    def cached(
        cls, tools: Sequence[Union[ToolSchema, Mapping[str, object]]]
    ) -> "LexicalToolRetriever":
        fingerprint = catalog_fingerprint(tools)
        key = (cls.strategy, fingerprint)
        cached = cls._cache.get(key)
        if cached is not None:
            cached.info = RetrievalIndexInfo(
                cached.info.strategy,
                cached.info.catalog_fingerprint,
                cached.info.tool_count,
                True,
                cached.info.fields,
                cached.info.metadata_policy,
            )
            return cached
        retriever = cls(tools)
        cls._cache[key] = retriever
        return retriever

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()

    def score(self, query: str) -> Sequence[float]:
        raise NotImplementedError

    def rank(self, query: str, limit: Optional[int] = None) -> Tuple[RetrievalHit, ...]:
        scored = list(zip(self.tools, self.score(query)))
        scored.sort(key=lambda item: (-item[1], item[0].tool_id))
        if limit is not None:
            scored = scored[: max(0, limit)]
        return tuple(
            RetrievalHit(tool, float(score), rank + 1) for rank, (tool, score) in enumerate(scored)
        )


class TfidfToolRetriever(LexicalToolRetriever):
    """Local TF-IDF lexical baseline with a fixed, inspectable implementation."""

    strategy = "tfidf_v1"

    def __init__(self, tools: Sequence[Union[ToolSchema, Mapping[str, object]]]) -> None:
        super().__init__(tools)
        self.document_counts = tuple(Counter(document) for document in self.documents)
        self.document_frequency: Counter[str] = Counter()
        for document in self.documents:
            self.document_frequency.update(set(document))
        self.idf = {
            term: math.log((1.0 + len(self.documents)) / (1.0 + frequency)) + 1.0
            for term, frequency in self.document_frequency.items()
        }
        self.norms = tuple(
            math.sqrt(sum((count * self.idf[term]) ** 2 for term, count in document.items()))
            for document in self.document_counts
        )

    def score(self, query: str) -> Sequence[float]:
        query_counts = Counter(normalize_text(query))
        query_norm = math.sqrt(
            sum((count * self.idf.get(term, 0.0)) ** 2 for term, count in query_counts.items())
        )
        if not query_norm:
            return [0.0] * len(self.tools)
        scores: List[float] = []
        for document, norm in zip(self.document_counts, self.norms):
            dot = sum(
                query_counts[term] * document.get(term, 0) * self.idf.get(term, 0.0) ** 2
                for term in query_counts
            )
            scores.append(dot / (query_norm * norm) if norm else 0.0)
        return scores


class BM25ToolRetriever(LexicalToolRetriever):
    """Okapi BM25 baseline; parameters are intentionally fixed and reported."""

    strategy = "bm25_v1_k1_1.2_b_0.75"

    def __init__(
        self,
        tools: Sequence[Union[ToolSchema, Mapping[str, object]]],
        k1: float = 1.2,
        b: float = 0.75,
    ) -> None:
        self.k1, self.b = k1, b
        super().__init__(tools)
        self.document_counts = tuple(Counter(document) for document in self.documents)
        self.lengths = tuple(len(document) for document in self.documents)
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        frequencies: Counter[str] = Counter()
        for document in self.documents:
            frequencies.update(set(document))
        total = len(self.documents)
        self.idf = {
            term: math.log(1.0 + (total - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in frequencies.items()
        }

    def score(self, query: str) -> Sequence[float]:
        query_terms = set(normalize_text(query))
        scores: List[float] = []
        for document, length in zip(self.document_counts, self.lengths):
            score = 0.0
            for term in query_terms:
                tf = document.get(term, 0)
                if not tf:
                    continue
                denominator = tf + self.k1 * (1.0 - self.b + self.b * length / self.average_length)
                score += self.idf.get(term, 0.0) * tf * (self.k1 + 1.0) / denominator
            scores.append(score)
        return scores


__all__ = [
    "BM25ToolRetriever",
    "LexicalToolRetriever",
    "RetrievalHit",
    "RetrievalIndexInfo",
    "TfidfToolRetriever",
    "catalog_fingerprint",
    "normalize_text",
    "retrieval_document",
]
