"""Pydantic AI history processor backed by LLMSlim.

:func:`llmslim_history_processor` returns a function that keeps the message
history Pydantic AI sends to the model within a token budget. Pass it where a
history processor goes::

    from pydantic_ai import Agent
    from pydantic_ai.capabilities import ProcessHistory
    from llmslim.integrations.pydantic_ai import llmslim_history_processor

    fit = llmslim_history_processor(max_tokens=8_000)
    agent = Agent("openai:gpt-5", capabilities=[ProcessHistory(fit)])

    # Pydantic AI 1.x releases without pydantic_ai.capabilities:
    agent = Agent("openai:gpt-5", history_processors=[fit])

Requires ``pip install "llmslim[pydantic-ai]"`` (Python 3.10+).
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

try:
    from pydantic_ai.messages import (
        ModelMessage,
        ModelRequest,
        ModelResponse,
        RetryPromptPart,
        SystemPromptPart,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )
except ImportError as exc:  # pragma: no cover - exercised only without the extra.
    raise ImportError(
        "llmslim.integrations.pydantic_ai requires the optional extra: "
        'pip install "llmslim[pydantic-ai]"'
    ) from exc

from ..core import ContextRole
from ..tokens import count_tokens
from ._history import HistoryFit, HistoryItem, fit_history, validate_history_options

__all__ = ["fit_messages", "history_tokens", "llmslim_history_processor"]

# Parts Pydantic AI needs to keep: the system prompt, rendered instructions, tool-availability
# changes (deferred tools) and provider-side compaction markers.
_KEEP_KINDS = frozenset({"system-prompt", "instruction", "tool-availability-delta", "compaction"})

HistoryProcessor = Callable[[List[ModelMessage]], List[ModelMessage]]


def llmslim_history_processor(
    max_tokens: int,
    *,
    keep_recent: int = 2,
    min_tokens: int = 50,
    relevance: Any = "lexical",
    additional_compress_kwargs: Optional[Mapping[str, Any]] = None,
) -> HistoryProcessor:
    """Build a history processor that fits the history into ``max_tokens``.

    The processor never changes system prompt parts or the most recent user
    prompt, and never removes anything from the last ``keep_recent`` messages.
    Until the history fits, it:

    1. compresses older text with LLMSlim: user prompts, model text and tool
       results that are strings (tool output keeps its failures and line
       structure);
    2. removes older tool exchanges, oldest first: a model response with tool
       calls together with the request that returns their results;
    3. removes older turns whole, oldest first: a user prompt and everything up
       to the next user prompt;
    4. as a last resort, compresses the text in the last ``keep_recent``
       messages (a huge tool result that just came back, for example).

    Something is removed only together with every message that shares a tool
    call id with it, so tool calls and their returns always stay paired, and
    the result still alternates request, response, request. The turn holding
    the system prompt is never removed.

    Args:
        max_tokens: Budget for the text of all message parts, counted with
            :func:`llmslim.count_tokens` (see :func:`history_tokens`). The
            instructions and tool definitions Pydantic AI adds to each request
            are not part of the history and not counted.
        keep_recent: Number of most recent messages that are never removed and
            are compressed only as a last resort (at least 1, so the request
            about to be sent is always there).
        min_tokens: Parts with at most this many tokens are not compressed.
        relevance: ``"lexical"``, ``"semantic"`` (needs ``llmslim[semantic]``)
            or a callable ``scorer(query, texts) -> scores``.
        additional_compress_kwargs: Other ``llmslim.ContextCompressor``
            options, for example ``mode``.

    Returns:
        A function ``(messages) -> messages``. It does not modify its input.
    """
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    if isinstance(keep_recent, bool) or not isinstance(keep_recent, int) or keep_recent < 1:
        raise ValueError("keep_recent must be an integer >= 1")
    validate_history_options(min_tokens, relevance, additional_compress_kwargs)
    options: Dict[str, Any] = {
        "min_tokens": min_tokens,
        "relevance": relevance,
        "additional_compress_kwargs": dict(additional_compress_kwargs or {}),
    }

    def llmslim_history(messages: List[ModelMessage]) -> List[ModelMessage]:
        processed, _ = fit_messages(messages, max_tokens, keep_recent=keep_recent, **options)
        return processed

    return llmslim_history


def history_tokens(messages: Sequence[ModelMessage]) -> int:
    """Tokens in the text of all message parts, as :func:`llmslim_history_processor` counts them."""
    return sum(count_tokens(_describe(part)[0]) for message in messages for part in message.parts)


def fit_messages(
    messages: Sequence[ModelMessage],
    max_tokens: int,
    *,
    keep_recent: int = 2,
    min_tokens: int = 50,
    relevance: Any = "lexical",
    additional_compress_kwargs: Optional[Mapping[str, Any]] = None,
) -> Tuple[List[ModelMessage], HistoryFit]:
    """Like the processor, and also return the :class:`HistoryFit` with the token counts."""
    messages = list(messages)
    recent_start = max(0, len(messages) - keep_recent)
    last_prompt = max(
        (i for i, message in enumerate(messages) if _has_user_prompt(message)), default=-1
    )
    items: List[HistoryItem] = []
    slots: List[Tuple[int, int]] = []
    for mi, message in enumerate(messages):
        for pi, part in enumerate(message.parts):
            text, role, compressible = _describe(part)
            protected = getattr(part, "part_kind", None) in _KEEP_KINDS or (
                mi == last_prompt and isinstance(part, UserPromptPart)
            )
            items.append(
                HistoryItem(
                    text,
                    role,
                    protected=protected,
                    compressible=compressible,
                    recent=mi >= recent_start,
                )
            )
            slots.append((mi, pi))

    fit = fit_history(
        items,
        max_tokens,
        drop_order=_drop_order(messages, slots),
        drop="remove",
        min_tokens=min_tokens,
        relevance=relevance,
        additional_compress_kwargs=additional_compress_kwargs,
    )
    if not fit.changed:
        return messages, fit

    new_parts: Dict[int, List[Any]] = {mi: [] for mi in range(len(messages))}
    changed: Set[int] = set()
    for (mi, pi), new_text, item in zip(slots, fit.texts, items):
        # Any: the part types are a union that dataclasses.replace cannot be typed against.
        kept: Any = messages[mi].parts[pi]
        if new_text is None:
            changed.add(mi)
            continue
        if new_text != item.text:
            kept = dataclasses.replace(kept, content=new_text)
            changed.add(mi)
        new_parts[mi].append(kept)
    processed: List[ModelMessage] = []
    for mi, message in enumerate(messages):
        if mi not in changed:
            processed.append(message)
        elif new_parts[mi]:
            original: Any = message
            processed.append(dataclasses.replace(original, parts=new_parts[mi]))
    return processed, fit


def _describe(part: Any) -> Tuple[str, ContextRole, bool]:
    """Text counted for a part, its provenance, and whether LLMSlim may rewrite it."""
    if isinstance(part, SystemPromptPart):
        return part.content, ContextRole.SYSTEM, False
    if isinstance(part, UserPromptPart):
        if isinstance(part.content, str):
            return part.content, ContextRole.USER, True
        return " ".join(c for c in part.content if isinstance(c, str)), ContextRole.USER, False
    if isinstance(part, TextPart):
        return part.content, ContextRole.ASSISTANT, True
    if isinstance(part, ToolReturnPart):
        if isinstance(part.content, str):
            return part.content, ContextRole.TOOL, True
        return part.model_response_str(), ContextRole.TOOL, False
    if isinstance(part, ToolCallPart):
        return part.tool_name + " " + part.args_as_json_str(), ContextRole.ASSISTANT, False
    if isinstance(part, RetryPromptPart):
        return part.model_response(), ContextRole.TOOL, False
    content = getattr(part, "content", None)
    return (content if isinstance(content, str) else ""), ContextRole.GENERAL, False


def _has_user_prompt(message: ModelMessage) -> bool:
    return isinstance(message, ModelRequest) and any(
        isinstance(part, UserPromptPart) for part in message.parts
    )


def _drop_order(
    messages: Sequence[ModelMessage], slots: Sequence[Tuple[int, int]]
) -> List[List[int]]:
    """Item groups to remove, in order: older tool exchanges, then older turns.

    A group is offered only if no tool call id in it also appears outside it,
    so removing it can never orphan a tool call or a tool return.
    """
    ids = [
        {pid for pid in (getattr(p, "tool_call_id", None) for p in m.parts) if pid}
        for m in messages
    ]
    everywhere = Counter(pid for message_ids in ids for pid in message_ids)

    def self_contained(group: Sequence[int]) -> bool:
        inside = Counter(pid for i in group for pid in ids[i])
        return all(count == everywhere[pid] for pid, count in inside.items())

    exchanges = [
        [j, j + 1]
        for j in range(len(messages) - 1)
        if isinstance(messages[j], ModelResponse)
        and any(isinstance(p, ToolCallPart) for p in messages[j].parts)
        and isinstance(messages[j + 1], ModelRequest)
        and not _has_user_prompt(messages[j + 1])
    ]
    starts = [i for i, message in enumerate(messages) if _has_user_prompt(message)]
    if not starts or starts[0] != 0:
        starts.insert(0, 0)
    turns = [list(range(a, b)) for a, b in zip(starts, starts[1:] + [len(messages)])]

    by_message: Dict[int, List[int]] = {}
    for index, (mi, _) in enumerate(slots):
        by_message.setdefault(mi, []).append(index)
    return [
        [index for mi in group for index in by_message.get(mi, [])]
        for group in exchanges + turns
        if self_contained(group)
    ]
