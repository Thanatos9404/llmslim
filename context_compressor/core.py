"""Core compression engine.

This module ties together sentence splitting, semantic chunking,
extractive ranking, and budget-aware selection into the main
:func:`compress` function and :class:`ContextCompressor` class.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from .chunking import Chunk, semantic_chunk
from .embeddings import EmbeddingBackend, get_default_backend
from .ranking import score_chunk_sentences
from .tokenization import split_paragraphs, split_sentences
from .tokens import count_tokens

# Below this many tokens, compression overhead isn't worth it and the
# original text is returned unchanged.
DEFAULT_MIN_TOKENS_FOR_COMPRESSION = 40

_LIST_ITEM_RE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s)")


@dataclass
class ChunkResult:
    """Per-chunk compression detail, useful for debugging and analytics."""

    text: str
    original_tokens: int
    compressed_tokens: int
    sentences_total: int
    sentences_kept: int


@dataclass
class CompressionResult:
    """The result of compressing a piece of text.

    The compressed text is available both as ``.compressed_text`` and via
    ``str(result)``, so it can often be dropped directly into an existing
    prompt-building pipeline.
    """

    original_text: str
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    target_ratio: float
    sentences_total: int
    sentences_kept: int
    num_chunks: int
    backend: str = ""
    chunk_results: List[ChunkResult] = field(default_factory=list, repr=False)

    @property
    def actual_ratio(self) -> float:
        """Fraction of original tokens retained (lower = more compression)."""
        if self.original_tokens == 0:
            return 1.0
        return self.compressed_tokens / self.original_tokens

    @property
    def reduction_percent(self) -> float:
        """Percentage reduction in token count."""
        return round((1 - self.actual_ratio) * 100, 1)

    @property
    def tokens_saved(self) -> int:
        return self.original_tokens - self.compressed_tokens

    def summary(self) -> str:
        """A human-readable summary of the compression result."""
        target_reduction = round((1 - self.target_ratio) * 100, 1)
        return (
            f"Original tokens : {self.original_tokens}\n"
            f"Compressed tokens: {self.compressed_tokens}\n"
            f"Reduction        : {self.reduction_percent}% (target ~{target_reduction}%)\n"
            f"Sentences kept   : {self.sentences_kept}/{self.sentences_total}\n"
            f"Chunks           : {self.num_chunks}\n"
            f"Embedding backend: {self.backend}"
        )

    def __str__(self) -> str:
        return self.compressed_text


class ContextCompressor:
    """Compresses text via semantic chunking + extractive sentence ranking.

    Example:
        >>> compressor = ContextCompressor()
        >>> result = compressor.compress(long_text, target_ratio=0.5)
        >>> print(result.compressed_text)
        >>> print(result.summary())

    Args:
        embedding_backend: Custom :class:`EmbeddingBackend`. Defaults to
            :func:`get_default_backend` (sentence-transformers if
            available, otherwise TF-IDF).
        max_chunk_tokens: Soft token cap per semantic chunk.
        similarity_threshold: Cosine similarity below which a new chunk
            is started. Lower values create fewer, larger chunks.
        min_tokens_for_compression: Texts at or below this token count
            are returned unchanged.
        weights: Optional overrides for ranking weights -- see
            ``context_compressor.ranking.DEFAULT_WEIGHTS``.
        preserve_patterns: Optional list of regex strings; any sentence
            matching one of these is always retained (e.g.
            ``[r"API_KEY", r"^System:"]``).
    """

    def __init__(
        self,
        embedding_backend: Optional[EmbeddingBackend] = None,
        max_chunk_tokens: int = 300,
        similarity_threshold: float = 0.35,
        min_tokens_for_compression: int = DEFAULT_MIN_TOKENS_FOR_COMPRESSION,
        weights: Optional[Dict[str, float]] = None,
        preserve_patterns: Optional[Sequence[str]] = None,
    ):
        self.backend = embedding_backend or get_default_backend()
        self.max_chunk_tokens = max_chunk_tokens
        self.similarity_threshold = similarity_threshold
        self.min_tokens_for_compression = min_tokens_for_compression
        self.weights = weights
        self.preserve_patterns = list(preserve_patterns or [])

    def compress(
        self,
        text: str,
        target_ratio: float = 0.5,
        query: Optional[str] = None,
    ) -> CompressionResult:
        """Compress ``text``, retaining approximately ``target_ratio`` of its tokens.

        Args:
            text: The prompt or document to compress.
            target_ratio: Fraction of original tokens to retain
                (e.g. ``0.5`` keeps ~50%, i.e. a ~50% reduction).
                Must be in ``(0, 1]``.
            query: Optional query string. When provided, sentences more
                similar to the query are favored -- ideal for compressing
                retrieved documents in a RAG pipeline.

        Returns:
            A :class:`CompressionResult`.
        """
        if not (0.0 < target_ratio <= 1.0):
            raise ValueError("target_ratio must be in the range (0, 1]")

        original_tokens = count_tokens(text)

        if original_tokens <= self.min_tokens_for_compression:
            return self._passthrough(text, original_tokens, target_ratio, sentences_total=0)

        paragraphs = split_paragraphs(text)
        all_sentences: List[str] = []
        para_end_indices: List[int] = []
        for paragraph in paragraphs:
            sentences = split_sentences(paragraph)
            if not sentences:
                continue
            all_sentences.extend(sentences)
            para_end_indices.append(len(all_sentences))

        if len(all_sentences) <= 1:
            return self._passthrough(text, original_tokens, target_ratio, sentences_total=len(all_sentences))

        embeddings, query_embedding = self._encode(all_sentences, query)

        chunks = semantic_chunk(
            all_sentences,
            embeddings,
            max_chunk_tokens=self.max_chunk_tokens,
            similarity_threshold=self.similarity_threshold,
        )

        kept_mask = np.zeros(len(all_sentences), dtype=bool)
        chunk_results: List[ChunkResult] = []

        for chunk in chunks:
            chunk_embeddings = embeddings[chunk.sentence_indices]
            scored = score_chunk_sentences(
                chunk,
                chunk_embeddings,
                query_embedding=query_embedding,
                weights=self.weights,
                preserve_patterns=self.preserve_patterns,
            )
            kept_local = self._select_for_chunk(scored, chunk.token_counts, target_ratio)

            for local_idx in kept_local:
                kept_mask[chunk.sentence_indices[local_idx]] = True

            kept_tokens = sum(chunk.token_counts[i] for i in kept_local)
            chunk_results.append(
                ChunkResult(
                    text=" ".join(chunk.sentences[i] for i in sorted(kept_local)),
                    original_tokens=chunk.total_tokens,
                    compressed_tokens=kept_tokens,
                    sentences_total=len(chunk.sentences),
                    sentences_kept=len(kept_local),
                )
            )

        compressed_text = self._reassemble(all_sentences, kept_mask, para_end_indices)
        compressed_tokens = count_tokens(compressed_text)

        return CompressionResult(
            original_text=text,
            compressed_text=compressed_text,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            target_ratio=target_ratio,
            sentences_total=len(all_sentences),
            sentences_kept=int(kept_mask.sum()),
            num_chunks=len(chunks),
            backend=self.backend.name,
            chunk_results=chunk_results,
        )

    def _passthrough(self, text: str, original_tokens: int, target_ratio: float, sentences_total: int) -> CompressionResult:
        return CompressionResult(
            original_text=text,
            compressed_text=text,
            original_tokens=original_tokens,
            compressed_tokens=original_tokens,
            target_ratio=target_ratio,
            sentences_total=sentences_total,
            sentences_kept=sentences_total,
            num_chunks=0,
            backend=self.backend.name,
        )

    def _encode(self, sentences: List[str], query: Optional[str]):
        """Encode sentences (and optionally a query) with a single, consistent vector space."""
        texts = list(sentences)
        if query:
            texts.append(query)

        encoded = np.asarray(self.backend.encode(texts))

        if query:
            return encoded[:-1], encoded[-1]
        return encoded, None

    @staticmethod
    def _select_for_chunk(scored: List[Dict], token_counts: List[int], target_ratio: float) -> set:
        """Greedily select sentence indices for a chunk within its token budget."""
        total_tokens = sum(token_counts)
        target_tokens = max(1, round(total_tokens * target_ratio))

        must_keep = [s for s in scored if s["must_keep"]]
        optional = sorted(
            (s for s in scored if not s["must_keep"]),
            key=lambda s: s["score"],
            reverse=True,
        )

        selected = {s["index"] for s in must_keep}
        used_tokens = sum(token_counts[i] for i in selected)

        if used_tokens > target_tokens:
            # Too many must-keep sentences for the budget: keep the
            # highest-scoring ones until we exceed the budget, but always
            # keep at least one sentence.
            must_sorted = sorted(must_keep, key=lambda s: s["score"], reverse=True)
            selected = set()
            used_tokens = 0
            for s in must_sorted:
                if not selected or used_tokens + token_counts[s["index"]] <= target_tokens:
                    selected.add(s["index"])
                    used_tokens += token_counts[s["index"]]
        else:
            for s in optional:
                if used_tokens >= target_tokens:
                    break
                if used_tokens + token_counts[s["index"]] <= target_tokens:
                    selected.add(s["index"])
                    used_tokens += token_counts[s["index"]]

        if not selected:
            best = max(scored, key=lambda s: s["score"])
            selected.add(best["index"])

        return selected

    @staticmethod
    def _reassemble(sentences: List[str], kept_mask: np.ndarray, para_end_indices: List[int]) -> str:
        """Rebuild paragraphs from kept sentences, preserving list formatting."""
        paragraphs_out: List[str] = []
        start = 0
        for end in para_end_indices:
            kept_sentences = [s for s, keep in zip(sentences[start:end], kept_mask[start:end]) if keep]
            start = end
            if not kept_sentences:
                continue
            if len(kept_sentences) > 1 and all(_LIST_ITEM_RE.match(s) for s in kept_sentences):
                paragraphs_out.append("\n".join(kept_sentences))
            else:
                paragraphs_out.append(" ".join(kept_sentences))
        return "\n\n".join(paragraphs_out)


_default_compressor: Optional[ContextCompressor] = None


def _get_default_compressor() -> ContextCompressor:
    global _default_compressor
    if _default_compressor is None:
        _default_compressor = ContextCompressor()
    return _default_compressor


def compress(
    text: str,
    target_ratio: float = 0.5,
    query: Optional[str] = None,
    **kwargs,
) -> CompressionResult:
    """Compress ``text``, retaining approximately ``target_ratio`` of its tokens.

    This is the main entry point for the library -- a single function
    call that performs semantic chunking, extractive ranking, and
    reassembly.

    Args:
        text: The prompt or document to compress.
        target_ratio: Fraction of original tokens to retain (e.g. ``0.5``
            for a ~50% reduction, ``0.3`` for a ~70% reduction).
        query: Optional query string for relevance-aware compression
            (useful for RAG contexts).
        **kwargs: Passed to :class:`ContextCompressor` if provided (e.g.
            ``max_chunk_tokens``, ``similarity_threshold``,
            ``preserve_patterns``). If no kwargs are given, a shared
            default compressor instance is reused for efficiency.

    Returns:
        A :class:`CompressionResult` with ``.compressed_text``,
        ``.reduction_percent``, and other statistics.

    Example:
        >>> from context_compressor import compress
        >>> result = compress(my_long_prompt, target_ratio=0.5)
        >>> send_to_llm(result.compressed_text)
        >>> print(f"Saved {result.tokens_saved} tokens ({result.reduction_percent}%)")
    """
    compressor = ContextCompressor(**kwargs) if kwargs else _get_default_compressor()
    return compressor.compress(text, target_ratio=target_ratio, query=query)
