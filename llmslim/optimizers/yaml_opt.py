"""YAML structure optimizer with optional PyYAML support and regex fallback.

Optimizes YAML by:
1. Stripping comments and redundant whitespace.
2. If `pyyaml` is installed: parsing, compacting, and re-serializing.
3. Fallback: regex-based comment stripping and indentation normalization.
"""

from __future__ import annotations

import re
from typing import Optional

from ..tokens import count_tokens

_YAML_COMMENT_RE = re.compile(r"^\s*#.*$", re.MULTILINE)
_YAML_INLINE_COMMENT_RE = re.compile(r"\s+#.*$", re.MULTILINE)
_BLANK_LINES_RE = re.compile(r"\n\s*\n")


def _regex_fallback_optimize(text: str) -> str:
    """Fallback comment and whitespace stripping without PyYAML."""
    lines = []
    for line in text.splitlines():
        # Remove comments if line is purely comment
        if _YAML_COMMENT_RE.match(line):
            continue
        # Strip inline comments unless inside quotes (basic heuristic)
        cleaned = _YAML_INLINE_COMMENT_RE.sub("", line)
        if cleaned.strip():
            lines.append(cleaned)
    res = "\n".join(lines)
    return _BLANK_LINES_RE.sub("\n", res).strip()


def optimize_yaml(text: str, target_ratio: float = 0.5) -> Optional[str]:
    """Compress YAML text. Uses PyYAML if available, otherwise regex fallback.

    Args:
        text: YAML text string.
        target_ratio: Target token fraction.

    Returns:
        Optimised YAML string, or ``None`` if optimization fails or isn't applicable.
    """
    try:
        import yaml
    except ImportError:
        yaml = None

    if yaml is not None:
        try:
            # Parse YAML documents
            data = list(yaml.safe_load_all(text))
            if not data or (len(data) == 1 and data[0] is None):
                return _regex_fallback_optimize(text)

            # Re-dump with compact settings
            if len(data) == 1:
                dumped = yaml.dump(data[0], default_flow_style=False, sort_keys=False)
            else:
                dumped = yaml.dump_all(data, default_flow_style=False, sort_keys=False)

            dumped_tokens = count_tokens(dumped)
            orig_tokens = count_tokens(text)
            if orig_tokens > 0 and dumped_tokens / orig_tokens <= target_ratio:
                return dumped.strip()

            # Fallback to regex optimization if dump wasn't sufficiently compressed
            regex_opt = _regex_fallback_optimize(text)
            return regex_opt if count_tokens(regex_opt) < dumped_tokens else dumped.strip()

        except Exception:
            return _regex_fallback_optimize(text)

    # PyYAML not available -> use regex fallback
    return _regex_fallback_optimize(text)
