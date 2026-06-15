"""Sentence scoring for extractive selection.

Each sentence in a chunk is scored on several signals and combined into
a single relevance score:

* **centrality** -- how representative the sentence is of the chunk's
  overall meaning (LexRank-style degree centrality over cosine
  similarity).
* **position** -- topic and concluding sentences (first/last in a chunk)
  tend to carry more information.
* **entity density** -- sentences mentioning named entities, numbers,
  emails, or URLs are more information-dense.
* **instruction signal** -- imperative/directive language ("must",
  "ensure", numbered steps, code spans) is boosted to preserve
  instruction fidelity.
* **query relevance** -- if a query is supplied (e.g. for RAG), cosine
  similarity to the query embedding is added.

A small set of high-confidence "critical directive" patterns (and any
sentence containing a code span, or matching a user-supplied
``preserve_patterns`` regex) are marked ``must_keep`` and are retained
whenever possible, regardless of score.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

import numpy as np

from .chunking import Chunk

# General instruction / directive language -- contributes to the
# continuous instruction score used for ranking.
_INSTRUCTION_PATTERNS = [
    r"\bmust\b",
    r"\bshould\b",
    r"\bplease\b",
    r"\bensure\b",
    r"\bmake sure\b",
    r"\bneed(?:s)? to\b",
    r"\brequire[sd]?\b",
    r"\balways\b",
    r"\bnever\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bimportant\b",
    r"\bnote that\b",
    r"\bremember\b",
    r"\bcritical\b",
    r"\?\s*$",
]
_INSTRUCTION_RE = re.compile("|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE | re.MULTILINE)

# High-confidence directive language -- these sentences are force-kept
# (subject to the chunk's token budget) to preserve instruction fidelity.
_CRITICAL_PATTERNS = [
    r"\bmust\b",
    r"\bnever\b",
    r"\balways\b",
    r"\brequired?\b",
    r"\bensure\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bcritical\b",
    r"^\s*(\d+[.)]|[-*+])\s",  # numbered or bulleted steps
]
_CRITICAL_RE = re.compile("|".join(_CRITICAL_PATTERNS), re.IGNORECASE | re.MULTILINE)

_CODE_PATTERN = re.compile(r"```|`[^`\n]+`")

# Proxy for "named entities" without requiring a full NER model: capitalized
# multi-word spans, standalone numbers/percentages, emails, and URLs.
_ENTITY_PATTERN = re.compile(
    r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\b"
    r"|\b\d[\d,.]*%?\b"
    r"|\b[\w.+-]+@[\w-]+\.[\w.-]+\b"
    r"|https?://\S+"
)

DEFAULT_WEIGHTS: Dict[str, float] = {
    "centrality": 0.35,
    "position": 0.15,
    "entity": 0.15,
    "instruction": 0.25,
    "query": 0.35,
    "length_penalty": 0.20,
}


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1e-9
    return matrix / norms


def _cosine_matrix(embeddings: np.ndarray) -> np.ndarray:
    normalized = _normalize_rows(embeddings)
    return normalized @ normalized.T


def _centrality_scores(embeddings: np.ndarray) -> np.ndarray:
    n = len(embeddings)
    if n <= 1:
        return np.ones(n)
    similarity = _cosine_matrix(embeddings)
    np.fill_diagonal(similarity, 0.0)
    scores = similarity.sum(axis=1) / max(n - 1, 1)
    max_score = scores.max()
    if max_score > 0:
        scores = scores / max_score
    return scores


def _instruction_score(sentence: str) -> float:
    score = 0.0
    if _INSTRUCTION_RE.search(sentence):
        score += 0.6
    if _CODE_PATTERN.search(sentence):
        score += 0.6
    return min(score, 1.0)


def _entity_score(sentence: str) -> float:
    matches = _ENTITY_PATTERN.findall(sentence)
    words = max(len(sentence.split()), 1)
    return min((len(matches) / words) * 2.0, 1.0)


def _position_score(index: int, total: int) -> float:
    if total <= 1:
        return 1.0
    if index == 0 or index == total - 1:
        return 1.0
    return 0.4


def _length_penalty(sentence: str, min_words: int = 4) -> float:
    return 0.5 if len(sentence.split()) < min_words else 0.0


def _is_must_keep(sentence: str, preserve_res: Sequence["re.Pattern"]) -> bool:
    if _CODE_PATTERN.search(sentence):
        return True
    if _CRITICAL_RE.search(sentence):
        return True
    return any(pattern.search(sentence) for pattern in preserve_res)


def score_chunk_sentences(
    chunk: Chunk,
    embeddings: np.ndarray,
    query_embedding: Optional[np.ndarray] = None,
    weights: Optional[Dict[str, float]] = None,
    preserve_patterns: Optional[Sequence[str]] = None,
) -> List[Dict]:
    """Score every sentence in ``chunk`` for extractive selection.

    Args:
        chunk: The chunk to score.
        embeddings: Embeddings for the sentences in ``chunk``, in the
            same order, shape ``(len(chunk), dim)``.
        query_embedding: Optional embedding of a query (for RAG-style
            relevance-aware compression).
        weights: Override scoring weights. See :data:`DEFAULT_WEIGHTS`.
        preserve_patterns: Extra regex strings; any sentence matching one
            is force-kept (``must_keep``).

    Returns:
        A list of per-sentence score dictionaries (chunk-local
        ``index``, ``sentence`` text, combined ``score``, component
        scores, and a ``must_keep`` flag).
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    preserve_res = [re.compile(p, re.IGNORECASE) for p in (preserve_patterns or [])]

    centrality = _centrality_scores(embeddings)
    n = len(chunk.sentences)

    results: List[Dict] = []
    for i, sentence in enumerate(chunk.sentences):
        instruction = _instruction_score(sentence)
        entity = _entity_score(sentence)
        position = _position_score(i, n)
        penalty = _length_penalty(sentence)

        score = (
            weights["centrality"] * centrality[i]
            + weights["position"] * position
            + weights["entity"] * entity
            + weights["instruction"] * instruction
            - weights["length_penalty"] * penalty
        )

        query_similarity = None
        if query_embedding is not None:
            sim_matrix = _cosine_matrix(np.vstack([embeddings[i], query_embedding]))
            query_similarity = float(sim_matrix[0, 1])
            score += weights["query"] * max(query_similarity, 0.0)

        results.append(
            {
                "index": i,
                "sentence": sentence,
                "score": float(score),
                "centrality": float(centrality[i]),
                "instruction_score": instruction,
                "entity_score": entity,
                "query_similarity": query_similarity,
                "must_keep": _is_must_keep(sentence, preserve_res),
            }
        )

    return results
