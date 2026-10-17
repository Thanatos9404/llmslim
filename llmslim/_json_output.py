"""Shorten a JSON tool result without silently dropping items.

Line-based selection treats JSON as lines, so a list of 80 issues keeps a window of a few and drops the rest without a
trace. Agents use list results to choose what to do next, so here:

- **Every item of a list stays**, as one compact line with its short identifying fields: ids, names, titles, states,
  dates, numbers and flags. Long text is cut to its first words; nested lists and objects become ``[12 items]`` or a
  few short fields.
- **Items related to the call stay whole**, ranked by the words they share with it.
- Only if even the compact lines don't fit are items dropped, from the middle, with a line saying how many and which
  numbers they had.

The output is deterministic. Nothing here calls a model.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from .focus import terms
from .tokens import count_tokens

_SHORT = 80  # characters a string keeps in a compact item
_MIN_ITEMS = 3  # smaller lists aren't worth restructuring
_WHOLE_SHARE = 0.5  # share of the budget that related items may use whole


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


# Fields that identify an item, kept at the tightest level.
_IDENTITY = (
    "id",
    "number",
    "key",
    "name",
    "title",
    "slug",
    "state",
    "status",
    "type",
    "kind",
    "created_at",
    "updated_at",
    "createdAt",
    "updatedAt",
    "date",
    "url",
    "path",
)
# (characters a string keeps, whether only identity fields stay); tried in order until every item fits.
_LEVELS = ((_SHORT, False), (40, False), (40, True))


def _short(value: Any, limit: int = _SHORT, depth: int = 0) -> Any:
    """A compact view of one value: short scalars as they are, long text cut, nesting summarized."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        if not value:
            return []
        if (
            depth == 0
            and all(isinstance(v, (str, int, float, bool)) for v in value)
            and len(_dumps(value)) <= limit
        ):
            return value
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        if depth >= 1:
            return "{…}"
        inner = {
            k: _short(v, limit, depth + 1)
            for k, v in value.items()
            if isinstance(v, (str, int, float, bool))
        }
        kept = dict(list(inner.items())[:3])
        return kept or "{…}"
    return str(value)[:limit]


def _compact(item: Any, limit: int = _SHORT, identity_only: bool = False) -> Any:
    if isinstance(item, dict):
        fields = item
        if identity_only:
            picked = {key: value for key, value in item.items() if key in _IDENTITY}
            fields = picked or dict(list(item.items())[:2])
        return {key: _short(value, limit) for key, value in fields.items()}
    return _short(item, limit)


def _label(item: Any, index: int) -> str:
    """How a dropped item is named in the marker line: its id, number or name, else its position."""
    if isinstance(item, dict):
        for key in ("number", "id", "key", "name", "title", "slug", "uuid"):
            value = item.get(key)
            if isinstance(value, (str, int)) and len(str(value)) <= 40:
                return str(value)
    return f"#{index}"


def _largest_list(
    data: Any, path: Tuple[Any, ...] = ()
) -> Optional[Tuple[Tuple[Any, ...], List[Any]]]:
    """The longest list of items in ``data`` (the list itself, or one inside an envelope like ``{"items": [...]}``)."""
    best: Optional[Tuple[Tuple[Any, ...], List[Any]]] = None
    if isinstance(data, list) and len(data) >= _MIN_ITEMS:
        best = (path, data)
    if isinstance(data, dict):
        for key, value in data.items():
            found = _largest_list(value, path + (key,)) if len(path) < 2 else None
            if found and (best is None or len(found[1]) > len(best[1])):
                best = found
    return best


def is_json(text: str) -> bool:
    """Whether ``text`` is a JSON object or array."""
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        json.loads(stripped)
    except ValueError:
        return False
    return True


def shorten_json(text: str, budget: int, query: Optional[str] = None) -> Optional[str]:
    """``text`` (JSON) shortened to about ``budget`` tokens, or ``None`` when it isn't JSON with a list worth shortening."""
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        data = json.loads(stripped)
    except ValueError:
        return None
    found = _largest_list(data)
    if found is None:
        return None
    path, items = found
    wanted = set(terms(query)) if query else set()

    def related(item: Any) -> int:
        return len(wanted & set(terms(_dumps(item)))) if wanted else 0

    scores = [related(item) for item in items]
    ranked = sorted((i for i in range(len(items)) if scores[i] > 0), key=lambda i: (-scores[i], i))
    whole: Dict[int, str] = {}
    used = 0
    for index in ranked:
        line = _dumps(items[index])
        cost = count_tokens(line)
        if used + cost > budget * _WHOLE_SHARE:
            continue
        whole[index] = line
        used += cost
    envelope = _envelope(data, path)
    overhead = count_tokens(envelope) + 30  # the header line
    for limit, identity_only in _LEVELS:
        lines = [
            whole.get(index) or _dumps(_compact(item, limit, identity_only))
            for index, item in enumerate(items)
        ]
        if sum(count_tokens(line) for line in lines) + overhead <= budget:
            break

    # Drop from the middle, never related items, until the list fits.
    keep = list(range(len(lines)))
    costs = [count_tokens(line) for line in lines]
    total = sum(costs) + overhead
    dropped: List[int] = []
    middle = len(keep) // 2
    order = sorted((i for i in keep if i not in whole), key=lambda i: (abs(i - middle), i))
    for index in order:
        if total <= budget:
            break
        dropped.append(index)
        total -= costs[index]
    dropped_set = set(dropped)
    body: List[str] = []
    marker_done = False
    for index, line in enumerate(lines):
        if index in dropped_set:
            if not marker_done:
                labels = [_label(items[i], i) for i in sorted(dropped)]
                shown = ", ".join(labels[:12]) + (", …" if len(labels) > 12 else "")
                body.append(f"… [{len(dropped)} more items not shown: {shown}]")
                marker_done = True
            continue
        body.append(line)
    where = (
        "".join(f"[{key!r}]" if isinstance(key, int) else f".{key}" for key in path)
        or "(top level)"
    )
    header = f"JSON list at {where}: {len(items)} items, one per line"
    if whole:
        header += (
            f"; the {len(whole)} related to the call are whole, the others show their short fields"
        )
    else:
        header += ", with their short fields"
    parts = [header + "."]
    if envelope:
        parts.append(f"Around the list: {envelope}")
    parts.extend(body)
    return "\n".join(parts)


def _envelope(data: Any, path: Tuple[Any, ...]) -> str:
    """The rest of the document around the list (counts, cursors, totals), compacted, or ''."""
    if not path or not isinstance(data, dict):
        return ""
    view = {key: _short(value) for key, value in data.items() if key != path[0]}
    return _dumps(view) if view else ""
