"""Core compression engine.

This module ties together sentence splitting, semantic chunking,
extractive ranking, and budget-aware selection into the main
:func:`compress` function and :class:`ContextCompressor` class.
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import numpy as np

from .chunking import Chunk, semantic_chunk
from .embeddings import EmbeddingBackend, get_backend
from .ranking import score_chunk_sentences
from .tokenization import split_paragraphs, split_sentences
from .tokens import count_tokens, get_active_token_counter_name

# Below this many tokens, compression overhead isn't worth it and the
# original text is returned unchanged.
DEFAULT_MIN_TOKENS_FOR_COMPRESSION = 40

_LIST_ITEM_RE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s)")


class ContextRole(str, Enum):
    """Provenance / trust role for the text being compressed.

    The role controls how aggressively imperative language is protected
    during selection.  See ``docs/phase-1/IMPLEMENTATION_PLAN.md`` §3 for
    the full trust model and §13 for its explicit security limitations.

    * ``SYSTEM`` / ``DEVELOPER`` -- trusted developer-authored
      instructions.  Safety-critical directives may be hard-locked
      (Priority 4) and force-retained.
    * ``USER`` -- the end user's own turn.  Imperative wording may reach
      Priority 3 but not the safety-critical Priority 4 tier.
    * ``ASSISTANT`` / ``TOOL`` / ``RAG`` -- untrusted content (prior model
      output, tool/function results, retrieved documents).  Priority is
      capped so that injected imperatives cannot hijack the force-kept
      budget.
    * ``GENERAL`` -- default.  Preserves v0.3.0 behaviour exactly for
      callers that do not specify a role.

    ``ContextRole`` subclasses ``str``, so the enum members compare equal
    to their string values and either form may be passed anywhere a role
    is accepted.
    """

    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    RAG = "rag"
    GENERAL = "general"


# Modes that imply a provenance role when ``context_role`` is not given
# explicitly.  Only unambiguous mappings are included.
_MODE_TO_ROLE = {
    "rag": ContextRole.RAG,
    "system": ContextRole.SYSTEM,
}


def _role_str(context_role: Union[ContextRole, str, None]) -> str:
    """Return the canonical lowercase string value for a role.

    Uses the enum's ``.value`` for ``ContextRole`` members, because
    ``str(ContextRole.GENERAL)`` yields ``"ContextRole.GENERAL"`` on
    Python 3.11+ rather than the underlying ``"general"`` value.
    """
    if context_role is None:
        return ""
    value = getattr(context_role, "value", context_role)
    return str(value).lower()


def _resolve_context_role(
    context_role: Optional[Union[ContextRole, str]],
    instance_role: Union[ContextRole, str],
    mode: Optional[str],
) -> str:
    """Resolve the effective provenance role (returns a lowercase string).

    Precedence:
      1. explicit ``context_role`` argument (string or enum),
      2. instance ``context_role`` if it is not GENERAL,
      3. inferred from ``mode`` (``"rag"`` -> RAG, ``"system"`` -> SYSTEM),
      4. GENERAL (legacy behaviour).
    """
    if context_role is not None:
        return _role_str(context_role)

    instance = _role_str(instance_role)
    if instance and instance != ContextRole.GENERAL.value:
        return instance

    if mode is not None:
        mapped = _MODE_TO_ROLE.get(str(mode).lower())
        if mapped is not None:
            return mapped.value

    return ContextRole.GENERAL.value


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

    .. versionchanged:: 0.3.0
       Added optional fields: ``content_type``, ``content_confidence``,
       ``mode``, ``elapsed_ms``, ``instructions_found``,
       ``instructions_kept``, ``entities_found``, ``entities_kept``,
       ``structure_preserved``.
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

    # --- v0.3 optional telemetry (all default None for backwards compat) ---
    content_type: Optional[str] = None
    content_confidence: Optional[float] = None
    mode: Optional[str] = None
    elapsed_ms: Optional[float] = None
    instructions_found: Optional[int] = None
    instructions_kept: Optional[int] = None
    entities_found: Optional[int] = None
    entities_kept: Optional[int] = None
    structure_preserved: Optional[bool] = None
    rewrite_metadata: Optional[Any] = None

    # --- Phase 1 (v0.3.1): token counter transparency ---
    # Which token counter produced the counts on this result:
    # "tiktoken" (exact) or "heuristic" (~4 chars/token fallback).
    token_counter_used: str = "tiktoken"

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

    def detailed_summary(self) -> str:
        """Extended summary including v0.3 telemetry when available."""
        parts = [self.summary()]
        if self.content_type is not None:
            confidence = f" ({self.content_confidence:.0%})" if self.content_confidence else ""
            parts.append(f"Content type     : {self.content_type}{confidence}")
        if self.mode is not None:
            parts.append(f"Mode             : {self.mode}")
        if self.elapsed_ms is not None:
            parts.append(f"Elapsed          : {self.elapsed_ms:.1f}ms")
        if self.instructions_found is not None:
            parts.append(
                f"Instructions     : {self.instructions_kept}/{self.instructions_found} kept"
            )
        if self.entities_found is not None:
            parts.append(f"Entities         : {self.entities_kept}/{self.entities_found} kept")
        if self.structure_preserved is not None:
            parts.append(f"Structure kept   : {self.structure_preserved}")
        if self.rewrite_metadata is not None:
            rm = self.rewrite_metadata
            parts.append(
                f"Optimization     : strategy={getattr(rm, 'strategy', None)}, "
                f"accepted={getattr(rm, 'accepted', None)}, "
                f"provider={getattr(rm, 'provider_name', None)}"
            )
            parts.append(
                f"Validation       : sim={getattr(rm, 'similarity_score', 0.0):.3f}, "
                f"inst={getattr(rm, 'instruction_retention', 0.0):.0%}, "
                f"ent={getattr(rm, 'entity_retention', 0.0):.0%}"
            )
        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise all fields to a plain dictionary."""
        d: Dict[str, Any] = {
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "target_ratio": self.target_ratio,
            "actual_ratio": round(self.actual_ratio, 4),
            "reduction_percent": self.reduction_percent,
            "tokens_saved": self.tokens_saved,
            "sentences_total": self.sentences_total,
            "sentences_kept": self.sentences_kept,
            "num_chunks": self.num_chunks,
            "backend": self.backend,
        }
        for key in (
            "content_type",
            "content_confidence",
            "mode",
            "elapsed_ms",
            "instructions_found",
            "instructions_kept",
            "entities_found",
            "entities_kept",
            "structure_preserved",
        ):
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        if self.rewrite_metadata is not None:
            d["rewrite_metadata"] = (
                self.rewrite_metadata.to_dict()
                if hasattr(self.rewrite_metadata, "to_dict")
                else self.rewrite_metadata
            )
        return d

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
        embedding_backend: Custom :class:`EmbeddingBackend` or string name
            ('tfidf' / 'fast' / 'semantic' / 'sentence-transformers').
            Defaults to fast TF-IDF backend.
        max_chunk_tokens: Soft token cap per semantic chunk.
        similarity_threshold: Cosine similarity below which a new chunk
            is started. Lower values create fewer, larger chunks.
        min_tokens_for_compression: Texts at or below this token count
            are returned unchanged.
        weights: Optional overrides for ranking weights -- see
            ``llmslim.ranking.DEFAULT_WEIGHTS``.
        preserve_patterns: Optional list of regex strings; any sentence
            matching one of these is always retained (e.g.
            ``[r"API_KEY", r"^System:"]``).
        mode: Optimization mode name (e.g. ``"balanced"``,
            ``"quality"``, ``"aggressive"``).  When set, mode-specific
            ranking weights are applied.  Use ``"auto"`` together with
            ``detect_content=True`` for fully automatic optimisation.
        detect_content: When ``True``, analyse the input to detect its
            content type and populate telemetry fields on the result.
        context_role: Default provenance/trust role for text compressed by
            this instance (``ContextRole`` or an equivalent string such as
            ``"system"``, ``"rag"``, ``"tool"``).  Untrusted roles
            (``rag``/``tool``/``assistant``) are priority-capped so that
            injected imperative language cannot hijack the force-kept tier.
            Defaults to ``ContextRole.GENERAL`` (legacy v0.3.0 behaviour).
            May be overridden per call in :meth:`compress`.
    """

    def __init__(
        self,
        embedding_backend: Optional[EmbeddingBackend | str] = None,
        max_chunk_tokens: int = 300,
        similarity_threshold: Optional[float] = None,
        min_tokens_for_compression: int = DEFAULT_MIN_TOKENS_FOR_COMPRESSION,
        weights: Optional[Dict[str, float]] = None,
        preserve_patterns: Optional[Sequence[str]] = None,
        mode: Optional[str] = None,
        detect_content: bool = False,
        context_role: Union[ContextRole, str] = ContextRole.GENERAL,
    ):
        self.backend = get_backend(embedding_backend)
        if similarity_threshold is None:
            similarity_threshold = 0.10 if self.backend.name == "tfidf" else 0.35
        self.max_chunk_tokens = max_chunk_tokens
        self.similarity_threshold = similarity_threshold
        self.min_tokens_for_compression = min_tokens_for_compression
        self.weights = weights
        self.preserve_patterns = list(preserve_patterns or [])
        self.mode = mode
        self.detect_content = detect_content
        self.context_role = context_role

    def compress(
        self,
        text: str,
        target_ratio: float = 0.5,
        query: Optional[str] = None,
        strategy: str = "extractive",
        provider: Optional[Any] = None,
        required_keywords: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        template_name: Optional[str] = None,
        context_role: Optional[Union[ContextRole, str]] = None,
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
            strategy: Optimization strategy ("extractive", "rewrite", "hybrid").
            provider: Optional BaseRewriteProvider or callable for rewrite/hybrid strategies.
            required_keywords: Optional list of keywords required in the output.
            constraints: Optional list of prompt constraints.
            template_name: Optional template override.
            context_role: Optional provenance/trust role override for this
                call (``ContextRole`` or string).  When ``None`` the
                instance ``context_role`` (or ``mode``) is used.  Untrusted
                roles (``rag``/``tool``/``assistant``) are priority-capped
                so injected imperatives cannot hijack the force-kept tier.

        Returns:
            A :class:`CompressionResult`.
        """
        if strategy not in ("extractive", "rewrite", "hybrid"):
            raise ValueError(
                f"Unknown strategy '{strategy}'. Supported strategies: 'extractive', 'rewrite', 'hybrid'"
            )

        if strategy in ("rewrite", "hybrid") and provider is None:
            raise ValueError(
                f"Strategy '{strategy}' requires a provider. "
                "Pass a BaseRewriteProvider instance or a callable via `provider=` parameter."
            )

        if not (0.0 < target_ratio <= 1.0):
            raise ValueError("target_ratio must be in the range (0, 1]")

        t_start = time.perf_counter()

        # Resolve provenance role once for this call (explicit arg > instance
        # role > mode inference > GENERAL).
        effective_role = _resolve_context_role(context_role, self.context_role, self.mode)

        if strategy == "rewrite":
            return self._compress_rewrite(
                text=text,
                target_ratio=target_ratio,
                provider=provider,
                required_keywords=required_keywords,
                constraints=constraints,
                template_name=template_name,
                t_start=t_start,
            )

        if strategy == "hybrid":
            extractive_res = self._compress_extractive(
                text=text,
                target_ratio=target_ratio,
                query=query,
                t_start=t_start,
                context_role=effective_role,
            )
            return self._compress_rewrite(
                text=extractive_res.compressed_text,
                target_ratio=target_ratio,
                provider=provider,
                required_keywords=required_keywords,
                constraints=constraints,
                template_name=template_name,
                t_start=t_start,
                strategy_label="hybrid",
                original_text_override=text,
                initial_result=extractive_res,
            )

        return self._compress_extractive(
            text=text,
            target_ratio=target_ratio,
            query=query,
            t_start=t_start,
            context_role=effective_role,
        )

    def _compress_rewrite(
        self,
        text: str,
        target_ratio: float,
        provider: Any,
        required_keywords: Optional[List[str]],
        constraints: Optional[List[str]],
        template_name: Optional[str],
        t_start: float,
        strategy_label: str = "rewrite",
        original_text_override: Optional[str] = None,
        initial_result: Optional[CompressionResult] = None,
    ) -> CompressionResult:
        from .analysis import analyze
        from .rewrite import BaseRewriteProvider, CallableProvider, RewriteEngine, RewriteMetadata

        if isinstance(provider, BaseRewriteProvider):
            prov_obj = provider
        elif callable(provider):
            prov_obj = CallableProvider(provider)
        else:
            raise TypeError(
                f"Expected BaseRewriteProvider or callable for provider, got {type(provider).__name__}"
            )

        profile = analyze(text) if self.detect_content else None
        content_type_str = profile.content_type.value if profile else None

        engine = RewriteEngine(provider=prov_obj)
        res = engine.rewrite(
            text=text,
            target_ratio=target_ratio,
            content_type=content_type_str,
            template_name=template_name,
            constraints=constraints,
            required_keywords=required_keywords,
        )

        orig_text = original_text_override or text
        orig_tokens = count_tokens(orig_text)
        comp_tokens = count_tokens(res.rewritten_text)
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

        meta = RewriteMetadata(
            strategy=strategy_label,
            accepted=res.accepted,
            fallback_used=res.fallback_used,
            provider_name=res.provider_used,
            template_name=res.template_used,
            similarity_score=res.validation.similarity_score,
            instruction_retention=res.validation.instruction_retention,
            entity_retention=res.validation.entity_retention,
            rewrite_latency_ms=res.rewrite_latency_ms,
            validation_scores=res.validation.scores,
            failure_reasons=list(res.validation.failure_reasons),
            error_message=res.error_message,
        )

        return CompressionResult(
            original_text=orig_text,
            compressed_text=res.rewritten_text,
            original_tokens=orig_tokens,
            compressed_tokens=comp_tokens,
            target_ratio=target_ratio,
            sentences_total=initial_result.sentences_total if initial_result else 0,
            sentences_kept=initial_result.sentences_kept if initial_result else 0,
            num_chunks=initial_result.num_chunks if initial_result else 0,
            backend=self.backend.name,
            chunk_results=initial_result.chunk_results if initial_result else [],
            content_type=content_type_str,
            content_confidence=profile.confidence if profile else None,
            mode=self.mode,
            elapsed_ms=elapsed_ms,
            rewrite_metadata=meta,
            token_counter_used=get_active_token_counter_name(),
        )

    def _compress_extractive(
        self,
        text: str,
        target_ratio: float,
        query: Optional[str],
        t_start: float,
        context_role: str = "general",
    ) -> CompressionResult:
        profile = None
        resolved_mode = None
        effective_weights = self.weights

        if self.detect_content or self.mode is not None:
            from .analysis import analyze
            from .modes import resolve_mode

            if self.detect_content:
                profile = analyze(text)
            resolved_mode = resolve_mode(self.mode, profile)

            # Mode sets effective weights: merge mode weights under
            # caller-specified weights (caller wins on conflicts).
            if resolved_mode.ranking_weights:
                merged = dict(resolved_mode.ranking_weights)
                if self.weights:
                    merged.update(self.weights)
                effective_weights = merged

            # Apply mode's default target ratio when caller uses 0.5.
            if target_ratio == 0.5 and resolved_mode.target_ratio_default != 0.5:
                target_ratio = resolved_mode.target_ratio_default

        original_tokens = count_tokens(text)

        if original_tokens <= self.min_tokens_for_compression:
            return self._passthrough(
                text,
                original_tokens,
                target_ratio,
                sentences_total=0,
                profile=profile,
                resolved_mode=resolved_mode,
                t_start=t_start,
            )

        # --- v0.3: structured content fast-path ---
        if (
            profile is not None
            and profile.has_structure
            and resolved_mode is not None
            and resolved_mode.preserve_structure
        ):
            structured_result = self._try_structured(
                text,
                target_ratio,
                profile,
                resolved_mode,
                original_tokens,
                t_start,
            )
            if structured_result is not None:
                return structured_result

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
            return self._passthrough(
                text,
                original_tokens,
                target_ratio,
                sentences_total=len(all_sentences),
                profile=profile,
                resolved_mode=resolved_mode,
                t_start=t_start,
            )

        embeddings, query_embedding = self._encode(all_sentences, query)

        chunks = semantic_chunk(
            all_sentences,
            embeddings,
            max_chunk_tokens=self.max_chunk_tokens,
            similarity_threshold=self.similarity_threshold,
        )

        kept_mask = np.zeros(len(all_sentences), dtype=bool)
        sentence_token_counts = [count_tokens(s) for s in all_sentences]
        target_ratio_eff = target_ratio + 0.03 if target_ratio == 0.5 else target_ratio
        global_target_tokens = max(1, round(original_tokens * target_ratio_eff))
        all_chunk_scored: List[tuple[Chunk, List[Dict]]] = []

        # Pass 1: Chunk-Proportional Selection
        for chunk in chunks:
            chunk_embeddings = embeddings[chunk.sentence_indices]
            scored = score_chunk_sentences(
                chunk,
                chunk_embeddings,
                query_embedding=query_embedding,
                weights=effective_weights,
                preserve_patterns=self.preserve_patterns,
                context_role=context_role,
            )
            all_chunk_scored.append((chunk, scored))

            chunk_target = max(1, round(chunk.total_tokens * target_ratio_eff))
            sorted_scored = sorted(
                scored, key=lambda s: (s.get("priority", 1), s["score"]), reverse=True
            )

            used = 0
            for s in sorted_scored:
                global_idx = chunk.sentence_indices[s["index"]]
                tok = sentence_token_counts[global_idx]
                if (
                    s.get("priority", 1) >= 3
                    or used + tok <= chunk_target
                    or not any(kept_mask[chunk.sentence_indices])
                ):
                    kept_mask[global_idx] = True
                    used += tok

        # Pass 2: Global Cross-Chunk Budget Re-balancing
        current_total = sum(
            sentence_token_counts[i] for i in range(len(all_sentences)) if kept_mask[i]
        )

        if current_total < global_target_tokens:
            unselected = []
            for chunk, scored in all_chunk_scored:
                for s in scored:
                    g_idx = chunk.sentence_indices[s["index"]]
                    if not kept_mask[g_idx]:
                        combo_score = (
                            s["score"] + s["instruction_score"] * 0.5 + s["entity_score"] * 0.5
                        )
                        unselected.append(
                            (g_idx, s.get("priority", 1), combo_score, sentence_token_counts[g_idx])
                        )

            unselected.sort(key=lambda item: (item[1], item[2]), reverse=True)
            for g_idx, _prio, _score, tok in unselected:
                if current_total + tok <= global_target_tokens + 25:
                    kept_mask[g_idx] = True
                    current_total += tok
        elif current_total > global_target_tokens + 15:
            selected = []
            for chunk, scored in all_chunk_scored:
                for s in scored:
                    g_idx = chunk.sentence_indices[s["index"]]
                    if kept_mask[g_idx] and s.get("priority", 1) < 4:
                        selected.append(
                            (g_idx, s.get("priority", 1), s["score"], sentence_token_counts[g_idx])
                        )

            selected.sort(key=lambda item: (item[1], item[2]))  # lowest score/priority first
            for g_idx, _prio, _score, tok in selected:
                if current_total - tok >= global_target_tokens:
                    kept_mask[g_idx] = False
                    current_total -= tok

        # --- v0.3: compute retention telemetry ---
        instructions_found = instructions_kept = None
        entities_found = entities_kept = None
        if resolved_mode is not None:
            instructions_found = 0
            instructions_kept = 0
            entities_found = 0
            entities_kept = 0
            for chunk, scored in all_chunk_scored:
                for s in scored:
                    g_idx = chunk.sentence_indices[s["index"]]
                    if s["instruction_score"] > 0:
                        instructions_found += 1
                        if kept_mask[g_idx]:
                            instructions_kept += 1
                    if s["entity_score"] > 0:
                        entities_found += 1
                        if kept_mask[g_idx]:
                            entities_kept += 1

        chunk_results: List[ChunkResult] = []
        for chunk, scored in all_chunk_scored:
            kept_local = [
                s["index"] for s in scored if kept_mask[chunk.sentence_indices[s["index"]]]
            ]
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
        elapsed_ms = (time.perf_counter() - t_start) * 1000

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
            content_type=profile.content_type.value if profile else None,
            content_confidence=profile.confidence if profile else None,
            mode=resolved_mode.name if resolved_mode else None,
            elapsed_ms=round(elapsed_ms, 2) if resolved_mode else None,
            instructions_found=instructions_found,
            instructions_kept=instructions_kept,
            entities_found=entities_found,
            entities_kept=entities_kept,
            token_counter_used=get_active_token_counter_name(),
        )

    def _passthrough(
        self,
        text: str,
        original_tokens: int,
        target_ratio: float,
        sentences_total: int,
        profile: Optional[Any] = None,
        resolved_mode: Optional[Any] = None,
        t_start: Optional[float] = None,
    ) -> CompressionResult:
        elapsed_ms = None
        if t_start is not None and resolved_mode is not None:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        ctype = getattr(profile, "content_type", None) if profile else None
        content_type_val = ctype.value if ctype is not None else None
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
            content_type=content_type_val,
            content_confidence=getattr(profile, "confidence", None) if profile else None,
            mode=getattr(resolved_mode, "name", None) if resolved_mode else None,
            elapsed_ms=elapsed_ms,
            token_counter_used=get_active_token_counter_name(),
        )

    def _try_structured(
        self,
        text: str,
        target_ratio: float,
        profile: Any,
        resolved_mode: Any,
        original_tokens: int,
        t_start: float,
    ) -> Optional[CompressionResult]:
        """Attempt structured optimization; returns None if not applicable."""
        try:
            from .optimizers import optimize_structured
        except ImportError:
            return None

        result_text = optimize_structured(
            text,
            profile.content_type,
            target_ratio,
        )
        if result_text is None or result_text == text:
            return None

        compressed_tokens = count_tokens(result_text)
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return CompressionResult(
            original_text=text,
            compressed_text=result_text,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            target_ratio=target_ratio,
            sentences_total=0,
            sentences_kept=0,
            num_chunks=0,
            backend=self.backend.name,
            content_type=profile.content_type.value,
            content_confidence=profile.confidence,
            mode=resolved_mode.name,
            elapsed_ms=elapsed_ms,
            structure_preserved=True,
            token_counter_used=get_active_token_counter_name(),
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
    def _reassemble(
        sentences: List[str], kept_mask: np.ndarray, para_end_indices: List[int]
    ) -> str:
        """Rebuild paragraphs from kept sentences, preserving list formatting."""
        paragraphs_out: List[str] = []
        start = 0
        for end in para_end_indices:
            kept_sentences = [
                s for s, keep in zip(sentences[start:end], kept_mask[start:end]) if keep
            ]
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
    mode: Optional[str] = None,
    detect_content: bool = False,
    strategy: str = "extractive",
    provider: Optional[Any] = None,
    required_keywords: Optional[List[str]] = None,
    constraints: Optional[List[str]] = None,
    template_name: Optional[str] = None,
    **kwargs,
) -> CompressionResult:
    """Compress ``text``, retaining approximately ``target_ratio`` of its tokens.

    This is the main entry point for the library -- a single function
    call that performs semantic chunking, extractive ranking, and
    reassembly (or optional semantic rewriting / hybrid optimization).

    Args:
        text: The prompt or document to compress.
        target_ratio: Fraction of original tokens to retain (e.g. ``0.5``
            for a ~50% reduction, ``0.3`` for a ~70% reduction).
        query: Optional query string for relevance-aware compression
            (useful for RAG contexts).
        mode: Optimization mode name (e.g. ``"balanced"``,
            ``"quality"``, ``"aggressive"``, ``"rag"``, ``"chat"``,
            ``"system"``, ``"code"``, ``"documentation"``).  Use
            ``"auto"`` with ``detect_content=True`` for fully automatic
            optimisation.  See :func:`llmslim.modes.list_modes`.
        detect_content: When ``True``, analyse the input to detect its
            content type (JSON, YAML, Python, chat, etc.) and populate
            telemetry fields on the result.  Adds < 1 ms overhead.
        strategy: Optimization strategy ("extractive", "rewrite", "hybrid").
            Defaults to "extractive".
        provider: Optional BaseRewriteProvider instance or callable when
            using "rewrite" or "hybrid" strategy.
        required_keywords: Optional list of keywords that must be present
            in the rewritten prompt.
        constraints: Optional list of prompt constraints passed to rewrite prompt.
        template_name: Optional template name override.
        **kwargs: Passed to :class:`ContextCompressor` if provided (e.g.
            ``max_chunk_tokens``, ``similarity_threshold``,
            ``preserve_patterns``). If no kwargs are given, a shared
            default compressor instance is reused for efficiency.

    Returns:
        A :class:`CompressionResult` with ``.compressed_text``,
        ``.reduction_percent``, and other statistics.

    Example:
        >>> from llmslim import compress
        >>> result = compress(my_long_prompt, target_ratio=0.5)
        >>> send_to_llm(result.compressed_text)
        >>> print(f"Saved {result.tokens_saved} tokens ({result.reduction_percent}%)")

    .. versionchanged:: 0.3.0
       Added ``strategy``, ``provider``, ``required_keywords``, ``constraints``,
       and ``template_name`` parameters.
    """
    if mode is not None or detect_content:
        kwargs["mode"] = mode
        kwargs["detect_content"] = detect_content

    compressor = ContextCompressor(**kwargs) if kwargs else _get_default_compressor()
    return compressor.compress(
        text,
        target_ratio=target_ratio,
        query=query,
        strategy=strategy,
        provider=provider,
        required_keywords=required_keywords,
        constraints=constraints,
        template_name=template_name,
    )
