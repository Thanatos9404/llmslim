"""Sentence and paragraph splitting utilities.

The default splitter is a fast, dependency-free regex tokenizer that
protects fenced code blocks and Markdown structure (headings, lists) from
being split mid-line. If NLTK's ``punkt`` tokenizer data is already
available locally, it is used for higher-accuracy sentence boundaries.
"""

from __future__ import annotations

import re
from typing import List, Optional

# Matches fenced code blocks so they are never split on sentence boundaries.
_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)

# Common abbreviations that should not be treated as sentence boundaries.
ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "vs.", "etc.",
    "e.g.", "i.e.", "fig.", "eq.", "al.", "no.", "vol.", "approx.",
    "inc.", "ltd.", "co.", "st.", "a.m.", "p.m.",
}

# Split on '.', '!' or '?' followed by whitespace and an uppercase letter,
# digit, or opening quote/bracket -- i.e. the likely start of a new sentence.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")

# Lines that should be kept intact as a single "sentence" (Markdown
# headings, bullet/numbered list items, block placeholders).
_STRUCTURAL_LINE_RE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|\x00BLOCK)")


def split_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs on blank lines."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _protect_code_blocks(text: str):
    """Replace fenced code blocks with placeholders so they survive splitting."""
    blocks: List[str] = []

    def _store(match: "re.Match") -> str:
        blocks.append(match.group(0))
        return f"\x00BLOCK{len(blocks) - 1}\x00"

    protected = _CODE_BLOCK_PATTERN.sub(_store, text)
    return protected, blocks


def _restore_code_blocks(sentences: List[str], blocks: List[str]) -> List[str]:
    restored = []
    for sentence in sentences:
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
            # Keep headings, list items, and code-block placeholders intact.
            sentences.append(line)
            continue
        parts = _SENTENCE_SPLIT_RE.split(line)
        sentences.extend(part.strip() for part in parts if part.strip())
    return _merge_false_splits(sentences)


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

    Fenced code blocks are preserved as single units. Falls back to a
    fast regex splitter if NLTK's sentence tokenizer data is unavailable.
    """
    text = text.strip()
    if not text:
        return []

    protected, blocks = _protect_code_blocks(text)

    sentences = _try_nltk_split(protected)
    if sentences is None:
        sentences = _regex_split(protected)

    sentences = _restore_code_blocks(sentences, blocks)
    return [s.strip() for s in sentences if s.strip()]
