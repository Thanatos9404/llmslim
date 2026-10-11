"""Haystack component backed by :func:`llmslim.compress_documents`.

Put it between a retriever and the prompt builder::

    from haystack import Pipeline
    from llmslim.integrations.haystack import LLMSlimDocumentCompressor

    pipeline = Pipeline()
    pipeline.add_component("retriever", retriever)
    pipeline.add_component("compressor", LLMSlimDocumentCompressor(target_ratio=0.25))
    pipeline.add_component("prompt_builder", prompt_builder)
    pipeline.connect("retriever.documents", "compressor.documents")
    pipeline.connect("compressor.documents", "prompt_builder.documents")

Requires ``pip install "llmslim[haystack]"`` (``haystack-ai``).
"""

# No ``from __future__ import annotations`` here: Haystack builds the component's
# input and output sockets from the runtime type annotations of ``run``.
import dataclasses
from typing import Any, Callable, Dict, List, Optional, Union

try:
    from haystack import Document, component, default_from_dict, default_to_dict
except ImportError as exc:  # pragma: no cover - exercised only without the extra.
    raise ImportError(
        'llmslim.integrations.haystack requires the optional extra: pip install "llmslim[haystack]"'
    ) from exc

from ..core import ContextRole
from ._documents import compress_texts, token_metadata, validate_options

__all__ = ["LLMSlimDocumentCompressor"]


@component
class LLMSlimDocumentCompressor:
    """Compress retrieved documents into a token budget with LLMSlim.

    With a query, the documents share one budget (``target_ratio`` of their
    combined tokens) and it goes where the query points: the most relevant
    documents stay whole and irrelevant ones are dropped. Without a query, each
    document is compressed to ``target_ratio`` on its own. Kept documents keep
    their order, id, score and ``meta``; documents without text, or that
    compress to nothing, are dropped.
    """

    def __init__(
        self,
        target_ratio: float = 0.25,
        relevance: Union[str, Callable[..., Any]] = "lexical",
        selection: str = "auto",
        context_role: str = "rag",
        record_token_counts: bool = True,
        additional_compress_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Args:
            target_ratio: Fraction of tokens to keep: across all documents with a
                query, per document without one.
            relevance: ``"lexical"`` (BM25, no model), ``"semantic"`` (cross-encoder,
                needs ``llmslim[semantic]``) or a callable ``scorer(query, texts) -> scores``.
            selection: ``"auto"``, ``"focus"`` or ``"proportional"`` (the 0.7 per-document split).
            context_role: Provenance of the documents. Retrieved text is untrusted by default.
            record_token_counts: Add ``llmslim_original_tokens`` and
                ``llmslim_compressed_tokens`` to each kept document's ``meta``.
            additional_compress_kwargs: Other keyword arguments for
                ``llmslim.compress_documents`` (for example ``mode``).
        """
        validate_options(target_ratio, relevance, selection, additional_compress_kwargs)
        self.target_ratio = target_ratio
        self.relevance = relevance
        self.selection = selection
        self.context_role = (
            context_role.value if isinstance(context_role, ContextRole) else context_role
        )
        self.record_token_counts = record_token_counts
        self.additional_compress_kwargs = dict(additional_compress_kwargs or {})

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Haystack pipelines. A callable ``relevance`` cannot be serialized."""
        if callable(self.relevance):
            raise ValueError(
                "LLMSlimDocumentCompressor with a callable relevance scorer cannot be serialized"
            )
        return default_to_dict(
            self,
            target_ratio=self.target_ratio,
            relevance=self.relevance,
            selection=self.selection,
            context_role=self.context_role,
            record_token_counts=self.record_token_counts,
            additional_compress_kwargs=self.additional_compress_kwargs,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMSlimDocumentCompressor":
        return default_from_dict(cls, data)

    @component.output_types(documents=List[Document])
    def run(self, documents: List[Document], query: Optional[str] = None) -> Dict[str, Any]:
        """Return ``{"documents": [...]}``: the kept documents, in order, with compressed ``content``."""
        results = compress_texts(
            [doc.content for doc in documents],
            query,
            target_ratio=self.target_ratio,
            relevance=self.relevance,
            selection=self.selection,
            context_role=self.context_role,
            additional_compress_kwargs=self.additional_compress_kwargs,
        )
        kept: List[Document] = []
        for doc, result in zip(documents, results):
            if result is None:
                continue
            meta = dict(doc.meta)
            if self.record_token_counts:
                meta.update(token_metadata(result))
            kept.append(dataclasses.replace(doc, content=result.compressed_text, meta=meta))
        return {"documents": kept}
