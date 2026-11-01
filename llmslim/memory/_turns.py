"""Turn-level selection for :meth:`llmslim.memory.Memory.search`, with no model call on the way in or out.

A long history does not fit the budget, so the read path picks what the question needs. It works on the stored turns
themselves, not on rendered session text:

* **User turns are units of their own.** What a user said (a name, a date, an amount, a preference) is usually short
  and stated once, while the replies around it are long and repeat the user's words. Ranked together, the replies
  crowd the user's turn out. So user turns form their own candidate pool with a reserved share of the budget
  (``USER_SHARE``), ranked by the same relevance as everything else (lexical, then the reranker when one is set).
  A user turn is kept whole when it fits its cap; a longer one keeps its most relevant sentences and is marked
  partial.
* **Replies are cut into windows** of a few sentences (code blocks and tables stay whole), ranked in their own pool,
  and fill the rest of the budget. A window inherits part of its reply's relevance. A reply of one window inherits
  part of its session's instead (the relevance of the session's replies of one window), as a user turn does.
* **Repeated text is dropped** (``DEDUP_OVERLAP``): a candidate whose word 5-grams are mostly in the text already
  kept adds nothing.
* **One labelled, dated block per turn.** Each kept turn is rendered as ``[date] role: text``: prose on that line
  (markdown headings folded into the sentence they head, so no heading stands alone), code blocks and tables on the
  lines below, fenced. Kept turns appear in date order, with a blank line between sessions. Text inside a turn can
  never start a line that looks like another turn's label.

Everything here is deterministic: the same history, question and settings give the same text.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from ..focus import BM25, Unit, _query_terms, _rerank, rank, terms
from ..tokenization import split_sentences
from ..tokens import count_tokens
from ._types import MemoryItem

# ------------------------------------------------------------------ settings (module constants, tuned on dev data)

USER_SHARE = 0.55  # share of the relevance budget reserved for user turns
USER_TURN_SHARE = (
    0.1  # a user turn longer than this share of the budget keeps only its most relevant sentences
)
USER_TURN_MIN = 120  # ... but the cap is never below this many tokens
USER_TURN_MAX = 400  # ... nor above this many
WINDOW_DIVISOR = 32  # reply windows of about a thirty-second of the budget
WINDOW_MIN = 60
WINDOW_MAX = 200
RERANK_USER = 160  # user turns the reranker reads (the strongest lexical candidates)
RERANK_REPLY = 80  # reply windows the reranker reads
# A reply window inherits part of its whole reply's relevance, and a reply of one window part of its session's
# (``score_pool``). When this is off, every reply window inherits its session's.
REPLY_GROUP = True
DEDUP_OVERLAP = 0.8  # share of a candidate's word 5-grams already kept above which it is left out
SHINGLE = 5
SLACK = 1.0  # the context never runs over the budget (Memory.search clips what fit leaves over)
GAP = " ... "  # marks text left out between two kept parts of one turn

Scorer = Callable[[str, Sequence[str]], Sequence[float]]

# ------------------------------------------------------------------ text shapes

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
# A fenced code block, opening wherever its fence starts; a fence followed by a word (an info string such as
# "```bash") opens a block and never closes one, as in CommonMark.
_CODE_SPAN = re.compile(
    r"(?P<fence>`{3,}|~{3,}).*?(?:(?P<close>(?P=fence))(?![\w-])|\Z)", re.DOTALL
)
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
# What a turn's own label looks like at the start of a line ("[2026-01-05 (Mon) 09:30] user: ..."). Text inside a
# turn that would start a line this way is indented, so stored text can never pass for another turn.
_LABEL_LIKE = re.compile(
    r"^\s*\[[^\]\n]{1,60}\]\s*(?:user|assistant|system|tool)\s*:", re.IGNORECASE
)
_WORDS = re.compile(r"\w+", re.UNICODE)

# A markdown heading ("## Setup") is a match of the regular expression
#
#     ^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$
#
# (group 1 is the heading's text). Python's backtracking takes time cubic in a run of spaces or tabs inside such a
# line (seconds for a few thousand), so ``heading_of`` and ``heading_spans`` compute the same matches directly, in
# linear time. tests/test_memory_production.py checks them against the expression on random text.
_SPACE_RUN = re.compile(r"\s+")
_HASH_RUN = re.compile(r"#+")
_SPACE_OR_HASH = re.compile(r"[\s#]")


def _run_end(run: "re.Pattern[str]", text: str, at: int) -> int:
    """Where the run of ``run`` that starts at ``at`` ends (``at`` itself when there is none)."""
    found = run.match(text, at)
    return found.end() if found else at


def _heading_tail(text: str, at: int) -> int:
    """Where ``\\s*#*\\s*$`` (re.MULTILINE) first matches from ``at``, in the expression's own search order, or -1.

    The expression tries the longest leading whitespace first: then a run of '#' and whitespace up to the end of the
    text or the last line break in that whitespace. Failing that, it ends at the last line break in the leading
    whitespace itself."""
    size = len(text)
    spaces = _run_end(_SPACE_RUN, text, at)
    if spaces == size:
        return size
    if text[spaces] == "#":
        hashes = _run_end(_HASH_RUN, text, spaces)
        after = _run_end(_SPACE_RUN, text, hashes)
        if after == size:
            return size
        last = text.rfind("\n", hashes, after)
        if last >= 0:
            return last
    return text.rfind("\n", at, spaces)


def _heading_at(text: str, start: int) -> Optional[Tuple[int, str]]:
    """The heading expression (re.MULTILINE) matched at ``start``, a line start: (where the match ends, group 1)."""
    size = len(text)
    hashes = _run_end(_SPACE_RUN, text, start)
    if hashes - start > 3 or hashes == size or text[hashes] != "#":
        return None
    gap = _run_end(_HASH_RUN, text, hashes)
    if gap - hashes > 6:
        return None
    title = _run_end(_SPACE_RUN, text, gap)
    if title == gap:
        return None
    if title == size:
        # Only whitespace after the hashes: the expression gives its last character that is not a line break to the
        # text, if the whitespace before it still has one character.
        for last in range(size - 1, gap, -1):
            if text[last] != "\n":
                return size, text[last]
        return None
    line_end = text.find("\n", title)
    line_end = size if line_end < 0 else line_end
    # The text is as short as it can be: it ends where the tail first matches. The tail's result is the same at every
    # position of a run of whitespace or of '#', and it never matches at another character, so one try per run does.
    at = title + 1
    while True:
        end = _heading_tail(text, at)
        if end >= 0:
            return end, text[title:at]
        if text[at].isspace():
            at = _run_end(_SPACE_RUN, text, at)
        elif text[at] == "#":
            at = _run_end(_HASH_RUN, text, at)
        else:
            found = _SPACE_OR_HASH.search(text, at + 1, line_end)
            at = found.start() if found else line_end


def heading_of(line: str) -> Optional[str]:
    """The text of the markdown heading ``line`` is, as the heading expression's group 1, or None."""
    found = _heading_at(line, 0) if "#" in line else None
    return found[1] if found else None


def heading_spans(text: str) -> List[Tuple[int, str]]:
    """(start, group 1) of every match of the heading expression in ``text`` with re.MULTILINE, in the order
    ``finditer`` gives them (whitespace, as ``\\s``, may run across lines)."""
    spans: List[Tuple[int, str]] = []
    if "#" not in text:
        return spans
    at = 0
    while at < len(text):
        found = _heading_at(text, at)
        if found is not None:
            spans.append((at, found[1]))
            at = found[0]
            if at and text[at - 1] == "\n":
                continue
        line_break = text.find("\n", at)
        if line_break < 0:
            break
        at = line_break + 1
    return spans


@dataclass(frozen=True)
class Segment:
    """A sentence of prose, or a whole code block or table (``block`` true), in the turn's order."""

    text: str
    block: bool = False


def segments(content: str) -> List[Segment]:
    """A turn's text as segments: prose split into sentences, one per source line at least (so list items stay
    apart), markdown headings folded into the first sentence under them ("Setup: Install the package."), and fenced
    code blocks (wherever their fence starts, as users paste them mid-line) and tables kept whole with their line
    breaks. An unterminated code block is closed at the end of the turn."""
    out: List[Segment] = []
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    heading = ""
    start = 0
    for match in _CODE_SPAN.finditer(text):
        heading = _prose(text[start : match.start()], out, heading)
        block = match.group(0).strip()
        if not match.group("close"):
            block = f"{block}\n{match.group('fence')}"
        if heading:
            out.append(Segment(heading.rstrip(":") + ":"))
            heading = ""
        out.append(Segment(block, block=True))
        start = match.end()
    heading = _prose(text[start:], out, heading)
    if heading:
        out.append(Segment(heading.rstrip(":") + "."))
    return out


def _prose(text: str, out: List[Segment], heading: str) -> str:
    """Appends the segments of a stretch of text with no code block in it; returns a heading still waiting for the
    sentence it heads."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if _TABLE_ROW.match(line):
            rows = []
            while i < len(lines) and _TABLE_ROW.match(lines[i]):
                rows.append(lines[i].strip())
                i += 1
            if heading:
                out.append(Segment(heading.rstrip(":") + ":"))
                heading = ""
            out.append(Segment("\n".join(rows), block=True))
            continue
        i += 1
        stripped = " ".join(line.split())
        if not stripped:
            continue
        title = heading_of(line)
        if title is not None:
            text = title.replace("**", "").strip()
            heading = f"{heading.rstrip(':')}: {text}" if heading else text
            continue
        cursor = 0
        # The line's current segment: a sentence and those attached to it, joined once it is complete (adding them
        # one at a time took time quadratic in a long paragraph of Chinese or Japanese).
        current: List[str] = []
        for k, sentence in enumerate(split_sentences(stripped) or [stripped]):
            at = stripped.find(sentence, cursor)
            attached = (
                k > 0 and at == cursor
            )  # no space before it (CJK sentences): it stays with the one before
            cursor = at + len(sentence) if at >= 0 else cursor
            if attached:
                current.append(sentence)
                continue
            if current:
                out.append(Segment("".join(current)))
            if heading and k == 0:
                sentence = f"{heading.rstrip(':')}: {sentence}"
                heading = ""
            current = [sentence]
        if current:
            out.append(Segment("".join(current)))
    return heading


@lru_cache(maxsize=1 << 16)
def tokens_of(text: str) -> int:
    """``count_tokens`` for the texts a search measures again and again (sentences, windows, labels)."""
    return count_tokens(text)


@lru_cache(maxsize=1 << 14)
def segments_of(content: str) -> Tuple[Segment, ...]:
    """``segments`` of a stored turn's text, kept between searches (a turn's text rarely changes)."""
    return tuple(segments(content))


def _guard(block: str) -> str:
    """A code block or table with any line that looks like a turn label indented, so it cannot pass for one."""
    return "\n".join("  " + line if _LABEL_LIKE.match(line) else line for line in block.split("\n"))


def join(parts: Sequence[Tuple[str, bool]]) -> str:
    """Segments (text, is_block) as one turn's text: prose on one line, blocks on their own lines. Text that opens
    with a block starts with a line break, so the block's first line never shares the turn's label line."""
    # The text is built from pieces (never empty) and joined once: rebuilding it for every part took time quadratic
    # in a long turn's length, on every search.
    pieces: List[str] = []
    for text, block in parts:
        if block:
            while pieces:  # the text so far without its trailing whitespace
                last = pieces[-1].rstrip()
                if last:
                    pieces[-1] = last
                    break
                pieces.pop()
            pieces.append("\n")
            guarded = _guard(text)
            if guarded:
                pieces.append(guarded)
            pieces.append("\n")
        elif pieces and not pieces[-1].endswith("\n"):
            pieces.append(" ")
            if text:
                pieces.append(text)
        elif text:
            pieces.append(text)
    return "".join(pieces).rstrip()


def labelled(label: str, body: str) -> str:
    """A turn's block: its label, then its text (on the next line when the text opens with a code block)."""
    return f"{label.rstrip()}{body}" if body.startswith("\n") else f"{label}{body}"


def words(text: str) -> List[str]:
    """The case-folded words of ``text`` (any script), for near-duplicate checks."""
    return _WORDS.findall(text.casefold())


def shingles(text: str, n: int = SHINGLE) -> Set[Tuple[str, ...]]:
    """The word ``n``-grams of ``text`` (one shorter tuple when it has fewer words)."""
    ws = words(text)
    if len(ws) < n:
        return {tuple(ws)} if ws else set()
    return {tuple(ws[k : k + n]) for k in range(len(ws) - n + 1)}


# ------------------------------------------------------------------ candidates


@dataclass
class Piece:
    """A candidate: a whole user turn, or a window of a reply (one or more of its segments)."""

    turn: int  # index of the turn in the history (date order)
    part: int  # position of the window within its turn
    segs: List[Segment]
    text: str
    tokens: int
    score: float = 0.0
    trimmed: bool = False  # set when the piece holds only part of its turn (a digest opening)


@dataclass
class Turn:
    """A stored turn as selection sees it: its session's index, its labels and its segments."""

    item: MemoryItem
    session: int
    stamp: str  # the full stamp, shown on the first kept turn of its session
    segs: List[Segment] = field(default_factory=list)
    parts: int = 0  # how many windows (or 1 for a user turn)
    date: str = ""  # the short stamp, shown on the session's other kept turns


def cap_for_user_turn(budget: int) -> int:
    """The most of ``budget`` one user turn may take whole (``USER_TURN_SHARE``, within the min and max)."""
    return max(USER_TURN_MIN, min(USER_TURN_MAX, int(budget * USER_TURN_SHARE)))


def window_size(budget: int) -> int:
    """About how many tokens a reply window holds at ``budget`` (``WINDOW_DIVISOR``, within the min and max)."""
    return max(WINDOW_MIN, min(WINDOW_MAX, budget // WINDOW_DIVISOR))


def windows(segs: Sequence[Segment], size: int) -> List[List[Segment]]:
    """Consecutive segments in windows of about ``size`` tokens; a code block or table is a window of its own (split
    by lines, each part fenced again, when it is far larger than a window)."""
    out: List[List[Segment]] = []
    current: List[Segment] = []
    used = 0
    for seg in segs:
        cost = tokens_of(seg.text)
        if seg.block:
            if current:
                out.append(current)
                current, used = [], 0
            out.extend([[part] for part in _split_block(seg, cost, size)])
            continue
        if current and used + cost > size:
            out.append(current)
            current, used = [], 0
        current.append(seg)
        used += cost
    if current:
        out.append(current)
    return out


def _split_block(seg: Segment, cost: int, size: int) -> List[Segment]:
    if cost <= size * 2:
        return [seg]
    lines = seg.text.split("\n")
    fenced = bool(_FENCE.match(lines[0])) and len(lines) >= 2
    opener, closer = (lines[0], lines[-1]) if fenced else ("", "")
    body = lines[1:-1] if fenced else lines
    parts: List[Segment] = []
    chunk: List[str] = []
    used = 0
    for line in body:
        c = tokens_of(line) + 1
        if chunk and used + c > size:
            parts.append(Segment("\n".join([opener, *chunk, closer] if fenced else chunk), True))
            chunk, used = [], 0
        chunk.append(line)
        used += c
    if chunk:
        parts.append(Segment("\n".join([opener, *chunk, closer] if fenced else chunk), True))
    return parts


# ------------------------------------------------------------------ ranking


def score_pool(
    pieces: Sequence[Piece],
    turns: Sequence[Turn],
    query: str,
    scorer: Optional[Scorer],
    candidates: int,
    by_turn: bool,
    recency: bool = True,
) -> List[float]:
    """Relevance of each piece to ``query``: LLMSlim's lexical ranking (BM25 with feedback and bonuses; a piece
    inherits part of its group's relevance), then the reranker over the ``candidates`` strongest lexical candidates
    when one is set. ``recency`` as in ``rank_units``.

    The group is the piece's session (the pool's pieces from that session), or with ``by_turn`` its turn: a window
    then inherits part of its whole reply's relevance. A reply of one window would only inherit its own, so it is
    grouped by its session instead, with the session's other replies of one window, as a user turn is grouped with
    the session's user turns. A short reply (a person's turn in a conversation between two people, or an agent's
    one-line answer) then gets the same help from its session as the user turns around it."""
    if not pieces:
        return []
    units = [
        Unit(k, _group(p, turns, by_turn), p.text, p.tokens, "", "\n") for k, p in enumerate(pieces)
    ]
    return rank_units(units, query, scorer, candidates, recency)


def _group(piece: Piece, turns: Sequence[Turn], by_turn: bool) -> int:
    """The group ``piece`` inherits relevance from (see ``score_pool``): its turn (numbered from 0) when ``by_turn``
    and the turn has more than one window, else its session (numbered from -1 down, so the two never meet)."""
    turn = turns[piece.turn]
    if by_turn and turn.parts > 1:
        return piece.turn
    return -1 - turn.session


# Letters outside the Latin alphabet: Chinese, Japanese, Korean, Cyrillic, Arabic and so on. LLMSlim's lexical
# ranking reads Latin-script words and numbers only, so a question with none of them (written in another script, or
# only common words such as "What is it?") is matched on these letters instead: every pair of adjacent letters in a
# run of them (or the letter itself, in a run of one) counts as a word for BM25. Chinese and Japanese put no spaces
# between words, and letter pairs are the usual way to match them without a dictionary.
_OTHER_LETTERS = re.compile(r"[^\W\d_A-Za-z]+")


def query_grams(query: str) -> Tuple[str, ...]:
    """What a question with no Latin-script word to match is matched on: the pairs of adjacent letters in each run of
    letters outside the Latin alphabet (a run of one letter gives that letter), case-folded, without repeats."""
    grams: List[str] = []
    for run in _OTHER_LETTERS.findall(query.casefold()):
        grams.extend([run] if len(run) == 1 else (run[k : k + 2] for k in range(len(run) - 1)))
    return tuple(dict.fromkeys(grams))


@lru_cache(maxsize=1 << 15)
def text_grams(text: str) -> Tuple[str, ...]:
    """The letters and pairs of adjacent letters of ``text``'s runs of letters outside the Latin alphabet."""
    grams: List[str] = []
    for run in _OTHER_LETTERS.findall(text.casefold()):
        grams.extend(run)
        grams.extend(run[k : k + 2] for k in range(len(run) - 1))
    return tuple(grams)


def _grams_match(user: Sequence[Piece], other: Sequence[Piece], query: str) -> bool:
    """Whether any piece shares a letter or letter pair (``query_grams``) with a question matched on its letters."""
    wanted = set(query_grams(query))
    return bool(wanted) and any(wanted.intersection(text_grams(p.text)) for p in (*user, *other))


def gram_scores(texts: Sequence[str], query: str) -> List[float]:
    """BM25 of ``query_grams(query)`` against each text's ``text_grams``; all 0 when the question has none."""
    wanted = query_grams(query)
    if not wanted or not texts:
        return [0.0] * len(texts)
    return BM25([text_grams(text) for text in texts]).scores(dict.fromkeys(wanted, 1.0))


def rank_units(
    units: Sequence[Unit],
    query: str,
    scorer: Optional[Scorer],
    candidates: int,
    recency: bool = True,
) -> List[float]:
    """Relevance of each unit to ``query``, the units in date order.

    A question with a Latin-script word or a number to match is ranked by ``focus.rank``, exactly as before. One with
    none is matched on its other letters (``gram_scores``). When nothing matches either, the most recent units score
    highest (with ``recency``; without it they all score 0). With a reranker or a custom scorer set, it reads the
    strongest of these (``candidates`` of them: the matching units, then the most recent), as for any question."""
    if not units:
        return []
    if _query_terms(query):
        return rank(units, query, scorer, candidates=candidates)
    size = len(units)
    scores = gram_scores([u.text for u in units], query)
    if not any(score > 0 for score in scores):
        if not recency:
            return scores
        scores = [(k + 1) / size for k in range(size)]
    if scorer is None:
        return scores
    top = max(scores)
    lexical = [s if s > 0 else top * 1e-6 * (k + 1) / size for k, s in enumerate(scores)]
    return _rerank(units, query, lexical, scorer, candidates)


def excerpt(segs: Sequence[Segment], query: str, limit: int) -> Tuple[List[Tuple[str, bool]], bool]:
    """The most relevant segments of a long turn within ``limit`` tokens, in their order, with gaps marked: by the
    query's terms, or by its other letters when it has no Latin-script word (``gram_scores``). Falls back to the
    opening segments when none shares anything with the query. Returns (parts, trimmed)."""
    costs = [tokens_of(s.text) for s in segs]
    if sum(costs) <= limit:
        return [(s.text, s.block) for s in segs], False
    weights = dict.fromkeys(_query_terms(query), 1.0)
    if weights:
        scores = BM25([terms(s.text) for s in segs]).scores(weights)
    else:
        scores = gram_scores([s.text for s in segs], query)
    order = sorted(range(len(segs)), key=lambda k: (-scores[k], k))
    if not any(s > 0 for s in scores):
        order = list(range(len(segs)))
    chosen: Set[int] = set()
    used = 0
    for k in order:
        if used + costs[k] + 2 > limit:
            continue
        chosen.add(k)
        used += costs[k] + 2
    if not chosen:  # even the best segment is too long: its opening words
        best = order[0]
        return [(_cut(segs[best].text, limit), segs[best].block)], True
    parts: List[Tuple[str, bool]] = []
    previous = -1
    for k in sorted(chosen):
        if previous >= 0 and k != previous + 1 or previous < 0 and k > 0:
            parts.append((GAP.strip(), False))
        parts.append((segs[k].text, segs[k].block))
        previous = k
    if previous < len(segs) - 1:
        parts.append((GAP.strip(), False))
    return parts, True


def _cut(text: str, limit: int) -> str:
    """The longest prefix of whole words within ``limit`` tokens, marked as cut."""
    ws = text.split()
    low, high = 1, len(ws)
    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(" ".join(ws[:mid])) + 2 <= limit:
            low = mid
        else:
            high = mid - 1
    return " ".join(ws[:low]) + (GAP.rstrip() if low < len(ws) else "")


def _regional(char: str) -> bool:
    return "\U0001f1e6" <= char <= "\U0001f1ff"


def _joins(char: str, previous: str, regional_before: int) -> bool:
    """Whether ``char`` belongs with the character before it, so text is never cut between them: a combining mark,
    a zero-width joiner or the character after one, a variation selector, an emoji skin tone or tag, the second
    regional indicator of a flag, a Hangul vowel or final consonant (conjoining jamo), or the low half of a
    surrogate pair."""
    code = ord(char)
    return (
        unicodedata.category(char) in ("Mn", "Mc", "Me")
        or char == "\u200d"
        or previous == "\u200d"
        or 0xFE00 <= code <= 0xFE0F
        or 0xE0100 <= code <= 0xE01EF
        or 0x1F3FB <= code <= 0x1F3FF
        or 0xE0020 <= code <= 0xE007F
        or 0x1160 <= code <= 0x11FF
        or 0xD7B0 <= code <= 0xD7FF
        or (0xDC00 <= code <= 0xDFFF and 0xD800 <= ord(previous) <= 0xDBFF)
        or (_regional(char) and regional_before % 2 == 1)
    )


def _cut_points(text: str, stop: int) -> List[int]:
    """The offsets up to ``stop`` where ``text`` can be cut without splitting a character sequence (``_joins``)."""
    points: List[int] = []
    regional = 0  # regional indicators in a row just before the offset
    for at in range(1, min(stop, len(text)) + 1):
        regional = regional + 1 if _regional(text[at - 1]) else 0
        if at == len(text) or not _joins(text[at], text[at - 1], regional):
            points.append(at)
    return points


def _cut_chars(text: str, limit: int) -> str:
    """The longest prefix of ``text`` within ``limit`` tokens, cut between two characters and marked as cut, for
    text with no space where a whole word fits (Chinese or Japanese prose, a long URL or token). A character sequence
    that shows as one (an accented letter, an emoji, a flag) is never split. Empty when not one character fits."""
    # A token covers at most a few characters of such text, so the cut is looked for in the first ones only.
    points = _cut_points(text, max(1, limit) * 32)
    low, high = 0, len(points)
    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(text[: points[mid - 1]]) + 2 <= limit:
            low = mid
        else:
            high = mid - 1
    return text[: points[low - 1]] + GAP.rstrip() if low else ""


# ------------------------------------------------------------------ selection


@dataclass
class Trace:
    """What selection decided about each piece, recorded only for ``Memory.search(..., explain=True)``.

    ``outcome`` maps a piece (by ``id``) to the last thing that happened to it: ``"kept"``, a reason it was kept in
    part (``"user_turn_cap"``, ``"last_resort"``, ``"cut_at_fit"``) or a reason it was left out (``"over_budget"``,
    ``"over_share"``, ``"duplicate"``, ``"dropped_at_fit"``, ``"detail_kept"``). A piece with no outcome was never
    tried: the budget, or its pool's share, was full first."""

    pools: List[Tuple[str, str, List[Piece], bool]] = field(default_factory=list)
    outcome: Dict[int, str] = field(default_factory=dict)
    slots: Dict[Tuple[int, int], Piece] = field(default_factory=dict)  # (turn, part) -> kept piece
    user_room: Optional[int] = None
    user_cap: Optional[int] = None

    def pool(self, name: str, kind: str, pieces: Sequence[Piece], scored: bool = True) -> None:
        """Record a pool of candidates: its name, the kind of its pieces, and whether they were ranked."""
        self.pools.append((name, kind, list(pieces), scored))

    def keep(self, piece: Piece, outcome: str = "kept") -> None:
        self.slots[(piece.turn, piece.part)] = piece
        self.outcome[id(piece)] = outcome

    def refuse(self, piece: Piece, reason: str) -> None:
        self.outcome[id(piece)] = reason

    def mark(self, turn: int, part: int, outcome: str) -> None:
        """What happened later to the piece kept at (turn, part)."""
        piece = self.slots.get((turn, part))
        if piece is not None:
            self.outcome[id(piece)] = outcome


class Selection:
    """Greedy fill of one budget from ranked pieces, with per-turn label costs and near-duplicate removal."""

    def __init__(
        self,
        turns: Sequence[Turn],
        budget: int,
        query: str,
        dedup: Optional[float] = None,
        trace: Optional[Trace] = None,
    ):
        self.turns = turns
        self.budget = budget
        self.query = query
        # Read at call time (not as a default argument), so the module setting can be tuned.
        self.dedup = DEDUP_OVERLAP if dedup is None else dedup
        self.used = 0
        self.kept: Dict[int, Dict[int, Tuple[List[Tuple[str, bool]], float, bool]]] = {}
        self.seen: Set[Tuple[str, ...]] = set()
        self.exact: Set[Tuple[str, ...]] = set()
        self.per_session: Dict[int, int] = {}
        self.stamps: Dict[int, Set[str]] = {}  # per session: the full stamps of its kept turns
        self.trace = trace

    def label(self, turn: int, first: bool = True) -> str:
        """A turn's label: its full stamp when ``first`` (the first kept turn of its session, or one whose time
        differs from the one shown last in its session), else its date."""
        t = self.turns[turn]
        stamp = t.stamp if first or not t.date else t.date
        return f"[{stamp}] {t.item.role}: "

    def label_cost(self, turn: int) -> int:
        """What a new turn's label adds: a full stamp when no kept turn of its session has its time yet, else a
        date (an estimate: the exact labels depend on the order of the kept turns, and ``fit`` counts them)."""
        t = self.turns[turn]
        first = t.stamp not in self.stamps.get(t.session, ())
        return tokens_of(self.label(turn, first)) + 1

    def duplicate(self, text: str) -> bool:
        ws = tuple(words(text))
        if not ws:
            return True
        if ws in self.exact:
            return True
        sh = shingles(text)
        if len(ws) >= SHINGLE and sh:
            return len(sh & self.seen) / len(sh) >= self.dedup
        return False

    def take(self, piece: Piece, limit: int, user_cap: int = 0) -> bool:
        """Keep ``piece`` (a long user turn trimmed to ``user_cap``) if it fits within ``limit`` tokens in all and is
        not a near-duplicate of what is kept. Returns whether it was kept."""
        parts: List[Tuple[str, bool]]
        trimmed = False
        if user_cap and piece.tokens > user_cap:
            parts, trimmed = excerpt(piece.segs, self.query, user_cap)
            text = join(parts)
            cost = count_tokens(text)
        else:
            parts = [(s.text, s.block) for s in piece.segs]
            text, cost = piece.text, piece.tokens
        cost += 2 if piece.turn in self.kept else self.label_cost(piece.turn)
        if self.used + cost > limit:
            if self.trace is not None:
                self.trace.refuse(piece, "over_share" if limit < self.budget else "over_budget")
            return False
        if self.duplicate(text):
            if self.trace is not None:
                self.trace.refuse(piece, "duplicate")
            return False
        if self.trace is not None:
            self.trace.keep(piece, "user_turn_cap" if trimmed else "kept")
        if piece.turn not in self.kept:
            session = self.turns[piece.turn].session
            self.per_session[session] = self.per_session.get(session, 0) + 1
            self.stamps.setdefault(session, set()).add(self.turns[piece.turn].stamp)
        self.kept.setdefault(piece.turn, {})[piece.part] = (
            parts,
            piece.score,
            trimmed or piece.trimmed,
        )
        self.used += cost
        self.exact.add(tuple(words(text)))
        self.seen |= shingles(text)
        return True

    def render_turn(self, turn: int, first: bool = True) -> Tuple[str, bool]:
        """One turn's block and whether it is partial (some of its text left out)."""
        t = self.turns[turn]
        kept = self.kept[turn]
        parts: List[Tuple[str, bool]] = []
        previous = -1
        partial = False
        for part in sorted(kept):
            pieces, _, trimmed = kept[part]
            partial = partial or trimmed
            if part != previous + 1:
                parts.append((GAP.strip(), False))
                partial = True
            parts.extend(pieces)
            previous = part
        if previous != t.parts - 1:
            parts.append((GAP.strip(), False))
            partial = True
        body = join(parts)
        return labelled(self.label(turn, first), body), partial

    def blocks(self) -> List[Tuple[int, int, str, bool]]:
        """Kept turns in date order as (session, turn, block, partial). Each turn shows its own time: its full stamp
        when it is the first kept turn of its session or its time differs from the one shown last there, else its
        date."""
        shown: Dict[int, str] = {}
        out = []
        for turn in sorted(self.kept):
            t = self.turns[turn]
            block, partial = self.render_turn(turn, shown.get(t.session) != t.stamp)
            shown[t.session] = t.stamp
            out.append((t.session, turn, block, partial))
        return out

    def render(self) -> Tuple[List[str], List[Tuple[int, bool]]]:
        """Kept turns in date order (see ``blocks``): one text per session (empty when nothing of it is kept), and
        (turn, partial)."""
        sessions: Dict[int, List[str]] = {}
        recalled = []
        for session, turn, block, partial in self.blocks():
            sessions.setdefault(session, []).append(block)
            recalled.append((turn, partial))
        count = max((t.session for t in self.turns), default=-1) + 1
        return ["\n".join(sessions.get(s, [])) for s in range(count)], recalled

    def drop_weakest(self) -> bool:
        """Remove the lowest-scored kept piece (used only if the exact count runs over the budget)."""
        weakest = None
        for turn, parts in self.kept.items():
            for part, (_, score, _) in parts.items():
                if weakest is None or score < weakest[0]:
                    weakest = (score, turn, part)
        if weakest is None or sum(len(p) for p in self.kept.values()) <= 1:
            return False
        _, turn, part = weakest
        if self.trace is not None:
            self.trace.mark(turn, part, "dropped_at_fit")
        del self.kept[turn][part]
        if not self.kept[turn]:
            del self.kept[turn]
        return True


def build_turns(
    sessions: Sequence[Sequence[MemoryItem]],
    stamp: Callable[[MemoryItem], str],
    date: Optional[Callable[[MemoryItem], str]] = None,
) -> List[Turn]:
    """Every turn of ``sessions`` (in session order, then stored order) with its labels and cached segments."""
    turns: List[Turn] = []
    for s, session in enumerate(sessions):
        for item in session:
            short = date(item) if date else ""
            turns.append(Turn(item, s, stamp(item), list(segments_of(item.content)), 0, short))
    return turns


def pools(turns: Sequence[Turn], budget: int) -> Tuple[List[Piece], List[Piece]]:
    """User pieces (one per user turn) and reply pieces (windows of every other turn)."""
    size = window_size(budget)
    user: List[Piece] = []
    other: List[Piece] = []
    for k, t in enumerate(turns):
        if not t.segs:
            continue
        if t.item.role == "user":
            text = join([(s.text, s.block) for s in t.segs])
            user.append(Piece(k, 0, list(t.segs), text, tokens_of(text)))
            t.parts = 1
            continue
        groups = windows(t.segs, size)
        t.parts = len(groups)
        for p, segs in enumerate(groups):
            text = join([(s.text, s.block) for s in segs])
            other.append(Piece(k, p, segs, text, tokens_of(text)))
    return user, other


def select_turns(
    turns: Sequence[Turn],
    query: str,
    budget: int,
    scorer: Optional[Scorer],
    *,
    user_share: Optional[float] = None,
    expansion: str = "",
    trace: Optional[Trace] = None,
) -> Selection:
    """Fill ``budget`` from the user pool (up to its share) and the reply pool, then top up from both. ``trace``
    records what was decided about each piece (for ``Memory.search(..., explain=True)``)."""
    share = USER_SHARE if user_share is None else user_share
    user, other = pools(turns, budget)
    # A request's words widen a question that has Latin-script words of its own. A question with none is matched on
    # its letters, which added Latin-script words would switch off, so it is ranked as asked.
    ranked_query = f"{query} {expansion}".strip() if expansion and _query_terms(query) else query
    # Without a reranker, a question matched on its letters falls back to recency only when no piece of either pool
    # shares a letter pair with it: a pool with no match then scores 0, and waits for the top-up like any piece
    # with no shared term, instead of crowding out the matches in the other pool.
    recency = (
        scorer is not None
        or bool(_query_terms(ranked_query))
        or not _grams_match(user, other, ranked_query)
    )
    for pool, n, by_turn in ((user, RERANK_USER, False), (other, RERANK_REPLY, REPLY_GROUP)):
        for piece, value in zip(
            pool, score_pool(pool, turns, ranked_query, scorer, n, by_turn, recency)
        ):
            piece.score = value
    if trace is not None:
        trace.pool("user", "turn", user)
        trace.pool("reply", "window", other)
    chosen = Selection(turns, budget, ranked_query, trace=trace)
    fill(chosen, user, other, budget, share, scorer is None, cap_for_user_turn(budget))
    return chosen


def fill(
    chosen: Selection,
    user: Sequence[Piece],
    other: Sequence[Piece],
    budget: int,
    share: float,
    lexical: bool,
    cap: int = 0,
) -> None:
    """Fill ``budget``: user pieces by score up to ``share`` of it (long ones trimmed to ``cap``), then the other
    pieces, then what is left of either by relevance relative to its pool's best. Lexical scores of 0 (no shared
    term) wait for that last top-up. When nothing fits whole, the best piece is cut to fit."""
    user_order = sorted(user, key=lambda p: (-p.score, p.turn))
    other_order = sorted(other, key=lambda p: (-p.score, p.turn, p.part))
    user_room = int(budget * share)
    if chosen.trace is not None:
        chosen.trace.user_room, chosen.trace.user_cap = user_room, cap or None
    taken: Set[int] = set()
    for piece in user_order:
        if lexical and piece.score <= 0:
            break
        if user_room - chosen.used < 8:
            break
        if chosen.take(piece, user_room, cap):
            taken.add(id(piece))
    for piece in other_order:
        if lexical and piece.score <= 0:
            break
        if budget - chosen.used < 8:
            break
        if chosen.take(piece, budget):
            taken.add(id(piece))
    if budget - chosen.used >= 8:
        top_user = max((p.score for p in user), default=0.0) or 1.0
        top_other = max((p.score for p in other), default=0.0) or 1.0
        rest = [(p.score / top_user, 0, p) for p in user if id(p) not in taken]
        rest += [(p.score / top_other, 1, p) for p in other if id(p) not in taken]
        rest.sort(key=lambda r: (-r[0], r[2].turn, r[1], r[2].part))
        for _, kind, piece in rest:
            if budget - chosen.used < 8:
                break
            chosen.take(piece, budget, cap if kind == 0 else 0)
    if not chosen.kept:
        last_resort(chosen, user_order + other_order, budget)


def last_resort(chosen: Selection, order: Sequence[Piece], budget: int) -> None:
    """Nothing fitted whole (a tiny budget): the best piece, cut to what is left after its label."""
    if not order:
        return
    best = max(order, key=lambda p: (p.score, -p.turn))
    room = max(1, budget - chosen.label_cost(best.turn))
    parts, _ = excerpt(best.segs, chosen.query, room)
    text = join(parts)
    if count_tokens(text) > room:
        text = _cut(best.text.replace("\n", " "), room)
        parts = [(text, False)]
    chosen.used = count_tokens(text) + chosen.label_cost(best.turn)
    chosen.kept[best.turn] = {best.part: (parts, best.score, True)}
    if chosen.trace is not None:
        chosen.trace.keep(best, "last_resort")
    chosen.per_session[chosen.turns[best.turn].session] = 1
    chosen.stamps[chosen.turns[best.turn].session] = {chosen.turns[best.turn].stamp}


Fitted = Tuple[List[str], List[Tuple[int, bool]], int]


def fit(
    chosen: Selection, budget: int, prefix: str, count: Callable[[str], int] = count_tokens
) -> Fitted:
    """Render, count exactly with the sections above (``prefix``), and drop the weakest pieces while the whole runs
    over the budget's slack; the last piece left is cut short instead, or dropped when no room is left for it.
    Returns (session texts, recalled turns, tokens)."""
    limit = int(budget * SLACK)
    while True:
        texts, recalled = chosen.render()
        body = "\n\n".join(t for t in texts if t)
        whole = "\n\n".join(p for p in (prefix, body) if p)
        tokens = count(whole) if whole else 0
        if tokens <= limit or not chosen.kept:
            return texts, recalled, tokens
        if chosen.drop_weakest():
            continue
        # One piece left and still too long: cut it to what is left, or drop it.
        ((turn, parts),) = chosen.kept.items()
        ((part, (pieces, score, _)),) = parts.items()
        flat = " ".join(" ".join(text.split()) for text, _ in pieces)
        room = count(flat) - (tokens - limit) - 4
        cut = [(_cut(flat, room), False)] if room >= 4 else []
        if cut and cut == pieces:
            # A cut at a space leaves the piece as it is: its first word alone is longer than the room (text with no
            # spaces, such as Chinese or Japanese prose, a long URL or an encoded blob). It is cut between two
            # characters instead. When that cannot shorten it either, cutting again would give the same text
            # forever, so the piece is dropped, as when no room is left.
            chars = _cut_chars(flat, room)
            cut = [(chars, False)] if chars else []
        if not cut or cut == pieces:
            if chosen.trace is not None:
                chosen.trace.mark(turn, part, "dropped_at_fit")
            chosen.kept.clear()
        else:
            if chosen.trace is not None:
                chosen.trace.mark(turn, part, "cut_at_fit")
            chosen.kept[turn][part] = (cut, score, True)


def as_items(
    turns: Sequence[Turn], recalled: Sequence[Tuple[int, bool]]
) -> List[Tuple[MemoryItem, bool]]:
    """The stored turns behind ``render``'s (turn index, partial) pairs."""
    return [(turns[k].item, partial) for k, partial in recalled]
