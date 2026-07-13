"""High-level pipelines for common real-world use cases.

These helpers wrap :func:`llmslim.core.compress` for the two
most common scenarios: compressing chat-style message histories before
sending them to a model, and compressing retrieved documents in a RAG
pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Dict, List, Optional

from .core import CompressionResult, compress

# Roles whose content is typically long, free-form, and safe to compress.
# System prompts are left untouched by default since they often contain
# precise, load-bearing instructions and are usually short and reused
# across many requests.
DEFAULT_COMPRESSIBLE_ROLES = ("user", "assistant")


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
            result = compress(content, target_ratio=target_ratio, **kwargs)
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
    return [compress(doc, target_ratio=target_ratio, query=query, **kwargs) for doc in documents]
