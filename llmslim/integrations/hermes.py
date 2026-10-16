"""Hermes Agent context engine backed by LLMSlim.

Hermes Agent (NousResearch/hermes-agent) lets a plugin replace its built-in
context compressor with any ``agent.context_engine.ContextEngine``.
:class:`LLMSlimContextEngine` compresses locally instead of asking a model to
summarize: no LLM call, deterministic output, and the start of the prompt stays
byte-for-byte the same so the provider's prompt cache keeps hitting.

Hermes finds the plugin in either of two ways:

* llmslim's ``hermes_agent.plugins`` entry point, when llmslim is installed in
  the Python environment Hermes runs in, or
* a two-file directory plugin in ``~/.hermes/plugins/llmslim/`` whose
  ``__init__.py`` re-exports :func:`register` (see
  ``docs/integrations/HERMES.md``).

Either way, enable it and select the engine in ``~/.hermes/config.yaml``::

    plugins:
      enabled: [llmslim]
    context:
      engine: llmslim

Optional settings (see :data:`CONFIG_KEYS`) go under
``plugins.entries.llmslim.settings``. There is no ``llmslim[hermes]`` extra:
current Hermes releases are installed with its installer, not from PyPI, and the
engine needs nothing beyond llmslim itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from agent.context_engine import ContextEngine
except ImportError as exc:  # pragma: no cover - exercised only without Hermes Agent.
    raise ImportError(
        "llmslim.integrations.hermes needs Hermes Agent (agent.context_engine): "
        "install llmslim into the Python environment Hermes runs in"
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
    is_signed_thinking,
    open_tool_round,
    validate_history_options,
)

__all__ = ["CONFIG_KEYS", "ENGINE_NAME", "LLMSlimContextEngine", "plugin_settings", "register"]

logger = logging.getLogger(__name__)

ENGINE_NAME = "llmslim"
CONFIG_KEYS = (
    "threshold_percent",
    "target_percent",
    "protect_first_n",
    "protect_last_n",
    "min_tokens",
    "relevance",
    "additional_compress_kwargs",
)
_ROLES = {"tool": ContextRole.TOOL, "assistant": ContextRole.ASSISTANT, "user": ContextRole.USER}
# Where Hermes keeps an assistant turn's Anthropic thinking blocks, and the readable copies of
# their text; Hermes's own agent/anthropic_thinking_replay.py strips rejected thinking from both.
_THINKING_CARRIERS = ("reasoning_details", "anthropic_content_blocks", "_anthropic_content_blocks")
_READABLE_THINKING = ("reasoning", "reasoning_content")


class LLMSlimContextEngine(ContextEngine):
    """A Hermes context engine that compresses older turns with LLMSlim.

    Compaction fires when the prompt reaches ``threshold_percent`` of the
    model's context window. It then keeps, unchanged and as the same objects:

    * the system prompt and the first ``protect_first_n`` other messages
      (Hermes's protected head), and
    * the user and assistant messages among the last ``protect_last_n``,

    and compresses the text content of the messages in between (tool results,
    user and assistant text) until the prompt is about ``target_percent`` of the
    window. If that is not enough, the oldest of them are replaced by a
    one-line placeholder, and as a last resort tool results in the tail are
    compressed too. Tool calls, ``tool_call_id`` and every other field are
    untouched, and no message is removed, so tool calls and results stay
    paired.

    Prompt caching: messages this engine already compressed in an earlier
    compaction are left alone as long as compressing the newer ones is enough,
    so the cached prefix (system prompt, head, earlier compacted history) is
    sent byte-for-byte the same and only the tail after it changes.
    ``focus_topic`` from ``/compress <topic>`` is used as the query, so the
    parts of each message about that topic are kept first.

    Claude thinking: each signed thinking block is bound to everything before
    it, so the signed thinking of the first changed message and of every later
    assistant message is removed (Anthropic would reject it); the blocks before
    the first change are kept. While a tool round is unfinished and its
    assistant turns have signed thinking, compaction first leaves everything up
    to the round's last thinking alone, and compacts the earlier messages at
    the next user message instead, as long as the request still fits the
    model's context window.
    """

    def __init__(
        self,
        *,
        context_length: int = 0,
        threshold_percent: float = 0.75,
        target_percent: float = 0.5,
        protect_first_n: int = 3,
        protect_last_n: int = 6,
        min_tokens: int = 200,
        relevance: Any = "lexical",
        additional_compress_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> None:
        for name, value in (
            ("protect_first_n", protect_first_n),
            ("protect_last_n", protect_last_n),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not 0.0 < float(target_percent) < float(threshold_percent) <= 1.0:
            raise ValueError("need 0 < target_percent < threshold_percent <= 1")
        validate_history_options(min_tokens, relevance, additional_compress_kwargs)
        self.threshold_percent = float(threshold_percent)
        self.target_percent = float(target_percent)
        self.protect_first_n = protect_first_n
        self.protect_last_n = protect_last_n
        self.min_tokens = min_tokens
        self.relevance = relevance
        self.additional_compress_kwargs = dict(additional_compress_kwargs or {})
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.compression_count = 0
        self.context_length = 0
        self.threshold_tokens = 0
        self.last_fit: Optional[HistoryFit] = None
        self._previous_output: List[str] = []
        if context_length:
            self.context_length = int(context_length)
            self.threshold_tokens = int(self.context_length * self.threshold_percent)

    @property
    def name(self) -> str:
        return ENGINE_NAME

    def update_from_response(self, usage: Dict[str, Any]) -> None:
        prompt = _as_int(usage.get("prompt_tokens"))
        completion = _as_int(usage.get("completion_tokens"))
        self.last_prompt_tokens = prompt
        self.last_completion_tokens = completion
        self.last_total_tokens = _as_int(usage.get("total_tokens")) or prompt + completion

    def should_compress(self, prompt_tokens: Optional[int] = None) -> bool:
        tokens = self.last_prompt_tokens if prompt_tokens is None else prompt_tokens
        return self.threshold_tokens > 0 and tokens >= self.threshold_tokens

    def should_compress_preflight(self, messages: List[Dict[str, Any]]) -> bool:
        """Count the messages locally before the first API call of a turn."""
        return self.should_compress(sum(count_tokens(_text(m)[0]) for m in messages))

    def has_content_to_compress(self, messages: List[Dict[str, Any]]) -> bool:
        head_end, tail_start = self._bounds(messages)
        return any(
            _compressible(message) and count_tokens(_text(message)[0]) > self.min_tokens
            for message in messages[head_end:tail_start]
        )

    def compress(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: Optional[int] = None,
        focus_topic: Optional[str] = None,
        force: bool = False,
        memory_context: str = "",
    ) -> List[Dict[str, Any]]:
        """Return the messages with older turns compressed to fit ``target_percent``.

        ``current_tokens`` (Hermes's estimate of the whole request, including the
        system prompt and tool schemas) is used to leave room for what is not in
        ``messages``. ``force`` and ``memory_context`` are accepted for the
        interface and not needed: there is no cooldown and no summary prompt.
        """
        messages = list(messages)
        if not self.context_length:
            logger.warning("LLMSlim context engine has no context length yet; not compressing")
            return messages
        head_end, tail_start = self._bounds(messages)
        if head_end >= tail_start:
            return messages
        texts = [_text(message) for message in messages]
        message_tokens = sum(count_tokens(text) for text, _ in texts)
        overhead = max(0, (current_tokens or 0) - message_tokens)
        budget = max(0, int(self.context_length * self.target_percent) - overhead)

        frozen_end = self._unchanged_prefix(messages)
        fit: Optional[HistoryFit] = None
        tool_round = open_tool_round(
            [_kind(message) for message in messages], [_has_thinking(m) for m in messages]
        )
        if tool_round is not None:
            # Mid tool round: leave everything up to its last thinking alone while the request
            # still fits the context window; the earlier history waits for the next user message.
            attempt = self._fit(
                messages,
                texts,
                head_end,
                tail_start,
                max(frozen_end, tool_round[1]),
                budget,
                focus_topic,
            )
            if attempt.fits or attempt.tokens <= self.context_length - overhead:
                fit = attempt
                fit.kept_tool_round = True
        if fit is None:
            fit = self._fit(messages, texts, head_end, tail_start, frozen_end, budget, focus_topic)
            if not fit.fits and frozen_end > head_end:
                # Compressing the new turns is not enough: compress the earlier ones again too.
                fit = self._fit(
                    messages, texts, head_end, tail_start, head_end, budget, focus_topic
                )
        self.last_fit = fit

        first = first_edited(fit, range(len(messages)))
        compacted: List[Dict[str, Any]] = []
        for i, (message, (original, _), text) in enumerate(zip(messages, texts, fit.texts)):
            if text is not None and text != original:
                message = {**message, "content": text}
            if first is not None and i >= first and _has_thinking(message):
                # Its signature covers history that has just changed: Anthropic would reject it.
                message, removed = _without_thinking(message)
                fit.thinking_stripped += removed
            compacted.append(message)
        if fit.changed:
            self.compression_count += 1
            logger.info("LLMSlim context engine: %s", fit.summary())
        elif fit.kept_tool_round and not fit.fits:
            logger.info("LLMSlim context engine: %s", fit.summary())
        self._previous_output = [_digest(message) for message in compacted]
        return compacted

    def on_session_reset(self) -> None:
        super().on_session_reset()
        self._previous_output = []
        self.last_fit = None

    def _bounds(self, messages: Sequence[Mapping[str, Any]]) -> Tuple[int, int]:
        """Index after the protected head, and index where the protected tail starts."""
        n = len(messages)
        head_end = 0
        while head_end < n and messages[head_end].get("role") == "system":
            head_end += 1
        head_end = min(n, head_end + self.protect_first_n)
        return head_end, max(head_end, n - self.protect_last_n)

    def _unchanged_prefix(self, messages: Sequence[Mapping[str, Any]]) -> int:
        """How many leading messages are exactly what the last compaction returned."""
        count = 0
        for message, previous in zip(messages, self._previous_output):
            if _digest(message) != previous:
                break
            count += 1
        return count

    def _fit(
        self,
        messages: Sequence[Mapping[str, Any]],
        texts: Sequence[Tuple[str, bool]],
        head_end: int,
        tail_start: int,
        frozen_end: int,
        budget: int,
        focus_topic: Optional[str],
    ) -> HistoryFit:
        items = []
        for i, (message, (text, is_str)) in enumerate(zip(messages, texts)):
            role = message.get("role")
            in_tail = i >= tail_start
            items.append(
                HistoryItem(
                    text,
                    _ROLES.get(str(role), ContextRole.GENERAL),
                    # Tool results in the tail are compressed only as a last resort; system
                    # messages and multimodal content are never rewritten.
                    protected=(
                        i < max(head_end, frozen_end)
                        or role == "system"
                        or not is_str
                        or (in_tail and role != "tool")
                    ),
                    compressible=is_str,
                    recent=in_tail,
                )
            )
        return fit_history(
            items,
            budget,
            # A placeholder keeps every message (and its tool_call_id) in place.
            drop="placeholder",
            query=focus_topic or None,
            min_tokens=self.min_tokens,
            relevance=self.relevance,
            additional_compress_kwargs=self.additional_compress_kwargs,
        )


def register(ctx: Any) -> None:
    """Hermes plugin hook: register the engine (select it with ``context.engine: llmslim``)."""
    ctx.register_context_engine(LLMSlimContextEngine(**plugin_settings(ctx)))


def plugin_settings(ctx: Any) -> Dict[str, Any]:
    """Engine options from ``plugins.entries.<plugin id>.settings`` in config.yaml.

    Uses ``ctx.get_config`` where Hermes provides it (0.21 and newer) and reads
    config.yaml directly on older releases.
    """
    getter = getattr(ctx, "get_config", None)
    if callable(getter):
        values = {key: getter(key) for key in CONFIG_KEYS}
        return {key: value for key, value in values.items() if value is not None}
    try:
        from hermes_cli.config import load_config

        config = load_config()
    except Exception:  # pragma: no cover - Hermes without hermes_cli or an unreadable config.
        return {}
    manifest = getattr(ctx, "manifest", None)
    plugin_id = getattr(manifest, "key", None) or getattr(manifest, "name", None) or ENGINE_NAME
    entries = (config.get("plugins") or {}).get("entries") or {}
    entry = entries.get(plugin_id) if isinstance(entries, Mapping) else None
    settings = entry.get("settings") if isinstance(entry, Mapping) else None
    if not isinstance(settings, Mapping):
        return {}
    return {key: settings[key] for key in CONFIG_KEYS if key in settings}


def _text(message: Mapping[str, Any]) -> Tuple[str, bool]:
    """The message's text, and whether it is a plain string LLMSlim may rewrite."""
    content = message.get("content")
    if isinstance(content, str):
        return content, True
    if isinstance(content, list):
        # Multimodal content: count the text parts, leave the list as it is.
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, Mapping) and isinstance(part.get("text"), str)
        ]
        return "\n".join(parts), False
    return "", False


def _compressible(message: Mapping[str, Any]) -> bool:
    return message.get("role") != "system" and isinstance(message.get("content"), str)


def _kind(message: Mapping[str, Any]) -> str:
    role = message.get("role")
    if role == "assistant":
        return CALL if message.get("tool_calls") else REPLY
    return PROMPT if role == "user" else OTHER


def _has_thinking(message: Mapping[str, Any]) -> bool:
    """Whether an assistant message carries signed Anthropic thinking."""
    return message.get("role") == "assistant" and any(
        is_signed_thinking(block)
        for key in _THINKING_CARRIERS
        if isinstance(message.get(key), list)
        for block in message[key]
    )


def _without_thinking(message: Mapping[str, Any]) -> Tuple[Dict[str, Any], int]:
    """A copy of ``message`` without its signed thinking, and how many blocks were removed.

    The readable copy of that thinking (``reasoning``, ``reasoning_content``)
    goes too, so Hermes cannot send it back as unsigned thinking or text.
    """
    copy = dict(message)
    readable: List[str] = []
    removed = 0
    for key in _THINKING_CARRIERS:
        blocks = message.get(key)
        if not isinstance(blocks, list):
            continue
        signed = [block for block in blocks if is_signed_thinking(block)]
        if not signed:
            continue
        removed += len(signed)
        if not readable:
            readable = [
                b["thinking"]
                for b in signed
                if isinstance(b, Mapping) and isinstance(b.get("thinking"), str)
            ]
        kept = [block for block in blocks if not is_signed_thinking(block)]
        if kept:
            copy[key] = kept
        else:
            del copy[key]
    mirror = "\n\n".join(text for text in readable if text)
    for key in _READABLE_THINKING:
        if mirror and copy.get(key) == mirror:
            del copy[key]
    return copy, removed


def _digest(message: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(message, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
