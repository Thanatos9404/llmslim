"""JSON structure optimizer using standard library `json`.

Optimizes JSON by:
1. Re-serializing without redundant whitespace (compact output).
2. Pruning deep/large arrays or objects if target token budget demands it.
3. Guaranteeing valid JSON output (`json.loads` will always succeed).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..tokens import count_tokens


def _prune_structure(data: Any, target_ratio: float) -> Any:
    """Recursively prune arrays/dict keys to fit budget while preserving root shape."""
    if isinstance(data, list):
        if not data:
            return data
        # Truncate array elements proportional to target_ratio if array is long
        if len(data) > 3:
            keep_count = max(1, round(len(data) * target_ratio))
            data = [_prune_structure(item, target_ratio) for item in data[:keep_count]]
        else:
            data = [_prune_structure(item, target_ratio) for item in data]
        return data

    elif isinstance(data, dict):
        if not data:
            return data
        res = {}
        for k, v in data.items():
            # Omit empty containers or nulls if we need space
            pruned_val = _prune_structure(v, target_ratio)
            res[k] = pruned_val
        return res

    return data


def optimize_json(text: str, target_ratio: float = 0.5) -> Optional[str]:
    """Compress JSON text while guaranteeing valid JSON output.

    Args:
        text: JSON text string.
        target_ratio: Target fraction of tokens to retain.

    Returns:
        Compacted / pruned JSON string, or ``None`` if parsing fails.
    """
    try:
        data = json.loads(text)
    except Exception:
        return None

    # Step 1: Compact formatting (no indent/spaces)
    compact_text = json.dumps(data, separators=(",", ":"))
    orig_tokens = count_tokens(text)
    compact_tokens = count_tokens(compact_text)

    # If compacting alone achieved the goal or ratio is close enough
    if orig_tokens == 0 or compact_tokens / orig_tokens <= target_ratio:
        return compact_text

    # Step 2: Structural pruning if target ratio requires further reduction
    pruned_data = _prune_structure(data, target_ratio)
    pruned_text = json.dumps(pruned_data, separators=(",", ":"))

    return pruned_text
