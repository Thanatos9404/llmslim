"""Sentence and paragraph splitting utilities.

The default splitter is a fast, dependency-free regex tokenizer that
protects fenced code blocks, inline backtick code spans, and Markdown
structure (headings, lists) from being split mid-line. If NLTK's
``punkt`` tokenizer data is already available locally, it is used for
higher-accuracy sentence boundaries; its output is then post-processed so
CJK ideographic sentence boundaries are still handled.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

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


def _restore_code_blocks(
    sentences: List[str], blocks: List[str], inline: List[str]
) -> List[str]:
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


def _try_nltk_split(text: str) -> Optional[List[str]]:
    try:
        import nltk

        nltk.data.find("tokenizers/punkt")
        from nltk.tokenize import sent_tokenize

        return sent_tokenize(text)
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
