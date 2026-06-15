"""context-compressor: cut LLM prompt size by 40-70% with one function call.

Quickstart:
    >>> from context_compressor import compress
    >>> result = compress(my_long_prompt, target_ratio=0.5)
    >>> print(result.compressed_text)
    >>> print(result.summary())
"""

from .core import CompressionResult, ContextCompressor, compress
from .cost import CostEstimate, MODEL_PRICING, estimate_cost_savings, list_supported_models
from .pipelines import compress_chat_messages, compress_documents
from .tokens import count_tokens, count_tokens_batch

__version__ = "0.1.0"

__all__ = [
    "compress",
    "ContextCompressor",
    "CompressionResult",
    "compress_chat_messages",
    "compress_documents",
    "estimate_cost_savings",
    "list_supported_models",
    "CostEstimate",
    "MODEL_PRICING",
    "count_tokens",
    "count_tokens_batch",
    "__version__",
]
