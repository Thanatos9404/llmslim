"""Deterministic, first-sight compression of tool output in Anthropic Messages requests.

A coding agent resends its whole conversation on every turn. Large tool output (test logs, build output, search
results, API responses) stays in that history and is paid for again and again, and it fills the context window until
the agent compacts and loses work. This module shrinks such output once, the first time the model is about to see it,
and then sends exactly the same bytes on every later request:

- Only ``tool_result`` text after the last assistant turn is ever compressed: output the model has not seen yet.
  (Claude Code adds a ``system`` message after it, so this is not always the last message.)
- The result is stored under a key made from the tool call id and the text. Whenever that block comes back in a
  later request, the stored text is sent instead, byte for byte. So the prompt prefix stays identical (prompt caches
  keep hitting), and Claude's thinking blocks, which are bound to what preceded them, stay valid.
- Only output from shell, search and web tools (and MCP tools you opt in) is compressed. File reads the agent edits from, and
  any tool not on the list, are never touched, and neither is anything the proxy did not compress the first time it
  saw it.

Nothing here calls a model or the network.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Protocol, Tuple

from .._tool_output import shorten_tool_output

__all__ = [
    "COMPRESSIBLE_TOOLS",
    "BlockCache",
    "Policy",
    "RewriteReport",
    "block_key",
    "rewrite_request",
]

# Built-in tools whose output is often long and rarely needed verbatim: shell output, searches, web pages. Anything
# else, including file reads the agent will edit from and tools added after this list, is never touched.
COMPRESSIBLE_TOOLS = frozenset(
    {"Bash", "PowerShell", "Grep", "Glob", "WebFetch", "WebSearch", "Monitor"}
)


@dataclass(frozen=True)
class Policy:
    """Which tool output is compressed, and how far.

    Args:
        min_tokens: Output at or below this many tokens is left alone.
        keep_ratio: Fraction of the tokens to keep when output is compressed.
        min_keep: Never shrink output below this many tokens.
        tools: Built-in tools whose output may be compressed. Output from any other tool is never touched.
        mcp: Whether every MCP tool's output (``mcp__server__tool``) may be compressed too. Off by default: some MCP
            tools return live state the agent acts on, such as a browser page snapshot whose element refs it clicks.
            Add data tools one by one in ``tools`` instead, e.g. ``mcp__github__list_issues``.
        never: Tools whose output is never compressed, even if listed above.
    """

    min_tokens: int = 1500
    keep_ratio: float = 0.35
    min_keep: int = 1000
    tools: FrozenSet[str] = COMPRESSIBLE_TOOLS
    mcp: bool = False
    never: FrozenSet[str] = frozenset()

    def __post_init__(self) -> None:
        if self.min_tokens < 1 or self.min_keep < 1:
            raise ValueError("min_tokens and min_keep must be positive")
        if not 0.0 < self.keep_ratio < 1.0:
            raise ValueError("keep_ratio must be between 0 and 1")

    def eligible(self, tool: Optional[str]) -> bool:
        if not tool or tool in self.never:
            return False
        return tool in self.tools or (self.mcp and tool.startswith("mcp__"))


class BlockCache(Protocol):
    """Where first-sight decisions live, so later requests can send the same bytes."""

    def get(self, key: str) -> Optional[Tuple[str, int, int]]:
        """``(compressed_text, tokens_before, tokens_after)`` for a block compressed earlier, or ``None``."""

    def put(
        self, key: str, *, tool: str, original: str, compressed: str, before: int, after: int
    ) -> None: ...


@dataclass
class RewriteReport:
    """What one request rewrite did. Token counts cover every compressed block in the request, new or replayed:
    ``tokens_before - tokens_after`` input tokens were not sent this time."""

    compressed: int = 0
    replayed: int = 0
    tokens_before: int = 0
    tokens_after: int = 0
    tools: Dict[str, int] = field(default_factory=dict)

    @property
    def saved(self) -> int:
        return self.tokens_before - self.tokens_after

    @property
    def changed(self) -> bool:
        return bool(self.compressed or self.replayed)


def block_key(tool_use_id: str, text: str) -> str:
    """Identity of one piece of tool output: its call id and its exact text."""
    return hashlib.sha256(f"{tool_use_id}\0{text}".encode("utf-8")).hexdigest()


def _tool_calls(messages: List[Any]) -> Dict[str, Tuple[str, Any]]:
    calls: Dict[str, Tuple[str, Any]] = {}
    for message in messages:
        if not isinstance(message, Mapping) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, Mapping)
                and block.get("type") == "tool_use"
                and isinstance(block.get("id"), str)
            ):
                calls[block["id"]] = (str(block.get("name", "")), block.get("input"))
    return calls


def _query(tool_input: Any) -> Optional[str]:
    """What the call asked for, to focus the compression: a shell command, a search pattern, or the input itself."""
    if isinstance(tool_input, Mapping):
        for key in ("command", "pattern", "query", "url", "prompt"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value[:500]
        try:
            return json.dumps(tool_input, sort_keys=True, ensure_ascii=False)[:500]
        except (TypeError, ValueError):
            return None
    return None


def compress_output(
    text: str, query: Optional[str], policy: Policy
) -> Optional[Tuple[str, int, int]]:
    """``(new_text, tokens_before, tokens_after)``, or ``None`` when the output should be left as it is."""
    return shorten_tool_output(
        text,
        query,
        min_tokens=policy.min_tokens,
        keep_ratio=policy.keep_ratio,
        min_keep=policy.min_keep,
    )


def rewrite_request(
    body: Mapping[str, Any], cache: BlockCache, policy: Policy = Policy()
) -> Tuple[Any, RewriteReport]:
    """Return ``(body, report)`` with tool output compressed on first sight and replayed byte for byte afterwards.

    ``body`` is a Messages API request (``/v1/messages`` or ``/v1/messages/count_tokens``). It is never modified;
    when nothing changes, the same object comes back.
    """
    report = RewriteReport()
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return body, report
    calls = _tool_calls(messages)
    # Output the model has not seen yet: everything after its last turn.
    assistant_turns = [
        i for i, m in enumerate(messages) if isinstance(m, Mapping) and m.get("role") == "assistant"
    ]
    first_new = assistant_turns[-1] + 1 if assistant_turns else 0
    out: Optional[List[Any]] = None

    for index, message in enumerate(messages):
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        new_content: Optional[List[Any]] = None
        for position, block in enumerate(content):
            if not isinstance(block, Mapping) or block.get("type") != "tool_result":
                continue
            call_id = block.get("tool_use_id")
            if not isinstance(call_id, str):
                continue
            tool, tool_input = calls.get(call_id, ("", None))
            new_block = _rewrite_block(
                block, call_id, tool, tool_input, index >= first_new, cache, policy, report
            )
            if new_block is not block:
                if new_content is None:
                    new_content = list(content)
                new_content[position] = new_block
        if new_content is not None:
            if out is None:
                out = list(messages)
            new_message = dict(message)
            new_message["content"] = new_content
            out[index] = new_message

    if out is None:
        return body, report
    new_body = dict(body)
    new_body["messages"] = out
    return new_body, report


def _rewrite_block(
    block: Mapping[str, Any],
    call_id: str,
    tool: str,
    tool_input: Any,
    newest: bool,
    cache: BlockCache,
    policy: Policy,
    report: RewriteReport,
) -> Any:
    content = block.get("content")
    if isinstance(content, str):
        new_text = _rewrite_text(content, call_id, tool, tool_input, newest, cache, policy, report)
        if new_text is None:
            return block
        new_block = dict(block)
        new_block["content"] = new_text
        return new_block
    if not isinstance(content, list):
        return block
    new_parts: Optional[List[Any]] = None
    for position, part in enumerate(content):
        if (
            not isinstance(part, Mapping)
            or part.get("type") != "text"
            or not isinstance(part.get("text"), str)
        ):
            continue  # images and other parts pass through
        new_text = _rewrite_text(
            part["text"], call_id, tool, tool_input, newest, cache, policy, report
        )
        if new_text is None:
            continue
        if new_parts is None:
            new_parts = copy.copy(content)
        new_part = dict(part)
        new_part["text"] = new_text
        new_parts[position] = new_part
    if new_parts is None:
        return block
    new_block = dict(block)
    new_block["content"] = new_parts
    return new_block


def _rewrite_text(
    text: str,
    call_id: str,
    tool: str,
    tool_input: Any,
    newest: bool,
    cache: BlockCache,
    policy: Policy,
    report: RewriteReport,
) -> Optional[str]:
    key = block_key(call_id, text)
    stored = cache.get(key)
    if stored is not None:
        compressed, before, after = stored
        report.replayed += 1
        report.tokens_before += before
        report.tokens_after += after
        return compressed
    if not newest or not policy.eligible(tool):
        return None
    result = compress_output(text, _query(tool_input), policy)
    if result is None:
        return None
    new_text, before, after = result
    cache.put(key, tool=tool, original=text, compressed=new_text, before=before, after=after)
    report.compressed += 1
    report.tokens_before += before
    report.tokens_after += after
    report.tools[tool] = report.tools.get(tool, 0) + 1
    return new_text
