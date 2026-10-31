"""Fit a text to a token budget: the shared helper behind the MCP server's fit_context and the HTTP server's /fit."""

from __future__ import annotations

from typing import Optional

from .core import compress
from .tokens import count_tokens

_FIT_PASSES = 4
_FIT_SLACK = 1.02


def fit_text(text: str, budget: int, query: Optional[str] = None) -> str:
    """``text`` compressed to at most about ``budget`` tokens (within 2%), focused on ``query`` when given.

    Text that already fits comes back unchanged. When compression can't get under the budget (a text that is one
    long code block, say, which compression keeps whole), the compressed text is cut to the longest head that fits,
    so the bound holds for any input.
    """
    if budget <= 0:
        raise ValueError("budget must be a positive number of tokens")
    total = count_tokens(text)
    if total <= budget:
        return text
    ratio = budget / total
    fitted = text
    tokens = total
    for _ in range(_FIT_PASSES):
        fitted = compress(text, target_ratio=min(ratio, 1.0), query=query or None).compressed_text
        tokens = count_tokens(fitted)
        if tokens <= budget * _FIT_SLACK:
            break
        ratio *= budget / tokens * 0.98
    if tokens > budget * _FIT_SLACK:
        fitted = _head_within(fitted, budget)
    return fitted


def _head_within(text: str, budget: int) -> str:
    """The longest head of ``text`` within ``budget`` tokens, ending at whitespace when one is near the end."""
    # Bound the search first: grow a prefix until it is over the budget, so a huge text isn't counted whole each step.
    high = min(len(text), max(64, budget * 8))
    while high < len(text) and count_tokens(text[:high]) <= budget:
        high = min(len(text), high * 2)
    low = 0
    while low < high:
        middle = (low + high + 1) // 2
        if count_tokens(text[:middle]) <= budget:
            low = middle
        else:
            high = middle - 1
    head = text[:low]
    cut = max(head.rfind(" "), head.rfind("\n"))
    return head[:cut].rstrip() if cut > len(head) * 0.8 else head
