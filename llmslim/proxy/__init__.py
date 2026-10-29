"""A local proxy that keeps coding agents' context lean: tool output is compressed once and replayed byte for byte.

``pip install "llmslim[proxy]"``, then ``llmslim wrap claude`` (or run ``llmslim proxy`` and set
``ANTHROPIC_BASE_URL``). See :mod:`llmslim.proxy.rewrite` for what is compressed and why it stays cache-safe and
thinking-safe.

Experimental: this package and the ``llmslim proxy`` and ``llmslim wrap`` commands may change in a minor release
(docs/API_STABILITY.md).
"""

from .rewrite import (
    COMPRESSIBLE_TOOLS,
    BlockCache,
    Policy,
    RewriteReport,
    block_key,
    rewrite_request,
)
from .store import ProxyStore

__all__ = [
    "COMPRESSIBLE_TOOLS",
    "BlockCache",
    "Policy",
    "ProxyStore",
    "RewriteReport",
    "block_key",
    "rewrite_request",
]
