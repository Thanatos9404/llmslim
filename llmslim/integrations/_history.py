"""Framework-free core shared by the gptme, Hermes Agent and Pydantic AI adapters.

An agent's history mixes text that must reach the model exactly as it is (the
system prompt, the newest turns, tool calls) with older history that can be
shortened. Each adapter describes its framework's messages as
:class:`HistoryItem` entries, calls :func:`fit_history`, and writes the result
back into copies of its own message objects. Keeping the budget logic here means
the three adapters behave the same way and it is tested without any framework
installed.

:func:`fit_history` works in steps and stops as soon as the history fits:

1. Items longer than their own ``cap`` are compressed to it.
2. If the total is over ``budget``, every older compressible item is compressed
   by the same ratio, so together they fill what the other items leave free.
3. If it is still over, groups of older items are dropped in ``drop_order``
   (oldest first by default). A dropped item is either removed or replaced by a
   short placeholder, as the adapter chooses.
4. If it is still over, the recent compressible items are compressed into what
   is left once the older history is reduced to what it cannot give up, and
   steps 2 and 3 run again with that room.

Protected items are never changed and never dropped; recent items are never
dropped. Token counts use :func:`llmslim.count_tokens`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from ..core import ContextCompressor, ContextRole
from ..tokens import count_tokens

# Options the adapters expose as their own fields; additional_compress_kwargs may not repeat them.
_RESERVED = ("min_tokens_for_compression", "relevance", "context_role")
# The smallest ratio LLMSlim is asked for, and how often to ask again after an overshoot.
_MIN_RATIO = 0.02
_ATTEMPTS = 3
# When recent items must shrink, older items that cannot be dropped are assumed to keep this
# share of their text; the recent items get the rest.
_OLDER_FLOOR_RATIO = 0.05

_KINDS = {
    ContextRole.TOOL.value: "tool output",
    ContextRole.ASSISTANT.value: "assistant message",
    ContextRole.USER.value: "user message",
}


@dataclass(frozen=True)
class HistoryItem:
    """One piece of history text, as :func:`fit_history` sees it.

    ``text`` is what is counted (and compressed, if ``compressible``). ``role``
    is the provenance used when compressing: tool output and assistant text are
    untrusted, so imperative wording in them is never force-kept. ``protected``
    items are kept verbatim and never dropped. ``cap`` is an optional per-item
    token limit applied before the overall budget. ``recent`` items are never
    dropped, and beyond their cap they are compressed only when nothing older
    is left to shorten.
    """

    text: str
    role: Union[ContextRole, str] = ContextRole.GENERAL
    protected: bool = False
    compressible: bool = True
    cap: Optional[int] = None
    recent: bool = False


@dataclass
class HistoryFit:
    """Result of :func:`fit_history`, one text per input item.

    ``texts[i]`` is the new text of item ``i``: unchanged, compressed, a
    placeholder, or ``None`` when the item was dropped with ``drop="remove"``.
    """

    texts: List[Optional[str]]
    original_tokens: int
    tokens: int
    budget: Optional[int]
    protected_tokens: int = 0
    compressed: List[int] = field(default_factory=list)
    dropped: List[int] = field(default_factory=list)

    @property
    def fits(self) -> bool:
        """Whether the history is now within the budget (always true without one)."""
        return self.budget is None or self.tokens <= self.budget

    @property
    def changed(self) -> bool:
        return bool(self.compressed or self.dropped)

    def summary(self) -> str:
        """One line for logs and adapter metadata."""
        parts = [f"{self.original_tokens:,} -> {self.tokens:,} tokens"]
        if self.budget is not None:
            parts.append(f"budget {self.budget:,}")
        parts.append(f"{len(self.compressed)} compressed, {len(self.dropped)} dropped")
        if self.budget is not None and not self.fits:
            if self.protected_tokens > self.budget:
                parts.append(
                    f"still over budget: the protected messages alone use {self.protected_tokens:,}"
                )
            else:
                parts.append("still over budget: what is left cannot be compressed or dropped")
        return "; ".join(parts)


def placeholder_text(item: HistoryItem, tokens: int) -> str:
    """The default stand-in for an item that was dropped or compressed to nothing."""
    role = item.role.value if isinstance(item.role, ContextRole) else str(item.role)
    kind = _KINDS.get(role, "context")
    return f"[{tokens:,} tokens of earlier {kind} omitted by LLMSlim]"


def validate_history_options(
    min_tokens: int,
    relevance: Any,
    additional_compress_kwargs: Optional[Mapping[str, Any]],
) -> None:
    """Fail when an adapter is built rather than on its first compaction."""
    if isinstance(min_tokens, bool) or not isinstance(min_tokens, int) or min_tokens < 0:
        raise ValueError("min_tokens must be a non-negative integer")
    clash = sorted(set(additional_compress_kwargs or {}) & set(_RESERVED))
    if clash:
        raise ValueError(
            "set these as adapter options, not in additional_compress_kwargs: " + ", ".join(clash)
        )
    # Builds the compressor once, so unknown options and bad relevance values fail here.
    _compressor(min_tokens, relevance, additional_compress_kwargs)


def _compressor(
    min_tokens: int, relevance: Any, additional_compress_kwargs: Optional[Mapping[str, Any]]
) -> ContextCompressor:
    try:
        return ContextCompressor(
            min_tokens_for_compression=min_tokens,
            relevance=relevance,
            **dict(additional_compress_kwargs or {}),
        )
    except TypeError as exc:
        raise ValueError(f"invalid additional_compress_kwargs: {exc}") from exc


def fit_history(
    items: Sequence[HistoryItem],
    budget: Optional[int],
    *,
    drop_order: Optional[Sequence[Sequence[int]]] = None,
    drop: str = "placeholder",
    placeholder: Callable[[HistoryItem, int], str] = placeholder_text,
    query: Optional[str] = None,
    min_tokens: int = 50,
    relevance: Any = "lexical",
    additional_compress_kwargs: Optional[Mapping[str, Any]] = None,
) -> HistoryFit:
    """Shorten the unprotected items so the history fits ``budget`` tokens.

    Args:
        items: The history, oldest first.
        budget: Token budget for all items together, or ``None`` to apply only
            the per-item caps.
        drop_order: Groups of item indices to drop, in order, when compression
            alone is not enough. A group is dropped whole, and only if none of
            its items is protected. Defaults to each item on its own, oldest
            first.
        drop: ``"placeholder"`` replaces a dropped item's text with
            ``placeholder(item, original_tokens)`` (for formats where the
            message itself must stay, such as a tool result paired with its
            call); ``"remove"`` returns ``None`` for it.
        placeholder: Text used for dropped items and for items that compress
            to nothing.
        query: Optional query; each item keeps the parts most relevant to it.
        min_tokens: Items with at most this many tokens are not compressed
            (they can still be dropped).
        relevance: ``"lexical"``, ``"semantic"`` or a callable scorer, as for
            :func:`llmslim.compress`.
        additional_compress_kwargs: Other :class:`llmslim.ContextCompressor`
            options, for example ``mode`` or ``selection``.
    """
    if drop not in ("placeholder", "remove"):
        raise ValueError("drop must be 'placeholder' or 'remove'")
    if budget is not None and budget < 0:
        raise ValueError("budget must be non-negative")
    n = len(items)
    texts: List[Optional[str]] = [item.text for item in items]
    original = [count_tokens(item.text) if item.text else 0 for item in items]
    current = list(original)
    compressed: Dict[int, None] = {}
    compressor = _compressor(min_tokens, relevance, additional_compress_kwargs)
    eligible = [
        i
        for i, item in enumerate(items)
        if item.compressible and not item.protected and original[i] > min_tokens
    ]
    flexible = set(eligible)

    def compress_to(i: int, target_tokens: float) -> Tuple[str, int]:
        """Item ``i``'s original text compressed to at most about ``target_tokens``."""
        ratio = min(1.0, max(target_tokens / original[i], _MIN_RATIO))
        for _ in range(_ATTEMPTS):
            result = compressor.compress(
                items[i].text, target_ratio=ratio, query=query, context_role=items[i].role
            )
            text = result.compressed_text
            if not text.strip():
                text = placeholder(items[i], original[i])
            tokens = count_tokens(text)
            if tokens <= target_tokens or ratio <= _MIN_RATIO:
                break
            # Whole sentences and lines can overshoot the target: ask for proportionally less.
            ratio = max(_MIN_RATIO, ratio * target_tokens / tokens * 0.95)
        return text, tokens

    def shrink(i: int, target_tokens: float) -> None:
        if current[i] <= target_tokens:
            return
        text, tokens = compress_to(i, target_tokens)
        if tokens < current[i]:
            texts[i] = text
            current[i] = tokens
            compressed[i] = None

    def shrink_together(indices: Sequence[int], force: bool = False) -> None:
        """Compress ``indices`` by one ratio so they fill what the other items leave free.

        With no room left for them at all, ``force`` compresses them as far as
        LLMSlim goes; otherwise they are left for dropping to deal with.
        """
        if budget is None or sum(current) <= budget:
            return
        tokens = sum(current[i] for i in indices)
        available = budget - (sum(current) - tokens)
        if tokens and (available > 0 or force):
            ratio = available / tokens if available > 0 else _MIN_RATIO
            for i in indices:
                shrink(i, current[i] * ratio)

    def stub_tokens(i: int) -> int:
        return count_tokens(placeholder(items[i], original[i])) if drop == "placeholder" else 0

    # 1. Per-item caps.
    for i in eligible:
        cap = items[i].cap
        if cap is not None and current[i] > cap:
            shrink(i, cap)

    older = [i for i in eligible if not items[i].recent]
    recent = [i for i in eligible if items[i].recent]
    groups = drop_order if drop_order is not None else [[i] for i in range(n)]
    droppable = [
        list(group)
        for group in groups
        if group and not any(items[i].protected or items[i].recent for i in group)
    ]
    after_caps = (list(texts), list(current), set(compressed))

    def fit_older(force: bool = False) -> List[int]:
        """Steps 2 and 3, on the older items as they were after the caps; returns the dropped."""
        for i in range(n):
            if not items[i].recent:
                texts[i], current[i] = after_caps[0][i], after_caps[1][i]
                compressed.pop(i, None)
                if i in after_caps[2]:
                    compressed[i] = None
        # 2. One shared ratio for the older compressible items.
        shrink_together(older, force)
        # 3. Drop groups, oldest first unless the adapter says otherwise.
        gone: List[int] = []
        for group in droppable:
            if budget is None or sum(current) <= budget:
                break
            live = [i for i in group if i not in gone]
            if drop == "placeholder":
                # A placeholder only helps where it is shorter than the text it replaces.
                live = [i for i in live if stub_tokens(i) < current[i]]
            for i in live:
                texts[i] = placeholder(items[i], original[i]) if drop == "placeholder" else None
                current[i] = stub_tokens(i)
                compressed.pop(i, None)
                gone.append(i)
        return gone

    dropped = fit_older()

    if budget is not None and sum(current) > budget and recent:
        # 4. The older history alone cannot make room. Leave it only what it cannot give up,
        #    compress the recent items into the rest, then fit the older history again.
        in_groups = {i for group in droppable for i in group}
        floor = 0
        for i in range(n):
            if items[i].recent:
                floor += 0 if i in flexible else current[i]
            elif i in in_groups:
                floor += min(stub_tokens(i), after_caps[1][i])
            elif i in flexible:
                floor += int(after_caps[1][i] * _OLDER_FLOOR_RATIO)
            else:
                floor += after_caps[1][i]
        recent_tokens = sum(current[i] for i in recent)
        # When even that cannot fit, get as close as LLMSlim can.
        ratio = (budget - floor) / recent_tokens if budget > floor else _MIN_RATIO
        for i in recent:
            shrink(i, current[i] * ratio)
        dropped = fit_older(force=True)

    return HistoryFit(
        texts=texts,
        original_tokens=sum(original),
        tokens=sum(current),
        budget=budget,
        protected_tokens=sum(original[i] for i, item in enumerate(items) if item.protected),
        compressed=sorted(compressed),
        dropped=sorted(dropped),
    )
