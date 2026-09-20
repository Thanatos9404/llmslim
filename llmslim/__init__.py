"""LLMSlim: local-first context planning and prompt compression.

Quickstart:
    >>> from llmslim import compress
    >>> result = compress(my_long_prompt, target_ratio=0.5, detect_content=True)
    >>> print(result.compressed_text)
    >>> print(result.detailed_summary())
"""

from .analysis import ContentProfile, ContentType, analyze
from .context import (
    ContextSource,
    ContextSourceError,
    ContextStore,
    InMemoryContextSource,
    InMemoryContextStore,
    collect_context_sources,
)
from .core import CompressionResult, ContextCompressor, ContextRole, compress
from .cost import MODEL_PRICING, CostEstimate, estimate_cost_savings, list_supported_models
from .modes import get_mode, list_modes
from .pipelines import compress_chat_messages, compress_documents
from .planning import (
    AdaptiveContextPlanner,
    CandidateMethod,
    ContextBudget,
    ContextItem,
    ContextKind,
    ContextPlan,
    InfeasibleContextError,
    MCPAdaptiveContextPlan,
    ModelProfile,
    PlannerPolicy,
    PolicyPreset,
    plan_context,
    plan_mcp_context,
)
from .rewrite import (
    BaseRewriteProvider,
    CallableProvider,
    RewriteEngine,
    RewriteMetadata,
    RewriteRequest,
    RewriteValidator,
    ValidationResult,
)
from .tokens import count_tokens, count_tokens_batch

__version__ = "0.6.0"

__all__ = [
    "compress",
    "ContextCompressor",
    "ContextRole",
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
    "BaseRewriteProvider",
    "CallableProvider",
    "RewriteRequest",
    "RewriteEngine",
    "RewriteMetadata",
    "RewriteValidator",
    "ValidationResult",
    "ContextSource",
    "ContextSourceError",
    "ContextStore",
    "InMemoryContextSource",
    "InMemoryContextStore",
    "collect_context_sources",
    "plan_context",
    "AdaptiveContextPlanner",
    "ContextItem",
    "ContextKind",
    "ContextBudget",
    "ContextPlan",
    "CandidateMethod",
    "PlannerPolicy",
    "PolicyPreset",
    "ModelProfile",
    "InfeasibleContextError",
    "MCPAdaptiveContextPlan",
    "plan_mcp_context",
    "__version__",
]
