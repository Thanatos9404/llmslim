"""Sentence and paragraph splitting utilities.

The default splitter is a fast, dependency-free regex tokenizer that
protects fenced code blocks, inline backtick code spans, and Markdown
structure (headings, lists) from being split mid-line. If NLTK's
``punkt`` tokenizer data is already available locally, it is used for
higher-accuracy sentence boundaries; its output is then post-processed so
CJK ideographic sentence boundaries are still handled.

:func:`words` is the script-aware word splitter for lexical matching:
Python's ``\\w`` excludes combining marks, so a plain ``\\w+`` cuts Indic words
at every vowel sign and virama.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Callable, List, Optional, Tuple

# Matches fenced code blocks so they are never split on sentence boundaries.
_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)

# Matches inline backtick code spans (e.g. ``config.v1.json``) so that
# periods/punctuation *inside* the span do not trigger a sentence split.
# Single-line only (no embedded newline), and non-greedy within one pair
# of backticks.
_INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")

# Common abbreviations that should not be treated as sentence boundaries.
ABBREVIATIONS = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "sr.",
    "jr.",
    "vs.",
    "etc.",
    "e.g.",
    "i.e.",
    "fig.",
    "eq.",
    "al.",
    "no.",
    "vol.",
    "approx.",
    "inc.",
    "ltd.",
    "co.",
    "st.",
    "a.m.",
    "p.m.",
}

# Split on:
#   (a) Western terminal punctuation ('.', '!' or '?') followed by
#       whitespace and an uppercase letter, digit, opening quote/bracket,
#       or a CJK ideographic/kana character (start of a new sentence); OR
#   (b) immediately AFTER a CJK full stop / exclamation / question mark
#       (``。``/``！``/``？``), which do not require a following space.
# CJK ranges covered on the look-behind start side: CJK Unified Ideographs
# (U+4E00–U+9FFF), Hiragana (U+3040–U+309F), Katakana (U+30A0–U+30FF).
_SENTENCE_SPLIT_RE = re.compile(
    r"(?:(?<=[.!?])\s+(?=[A-Z0-9\"'(\[\u4e00-\u9fff\u3040-\u30ff]))"
    r"|(?<=[。！？])"
)

# Lines that should be kept intact as a single "sentence" (Markdown
# headings, bullet/numbered list items, block/inline code placeholders).
_STRUCTURAL_LINE_RE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|\x00BLOCK|\x00INLINE)")


def split_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs on blank lines."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _protect_code_blocks(text: str) -> Tuple[str, List[str], List[str]]:
    """Replace fenced blocks and inline code spans with placeholders.

    Fenced blocks and inline spans use *separate* placeholder namespaces
    (``\\x00BLOCK{n}\\x00`` and ``\\x00INLINE{n}\\x00``) so restoration is
    unambiguous.  Fenced blocks are protected first so an inline pattern
    cannot match backticks that belong to a fence.

    Returns ``(protected_text, blocks, inline_spans)``.
    """
    blocks: List[str] = []
    inline: List[str] = []

    def _store_block(match: re.Match) -> str:
        blocks.append(match.group(0))
        return f"\x00BLOCK{len(blocks) - 1}\x00"

    def _store_inline(match: re.Match) -> str:
        inline.append(match.group(0))
        return f"\x00INLINE{len(inline) - 1}\x00"

    protected = _CODE_BLOCK_PATTERN.sub(_store_block, text)
    protected = _INLINE_CODE_PATTERN.sub(_store_inline, protected)
    return protected, blocks, inline


def _restore_code_blocks(sentences: List[str], blocks: List[str], inline: List[str]) -> List[str]:
    """Restore fenced-block and inline-span placeholders to their originals."""
    restored = []
    for sentence in sentences:
        # Restore inline spans first, then fenced blocks.  Order does not
        # matter for correctness because the placeholder namespaces are
        # disjoint, but doing inline first keeps short substitutions cheap.
        for i, span in enumerate(inline):
            placeholder = f"\x00INLINE{i}\x00"
            if placeholder in sentence:
                sentence = sentence.replace(placeholder, span)
        for i, block in enumerate(blocks):
            placeholder = f"\x00BLOCK{i}\x00"
            if placeholder in sentence:
                sentence = sentence.replace(placeholder, block)
        restored.append(sentence)
    return restored


def _merge_false_splits(sentences: List[str]) -> List[str]:
    """Re-join sentences that were incorrectly split after an abbreviation."""
    merged: List[str] = []
    for sentence in sentences:
        if merged:
            last = merged[-1]
            last_word = last.split()[-1].lower() if last.split() else ""
            if last_word in ABBREVIATIONS:
                merged[-1] = f"{last} {sentence}"
                continue
        merged.append(sentence)
    return merged


def _regex_split(text: str) -> List[str]:
    sentences: List[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if _STRUCTURAL_LINE_RE.match(line):
            # Keep headings, list items, and code-block/inline placeholders intact.
            sentences.append(line)
            continue
        parts = _SENTENCE_SPLIT_RE.split(line)
        sentences.extend(part.strip() for part in parts if part.strip())
    return _merge_false_splits(sentences)


def _split_cjk_boundaries(sentences: List[str]) -> List[str]:
    """Further split each sentence on CJK terminal punctuation.

    NLTK's ``punkt`` tokenizer does not reliably split CJK text that lacks
    inter-sentence whitespace (e.g. ``欢迎。谢谢。``).  We post-process its
    output so a trailing ``。``/``！``/``？`` still ends a sentence,
    regardless of whether ``punkt`` was used.  Placeholders are left intact
    (a CJK terminator cannot appear inside a placeholder token).
    """
    out: List[str] = []
    for sentence in sentences:
        # Split *after* each run of CJK terminal punctuation.
        parts = re.split(r"(?<=[。！？])", sentence)
        out.extend(part for part in (p.strip() for p in parts) if part)
    return out


_NLTK_SPLIT: Optional[Callable[[str], List[str]]] = None
_NLTK_CHECKED = False


def _try_nltk_split(text: str) -> Optional[List[str]]:
    # Finding punkt searches every nltk data path on disk; done once per call it cost most of the compression
    # time, so it now happens once per process.
    global _NLTK_SPLIT, _NLTK_CHECKED
    if not _NLTK_CHECKED:
        _NLTK_CHECKED = True
        try:
            import nltk

            nltk.data.find("tokenizers/punkt")
            from nltk.tokenize import sent_tokenize

            _NLTK_SPLIT = sent_tokenize
        except Exception:
            _NLTK_SPLIT = None
    if _NLTK_SPLIT is None:
        return None
    try:
        return _NLTK_SPLIT(text)
    except Exception:
        return None


def split_sentences(text: str) -> List[str]:
    """Split ``text`` into a list of sentence strings.

    Fenced code blocks and inline backtick code spans are preserved as
    single units (periods inside them never trigger a split).  CJK
    ideographic sentence boundaries (``。``/``！``/``？``) are supported in
    addition to Western punctuation.  Falls back to a fast regex splitter
    if NLTK's sentence tokenizer data is unavailable.
    """
    text = text.strip()
    if not text:
        return []

    protected, blocks, inline = _protect_code_blocks(text)

    sentences = _try_nltk_split(protected)
    if sentences is None:
        sentences = _regex_split(protected)

    # Ensure CJK boundaries are honoured regardless of which splitter ran.
    sentences = _split_cjk_boundaries(sentences)

    sentences = _restore_code_blocks(sentences, blocks, inline)
    return [s.strip() for s in sentences if s.strip()]


# ---------------------------------------------------------------------------
# Script-aware words
# ---------------------------------------------------------------------------

# Zero-width non-joiner / joiner: they shape Indic conjuncts inside a word,
# so they must not split it, and they are dropped for matching.
_ZERO_WIDTH_JOINERS = "\u200c\u200d"
_ZERO_WIDTH_TABLE = {ord(ch): None for ch in _ZERO_WIDTH_JOINERS}
_ASCII_WORD_RE = re.compile(r"[^\W_]+")


def _char_range(first: int, last: int) -> str:
    low = re.escape(chr(first))
    return low if first == last else f"{low}-{re.escape(chr(last))}"


@lru_cache(maxsize=1)
def _word_re() -> "re.Pattern[str]":
    """Letters, digits and combining marks of every script, compiled on first use.

    ``[^\\W_]`` covers letters and digits; combining marks (Unicode category
    M: vowel signs, virama, nukta, anusvara, accents) are added explicitly
    for planes 0-1, where every script in current use is encoded, plus the
    variation selectors supplement.
    """
    ranges: List[str] = []
    start = -1
    for code in range(0x20000):
        mark = unicodedata.category(chr(code))[0] == "M"
        if mark and start < 0:
            start = code
        elif not mark and start >= 0:
            ranges.append(_char_range(start, code - 1))
            start = -1
    ranges.append(_char_range(0xE0100, 0xE01EF))
    return re.compile(r"(?:[^\W_]|[" + "".join(ranges) + _ZERO_WIDTH_JOINERS + r"])+")


def _normalise_word(word: str) -> str:
    """NFC, without zero-width joiners, with decimal digits of every script as ASCII."""
    if word.isascii():
        return word
    word = unicodedata.normalize("NFC", word).translate(_ZERO_WIDTH_TABLE)
    if not any(ch.isdecimal() and not ch.isascii() for ch in word):
        return word
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in word)


def words(text: str) -> List[str]:
    """Split ``text`` into words of any script, for lexical matching.

    A word is a maximal run of letters, digits and combining marks, so
    Devanagari, Bengali, Odia, Tamil and other abugida words stay whole
    (Python's ``\\w`` alone splits them at every vowel sign and virama).
    Each word is NFC-normalised (nukta letters and other composition
    exclusions match however they were typed), zero-width joiners are
    dropped, and decimal digits of every script are written as ASCII
    digits, so ``"২০২৬"`` and ``"2026"`` are the same word. Case is
    preserved and the underscore separates words. ASCII text gives exactly
    the words of ``[^\\W_]+``.
    """
    if text.isascii():
        return _ASCII_WORD_RE.findall(text)
    found = (_normalise_word(match.group(0)) for match in _word_re().finditer(text))
    return [word for word in found if word]
