"""Query-focused selection (v0.8).

Up to v0.7, extractive compression gave every semantic chunk a proportional share of the budget, so a question
about one document kept a quarter of every document. With a query, LLMSlim now ranks the context's structural
units (documents, chat rounds, paragraphs) against the query and keeps the best units whole, in their original
order, inside the token budget; the remaining budget is filled sentence by sentence from the next best unit.

Line-structured text (code, logs, test output, listings) keeps its line breaks: failures, tracebacks and
definitions are kept first, runs of near-identical lines collapse into one line and a count, and omitted spans
are marked so a reader (or an agent) knows where to look.

Everything here is lexical and local: BM25 with light stemming and one round of pseudo-relevance feedback. No
model, no network, deterministic output.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .ranking import may_reach_priority, reaches_priority
from .rerank import Scorer
from .tokenization import split_sentences
from .tokens import count_tokens

# ------------------------------------------------------------------ terms

_WORD = re.compile(r"[a-z0-9]+(?:['.][a-z0-9]+)*")
_STOP = frozenset(
    """a an the and or but if then else of to in on at by for with from as is are was were be been being this that
    these those it its i me my we our you your he she him her his they them their what which who whom whose when where
    why how do does did done have has had having not no nor so too very can could should would will shall may might
    must just also than such there here about into over after before up down out off again further once all any both
    each few more most other some own same only s t don isn aren wasn weren hasn haven hadn doesn didn won wouldn
    shouldn couldn mustn let us via per am ll ve re d m o y""".split()
)
_SUFFIXES = (
    "ational",
    "ization",
    "fulness",
    "ousness",
    "iveness",
    "ations",
    "ation",
    "ments",
    "ment",
    "ness",
    "ings",
    "ing",
    "edly",
    "ies",
    "ied",
    "ed",
    "es",
    "ly",
    "s",
)
_UNDOUBLE = frozenset(("ings", "ing", "edly", "ed"))


@lru_cache(maxsize=1 << 16)
def _stem(word: str) -> str:
    """Light suffix stripping that brings a word's inflected forms to one stem: move, moves, moved and moving all
    become "mov"; shop and shopping "shop"; class and classes "class"."""
    if len(word) <= 3 or word[0].isdigit():
        return word
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            # "class" and "status" are not plurals.
            if suffix == "s" and word.endswith(("ss", "us")):
                break
            # "agreed" -> "agree", while "speed" and "breed" stay whole.
            if suffix == "ed" and word.endswith("eed"):
                word = word[:-1] if len(word) >= 6 else word
                break
            word = word[: -len(suffix)] + ("y" if suffix in ("ies", "ied") else "")
            # "classes" -> "class"; "businesses" -> "business" -> "busi".
            if suffix == "es" and word.endswith("ss"):
                return _stem(word)
            # "shopping" -> "shop", "planned" -> "plan"; "called", "kissed" and "buzzed" keep their double letter.
            if suffix in _UNDOUBLE and len(word) > 3 and word[-1] == word[-2]:
                word = word[:-1] if word[-1] not in "aeiouylsz" else word
            break
    # A final "e" goes whenever three letters remain, so "move" meets "moved" and "time" meets "times".
    return word[:-1] if len(word) > 3 and word.endswith("e") else word


def terms(text: str) -> List[str]:
    """Lower-cased, stop-word-free, lightly stemmed terms; numbers are kept as they are."""
    return [_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOP]


class BM25:
    """Okapi BM25 over a small in-memory collection."""

    def __init__(self, docs: Sequence[Sequence[str]], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.lengths = [len(d) for d in docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 1.0
        df: Counter = Counter()
        for counts in self.tf:
            df.update(counts.keys())
        n = len(docs)
        self.idf = {t: math.log(1.0 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def scores(self, weights: Dict[str, float]) -> List[float]:
        out = []
        for counts, length in zip(self.tf, self.lengths):
            norm = self.k1 * (1.0 - self.b + self.b * length / (self.avg or 1.0))
            total = 0.0
            for term, weight in weights.items():
                f = counts.get(term)
                if f:
                    total += weight * self.idf[term] * f * (self.k1 + 1.0) / (f + norm)
            out.append(total)
        return out


# ------------------------------------------------------------------ units


@dataclass
class Unit:
    index: int
    group: int
    text: str
    tokens: int
    header: str = ""
    joiner: str = "\n"
    must_keep: bool = False
    must_text: str = (
        ""  # the text that has to survive: the whole unit, or only its protected sentences
    )


_HEADER_LINE = re.compile(
    r"^(#{1,6}\s+\S|### Session\b|Session Date:|Session Content:|Title:\s|-{3,}\s*$|={3,}\s*$|\*\*[^*]{1,80}\*\*:?\s*$)",
    re.I,
)
_DOC_LINE = re.compile(
    r"^(Document \[\d+\](?:\(Title: [^)]*\))?|Passage \d+:|\[\d+\](?:\s*Title:[^\n]{0,120})?)"
)
_CHAT_LINE = re.compile(r'^\s*\[\s*\{\s*"role"\s*:')


def _windows(text: str, max_tokens: int) -> List[str]:
    """Split a long paragraph into consecutive sentence windows of at most ``max_tokens`` (one sentence may exceed it)."""
    sentences = split_sentences(text) or [text]
    windows: List[str] = []
    current: List[str] = []
    used = 0
    for sentence in sentences:
        cost = count_tokens(sentence)
        if current and used + cost > max_tokens:
            windows.append(" ".join(current))
            current, used = [], 0
        current.append(sentence)
        used += cost
    if current:
        windows.append(" ".join(current))
    return windows


def _chat_units(line: str, max_tokens: int) -> Optional[List[Tuple[str, str]]]:
    """Parse a JSON list of chat turns into rounds (a user turn and the replies after it). None if not chat."""
    try:
        turns = json.loads(line)
    except (ValueError, TypeError):
        return None
    if (
        not isinstance(turns, list)
        or not turns
        or not all(isinstance(t, dict) and "role" in t and "content" in t for t in turns)
    ):
        return None
    rounds: List[List[dict]] = []
    for turn in turns:
        if turn["role"] == "user" or not rounds:
            rounds.append([turn])
        else:
            rounds[-1].append(turn)
    out: List[Tuple[str, str]] = []
    for group in rounds:
        rendered = json.dumps(
            [{"role": t["role"], "content": t["content"]} for t in group], ensure_ascii=False
        )
        if count_tokens(rendered) <= max_tokens * 3:
            out.append((rendered, "\n"))
            continue
        # A very long round: keep the user turn as one unit and window the replies.
        for turn in group:
            content = str(turn["content"])
            parts = (
                _windows(content, max_tokens) if count_tokens(content) > max_tokens else [content]
            )
            for part in parts:
                out.append(
                    (
                        json.dumps([{"role": turn["role"], "content": part}], ensure_ascii=False),
                        "\n",
                    )
                )
    return out


# A transcript line: an optional bracketed stamp, then a short speaker name and a colon ("[8 May 2023] Caroline: hi",
# "user: ...", "Dr. Smith: ...").
_SPEAKER_LINE = re.compile(
    r"^(?:\[(?P<stamp>[^\]\n]{1,60})\]\s*)?(?P<speaker>(?:[A-Z][\w.'-]*|user|assistant|system|tool|human|ai|bot)"
    r"(?: [A-Z][\w.'-]*){0,3}):\s+\S"
)
TRANSCRIPTS = True  # speaker-prefixed lines become one unit per turn
TRANSCRIPT_ROUNDS = (
    True  # a turn that asks a question is kept together with the reply that follows it
)
FACTOR_STAMPS = (
    True  # a stamp shared by every line of a transcript block is shown once, as its header
)
CHAINED_ROUNDS = (
    True  # a reply that asks a question back keeps its own reply too (at most three turns)
)


def _transcript(lines: Sequence[str]) -> Optional[List[Tuple[Optional[str], str, str]]]:
    """(stamp, speaker, line) per turn when the block reads as a transcript: at least two turns, two speakers, and
    nearly every line starting with a speaker. A line without one continues the turn above it. None otherwise."""
    turns: List[List] = []
    for raw in lines:
        line = raw.strip()
        match = _SPEAKER_LINE.match(line)
        if match:
            turns.append([match.group("stamp"), match.group("speaker"), line])
        elif turns:
            turns[-1][2] += " " + line
        else:
            return None
    if len(turns) < 2 or len({t[1] for t in turns}) < 2 or len(turns) < 0.8 * len(lines):
        return None
    return [(t[0], t[1], t[2]) for t in turns]


def _transcript_units(
    turns: Sequence[Tuple[Optional[str], str, str]], max_tokens: int
) -> Tuple[Optional[str], List[Tuple[str, str]]]:
    """Units for a transcript block, and the stamp to show once as its header (when every turn shares it)."""
    stamps = {t[0] for t in turns}
    shared = (
        next(iter(stamps)) if FACTOR_STAMPS and len(stamps) == 1 and None not in stamps else None
    )
    texts = [t[2][len(f"[{shared}]") :].lstrip() if shared else t[2] for t in turns]
    groups: List[List[int]] = []
    i = 0
    longest = 3 if CHAINED_ROUNDS else 2
    while i < len(turns):
        group = [i]
        while (
            TRANSCRIPT_ROUNDS
            and len(group) < longest
            and "?" in texts[group[-1]]
            and group[-1] + 1 < len(turns)
            and turns[group[-1] + 1][1] != turns[group[-1]][1]
        ):
            group.append(group[-1] + 1)
        groups.append(group)
        i += len(group)
    out: List[Tuple[str, str]] = []
    for group in groups:
        body = "\n".join(texts[j] for j in group)
        if count_tokens(body) <= max_tokens * 3:
            out.append((body, "\n"))
            continue
        for j in group:  # a very long round: each turn on its own, long turns in sentence windows
            parts = (
                _windows(texts[j], max_tokens)
                if count_tokens(texts[j]) > max_tokens
                else [texts[j]]
            )
            out.extend((part, " " if k else "\n") for k, part in enumerate(parts))
    return (f"[{shared}]" if shared else None), out


def segment(text: str, max_unit_tokens: int = 220) -> List[Unit]:
    """Split text into rankable units: documents, chat rounds, paragraphs or sentence windows of long paragraphs.

    Header lines (markdown headings, ``### Session``, ``Session Date:``, ``Document [k](Title: ...)``) start a new
    group; the group's header is shown once before the first kept unit of that group.
    """
    units: List[Unit] = []
    group = 0
    header_lines: List[str] = []
    last_was_header = False

    def add(body: str, joiner: str = " ") -> None:
        body = body.strip()
        if not body:
            return
        header = "\n".join(header_lines)
        if count_tokens(body) <= max_unit_tokens:
            units.append(Unit(len(units), group, body, count_tokens(body), header, "\n"))
            return
        for part in _windows(body, max_unit_tokens):
            units.append(Unit(len(units), group, part, count_tokens(part), header, joiner))

    paragraph: List[str] = []

    def flush() -> None:
        nonlocal group
        if not paragraph:
            return
        turns = _transcript(paragraph) if TRANSCRIPTS else None
        if turns is None:
            add(" ".join(p.strip() for p in paragraph))
        else:
            stamp, pieces = _transcript_units(turns, max_unit_tokens)
            if stamp:
                group += 1  # the shared stamp heads this block only
            header = "\n".join([*header_lines, stamp] if stamp else header_lines)
            for body, joiner in pieces:
                units.append(Unit(len(units), group, body, count_tokens(body), header, joiner))
            if stamp:
                group += 1
        paragraph.clear()

    for raw in text.split("\n"):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if _CHAT_LINE.match(stripped):
            rounds = _chat_units(stripped, max_unit_tokens)
            if rounds is not None:
                flush()
                header = "\n".join(header_lines)
                for body, joiner in rounds:
                    units.append(Unit(len(units), group, body, count_tokens(body), header, joiner))
                last_was_header = False
                continue
        doc = _DOC_LINE.match(stripped)
        if doc:
            flush()
            group += 1
            header_lines = [doc.group(1)]
            body = stripped
            if count_tokens(body) <= max_unit_tokens:
                units.append(
                    Unit(len(units), group, body, count_tokens(body), header_lines[0], "\n")
                )
            else:
                for part in _windows(body, max_unit_tokens):
                    units.append(
                        Unit(len(units), group, part, count_tokens(part), header_lines[0], " ")
                    )
            last_was_header = False
            continue
        if _HEADER_LINE.match(stripped) and len(stripped) <= 160:
            flush()
            if not last_was_header:
                group += 1
                header_lines = []
            header_lines.append(stripped)
            last_was_header = True
            continue
        paragraph.append(line)
        last_was_header = False
    flush()
    return units


# ------------------------------------------------------------------ ranking

# What a question asks for, and what an answer of that kind looks like in text.
_ANSWER_SHAPES = {
    "time": re.compile(
        r"\b(1[0-9]{3}|20[0-9]{2})\b|\b(january|february|march|april|may|june|july|august|september|october|november|december)\b|\b\d{1,2}(st|nd|rd|th)\b",
        re.I,
    ),
    "number": re.compile(r"\d"),
    "person": re.compile(r"\b[A-Z][a-z]+(?:\s+(?:[A-Z]\.|[A-Z][a-z]+)){1,3}\b"),
    "place": re.compile(r"\b(?:in|at|near|from)\s+[A-Z][a-z]+"),
}


QUANTITY_TERMS = (
    True  # in "how long / how many ..." the word after "how" names the answer's kind, not a topic
)
_QUANTITY = re.compile(
    r"\bhow\s+(?:long|many|much|old|far|big|often|soon|tall|large|high|late|early)\b", re.I
)


def _query_terms(query: str) -> List[str]:
    """The query's terms for matching. "How long has she painted?" asks for a duration: "long" would match "long
    time no see", so it is left to the answer-type bonus instead."""
    return terms(_QUANTITY.sub("how", query) if QUANTITY_TERMS else query)


def _answer_type(query: str) -> Optional[str]:
    q = query.strip().lower()
    if re.match(r"(when|what year|which year|what date|in what year|how long ago)\b", q):
        return "time"
    if re.match(
        r"(how many|how much|how old|how long|how far|how big|what percentage|what number)\b", q
    ):
        return "number"
    if re.match(r"(who|whom|whose)\b", q):
        return "person"
    if re.match(r"(where|what country|which country|what city|which city)\b", q):
        return "place"
    return None


def _joined(words: Sequence[str]) -> List[str]:
    """Adjacent word pairs written as one word: "super bowl" -> "superbowl", "gall bladder" -> "gallbladder"."""
    return [
        _stem(a + b)
        for a, b in zip(words, words[1:])
        if len(a) >= 3
        and len(b) >= 3
        and a not in _STOP
        and b not in _STOP
        and not (a + b).isdigit()
    ]


def _with_compounds(
    query: str, query_terms: List[str], units: Sequence[Unit], unit_terms: List[List[str]]
) -> List[str]:
    """Match compounds in either direction: a query word the text splits in two, or a query word pair the text
    writes as one. Matching forms are added to the unit's terms (or the query's), so BM25 sees them as one term."""
    vocab = {t for ts in unit_terms for t in ts}
    wanted = set(query_terms)
    joined_query = [
        j for j in _joined(_WORD.findall(query.lower())) if j in vocab and j not in wanted
    ]
    for i, u in enumerate(units):
        extra = [j for j in _joined(_WORD.findall(u.text.lower())) if j in wanted]
        if extra:
            unit_terms[i] = unit_terms[i] + extra
    return query_terms + joined_query


def rank(units: Sequence[Unit], query: str, scorer: Optional[Scorer] = None) -> List[float]:
    """BM25 of the query against each unit (headers count), one round of pseudo-relevance feedback,
    and small bonuses for numbers and word pairs shared with the query. With a ``scorer`` (a reranking
    model), the strongest lexical candidates are rescored by the model."""
    query_terms = _query_terms(query)
    if not units or not query_terms:
        return [0.0] * len(units)
    # Headers (titles, section names) count twice: they say what a unit is about.
    unit_terms = [
        terms((u.header + " " + u.header + " " + u.text) if u.header else u.text) for u in units
    ]
    query_terms = _with_compounds(query, query_terms, units, unit_terms)
    bm25 = BM25(unit_terms)
    weights = dict.fromkeys(query_terms, 1.0)
    base = bm25.scores(weights)
    best = sorted(range(len(units)), key=lambda i: (-base[i], i))[:3]
    scores: List[float] = list(base)
    if base and base[best[0]] > 0:
        feedback: Dict[str, float] = {}
        for i in best:
            if base[i] <= 0:
                continue
            for term, f in bm25.tf[i].items():
                if term not in weights and not term.isdigit():
                    feedback[term] = feedback.get(term, 0.0) + f * bm25.idf.get(term, 0.0)
        strongest = sorted(feedback.items(), key=lambda item: (-item[1], item[0]))[:8]
        expansion = {t: 0.25 for t, _ in strongest}
        if expansion:
            scores = [s + e for s, e in zip(base, bm25.scores(expansion))]
    # Two levels: a unit also inherits part of its whole group's relevance (its document, session or section),
    # so the best window of the right document beats an equally worded window of a wrong one.
    groups: Dict[int, List[int]] = {}
    for i, u in enumerate(units):
        groups.setdefault(u.group, []).append(i)
    if len(groups) > 1:
        group_ids = list(groups)
        group_terms = [[t for i in groups[g] for t in unit_terms[i]] for g in group_ids]
        group_scores = BM25(group_terms).scores(weights)
        top_group = max(group_scores) or 1.0
        top_unit = max(scores) or 1.0
        for g, gs in zip(group_ids, group_scores):
            for i in groups[g]:
                scores[i] += 0.35 * top_unit * gs / top_group
    top = max(scores) if scores else 0.0
    query_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", query))
    query_pairs = set(zip(query_terms, query_terms[1:]))
    wants = _answer_type(query)
    for i, unit_t in enumerate(unit_terms):
        if not top:
            break
        bonus = 0.0
        if wants and scores[i] > 0 and _ANSWER_SHAPES[wants].search(units[i].text):
            bonus += 0.12
        if query_numbers and query_numbers & set(re.findall(r"\d+(?:[.,]\d+)?", units[i].text)):
            bonus += 0.10
        if query_pairs:
            pairs = set(zip(unit_t, unit_t[1:]))
            bonus += 0.08 * min(3, len(query_pairs & pairs))
        scores[i] += bonus * top
    if scorer is not None:
        return _rerank(units, query, scores, scorer)
    return scores


RERANK_CANDIDATES = 80  # units a reranking model reads: the strongest lexical candidates
RERANK_LEXICAL = 0.5  # weight of the lexical score next to the model's, both scaled to [0, 1]
RERANK_QUERY_WORDS = 64  # a longer query is cut to its last words for the model


def _rerank(units: Sequence[Unit], query: str, lexical: List[float], scorer: Scorer) -> List[float]:
    """Model score plus a share of the lexical score for the top lexical candidates; the rest keep only
    their (scaled) lexical share, so they rank below the candidates the model liked."""
    top = max(lexical) if lexical else 0.0
    lex = [s / top if top > 0 else 0.0 for s in lexical]
    candidates = sorted(range(len(units)), key=lambda i: (-lexical[i], i))[:RERANK_CANDIDATES]
    texts = [
        units[i].text
        if not units[i].header or units[i].text.startswith(units[i].header)
        else units[i].header + "\n" + units[i].text
        for i in candidates
    ]
    # A reranker reads the query and the unit together in a short window: a long query (a prompt with examples,
    # a pasted passage) keeps its end, where the question usually is.
    words = query.split()
    if len(words) > RERANK_QUERY_WORDS:
        query = " ".join(words[-RERANK_QUERY_WORDS:])
    model = list(scorer(query, texts))
    low, high = min(model), max(model)
    span = (high - low) or 1.0
    out = [RERANK_LEXICAL * v - 1.0 for v in lex]
    for i, m in zip(candidates, model):
        out[i] = (m - low) / span + RERANK_LEXICAL * lex[i]
    floor = min(out)
    return [v - floor for v in out]


# ------------------------------------------------------------------ selection


def _excerpt(unit: Unit, query: str, budget: int) -> Optional[str]:
    """The unit's best sentences (by BM25 against the query) that fit ``budget``, in their original order."""
    sentences = split_sentences(unit.text)
    if len(sentences) < 2:
        return None
    bm25 = BM25([terms(s) for s in sentences])
    scores = bm25.scores(dict.fromkeys(_query_terms(query), 1.0))
    chosen, used = set(), 0
    for i in sorted(range(len(sentences)), key=lambda k: (-scores[k], k)):
        cost = count_tokens(sentences[i])
        if scores[i] <= 0 or used + cost > budget:
            continue
        chosen.add(i)
        used += cost
    if not chosen:
        return None
    parts, previous = [], None
    for i in sorted(chosen):
        if previous is not None and i != previous + 1:
            parts.append("...")
        parts.append(sentences[i])
        previous = i
    return " ".join(parts)


def select(
    units: Sequence[Unit], scores: Sequence[float], budget: int, query: str
) -> Dict[int, str]:
    """Keep must-keep units, then whole units by score while they fit, then an excerpt of the best unit that did not."""
    header_cost: Dict[int, int] = {}
    for u in units:
        if u.header and u.group not in header_cost:
            header_cost[u.group] = count_tokens(u.header) + 1
    kept: Dict[int, str] = {}
    groups: Set[int] = set()
    used = 0

    def take(i: int, text: str, tokens: int) -> None:
        nonlocal used
        kept[i] = text
        if units[i].group not in groups:
            used += header_cost.get(units[i].group, 0)
            groups.add(units[i].group)
        used += tokens

    for u in units:
        if u.must_keep:
            text = u.must_text or u.text
            take(u.index, text, count_tokens(text))
    order = sorted(range(len(units)), key=lambda i: (-scores[i], i))
    for i in order:
        if i in kept:
            continue
        u = units[i]
        header = 0 if u.group in groups else header_cost.get(u.group, 0)
        if used + u.tokens + header <= budget:
            take(i, u.text, u.tokens)
        elif scores[i] > 0 or not kept:
            # A relevant unit that does not fit whole gives its best sentences before any weaker unit is considered.
            room = budget - used - header
            if room >= 20 or not kept:
                excerpt = _excerpt(u, query, max(room, 1))
                if excerpt:
                    take(i, excerpt, count_tokens(excerpt))
        if budget - used < 12:
            break
    if not kept and units:
        best = order[0]
        take(best, _truncate(units[best].text, budget), budget)
    return kept


def _truncate(text: str, budget: int) -> str:
    """The longest prefix of whole words within ``budget`` tokens (last resort: never return nothing)."""
    words = text.split()
    low, high = 1, len(words)
    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(" ".join(words[:mid])) <= budget:
            low = mid
        else:
            high = mid - 1
    return " ".join(words[:low])


def render(units: Sequence[Unit], kept: Dict[int, str]) -> str:
    """Kept units in their original order; each group's header once; ``...`` marks a gap inside a group."""
    blocks: List[str] = []
    pieces: List[str] = []
    current_group, previous = None, None
    for i in sorted(kept):
        u = units[i]
        if u.group != current_group:
            if pieces:
                blocks.append("\n".join(pieces))
            pieces, current_group, previous = [], u.group, None
            if u.header and not kept[i].startswith(u.header):
                pieces.append(u.header)
        if previous is not None and i != previous + 1:
            pieces.append("...")
        if previous is not None and i == previous + 1 and u.joiner == " " and pieces:
            pieces[-1] = pieces[-1] + " " + kept[i]
        else:
            pieces.append(kept[i])
        previous = i
    if pieces:
        blocks.append("\n".join(pieces))
    return "\n\n".join(blocks)


def _mark_must_keep(
    units: Sequence[Unit], preserve_res: Sequence[re.Pattern], context_role: str, budget: int
) -> None:
    """Trusted guardrails and developer preserve patterns survive selection; untrusted text never earns this tier.
    A small unit is kept whole; from a large one, only the protected sentences. Instructions (tier 3) are
    protected when the text itself is an instruction (system or developer role); elsewhere they compete on relevance."""
    role = str(getattr(context_role, "value", context_role)).lower()
    floor = 3 if role in ("system", "developer") else 4
    for u in units:
        if not may_reach_priority(u.text, preserve_res, role):
            continue
        sentences = split_sentences(u.text) or [u.text]
        protected = [s for s in sentences if reaches_priority(s, floor, preserve_res, role)]
        if not protected:
            continue
        u.must_keep = True
        u.must_text = u.text if u.tokens <= max(40, budget // 2) else " ... ".join(protected)


UNIT_DIVISOR = 32  # units of about 1/32 of the budget (dev split: LongBench answer retention 161 -> 166 of 192)


def unit_size(budget: int) -> int:
    """Finer units for tighter budgets: about a thirty-second of the budget, between 40 and 220 tokens."""
    return max(40, min(220, budget // UNIT_DIVISOR))


def focus(
    text: str,
    query: str,
    budget: int,
    *,
    preserve_res: Sequence[re.Pattern] = (),
    context_role: str = "general",
    scorer: Optional[Scorer] = None,
) -> Tuple[str, int, int]:
    """Query-focused selection over one text. Returns (compressed_text, units_total, units_kept)."""
    units = segment(text, unit_size(budget))
    if not units:
        return text, 0, 0
    _mark_must_keep(units, preserve_res, context_role, budget)
    kept = select(units, rank(units, query, scorer if query.strip() else None), budget, query)
    return render(units, kept), len(units), len(kept)


def focus_documents(
    documents: Sequence[str],
    query: str,
    budget: int,
    *,
    preserve_res: Sequence[re.Pattern] = (),
    context_role: str = "rag",
    scorer: Optional[Scorer] = None,
) -> List[str]:
    """Share one budget across documents by relevance: the best documents stay whole, irrelevant ones drop out."""
    units: List[Unit] = []
    owner: List[int] = []
    size = unit_size(budget)
    for d, document in enumerate(documents):
        for u in segment(document, size):
            units.append(
                Unit(len(units), d * 100_000 + u.group, u.text, u.tokens, u.header, u.joiner)
            )
            owner.append(d)
    if not units:
        return list(documents)
    _mark_must_keep(units, preserve_res, context_role, budget)
    kept = select(units, rank(units, query, scorer), budget, query)
    out = []
    for d in range(len(documents)):
        mine = {i: t for i, t in kept.items() if owner[i] == d}
        out.append(render(units, mine) if mine else "")
    return out


# ------------------------------------------------------------------ line-structured text: code, logs, tool output

_IMPORTANT_LINE = re.compile(
    r"(error|exception|traceback|fail(?:ed|ure|s)?\b|assert|warn(?:ing)?\b|fatal|panic|denied|not found|undefined|"
    r"segmentation fault|timed? ?out|^E\s{2,}|^\s*raise\b|exit code [1-9])",
    re.I,
)
_DEFINITION_LINE = re.compile(
    r"^\s*(?:async\s+def|def|class|function|export\s+(?:default\s+)?(?:function|class|const)|public|private|protected|"
    r"fn|func|interface|struct|impl|module|package|import|from\s+\S+\s+import|#include|using\s)\b"
)
_CODE_LINE = re.compile(
    r"^\s{2,}\S|^\s*(def |class |import |from \S+ import|return\b|if .*:$|for .*:$|while .*:$|elif |else:|try:|except|[{}()\[\];]\s*$|#include|function |const |let |var |public |private )"
)
_LOG_LINE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}|\[\d|\d{1,2}:\d{2}:\d{2}|(INFO|DEBUG|WARN|WARNING|ERROR|TRACE|CRITICAL)\b|[\w./-]+::\w+|[\w./-]+\.\w{1,4}:\d+|E\s{2,}|PASSED|FAILED|ok\b|---|\+\+\+|@@|[-+] )"
)


def is_line_structured(text: str) -> bool:
    """True for code, logs, test output, diffs and listings, where line breaks carry meaning.
    Chat transcripts and documents with headers are prose units, even when their lines are short."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) < 6:
        return False
    headed = sum(
        1
        for ln in lines
        if _CHAT_LINE.match(ln)
        or _DOC_LINE.match(ln.strip())
        or ln.strip().startswith(("### Session", "Session Date:", "Session Content:"))
    )
    if headed / len(lines) >= 0.2:
        return False
    long_prose = sum(
        1 for ln in lines if len(ln) > 220 and len(re.findall(r"[.!?](?:\s|$)", ln)) >= 2
    )
    if long_prose / len(lines) > 0.15:
        return False
    structured = sum(1 for ln in lines if _CODE_LINE.match(ln) or _LOG_LINE.match(ln))
    unpunctuated = sum(1 for ln in lines if not re.search(r"[.!?]\s*$", ln.strip()))
    avg = sum(len(ln) for ln in lines) / len(lines)
    return structured / len(lines) >= 0.3 or (unpunctuated / len(lines) >= 0.8 and avg < 140)


_BLOCK_START = re.compile(
    r"^(\s*)(?:@\w|async\s+def\b|def\b|class\b|function\b|export\s+(?:default\s+)?(?:async\s+)?function\b|public\b|private\b|protected\b|fn\b|func\b|impl\b|struct\b|interface\b)"
)


def _code_blocks(lines: Sequence[str]) -> List[Tuple[int, int]]:
    """(start, end) line ranges of definitions, found by indentation (decorators belong to their definition).
    Returns [] unless definitions cover a meaningful share of the text."""
    n = len(lines)
    blocks: List[Tuple[int, int]] = []
    k = 0
    while k < n:
        match = _BLOCK_START.match(lines[k])
        if not match:
            k += 1
            continue
        indent = len(match.group(1).expandtabs(4))
        start = k
        while k < n and lines[k].lstrip().startswith("@"):
            k += 1
        end = k + 1
        while end < n:
            line = lines[end]
            if (
                line.strip()
                and len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip()) <= indent
                and not line.lstrip().startswith((")", "]", "}"))
            ):
                break
            end += 1
        blocks.append((start, end))
        k = (
            start + 1
            if end - start > 1 and indent == 0 and lines[start].lstrip().startswith("class")
            else end
        )
    covered = sum(e - s for s, e in blocks)
    return blocks if blocks and covered >= 0.3 * n else []


def _signature(line: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\b[0-9a-f]{7,}\b", "#", line.strip()))[:48]


TAIL_SHARE = (
    0.35  # line-structured text without a query: share of the budget kept as a contiguous tail
)
TAIL_SHARE_QUERY = 0.15  # ... and with a query


def focus_lines(text: str, budget: int, query: Optional[str] = None) -> Tuple[str, int, int]:
    """Line-preserving compression. Returns (compressed_text, lines_total, lines_kept)."""
    lines = text.split("\n")
    n = len(lines)
    tokens = [count_tokens(ln) + 1 for ln in lines]
    # 1. Collapse runs of near-identical lines (test progress, repeated log records) unless a line is important.
    collapsed: Dict[int, int] = {}  # first index of a run -> run length
    i = 0
    while i < n:
        j = i
        while (
            j + 1 < n
            and lines[j + 1].strip()
            and _signature(lines[j + 1]) == _signature(lines[i])
            and not _IMPORTANT_LINE.search(lines[j + 1])
        ):
            j += 1
        if j - i + 1 >= 4 and not _IMPORTANT_LINE.search(lines[i]):
            collapsed[i] = j - i + 1
        i = j + 1
    hidden = {
        k for start, length in collapsed.items() for k in range(start + 1, start + length - 1)
    }
    # 2. Score lines: failures and their neighbourhood, definitions, the query, the first and last lines.
    score = [0.0] * n
    query_scores = (
        BM25([terms(ln) for ln in lines]).scores(dict.fromkeys(terms(query), 1.0))
        if query and terms(query)
        else [0.0] * n
    )
    top_query = max(query_scores) if any(query_scores) else 1.0
    in_traceback = False
    for k, line in enumerate(lines):
        if line.lstrip().startswith("Traceback"):
            in_traceback = True
        elif in_traceback and (
            not line.strip()
            or not line.startswith((" ", "\t"))
            and not line.startswith("Traceback")
        ):
            score[k] = max(score[k], 2.6)  # the exception line that ends a traceback
            in_traceback = False
        if in_traceback:
            score[k] = max(score[k], 2.5)
        if _IMPORTANT_LINE.search(line):
            score[k] = max(score[k], 3.0)
            for m in range(max(0, k - 2), min(n, k + 3)):
                score[m] = max(score[m], 1.6)
        if _DEFINITION_LINE.match(line):
            score[k] = max(score[k], 1.2)
        score[k] += 1.5 * query_scores[k] / top_query
    for k in list(range(min(3, n))) + list(range(max(0, n - 3), n)):
        score[k] = max(score[k], 1.0)
    for k in range(n):
        score[k] += 0.4 * k / max(1, n - 1)  # among equals, later lines win
    # 3. The end of line-structured text is where the work is: the cursor in a file being edited, the
    #    outcome of a run, the newest log records. Keep a contiguous tail first; most of the budget
    #    when there is no query to point elsewhere, a little when there is.
    used, keep = 0, set()
    tail_budget = budget * (TAIL_SHARE_QUERY if query and terms(query) else TAIL_SHARE)
    for k in range(n - 1, -1, -1):
        if k in hidden or not lines[k].strip():
            continue
        if used + tokens[k] > tail_budget:
            break
        keep.add(k)
        used += tokens[k]
    # 4. Code: keep the skeleton (imports and every signature), then whole bodies of the most relevant
    #    definitions, the way a reader skims a file. Any budget left goes to single lines by score.
    blocks = _code_blocks(lines)
    if blocks:
        for k, line in enumerate(lines):
            if _DEFINITION_LINE.match(line) and k not in hidden and used + tokens[k] <= budget:
                keep.add(k)
                used += tokens[k]
        if query and terms(query):
            block_scores = BM25([terms("\n".join(lines[s:e])) for s, e in blocks]).scores(
                dict.fromkeys(terms(query), 1.0)
            )
            for b in sorted(range(len(blocks)), key=lambda m: (-block_scores[m], blocks[m][0])):
                if block_scores[b] <= 0:
                    break
                start, end = blocks[b]
                body = [
                    k
                    for k in range(start, end)
                    if k not in keep and k not in hidden and lines[k].strip()
                ]
                cost = sum(tokens[k] for k in body)
                if used + cost <= budget:
                    keep.update(body)
                    used += cost
    for k in sorted(range(n), key=lambda m: (-score[m], m)):
        if k in keep:
            continue
        if k in hidden or not lines[k].strip():
            continue
        if used + tokens[k] > budget:
            continue
        keep.add(k)
        used += tokens[k]
    out, gap = [], 0
    for k, line in enumerate(lines):
        if k in keep:
            if gap:
                out.append(f"... [{gap} lines omitted]")
                gap = 0
            out.append(line)
            if k in collapsed:
                out.append(f"... [{collapsed[k] - 2} similar lines]")
        elif k in hidden:
            continue
        else:
            if line.strip():
                gap += 1
    if gap:
        out.append(f"... [{gap} lines omitted]")
    return "\n".join(out), n, len(keep)
