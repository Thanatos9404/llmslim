"""XML/HTML structure optimizer using standard library `xml.etree.ElementTree`.

Optimizes XML/HTML by:
1. Collapsing whitespace between tags.
2. Truncating long child node sequences according to target_ratio.
3. Guaranteeing valid XML element structure.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from ..tokens import count_tokens


def _prune_element(elem: ET.Element, target_ratio: float) -> None:
    """Recursively collapse whitespace and prune repetitive child elements."""
    if elem.text:
        elem.text = elem.text.strip()
    if elem.tail:
        elem.tail = elem.tail.strip()

    if len(elem) > 3:
        keep_count = max(1, round(len(elem) * target_ratio))
        # Remove trailing children
        for child in list(elem)[keep_count:]:
            elem.remove(child)

    for child in elem:
        _prune_element(child, target_ratio)


def optimize_xml(text: str, target_ratio: float = 0.5) -> Optional[str]:
    """Compress XML text while guaranteeing valid XML tags and attributes.

    Args:
        text: XML text string.
        target_ratio: Target fraction of tokens to retain.

    Returns:
        Optimised XML string, or ``None`` if parsing fails.
    """
    try:
        root = ET.fromstring(text)
    except Exception:
        return None

    _prune_element(root, target_ratio)

    try:
        xml_bytes = ET.tostring(root, encoding="utf-8")
        res = xml_bytes.decode("utf-8")
        return res if count_tokens(res) < count_tokens(text) else text
    except Exception:
        return None
