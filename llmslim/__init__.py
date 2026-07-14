"""llmslim: cut LLM prompt size by 40-70% with one function call.

Quickstart:
    >>> from llmslim import compress
    >>> result = compress(my_long_prompt, target_ratio=0.5, detect_content=True)
    >>> print(result.compressed_text)
    >>> print(result.detailed_summary())
"""

from .analysis import ContentProfile, ContentType, analyze
from .core import CompressionResult, ContextCompressor, compress
from .cost import MODEL_PRICING, CostEstimate, estimate_cost_savings, list_supported_models
from .modes import get_mode, list_modes
from .pipelines import compress_chat_messages, compress_documents
from .tokens import count_tokens, count_tokens_batch

__version__ = "0.3.0"

__all__ = [
    "compress",
    "ContextCompressor",
    "CompressionResult",
    "ContentType",
    "ContentProfile",
    "analyze",
    "list_modes",
    "get_mode",
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
