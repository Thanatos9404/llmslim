"""Turn-level selection for :meth:`llmslim.memory.Memory.search`, for a history that does not fit its budget.

Every session's units are ranked against the question and share one budget, with the query-focused ranking and
selection that ``compress_documents`` uses across documents, and each session's kept units are rendered in their
original order. That holds however many sessions there are: a history of one session goes through the same
selection, not through single-text compression, which reads ``[date] user: ...`` lines as a log and keeps its newest
lines.

A session with two speakers is segmented from its rendered text exactly as ``compress_documents`` segments a
document (one unit per turn, a question kept with its reply), so its selection is unchanged. A session of one
speaker, such as a day of ``remember`` calls in the ``llmslim mcp`` server, does not read as a transcript there and
would become one paragraph, so its units are built from the stored turns instead: one per turn, a long turn cut into
sentence windows, and a stamp every turn shares shown once as the session's header.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ..focus import Unit, _transcript_units, rank, render, segment, select
from ..rerank import Scorer
from ..tokens import count_tokens

Turn = Tuple[str, str, str]  # (stamp, role, content) of one stored turn, as Memory renders it
_GROUPS = 100_000  # group ids per session, as in focus_documents


@dataclass(frozen=True)
class Ranked:
    """The units of every session at one unit size, with their relevance to the question."""

    units: List[Unit]
    owner: List[int]  # the session each unit belongs to
    scores: List[float]
    sessions: int


def one_speaker(turns: Sequence[Turn]) -> bool:
    """True for a session of two or more turns that all have one role."""
    return len(turns) > 1 and len({role for _, role, _ in turns}) == 1


def turn_units(turns: Sequence[Turn], size: int) -> Tuple[str, List[Tuple[str, str]]]:
    """A session's units built from its turns, as (text, joiner), and its header: the stamp every turn shares, or ""
    when there is none. A turn's own lines are joined with spaces, as in a transcript read from text."""
    lines = []
    for stamp, role, content in turns:
        text = " ".join(part.strip() for part in content.splitlines() if part.strip())
        lines.append((stamp, role, f"[{stamp}] {role}: {text}"))
    header, pieces = _transcript_units(lines, size)
    return header or "", pieces


def rank_turns(
    sessions: Sequence[Sequence[Turn]],
    documents: Sequence[str],
    query: str,
    size: int,
    scorer: Optional[Scorer],
) -> Ranked:
    """Units of about ``size`` tokens for every session (``documents`` holds each one rendered), ranked against
    ``query``. A unit also inherits part of its group's relevance: its session, or a block of it."""
    units: List[Unit] = []
    owner: List[int] = []
    for s, (turns, document) in enumerate(zip(sessions, documents)):
        # Selected within a session, nearly every kept unit is a line of its own, often after a "..." line for the
        # units skipped before it, and ``select`` counts neither: one token per unit pays for that. Two-speaker
        # sessions of a longer history keep the count compress_documents gives them, so their selection is unchanged.
        extra = 1 if one_speaker(turns) or len(sessions) == 1 and len(turns) > 1 else 0
        if one_speaker(turns):
            header, pieces = turn_units(turns, size)
            parts = [(0, text, count_tokens(text), header, joiner) for text, joiner in pieces]
        else:
            parts = [
                (u.group, u.text, u.tokens, u.header, u.joiner) for u in segment(document, size)
            ]
        for group, text, tokens, header, joiner in parts:
            units.append(
                Unit(len(units), s * _GROUPS + group, text, tokens + extra, header, joiner)
            )
            owner.append(s)
    return Ranked(units, owner, rank(units, query, scorer), len(sessions))


def select_turns(ranked: Ranked, query: str, budget: int) -> List[str]:
    """Each session's kept units within ``budget`` tokens, in their original order ("" for a session with none)."""
    kept = select(ranked.units, ranked.scores, budget, query)
    mine: List[Dict[int, str]] = [{} for _ in range(ranked.sessions)]
    for i, text in kept.items():
        mine[ranked.owner[i]][i] = text
    return [render(ranked.units, own) if own else "" for own in mine]
