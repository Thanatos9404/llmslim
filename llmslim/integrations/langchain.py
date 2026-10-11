"""LangChain document compressor backed by :func:`llmslim.compress_documents`.

Use it wherever a LangChain ``BaseDocumentCompressor`` goes, for example as the
``base_compressor`` of a ``ContextualCompressionRetriever`` (where you would use
``LLMLinguaCompressor``)::

    from langchain_classic.retrievers.contextual_compression import (
        ContextualCompressionRetriever,
    )
    from llmslim.integrations.langchain import LLMSlimCompressor

    retriever = ContextualCompressionRetriever(
        base_compressor=LLMSlimCompressor(target_ratio=0.25),
        base_retriever=my_retriever,
    )

Requires ``pip install "llmslim[langchain]"`` (``langchain-core``).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Union

try:
    from langchain_core.callbacks import Callbacks
    from langchain_core.documents import BaseDocumentCompressor, Document
    from pydantic import Field, model_validator
except ImportError as exc:  # pragma: no cover - exercised only without the extra.
    raise ImportError(
        'llmslim.integrations.langchain requires the optional extra: pip install "llmslim[langchain]"'
    ) from exc

from ..core import ContextRole
from ._documents import compress_texts, token_metadata, validate_options

__all__ = ["LLMSlimCompressor"]


class LLMSlimCompressor(BaseDocumentCompressor):
    """Compress retrieved documents into a token budget with LLMSlim.

    With a query, the documents share one budget (``target_ratio`` of their
    combined tokens) and it goes where the query points: the most relevant
    documents stay whole and irrelevant ones are dropped. Without a query, each
    document is compressed to ``target_ratio`` on its own. Document metadata and
    ids are kept; documents that compress to nothing are dropped.
    """

    target_ratio: float = 0.25
    """Fraction of tokens to keep: across all documents with a query, per document without one."""

    relevance: Union[str, Callable[..., Any]] = "lexical"
    """``"lexical"`` (BM25, no model), ``"semantic"`` (cross-encoder, needs ``llmslim[semantic]``)
    or a callable ``scorer(query, texts) -> scores``."""

    selection: str = "auto"
    """``"auto"``, ``"focus"`` or ``"proportional"`` (the 0.7 per-document split)."""

    context_role: Union[ContextRole, str] = ContextRole.RAG
    """Provenance of the documents. Retrieved text is untrusted by default."""

    record_token_counts: bool = True
    """Add ``llmslim_original_tokens`` and ``llmslim_compressed_tokens`` to each kept document's metadata."""

    additional_compress_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Other keyword arguments for ``llmslim.compress_documents`` (for example ``mode``)."""

    @model_validator(mode="after")
    def _check_options(self) -> "LLMSlimCompressor":
        validate_options(
            self.target_ratio, self.relevance, self.selection, self.additional_compress_kwargs
        )
        return self

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        """Return the kept documents, in their original order, with compressed ``page_content``."""
        results = compress_texts(
            [doc.page_content for doc in documents],
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
            metadata = dict(doc.metadata)
            if self.record_token_counts:
                metadata.update(token_metadata(result))
            kept.append(
                doc.model_copy(
                    update={"page_content": result.compressed_text, "metadata": metadata}
                )
            )
        return kept
