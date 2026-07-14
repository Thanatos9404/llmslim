"""Structure-aware content optimizers for JSON, YAML, Markdown, and XML/HTML.

This package provides format-specific optimizers that preserve syntactic
and structural validity while compressing text content, removing redundancy,
and truncating elements to meet token target budgets.

Public API
----------
.. autofunction:: optimize_structured
"""

from __future__ import annotations

from typing import Optional

from ..analysis import ContentType
from .json_opt import optimize_json
from .markdown_opt import optimize_markdown
from .xml_opt import optimize_xml
from .yaml_opt import optimize_yaml


def optimize_structured(
    text: str,
    content_type: ContentType,
    target_ratio: float = 0.5,
) -> Optional[str]:
    """Dispatch text to the appropriate format optimizer based on *content_type*.

    Args:
        text: Input string.
        content_type: Detected or specified :class:`~llmslim.analysis.ContentType`.
        target_ratio: Target token compression ratio (0.0 to 1.0).

    Returns:
        Optimised string, or ``None`` if the content type is not supported or
        if structure optimization is not applicable/failed.
    """
    if content_type == ContentType.JSON:
        return optimize_json(text, target_ratio)
    elif content_type == ContentType.YAML:
        return optimize_yaml(text, target_ratio)
    elif content_type == ContentType.MARKDOWN:
        return optimize_markdown(text, target_ratio)
    elif content_type in (ContentType.XML, ContentType.HTML):
        return optimize_xml(text, target_ratio)
    return None
