"""LLMSlim: local-first context planning and prompt compression.

Quickstart:
    >>> from llmslim import compress
    >>> result = compress(my_long_prompt, target_ratio=0.5, detect_content=True)
    >>> print(result.compressed_text)
    >>> print(result.detailed_summary())
"""

from .adapters import (
    generic_request,
    make_openai_agents_input_filter,
    openai_compatible_request,
    sarvam_messages,
)
from .analysis import ContentProfile, ContentType, analyze
from .cache import (
    PROVIDER_CAPABILITIES,
    CacheCapabilities,
    CacheManager,
    CachePlan,
    CachePolicy,
    CacheSegment,
    CacheStatus,
    CacheTelemetry,
    cache_cost_breakdown,
    estimate_cache_cost,
)
from .cache_adapters import (
    anthropic_messages_request,
    gemini_cached_content_request,
    gemini_generate_request,
    openai_responses_request,
    parse_cache_telemetry,
    request_bytes,
    vllm_chat_request,
)
from .context import (
    ContextSource,
    ContextSourceError,
    ContextStore,
    InMemoryContextSource,
    InMemoryContextStore,
    collect_context_sources,
)
from .context_graph import ContextEdge, ContextGraph, EdgeType
from .context_policy import ContextPolicy
from .core import CompressionResult, ContextCompressor, ContextRole, compress
from .cost import MODEL_PRICING, CostEstimate, estimate_cost_savings, list_supported_models
from .envelope import ContextEnvelope
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
from .planning.progressive import plan_context_v2
from .quality import QualityReport
from .rewrite import (
    BaseRewriteProvider,
    CallableProvider,
    RewriteEngine,
    RewriteMetadata,
    RewriteRequest,
    RewriteValidator,
    ValidationResult,
)
from .runtime import ContextRuntime, ContextTrace, ModelInput, PreparedContext, RuntimeSession
from .self_hosted import TransformersKVSession
from .tokens import count_tokens, count_tokens_batch

__version__ = "0.7.1"

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
    "ContextEnvelope",
    "ContextGraph",
    "ContextEdge",
    "EdgeType",
    "ContextPolicy",
    "QualityReport",
    "ContextRuntime",
    "RuntimeSession",
    "PreparedContext",
    "ModelInput",
    "ContextTrace",
    "plan_context_v2",
    "generic_request",
    "sarvam_messages",
    "openai_compatible_request",
    "make_openai_agents_input_filter",
    "CacheCapabilities",
    "CacheManager",
    "CachePlan",
    "CachePolicy",
    "CacheSegment",
    "CacheStatus",
    "CacheTelemetry",
    "PROVIDER_CAPABILITIES",
    "estimate_cache_cost",
    "cache_cost_breakdown",
    "openai_responses_request",
    "anthropic_messages_request",
    "gemini_generate_request",
    "gemini_cached_content_request",
    "parse_cache_telemetry",
    "request_bytes",
    "vllm_chat_request",
    "TransformersKVSession",
    "__version__",
]
