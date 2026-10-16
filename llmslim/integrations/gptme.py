"""gptme context provider backed by LLMSlim.

gptme compacts a conversation when it grows too large, through a pluggable
``ContextProvider`` (see https://gptme.org/docs/context-compression.html).
:class:`LLMSlimContextProvider` implements that interface: it keeps the system
prompt, the protected head, pinned messages, tool calls and the most recent
messages exactly as they are, and compresses older tool output and history with
LLMSlim until the conversation fits gptme's limit. Tool output keeps its
failures, tracebacks and line structure instead of being replaced by a stub.

Installing llmslim registers two gptme entry points:

* ``gptme.context_providers``: ``llmslim``, so
  ``get_context_provider("llmslim")`` and ``list_providers()`` find it.
* ``gptme.plugins``: ``llmslim`` (:mod:`llmslim.integrations.gptme_plugin`).
  gptme's automatic compaction and ``/compact trim`` always use the provider
  named ``"default"``; with this in ``~/.config/gptme/config.toml`` (or a
  project's ``gptme.toml``) the plugin registers LLMSlim under that name::

      [plugin.llmslim]
      compaction = true

Without ``compaction = true`` gptme's own compaction is unchanged.

Requires gptme 0.34 or newer: ``pip install "llmslim[gptme]"`` (Python 3.10+).
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from gptme.message import Message
    from gptme.tools.autocompact.context_provider import (
        CompactionResult,
        CompressionConfig,
        ContextProvider,
    )
    from gptme.util.reduce import message_contains_tool_use
except ImportError as exc:  # pragma: no cover - exercised only without the extra.
    raise ImportError(
        'llmslim.integrations.gptme requires gptme 0.34 or newer: pip install "llmslim[gptme]"'
    ) from exc

from ..core import ContextRole
from ..tokens import count_tokens
from ._history import (
    CALL,
    OTHER,
    PROMPT,
    REPLY,
    HistoryFit,
    HistoryItem,
    first_edited,
    fit_history,
    open_tool_round,
    protect_before,
    validate_history_options,
)

__all__ = ["LLMSlimContextProvider", "PROVIDER_NAME", "source_digest"]

logger = logging.getLogger(__name__)

PROVIDER_NAME = "llmslim"
# gptme's own auto_compact_log uses 80% of the model's context when no limit is given.
_DEFAULT_LIMIT_FRACTION = 0.8
# gptme stores tool output as system messages; only the leading ones are the system prompt.
_ROLES = {"system": ContextRole.TOOL, "assistant": ContextRole.ASSISTANT, "user": ContextRole.USER}
_OPTIONS = ("keep_recent", "min_tokens", "relevance", "additional_compress_kwargs")
# gptme keeps Claude's thinking inline in the assistant message, with its signature in a comment:
# "<think>...<!-- think-sig: ... --></think>". It sends only signed blocks back as thinking.
_THINK_BLOCK = re.compile(r"<(think|thinking)>.*?</\1>\s*", re.DOTALL)
_THINK_SIGNATURE = re.compile(r"<!-- think-sig: (.*?) -->", re.DOTALL)


class LLMSlimContextProvider(ContextProvider):
    """Compress older gptme history with LLMSlim so the conversation fits the limit.

    Kept exactly as they are: the leading system messages (the system prompt),
    the first ``config.keep_head`` messages, pinned messages, assistant messages
    that contain a tool call or a code block, and the user and assistant
    messages among the last ``keep_recent``. Then:

    1. Tool output (gptme's system messages), recent or not, longer than
       ``config.max_tool_result_tokens`` is compressed to that size.
    2. If the conversation is still over ``config.limit`` (80% of the model's
       context when gptme passes no limit, as gptme's own compaction does), the
       older messages are compressed by a shared ratio to fill what the kept
       messages leave free.
    3. If that is not enough, the oldest of them are replaced by a one-line
       placeholder.
    4. As a last resort, recent tool output is compressed below its cap.

    Messages are never removed or reordered, and their role, timestamp and
    other fields are kept, so tool results stay next to their calls. gptme
    creates the provider with no arguments; options are class attributes, set
    with keyword arguments or :meth:`configured`.

    Claude thinking (gptme's signed ``<think>`` blocks) is bound to everything
    before it. It is never compressed as text (that would break the
    signature): only the visible text of an assistant message is counted and
    compressed. Once a message is changed, the signed thinking of that message
    and of every later one is removed; the thinking before it is kept. While a
    tool round is unfinished and its
    assistant messages have such thinking, the provider first tries to fit by
    shortening only the tool output after the round's last thinking; the
    earlier history is compacted after the next user message instead, unless
    the conversation cannot fit the limit that way.
    """

    keep_recent: int = 6
    """Number of most recent messages kept verbatim (tool output among them is still capped)."""

    min_tokens: int = 200
    """Messages with at most this many tokens are not compressed."""

    relevance: Any = "lexical"
    """``"lexical"``, ``"semantic"`` (needs ``llmslim[semantic]``) or a callable scorer."""

    additional_compress_kwargs: Optional[Mapping[str, Any]] = None
    """Other ``llmslim.ContextCompressor`` options, for example ``mode``."""

    def __init__(
        self,
        *,
        keep_recent: Optional[int] = None,
        min_tokens: Optional[int] = None,
        relevance: Any = None,
        additional_compress_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if keep_recent is not None:
            self.keep_recent = keep_recent
        if min_tokens is not None:
            self.min_tokens = min_tokens
        if relevance is not None:
            self.relevance = relevance
        if additional_compress_kwargs is not None:
            self.additional_compress_kwargs = dict(additional_compress_kwargs)
        if (
            isinstance(self.keep_recent, bool)
            or not isinstance(self.keep_recent, int)
            or self.keep_recent < 0
        ):
            raise ValueError("keep_recent must be a non-negative integer")
        validate_history_options(self.min_tokens, self.relevance, self.additional_compress_kwargs)

    @classmethod
    def configured(cls, **options: Any) -> type:
        """Return a subclass with these options as defaults, for ``register_provider``.

        gptme instantiates registered providers without arguments, so options
        travel as class attributes. The options are validated here.
        """
        unknown = sorted(set(options) - set(_OPTIONS))
        if unknown:
            raise ValueError("unknown LLMSlimContextProvider options: " + ", ".join(unknown))
        cls(**options)
        attributes: Dict[str, Any] = dict(options, __module__=cls.__module__)
        if callable(attributes.get("relevance")):
            # A function stored on a class would become a bound method.
            attributes["relevance"] = staticmethod(attributes["relevance"])
        return type(cls.__name__, (cls,), attributes)

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def should_compress(self, messages: List[Message], config: CompressionConfig) -> bool:
        """True when the conversation is over the limit or older tool output is over its cap."""
        items = self._items(messages, config)
        tokens = [count_tokens(item.text) for item in items]
        limit = _resolve_limit(config)
        if limit is not None and sum(tokens) > limit:
            return True
        return any(
            item.cap is not None and not item.protected and count > max(item.cap, self.min_tokens)
            for item, count in zip(items, tokens)
        )

    def compress(self, messages: List[Message], config: CompressionConfig) -> CompactionResult:
        """Return the compacted messages; ``covered_through`` is the last message."""
        messages = list(messages)
        items = self._items(messages, config)
        limit = _resolve_limit(config)
        options: Dict[str, Any] = {
            "min_tokens": self.min_tokens,
            "relevance": self.relevance,
            "additional_compress_kwargs": self.additional_compress_kwargs,
        }
        owners = range(len(messages))
        fit: Optional[HistoryFit] = None
        tool_round = open_tool_round(
            [_kind(message) for message in messages], [_has_thinking(m) for m in messages]
        )
        if tool_round is not None:
            # Mid tool round: shorten only the tool output after its thinking, if that fits.
            attempt = fit_history(protect_before(items, owners, tool_round[1]), limit, **options)
            if attempt.fits:
                fit = attempt
                fit.kept_tool_round = True
        if fit is None:
            fit = fit_history(items, limit, **options)
        first = first_edited(fit, owners)
        keep_head = _keep_head(config)
        compacted: List[Message] = []
        for i, (message, text, item) in enumerate(zip(messages, fit.texts, items)):
            if first is not None and i >= first and _has_thinking(message):
                # Its signature covers history that has just changed: Anthropic would reject it.
                content, removed = _without_thinking(message.content)
                message = message.replace(content=content)
                fit.thinking_stripped += removed
            if text is not None and text != item.text:
                message = message.replace(content=text)
            # Like gptme's own compaction: pin the protected head so a later
            # limit_log cannot drop it.
            if i < keep_head and not message.pinned:
                message = message.replace(pinned=True)
            compacted.append(message)
        limitations: List[str] = []
        if fit.changed or not fit.fits:
            limitations.append(f"LLMSlim extractive compression: {fit.summary()}")
            logger.info("LLMSlim compacted the conversation: %s", fit.summary())
        if fit.dropped:
            limitations.append(
                f"{len(fit.dropped)} older message(s) replaced by a placeholder to fit the limit"
            )
        if fit.thinking_stripped:
            limitations.append(
                f"Claude thinking removed from message {first} on ({fit.thinking_stripped} "
                "block(s)): its signature covered history that changed"
            )
        return CompactionResult(
            messages=compacted,
            source_digest=source_digest(messages),
            covered_through=len(messages) - 1 if messages else -1,
            limitations=limitations,
        )

    def _items(self, messages: Sequence[Message], config: CompressionConfig) -> List[HistoryItem]:
        n = len(messages)
        system_prompt_end = 0
        while system_prompt_end < n and messages[system_prompt_end].role == "system":
            system_prompt_end += 1
        protected_until = max(system_prompt_end, _keep_head(config))
        recent_start = n - self.keep_recent if self.keep_recent else n
        cap = getattr(config, "max_tool_result_tokens", None)
        items: List[HistoryItem] = []
        for i, message in enumerate(messages):
            content = message.content if isinstance(message.content, str) else str(message.content)
            if _has_thinking(message):
                # Only the visible text is counted and compressed: rewriting signed thinking
                # would break its signature, and a changed message loses its thinking anyway.
                content = _without_thinking(content)[0]
            tool_output = message.role == "system"
            recent = i >= recent_start
            fixed = i < protected_until or bool(message.pinned) or _contains_tool_use(message)
            items.append(
                HistoryItem(
                    content,
                    _ROLES.get(message.role, ContextRole.GENERAL),
                    # Recent tool output is still held to the cap, as gptme's own trim does.
                    protected=fixed or (recent and not tool_output),
                    recent=recent,
                    cap=cap if tool_output else None,
                )
            )
        return items


def source_digest(messages: Sequence[Message]) -> str:
    """SHA-256 over each message's role and content, as gptme computes ``source_digest``."""
    digest = hashlib.sha256()
    for message in messages:
        digest.update(message.role.encode())
        digest.update(b"\x00")
        content = message.content if isinstance(message.content, str) else str(message.content)
        digest.update(content.encode())
        digest.update(b"\x00")
    return digest.hexdigest()


def _keep_head(config: CompressionConfig) -> int:
    return max(0, int(getattr(config, "keep_head", 0) or 0))


def _contains_tool_use(message: Message) -> bool:
    """Assistant messages with a tool call stay intact so their results are not orphaned."""
    if message.role != "assistant":
        return False
    if "```" in message.content:
        return True
    return bool(message_contains_tool_use(message))


def _kind(message: Message) -> str:
    if message.role == "assistant":
        return CALL if _contains_tool_use(message) else REPLY
    return PROMPT if message.role == "user" else OTHER


def _signed(block: str) -> bool:
    match = _THINK_SIGNATURE.search(block)
    return match is not None and bool(match.group(1).strip())


def _has_thinking(message: Message) -> bool:
    """Whether an assistant message carries thinking that gptme sends back signed."""
    return (
        message.role == "assistant"
        and isinstance(message.content, str)
        and any(_signed(match.group(0)) for match in _THINK_BLOCK.finditer(message.content))
    )


def _without_thinking(content: str) -> Tuple[str, int]:
    """``content`` without its signed thinking blocks, and how many were removed."""
    removed = 0

    def drop(match: re.Match[str]) -> str:
        nonlocal removed
        if not _signed(match.group(0)):
            return match.group(0)
        removed += 1
        return ""

    return _THINK_BLOCK.sub(drop, content), removed


def _resolve_limit(config: CompressionConfig) -> Optional[int]:
    """``config.limit``, or 80% of the current model's context like gptme's compaction."""
    if config.limit is not None:
        return int(config.limit)
    try:
        from gptme.llm.models import get_default_model, get_model

        model = get_default_model() or get_model("gpt-4")
        return int(_DEFAULT_LIMIT_FRACTION * model.context)
    except Exception:  # pragma: no cover - gptme without a model registry.
        return None
