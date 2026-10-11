"""Framework-free core shared by the LangChain, LlamaIndex and Haystack adapters.

Each adapter extracts the text of its framework's document objects, calls
:func:`compress_texts`, and rebuilds the kept documents with their metadata.
Keeping this logic here means every adapter has the same semantics as
:func:`llmslim.compress_documents` and the logic is tested without any framework
installed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from ..core import CompressionResult, ContextRole
from ..pipelines import compress_documents

ORIGINAL_TOKENS_KEY = "llmslim_original_tokens"
COMPRESSED_TOKENS_KEY = "llmslim_compressed_tokens"
TOKEN_METADATA_KEYS = (ORIGINAL_TOKENS_KEY, COMPRESSED_TOKENS_KEY)

_SELECTIONS = ("auto", "focus", "proportional")
# Options the adapters expose as their own fields; additional_compress_kwargs may not repeat them.
_RESERVED = (
    "documents",
    "query",
    "target_ratio",
    "relevance",
    "selection",
    "context_role",
)


def validate_options(
    target_ratio: float,
    relevance: Any,
    selection: str,
    additional_compress_kwargs: Optional[Mapping[str, Any]],
) -> None:
    """Fail at construction time rather than on the first query."""
    if isinstance(target_ratio, bool) or not 0.0 < float(target_ratio) <= 1.0:
        raise ValueError("target_ratio must be in the range (0, 1]")
    if not (relevance in ("lexical", "semantic") or callable(relevance)):
        raise ValueError(
            "relevance must be 'lexical', 'semantic' or a callable scorer(query, texts)"
        )
    if selection not in _SELECTIONS:
        raise ValueError("selection must be 'auto', 'focus' or 'proportional'")
    clash = sorted(set(additional_compress_kwargs or {}) & set(_RESERVED))
    if clash:
        raise ValueError(
            "set these as adapter fields, not in additional_compress_kwargs: " + ", ".join(clash)
        )


def compress_texts(
    texts: Sequence[Optional[str]],
    query: Optional[str],
    *,
    target_ratio: float,
    relevance: Any = "lexical",
    selection: str = "auto",
    context_role: Union[ContextRole, str] = ContextRole.RAG,
    additional_compress_kwargs: Optional[Mapping[str, Any]] = None,
) -> List[Optional[CompressionResult]]:
    """Compress ``texts`` with :func:`llmslim.compress_documents`.

    Returns one entry per input text, in order: the :class:`CompressionResult`, or
    ``None`` where the text was empty or compressed to nothing (with a query, the
    documents share one budget and irrelevant ones are left out). Only non-default
    options are forwarded, so the defaults take exactly the ``compress_documents``
    code path.
    """
    keep = [i for i, text in enumerate(texts) if text and text.strip()]
    out: List[Optional[CompressionResult]] = [None] * len(texts)
    if not keep:
        return out
    kwargs: Dict[str, Any] = dict(additional_compress_kwargs or {})
    if relevance != "lexical":
        kwargs["relevance"] = relevance
    if selection != "auto":
        kwargs["selection"] = selection
    results = compress_documents(
        [texts[i] or "" for i in keep],
        query=query if query and query.strip() else None,
        target_ratio=target_ratio,
        context_role=context_role,
        **kwargs,
    )
    for i, result in zip(keep, results):
        if result.compressed_text.strip():
            out[i] = result
    return out


def token_metadata(result: CompressionResult) -> Dict[str, int]:
    """Original and kept token counts, under keys namespaced to LLMSlim."""
    return {
        ORIGINAL_TOKENS_KEY: result.original_tokens,
        COMPRESSED_TOKENS_KEY: result.compressed_tokens,
    }
