"""Transparent answer scorer for the frozen v0.6 context-planning suite.

The suite (``benchmarks/datasets/v06_context_planning.json``) ships known answers
but no answer scorer: ``benchmarks/v06_planner.py`` checks whether the expected
facts and tools survive in the *context*, with a case-folded substring test.
This module applies that same test to a reader's *answer*, with a fixed,
documented normalization so that formatting differences that do not change the
fact are not counted as misses. The rules were written before any live run and
are applied identically to every arm and every reader.

Expected items for a case are its ``expected_facts`` followed by its
``expected_tools``. ``required_instructions`` describe behaviour, not answer
content, and are not scored.

Normalization (applied to the answer and to each expected item):

1. Unicode NFKC; zero-width characters and soft hyphens removed.
2. Every decimal digit in any script (Devanagari, Bengali, Gujarati, Gurmukhi,
   Odia, Tamil, Telugu, Kannada, Malayalam, ...) mapped to ASCII 0-9.
3. Devanagari: a nasal consonant plus virama before a consonant is folded to
   anusvara, so both spellings of a word such as सितंबर / सितम्बर match.
4. Case folding.
5. Currency markers dropped: the rupee sign, and ``Rs``/``Rs.``/``INR`` when
   they precede a number. Thousands separators between digits dropped, so
   ``₹45,600``, ``Rs. 45,600`` and ``45600`` are the same amount, and Indian
   (``87,50,000``) and international (``8,750,000``) grouping agree.
6. Commas, semicolons, quotes, brackets, dandas, pipes and Markdown emphasis
   (``*`` and backticks) become spaces; whitespace is collapsed.

Matching is substring matching, as in the suite, with one tightening: when an
expected item starts or ends with an ASCII letter or digit, the neighbouring
answer character on that side must not be an ASCII letter or digit, so
``GJ-51`` does not match ``GJ-512`` and ``88421`` does not match ``188421``.
Indic suffixes are left alone, so inflected forms still match.

Known limitations: paraphrases, translations of status words, reordered dates
("September 18" for "18 September") and added words inside a fact ("6:15 PM
IST" for "6:15 IST") count as misses. Both arms of a pair face the same rules.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Mapping, Sequence

SCORER_ID = "v06-answer-contains/1"

_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
# Devanagari nasal consonants (NGA, NYA, NNA, NA, MA) + virama, before a consonant (KA..HA).
_DEVANAGARI_NASAL_CLUSTER = re.compile("[\u0919\u091e\u0923\u0928\u092e]\u094d(?=[\u0915-\u0939])")
_DEVANAGARI_ANUSVARA = "\u0902"
_CURRENCY_WORD = re.compile(r"\b(?:rs\.?|inr)\s*(?=\d)")
_DIGIT_GROUP = re.compile(r"(?<=\d),(?=\d)")
_SEPARATORS = re.compile('[,;"\u201c\u201d\u2018\u2019()\\[\\]{}|*`\u0964\u0965]')
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Normalize ``text`` with the documented rules; the same function serves both sides."""

    value = unicodedata.normalize("NFKC", str(text)).translate(_INVISIBLE)
    value = "".join(
        str(unicodedata.decimal(char)) if unicodedata.category(char) == "Nd" else char
        for char in value
    )
    value = _DEVANAGARI_NASAL_CLUSTER.sub(_DEVANAGARI_ANUSVARA, value)
    value = value.casefold().replace("\u20b9", " ")
    value = _CURRENCY_WORD.sub(" ", value)
    value = _DIGIT_GROUP.sub("", value)
    value = _SEPARATORS.sub(" ", value)
    return _WHITESPACE.sub(" ", value).strip()


def _ascii_alnum(char: str) -> bool:
    return char.isascii() and char.isalnum()


def contains_item(normalized_answer: str, normalized_item: str) -> bool:
    """Substring match with an ASCII alphanumeric boundary at ASCII-alphanumeric item edges."""

    if not normalized_item:
        return True
    check_start = _ascii_alnum(normalized_item[0])
    check_end = _ascii_alnum(normalized_item[-1])
    start = normalized_answer.find(normalized_item)
    while start != -1:
        end = start + len(normalized_item)
        before_ok = not (check_start and start > 0 and _ascii_alnum(normalized_answer[start - 1]))
        after_ok = not (
            check_end and end < len(normalized_answer) and _ascii_alnum(normalized_answer[end])
        )
        if before_ok and after_ok:
            return True
        start = normalized_answer.find(normalized_item, start + 1)
    return False


def expected_items(case: Mapping[str, Any]) -> List[str]:
    """The known answers of one case: expected facts, then expected tools."""

    items = [str(value) for value in case.get("expected_facts", ())]
    items.extend(str(value) for value in case.get("expected_tools", ()))
    if not items:
        raise ValueError(f"case {case.get('id')!r} has no expected facts or tools to score")
    return items


def score_text(text: str, items: Sequence[str]) -> Dict[str, Any]:
    """Score ``text`` against ``items``: fraction found, all-found flag, found and missing lists."""

    if not items:
        raise ValueError("at least one expected item is required")
    haystack = normalize(text)
    found: List[str] = []
    missing: List[str] = []
    for item in items:
        (found if contains_item(haystack, normalize(item)) else missing).append(item)
    return {
        "score": len(found) / len(items),
        "all_found": not missing,
        "found": found,
        "missing": missing,
    }


def score_answer(answer: str, case: Mapping[str, Any]) -> Dict[str, Any]:
    """Score one reader answer against a v0.6 case's known answers."""

    return score_text(answer, expected_items(case))


__all__ = [
    "SCORER_ID",
    "contains_item",
    "expected_items",
    "normalize",
    "score_answer",
    "score_text",
]
