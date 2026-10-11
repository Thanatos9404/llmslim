"""LlamaIndex node postprocessor backed by :func:`llmslim.compress_documents`.

Use it wherever a ``BaseNodePostprocessor`` goes, for example in a query
engine's ``node_postprocessors`` (where you would use
``LongLLMLinguaPostprocessor``)::

    from llmslim.integrations.llama_index import LLMSlimPostprocessor

    query_engine = index.as_query_engine(
        similarity_top_k=10,
        node_postprocessors=[LLMSlimPostprocessor(target_ratio=0.25)],
    )

Requires ``pip install "llmslim[llamaindex]"`` (``llama-index-core``).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

try:
    from llama_index.core.postprocessor.types import BaseNodePostprocessor
    from llama_index.core.schema import MetadataMode, NodeWithScore, QueryBundle
    from pydantic import Field, model_validator
except ImportError as exc:  # pragma: no cover - exercised only without the extra.
    raise ImportError(
        'llmslim.integrations.llama_index requires the optional extra: pip install "llmslim[llamaindex]"'
    ) from exc

from ..core import ContextRole
from ._documents import TOKEN_METADATA_KEYS, compress_texts, token_metadata, validate_options

__all__ = ["LLMSlimPostprocessor"]


class LLMSlimPostprocessor(BaseNodePostprocessor):
    """Compress retrieved nodes into a token budget with LLMSlim.

    With a query, the nodes share one budget (``target_ratio`` of their combined
    tokens) and it goes where the query points: the most relevant nodes stay
    whole and irrelevant ones are dropped. Without a query, each node is
    compressed to ``target_ratio`` on its own. Kept nodes keep their order,
    score, id and metadata; nodes that compress to nothing are dropped.
    """

    target_ratio: float = Field(
        default=0.25,
        description="Fraction of tokens to keep: across all nodes with a query, per node without one.",
    )
    relevance: Union[str, Callable[..., Any]] = Field(
        default="lexical",
        description='"lexical", "semantic" (needs llmslim[semantic]) or a callable scorer(query, texts) -> scores.',
    )
    selection: str = Field(
        default="auto", description='"auto", "focus" or "proportional" (the 0.7 per-node split).'
    )
    context_role: Union[ContextRole, str] = Field(
        default=ContextRole.RAG,
        description="Provenance of the nodes. Retrieved text is untrusted by default.",
    )
    record_token_counts: bool = Field(
        default=True,
        description="Add llmslim_original_tokens and llmslim_compressed_tokens to each kept node's "
        "metadata (excluded from the LLM and embedding text).",
    )
    additional_compress_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Other keyword arguments for llmslim.compress_documents (for example mode).",
    )

    @model_validator(mode="after")
    def _check_options(self) -> "LLMSlimPostprocessor":
        validate_options(
            self.target_ratio, self.relevance, self.selection, self.additional_compress_kwargs
        )
        return self

    @classmethod
    def class_name(cls) -> str:
        return "LLMSlimPostprocessor"

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        query = query_bundle.query_str if query_bundle is not None else None
        results = compress_texts(
            [n.node.get_content(metadata_mode=MetadataMode.NONE) for n in nodes],
            query,
            target_ratio=self.target_ratio,
            relevance=self.relevance,
            selection=self.selection,
            context_role=self.context_role,
            additional_compress_kwargs=self.additional_compress_kwargs,
        )
        kept: List[NodeWithScore] = []
        for item, result in zip(nodes, results):
            if result is None:
                continue
            node = item.node.model_copy()
            node.set_content(result.compressed_text)
            node.metadata = dict(item.node.metadata)
            if self.record_token_counts:
                node.metadata.update(token_metadata(result))
                # Bookkeeping only: keep the counts out of the text sent to the LLM and embedder.
                node.excluded_llm_metadata_keys = _with_keys(item.node.excluded_llm_metadata_keys)
                node.excluded_embed_metadata_keys = _with_keys(
                    item.node.excluded_embed_metadata_keys
                )
            kept.append(NodeWithScore(node=node, score=item.score))
        return kept


def _with_keys(keys: List[str]) -> List[str]:
    return list(keys) + [k for k in TOKEN_METADATA_KEYS if k not in keys]
