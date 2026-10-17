"""Shorten one long tool output, the way the proxy and the agent middleware do: once, deterministically, with a note.

Shared by :mod:`llmslim.proxy` (coding agents) and :mod:`llmslim.integrations.langchain_agents` (LangChain agents).
JSON with a list keeps every item, compactly (see :mod:`llmslim._json_output`). Other text keeps errors, failures and
tracebacks first, then the lines most related to the call; runs of similar lines collapse into one line and a count,
and omitted spans are marked. Nothing here calls a model.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ._fit import fit_text
from ._json_output import shorten_json
from .tokens import count_tokens

SHELL_HINT = "Run a narrower command to see more."
TOOL_HINT = "Call the tool again with a narrower request to see more."


def shorten_tool_output(
    text: str,
    query: Optional[str] = None,
    *,
    min_tokens: int = 1500,
    keep_ratio: float = 0.35,
    min_keep: int = 1000,
    hint: str = SHELL_HINT,
) -> Optional[Tuple[str, int, int]]:
    """``(new_text, tokens_before, tokens_after)``, or ``None`` when ``text`` should be left as it is.

    Output at or below ``min_tokens`` is left alone. Longer output keeps about ``keep_ratio`` of its tokens, and never
    fewer than ``min_keep``, focused on ``query`` (the command or request that produced it) when given.
    """
    before = count_tokens(text)
    if before <= min_tokens:
        return None
    budget = max(min_keep, int(before * keep_ratio))
    if budget >= before:
        return None
    body = shorten_json(text, budget, query)
    if body is not None:
        kept = "every list item with its short fields, and the items related to the call whole"
    else:
        body = fit_text(text, budget, query)
        kept = "errors and the lines most related to the call"
    note = (
        f"[LLMSlim shortened this tool output from {before:,} to about {count_tokens(body):,} tokens, keeping {kept}. "
        f"{hint}]\n"
    )
    new_text = note + body
    after = count_tokens(new_text)
    if after >= before:
        return None
    return new_text, before, after
