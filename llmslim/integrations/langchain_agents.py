"""LLMSlim middleware for LangChain agents (``langchain`` 1.x, ``create_agent``).

``LLMSlimToolOutputMiddleware`` shortens long tool results once, the first time the model is about to see them, and
writes the shorter text back into the agent's state under the same message id. Every later model call then sends
exactly those bytes:

- **Prompt caches keep hitting.** Nothing the model has already seen changes. LangChain's ``ContextEditingMiddleware``
  replaces old tool results with ``[cleared]`` instead, which changes the prefix each time it clears.
- **Claude's thinking stays valid.** Thinking is bound to everything before it, and the model only ever saw the short
  version.
- **The information that matters stays.** Errors, failures and tracebacks are kept first, then the lines most related
  to the call; runs of similar lines collapse into one line and a count. Nothing is summarized by a model.

Requires ``pip install "llmslim[langchain-agents]"`` (Python 3.10+).
"""

from __future__ import annotations

import json
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.messages import AIMessage, ToolMessage
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'LLMSlimToolOutputMiddleware needs LangChain 1.x: pip install "llmslim[langchain-agents]" (Python 3.10+)'
    ) from exc

from .._tool_output import TOOL_HINT, shorten_tool_output

__all__ = ["LLMSlimToolOutputMiddleware"]

_MARK = "llmslim"


def _text(content: Any) -> Optional[str]:
    """A tool result's text, or ``None`` when it holds anything other than text (images, files)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif (
                isinstance(part, Mapping)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            ):
                parts.append(part["text"])
            else:
                return None
        return "\n".join(parts)
    return None


def _query(args: Any) -> Optional[str]:
    """What the call asked for, to focus the shortening."""
    if isinstance(args, Mapping):
        for key in ("query", "command", "pattern", "question", "url", "sql", "search"):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                return value[:500]
        try:
            return json.dumps(dict(args), sort_keys=True, ensure_ascii=False, default=str)[:500]
        except (TypeError, ValueError):
            return None
    return None


class LLMSlimToolOutputMiddleware(AgentMiddleware):
    """Shorten long tool results the first time the model is about to see them, and keep the short text in the state.

    Args:
        min_tokens: Leave results at or below this many tokens alone.
        keep_ratio: Fraction of a long result's tokens to keep.
        min_keep: Never shorten a result below this many tokens.
        only: Only these tools' results are shortened. ``None`` (the default) means every tool's.
        never: Tools whose results are never shortened, for example one that returns file contents the agent edits.
        compress_json: Whether JSON results are shortened too. Off by default: agents given shortened JSON spent
            extra turns fetching the fields that were cut.

    Example:
        >>> from langchain.agents import create_agent
        >>> from llmslim.integrations.langchain_agents import LLMSlimToolOutputMiddleware
        >>> agent = create_agent(
        ...     "anthropic:claude-haiku-5-5",
        ...     tools=[run_tests, search_logs],
        ...     middleware=[LLMSlimToolOutputMiddleware(never={"read_file"})],
        ... )
    """

    def __init__(
        self,
        *,
        min_tokens: int = 1500,
        keep_ratio: float = 0.35,
        min_keep: int = 1000,
        only: Optional[Iterable[str]] = None,
        never: Iterable[str] = (),
        compress_json: bool = False,
    ) -> None:
        super().__init__()
        if min_tokens < 1 or min_keep < 1:
            raise ValueError("min_tokens and min_keep must be positive")
        if not 0.0 < keep_ratio < 1.0:
            raise ValueError("keep_ratio must be between 0 and 1")
        self.min_tokens = min_tokens
        self.keep_ratio = keep_ratio
        self.min_keep = min_keep
        # Not self.tools: AgentMiddleware uses that for tools a middleware adds to the agent.
        self._only: Optional[FrozenSet[str]] = frozenset(only) if only is not None else None
        self._never: FrozenSet[str] = frozenset(never)
        self.compress_json = compress_json

    def before_model(self, state: Any, runtime: Any) -> Optional[Dict[str, Any]]:
        return self._shorten(state["messages"])

    async def abefore_model(self, state: Any, runtime: Any) -> Optional[Dict[str, Any]]:
        return self._shorten(state["messages"])

    # ------------------------------------------------------------------ internals

    def _eligible(self, name: Optional[str]) -> bool:
        if not name or name in self._never:
            return False
        return self._only is None or name in self._only

    def _shorten(self, messages: Sequence[Any]) -> Optional[Dict[str, Any]]:
        last_ai = max(
            (i for i, message in enumerate(messages) if isinstance(message, AIMessage)), default=-1
        )
        calls: Dict[str, Tuple[str, Any]] = {}
        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    call_id = call.get("id")
                    if call_id:
                        calls[call_id] = (call.get("name", ""), call.get("args"))
        updates = []
        for message in messages[last_ai + 1 :]:
            if not isinstance(message, ToolMessage) or message.id is None:
                continue
            if _MARK in (message.response_metadata or {}):
                continue  # shortened already
            name, args = calls.get(message.tool_call_id or "", (message.name or "", None))
            if not self._eligible(message.name or name):
                continue
            text = _text(message.content)
            if text is None:
                continue
            result = shorten_tool_output(
                text,
                _query(args),
                min_tokens=self.min_tokens,
                keep_ratio=self.keep_ratio,
                min_keep=self.min_keep,
                hint=TOOL_HINT,
                compress_json=self.compress_json,
            )
            if result is None:
                continue
            new_text, before, after = result
            metadata = {
                **(message.response_metadata or {}),
                _MARK: {"tokens_before": before, "tokens_after": after},
            }
            updates.append(
                message.model_copy(update={"content": new_text, "response_metadata": metadata})
            )
        return {"messages": updates} if updates else None
