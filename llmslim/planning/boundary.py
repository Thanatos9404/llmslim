"""The provenance envelope that marks every planned item as trusted or untrusted.

The planner renders each kept item as::

    <llmslim_context id="..." kind="..." role="..." trusted="true|false">
    content
    </llmslim_context>

Two rules keep that boundary intact:

* attribute values are escaped (``&``, ``<``, ``>``, ``"``, line breaks and
  other control characters), so an item ID cannot add or change attributes;
* in untrusted content, every ``<llmslim_context`` and ``</llmslim_context``
  tag (any letter case, with whitespace or invisible format characters around
  the ``/``) has its ``<`` replaced by ``&lt;``. The text stays readable but can
  no longer close the block or open a forged, trusted one.

Content without such a tag is returned unchanged, byte for byte. Trusted
(system/developer) content is never rewritten. :mod:`llmslim.integrations.web_search`
uses the same helpers, so the escaping is identical wherever untrusted text is
cleaned.
"""

from __future__ import annotations

import re

__all__ = [
    "BOUNDARY_TAG",
    "escape_boundary_attribute",
    "neutralize_boundary_tags",
]

#: Element name of the planner's provenance envelope.
BOUNDARY_TAG = "llmslim_context"

_ATTRIBUTE_ENTITIES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}
# Characters that could end the attribute, start markup or break the header line.
_ATTRIBUTE_SPECIAL_RE = re.compile('[&<>"\x00-\x1f\x7f-\x9f\u2028\u2029]')

# Characters a tokenizer or reader may skip between ``<``, ``/`` and the tag name:
# whitespace plus zero-width, joiner, bidirectional and word-joiner formatting
# characters, the byte-order mark, variation selectors and Unicode tag characters.
_TAG_GAP = (
    "[\\s\u00ad\u034f\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f"
    "\ufe00-\ufe0f\ufeff\U000e0000-\U000e007f\U000e0100-\U000e01ef]*"
)
# Each ``/`` starts a new gap run (``(?:/gap)*`` rather than ``/?gap``), so a long
# gap run after ``<`` cannot be split between two adjacent ``*`` loops while
# backtracking, and matching stays linear in the length of the text.
_BOUNDARY_TAG_RE = re.compile(f"<({_TAG_GAP}(?:/{_TAG_GAP})*)({BOUNDARY_TAG})", re.IGNORECASE)


def _attribute_entity(match: re.Match[str]) -> str:
    char = match.group(0)
    return _ATTRIBUTE_ENTITIES.get(char) or f"&#x{ord(char):X};"


def escape_boundary_attribute(value: str) -> str:
    """Escape ``value`` for a double-quoted envelope attribute.

    ``&``, ``<``, ``>`` and ``"`` become named entities; C0/C1 control
    characters (including tab and line breaks) and U+2028/U+2029 become numeric
    references such as ``&#xA;``. Values without these characters are returned
    unchanged.
    """

    return _ATTRIBUTE_SPECIAL_RE.sub(_attribute_entity, value)


def neutralize_boundary_tags(text: str) -> str:
    """Make every envelope open or close tag in untrusted ``text`` inert.

    ``<llmslim_context``, ``</llmslim_context``, ``< / LLMSLIM_CONTEXT`` and
    similar spellings become ``&lt;llmslim_context`` and so on; nothing else
    changes. Already-neutralized text is left as it is, so applying this twice
    is the same as applying it once.
    """

    if "<" not in text:
        return text
    return _BOUNDARY_TAG_RE.sub(r"&lt;\1\2", text)
