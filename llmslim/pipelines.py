"""High-level pipelines for common real-world use cases.

These helpers wrap :func:`llmslim.core.compress` for the two
most common scenarios: compressing chat-style message histories before
sending them to a model, and compressing retrieved documents in a RAG
pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Dict, List, Optional, Union

from .core import CompressionResult, ContextRole, compress

# Roles whose content is typically long, free-form, and safe to compress.
# System prompts are left untouched by default since they often contain
# precise, load-bearing instructions and are usually short and reused
# across many requests.
DEFAULT_COMPRESSIBLE_ROLES = ("user", "assistant")

# Explicit mapping from chat message ``role`` strings to provenance
# ``ContextRole`` values.  Each distinct role maps to its own provenance —
# there is no silent collapsing of ``assistant`` into ``user``.  Unknown
# roles fall back to ``GENERAL`` (legacy behaviour) rather than guessing a
# trust level.
_CHAT_ROLE_TO_CONTEXT_ROLE: Dict[str, ContextRole] = {
    "system": ContextRole.SYSTEM,
    "developer": ContextRole.DEVELOPER,
    "user": ContextRole.USER,
    "assistant": ContextRole.ASSISTANT,
    "tool": ContextRole.TOOL,
}


def _chat_role_to_context_role(role: Optional[str]) -> ContextRole:
    """Map a chat message ``role`` to a provenance :class:`ContextRole`.

    Distinct roles map to distinct provenance; unknown/other roles map to
    ``GENERAL`` so their handling is explicit rather than an accidental
    collapse into a trusted or untrusted bucket.
    """
    if not role:
        return ContextRole.GENERAL
    return _CHAT_ROLE_TO_CONTEXT_ROLE.get(role.lower(), ContextRole.GENERAL)


def compress_chat_messages(
    messages: Sequence[Dict[str, str]],
    target_ratio: float = 0.5,
    compressible_roles: Iterable[str] = DEFAULT_COMPRESSIBLE_ROLES,
    min_tokens: int = 60,
    **kwargs,
) -> List[Dict[str, str]]:
    """Compress the ``content`` of chat messages before sending them to an LLM.

    Args:
        messages: A list of ``{"role": ..., "content": ...}`` dicts, in
            the same format used by OpenAI, Anthropic, and Gemini chat
            APIs.
        target_ratio: Fraction of tokens to retain in compressible
            messages.
        compressible_roles: Roles eligible for compression. Defaults to
            ``("user", "assistant")`` -- system prompts are preserved
            as-is.
        min_tokens: Messages below this token count are left untouched
            (compression overhead isn't worth it for short turns).
        **kwargs: Extra keyword arguments forwarded to
            :func:`llmslim.core.compress`.

    Returns:
        A new list of message dicts with ``content`` replaced by
        compressed text where applicable. The input list is not mutated.

    Example:
        >>> from llmslim import compress_chat_messages
        >>> compressed = compress_chat_messages(conversation_history, target_ratio=0.5)
        >>> response = openai_client.chat.completions.create(model="gpt-5", messages=compressed)
    """
    compressible_roles = set(compressible_roles)
    out: List[Dict[str, str]] = []

    for message in messages:
        role = message.get("role")
        content = message.get("content", "")

        if role in compressible_roles and isinstance(content, str) and content.strip():
            kwargs.setdefault("min_tokens_for_compression", min_tokens)
            # Provenance propagation (v0.3.1): compress each turn under its
            # own role so imperative wording in untrusted assistant/tool/user
            # turns cannot hijack the force-kept priority tier.  An explicit
            # caller-supplied ``context_role`` still wins.
            call_kwargs = dict(kwargs)
            call_kwargs.setdefault("context_role", _chat_role_to_context_role(role))
            result = compress(content, target_ratio=target_ratio, **call_kwargs)
            new_message = dict(message)
            new_message["content"] = result.compressed_text
            out.append(new_message)
        else:
            out.append(dict(message))

    return out


def compress_documents(
    documents: Sequence[str],
    query: Optional[str] = None,
    target_ratio: float = 0.5,
    context_role: Union[ContextRole, str] = ContextRole.RAG,
    **kwargs,
) -> List[CompressionResult]:
    """Compress a list of retrieved documents/chunks for a RAG pipeline.

    When ``query`` is provided, the documents share one budget
    (``target_ratio`` of their combined tokens) and it goes where the query
    points: the most relevant documents stay whole and irrelevant ones are
    left out (their ``compressed_text`` is empty). Without a query, each
    document is compressed to ``target_ratio`` on its own.

    Args:
        documents: Retrieved document texts/chunks.
        query: The user's query or search query, for relevance-aware
            ranking.
        target_ratio: Fraction of tokens to retain (across all documents
            when ``query`` is given, per document otherwise).
        context_role: Provenance/trust role for the documents.  Defaults to
            :attr:`ContextRole.RAG` (untrusted) so that imperative wording
            inside retrieved passages cannot be force-kept as a
            hard-locked priority.  This is an intentional v0.3.1 behavioural
            change from v0.3.0 (see the Phase 1 plan §8).  Pass a different
            role (e.g. ``"general"``) to opt out.
        **kwargs: Extra keyword arguments forwarded to
            :func:`llmslim.core.compress`.

    Returns:
        A list of :class:`CompressionResult`, one per input document, in
        the same order.

    Example:
        >>> from llmslim import compress_documents
        >>> results = compress_documents(retrieved_chunks, query=user_query, target_ratio=0.4)
        >>> context = "\\n\\n".join(r.compressed_text for r in results)
        >>> total_saved = sum(r.tokens_saved for r in results)

    .. versionchanged:: 0.8.0
       With a query, the budget is shared across documents by relevance
       (pass ``selection="proportional"`` for the v0.7 per-document split).
    """
    if (
        query
        and query.strip()
        and len(documents) > 1
        and kwargs.get("selection", "auto") != "proportional"
    ):
        return _focus_documents(documents, query, target_ratio, context_role, kwargs)
    return [
        compress(
            doc,
            target_ratio=target_ratio,
            query=query,
            context_role=context_role,
            **kwargs,
        )
        for doc in documents
    ]


def _focus_documents(
    documents: Sequence[str],
    query: str,
    target_ratio: float,
    context_role: Union[ContextRole, str],
    options: Dict,
) -> List[CompressionResult]:
    """One relevance-ranked budget across all documents (v0.8)."""
    import re
    import time

    from .core import _resolve_context_role
    from .focus import focus_documents
    from .rerank import resolve_relevance
    from .tokens import count_tokens, get_active_token_counter_name

    if not (0.0 < target_ratio <= 1.0):
        raise ValueError("target_ratio must be in the range (0, 1]")
    started = time.perf_counter()
    role = _resolve_context_role(context_role, ContextRole.GENERAL, options.get("mode"))
    originals = [count_tokens(doc) for doc in documents]
    budget = max(1, round(sum(originals) * target_ratio))
    preserve_res = [re.compile(p, re.IGNORECASE) for p in options.get("preserve_patterns") or []]
    scorer = resolve_relevance(options.get("relevance", "lexical"))
    texts = focus_documents(
        documents, query, budget, preserve_res=preserve_res, context_role=role, scorer=scorer
    )
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return [
        CompressionResult(
            original_text=doc,
            compressed_text=text,
            original_tokens=tokens,
            compressed_tokens=count_tokens(text) if text else 0,
            target_ratio=target_ratio,
            sentences_total=0,
            sentences_kept=0,
            num_chunks=0,
            backend="bm25" if scorer is None else "bm25+rerank",
            elapsed_ms=elapsed,
            token_counter_used=get_active_token_counter_name(),
            selection="focus",
        )
        for doc, tokens, text in zip(documents, originals, texts)
    ]
