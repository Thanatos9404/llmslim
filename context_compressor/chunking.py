"""Semantic chunking: group consecutive sentences into coherent chunks.

A new chunk is started whenever a sentence's embedding drifts too far
from the running topic centroid (a topic shift) or the chunk would
exceed a maximum token budget. This keeps each chunk focused on a single
idea, which makes per-chunk extractive ranking far more meaningful than
ranking sentences across an entire document at once.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

from .tokens import count_tokens


class Chunk:
    """A semantically coherent group of consecutive sentences."""

    __slots__ = ("sentence_indices", "sentences", "token_counts", "total_tokens")

    def __init__(self, sentence_indices: List[int], sentences: List[str], token_counts: List[int]):
        self.sentence_indices = sentence_indices
        self.sentences = sentences
        self.token_counts = token_counts
        self.total_tokens = sum(token_counts)

    def __len__(self) -> int:
        return len(self.sentence_indices)

    def __repr__(self) -> str:
        preview = self.sentences[0][:40] + "..." if self.sentences else ""
        return f"Chunk(n_sentences={len(self)}, tokens={self.total_tokens}, starts_with={preview!r})"


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def semantic_chunk(
    sentences: Sequence[str],
    embeddings: np.ndarray,
    max_chunk_tokens: int = 180,
    similarity_threshold: float = 0.35,
) -> List[Chunk]:
    """Group ``sentences`` into semantically coherent :class:`Chunk` objects.

    Args:
        sentences: Sentences in original document order.
        embeddings: Array of shape ``(len(sentences), dim)``.
        max_chunk_tokens: Soft cap on the token size of a chunk.
        similarity_threshold: Minimum cosine similarity to the running
            chunk centroid required to add a sentence to the current
            chunk. Lower values produce fewer, larger chunks.

    Returns:
        List of :class:`Chunk` objects covering every input sentence,
        in original order.
    """
    if not sentences:
        return []

    token_counts = [count_tokens(s) for s in sentences]

    chunks: List[Chunk] = []
    current_indices: List[int] = [0]
    current_embs: List[np.ndarray] = [embeddings[0]]
    current_tokens = token_counts[0]

    for i in range(1, len(sentences)):
        sent_tokens = token_counts[i]
        centroid = np.mean(current_embs, axis=0)
        similarity = _cosine(embeddings[i], centroid)

        starts_new_chunk = (
            similarity < similarity_threshold
            or current_tokens + sent_tokens > max_chunk_tokens
        )

        if starts_new_chunk and current_indices:
            chunks.append(_build_chunk(current_indices, sentences, token_counts))
            current_indices = [i]
            current_embs = [embeddings[i]]
            current_tokens = sent_tokens
        else:
            current_indices.append(i)
            current_embs.append(embeddings[i])
            current_tokens += sent_tokens

    if current_indices:
        chunks.append(_build_chunk(current_indices, sentences, token_counts))

    return chunks


def _build_chunk(indices: List[int], sentences: Sequence[str], token_counts: List[int]) -> Chunk:
    chunk_sentences = [sentences[i] for i in indices]
    chunk_token_counts = [token_counts[i] for i in indices]
    return Chunk(list(indices), chunk_sentences, chunk_token_counts)
