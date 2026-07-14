"""Markdown structure optimizer (regex-based).

Preserves heading hierarchy (# H1, ## H2, etc.), fenced code blocks (```...```),
and bullet/numbered lists while compressing prose sections under headings.
"""

from __future__ import annotations

import re
from typing import List, Optional

from ..tokens import count_tokens

_FENCED_CODE_RE = re.compile(r"(```[\s\S]*?```)", re.MULTILINE)
_HEADING_RE = re.compile(r"^(#{1,6}\s+.*)$", re.MULTILINE)


def optimize_markdown(text: str, target_ratio: float = 0.5) -> Optional[str]:
    """Compress prose sections in Markdown while keeping headings and code blocks intact.

    Args:
        text: Markdown text string.
        target_ratio: Target token fraction to retain.

    Returns:
        Compressed Markdown text string.
    """
    if not text or not text.strip():
        return text

    # Split by fenced code blocks to prevent modifying code inside code blocks
    parts = _FENCED_CODE_RE.split(text)
    optimized_parts: List[str] = []

    for part in parts:
        # If this part is a code block, keep it unchanged
        if part.startswith("```") and part.endswith("```"):
            optimized_parts.append(part)
            continue

        # Split non-code part into sections by headings
        lines = part.split("\n")
        output_lines: List[str] = []
        prose_buffer: List[str] = []

        def flush_prose(buf: List[str], out: List[str]) -> None:
            if not buf:
                return
            # Retain non-empty prose lines up to target_ratio
            non_empty = [line for line in buf if line.strip()]
            if non_empty:
                keep_count = max(1, round(len(non_empty) * target_ratio))
                kept_prose = "\n".join(non_empty[:keep_count])
                out.append(kept_prose)
            buf.clear()

        for line in lines:
            if _HEADING_RE.match(line):
                flush_prose(prose_buffer, output_lines)
                output_lines.append(line)
            else:
                prose_buffer.append(line)
        flush_prose(prose_buffer, output_lines)

        optimized_parts.append("\n".join(output_lines))

    res = "".join(optimized_parts)
    # Return res if compression occurred
    return res if count_tokens(res) < count_tokens(text) else text
