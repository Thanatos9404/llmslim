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

    When ``query`` is provided, sentences more relevant to the query are
    favored during selection -- this lets you compress retrieved context
    aggressively while keeping the parts most useful for answering the
    user's question.

    Args:
        documents: Retrieved document texts/chunks.
        query: The user's query or search query, for relevance-aware
            ranking.
        target_ratio: Fraction of tokens to retain per document.
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
    """
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
