"""Fit a text to a token budget: the shared helper behind the MCP server's fit_context and the HTTP server's /fit."""

from __future__ import annotations

from typing import Optional

from .core import compress
from .tokens import count_tokens

_FIT_PASSES = 4
_FIT_SLACK = 1.02


def fit_text(text: str, budget: int, query: Optional[str] = None) -> str:
    """``text`` compressed to at most about ``budget`` tokens (within 2%), focused on ``query`` when given.

    Text that already fits comes back unchanged.
    """
    if budget <= 0:
        raise ValueError("budget must be a positive number of tokens")
    total = count_tokens(text)
    if total <= budget:
        return text
    ratio = budget / total
    fitted = text
    for _ in range(_FIT_PASSES):
        fitted = compress(text, target_ratio=min(ratio, 1.0), query=query or None).compressed_text
        tokens = count_tokens(fitted)
        if tokens <= budget * _FIT_SLACK:
            break
        ratio *= budget / tokens * 0.98
    return fitted
