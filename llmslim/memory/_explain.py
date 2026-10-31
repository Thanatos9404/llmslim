"""The explanation of a ``Memory.search(..., explain=True)`` call, built from what each step of the search recorded.

Nothing here decides anything: selection records its decisions as it makes them (``SectionTrace`` for the sections,
``_turns.Trace`` for the turns), and :meth:`SearchTrace.explain` reads them back against the text the search returned.
The tokens of each block are counted on the returned text itself, with the line break after the block, so with
tiktoken they add up to the context's token count exactly: a line break followed by a block's first character (``[``,
``-`` or a letter) always ends one of tiktoken's pre-tokens, so no token spans two blocks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..tokens import count_tokens
from . import _turns
from ._types import (
    ExplainedCandidate,
    ExplainedSection,
    ExplainedTurn,
    MemoryContext,
    MemoryItem,
    SearchExplanation,
)

Owner = Tuple[
    Any, ...
]  # what a stretch of the text belongs to: ("turn", id), ("header", name), ("line", name, k)

# A turn kept in part: the most telling reason among its candidates' (the others follow from it).
_CLIP_REASONS = ("cut_at_fit", "last_resort", "user_turn_cap")
_CLIPPED = frozenset(_CLIP_REASONS)


class SectionTrace:
    """What a section (standing requests, preferences or conflicts) decided about each statement it weighed.

    ``outcome`` maps a candidate's index to the reason it was left out; a candidate with none that is not in
    ``picked`` was never reached, because the section already had its most statements (``"limit"``)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.reason: Optional[str] = None  # why the section is not shown
        self.header = ""
        self.cap = 0
        self.candidates: Sequence[Tuple[MemoryItem, str]] = ()
        self.tokens: List[int] = []
        self.scores: List[float] = []
        self.order: List[int] = []
        self.outcome: Dict[int, str] = {}
        self.sides: Dict[int, str] = {}
        self.picked: List[Tuple[int, str]] = []  # (candidate, line) in the order they were taken
        self.skipped: List[Tuple[MemoryItem, str]] = []  # preferences: turns shown as requests

    def ranked(
        self,
        header: str,
        candidates: Sequence[Tuple[MemoryItem, str]],
        tokens: List[int],
        scores: Sequence[float],
        order: List[int],
        cap: int,
    ) -> None:
        self.header, self.candidates, self.tokens = header, candidates, tokens
        self.scores, self.order, self.cap = [float(s) for s in scores], order, cap

    def dismiss(self, ks: Sequence[int], reason: str, section: bool = False) -> None:
        """Leave out the candidates ``ks`` for ``reason`` (and the whole section, with ``section``)."""
        for k in ks:
            self.outcome[k] = reason
        if section:
            self.reason = reason

    def shown(self) -> List[Tuple[int, str]]:
        """The picked statements in the order the section shows them (date order, as ``Memory._section`` sorts
        them), or none when the section was not shown."""
        if self.reason is not None:
            return []
        when = {
            k: (self.candidates[k][0].created_at, self.candidates[k][0].seq) for k, _ in self.picked
        }
        return sorted(self.picked, key=lambda picked: when[picked[0]])

    def parts(self) -> List[int]:
        """Each candidate's position among its turn's statements (a turn's statements are consecutive)."""
        parts: List[int] = []
        last = None
        for item, _ in self.candidates:
            parts.append(parts[-1] + 1 if item.id == last else 0)
            last = item.id
        return parts


class SearchTrace:
    """Everything one search recorded for its explanation."""

    def __init__(self, items: Sequence[MemoryItem]) -> None:
        self.items = items  # the turns in the time window, oldest first
        self.requests = SectionTrace("requests")
        self.preferences = SectionTrace("preferences")
        self.conflicts = SectionTrace("conflicts")
        self.selection = _turns.Trace()
        self.route: Optional[str] = None
        self.mode = "whole_history"
        self.room: Optional[int] = None
        self.units: Optional[Sequence[_turns.Turn]] = None
        self.blocks: List[Tuple[int, int, str, bool]] = []
        self.full = ""  # the text before the last-resort clip

    def selected(
        self,
        route: str,
        mode: str,
        room: int,
        units: Sequence[_turns.Turn],
        chosen: _turns.Selection,
        text: str,
    ) -> None:
        """Record the result of selection: the kept turns' blocks as the text shows them, and that text."""
        self.route, self.mode, self.room, self.units = route, mode, room, units
        self.blocks = chosen.blocks()
        self.full = text

    # ------------------------------------------------------------------ building the explanation

    def explain(
        self,
        context: MemoryContext,
        everything: Sequence[MemoryItem],
        sessions: Sequence[Sequence[MemoryItem]],
        lines: Sequence[Sequence[str]],
    ) -> SearchExplanation:
        """The explanation of ``context``. ``everything`` is every turn of the scope, oldest first: the turns the
        search read and those its time window left out. ``lines`` are the sessions' turns as the whole history
        renders them."""
        budget = context.budget
        sections = (self.requests, self.preferences, self.conflicts)
        groups: List[List[Tuple[Owner, str]]] = []
        if self.units is None:
            for session, rendered in zip(sessions, lines):
                groups.append([(("turn", item.id), line) for item, line in zip(session, rendered)])
            full = context.text
        else:
            for section in sections:
                shown = section.shown()
                if shown:
                    group: List[Tuple[Owner, str]] = [(("header", section.name), section.header)]
                    group.extend((("line", section.name, k), line) for k, line in shown)
                    groups.append(group)
            by_session: Dict[int, List[Tuple[Owner, str]]] = {}
            for session_index, turn, block, _ in self.blocks:
                owner = ("turn", self.units[turn].item.id)
                by_session.setdefault(session_index, []).append((owner, block))
            groups.extend(by_session[s] for s in sorted(by_session))
            full = self.full
        used = _measure(groups, context.text)
        clipped = context.text != full
        turns = self._turns(context, everything, sessions, used)
        explained = tuple(self._section(section, used, budget) for section in sections)
        attributed = sum(t.tokens for t in turns) + sum(s.tokens for s in explained)
        return SearchExplanation(
            mode=self.mode,
            route=self.route,
            budget=budget,
            tokens=context.tokens,
            history_tokens=context.history_tokens,
            room=budget if self.room is None else self.room,
            user_room=self.selection.user_room,
            user_turn_cap=self.selection.user_cap,
            clipped=clipped,
            unattributed_tokens=context.tokens - attributed,
            turns=turns,
            sections=explained,
        )

    def _turns(
        self,
        context: MemoryContext,
        everything: Sequence[MemoryItem],
        sessions: Sequence[Sequence[MemoryItem]],
        used: Dict[Owner, Tuple[int, bool]],
    ) -> Tuple[ExplainedTurn, ...]:
        budget = context.budget
        in_window = {item.id for item in self.items}
        session_of = {item.id: s for s, session in enumerate(sessions) for item in session}
        units = self.units or ()
        unit_of = {unit.item.id: k for k, unit in enumerate(units)}
        partial_of = {units[turn].item.id: partial for _, turn, _, partial in self.blocks}
        candidates = self._candidates()
        out = []
        for item in everything:
            tokens, whole = used.get(("turn", item.id), (0, False))
            if item.id not in in_window:
                status, reason, pool = "dropped", "outside_window", None
                found: List[ExplainedCandidate] = []
            elif self.units is None:
                status, reason, pool = "kept", None, None
                found = []
            else:
                pool = "user" if item.role == "user" else "reply"
                found = candidates.get(unit_of[item.id], [])
                if item.id not in partial_of:
                    status, reason = "dropped", _drop_reason(found)
                elif ("turn", item.id) not in used:  # the last-resort clip left it out
                    status, reason = "dropped", "clipped_at_end"
                    found = [_after_clip(c, "dropped") for c in found]
                elif not whole:  # ... or cut it
                    status, reason = "clipped", "clipped_at_end"
                    found = [_after_clip(c, "clipped") for c in found]
                elif partial_of[item.id]:
                    status, reason = "clipped", _clip_reason(found)
                else:
                    status, reason = "kept", None
            out.append(
                ExplainedTurn(
                    id=item.id,
                    role=item.role,
                    created_at=item.created_at,
                    session=session_of.get(item.id),
                    pool=pool,
                    status=status,
                    reason=reason,
                    tokens=tokens,
                    share=tokens / budget,
                    candidates=tuple(found),
                )
            )
        return tuple(out)

    def _candidates(self) -> Dict[int, List[ExplainedCandidate]]:
        """Every piece selection weighed, by the index of its turn, with its rank in its pool and what became of
        it."""
        trace = self.selection
        units = self.units or ()
        found: Dict[int, List[ExplainedCandidate]] = {}
        for pool, kind, pieces, scored in trace.pools:
            # The order the pool was tried in (``_turns.fill``); an opening set aside for a kept passage was not.
            ranked = [p for p in pieces if trace.outcome.get(id(p)) != "detail_kept"]
            order = sorted(ranked, key=lambda p: (-p.score, p.turn, p.part)) if scored else []
            rank = {id(p): n for n, p in enumerate(order, 1)}
            for piece in pieces:
                outcome = trace.outcome.get(id(piece))
                if outcome == "kept":
                    status, reason = "kept", None
                elif outcome in _CLIPPED:
                    status, reason = "clipped", outcome
                else:  # never tried: the budget, or the pool's share, was full first
                    status = "dropped"
                    reason = outcome or ("share_full" if pool == "detail" else "budget_full")
                found.setdefault(piece.turn, []).append(
                    ExplainedCandidate(
                        turn_id=units[piece.turn].item.id,
                        pool=pool,
                        kind=kind,
                        part=piece.part,
                        rank=rank.get(id(piece)),
                        score=float(piece.score) if id(piece) in rank else None,
                        tokens=piece.tokens,
                        status=status,
                        reason=reason,
                    )
                )
        return found

    def _section(
        self, section: SectionTrace, used: Dict[Owner, Tuple[int, bool]], budget: int
    ) -> ExplainedSection:
        name = section.name
        if self.units is None:
            return ExplainedSection(name, False, "history_fits", 0, 0, 0.0)
        displayed = {k for k, _ in section.shown()}
        parts = section.parts()
        candidates = []
        for rank, k in enumerate(section.order, 1):
            item, _ = section.candidates[k]
            owner = ("line", name, k)
            if k not in displayed:
                status, reason = "dropped", section.outcome.get(k, "limit")
            elif owner not in used:
                status, reason = "dropped", "clipped_at_end"
            elif not used[owner][1]:
                status, reason = "clipped", "clipped_at_end"
            else:
                status, reason = "kept", None
            candidates.append(
                ExplainedCandidate(
                    turn_id=item.id,
                    pool=name,
                    kind="statement",
                    part=parts[k],
                    rank=rank,
                    score=section.scores[k],
                    tokens=section.tokens[k],
                    status=status,
                    reason=reason,
                    side=section.sides.get(k),
                )
            )
        for item, said in section.skipped:
            candidates.append(
                ExplainedCandidate(
                    turn_id=item.id,
                    pool=name,
                    kind="statement",
                    part=0,
                    rank=None,
                    score=None,
                    tokens=count_tokens(said),
                    status="dropped",
                    reason="shown_as_request",
                )
            )
        owners = [("header", name)] + [("line", name, k) for k in displayed]
        tokens = sum(used[owner][0] for owner in owners if owner in used)
        shown = ("header", name) in used
        reason = section.reason
        if not shown and reason is None:
            reason = "clipped_at_end" if displayed else "nothing_fit"
        return ExplainedSection(
            name=name,
            shown=shown,
            reason=reason,
            cap=section.cap,
            tokens=tokens,
            share=tokens / budget,
            candidates=tuple(candidates),
        )


def _measure(
    groups: Sequence[Sequence[Tuple[Owner, str]]], text: str
) -> Dict[Owner, Tuple[int, bool]]:
    """The tokens of ``text`` each owner's stretch takes, with the line break after it, and whether all of the
    stretch is there. ``groups`` are the blocks of the text before any last-resort clip (blocks one line break
    apart, groups a blank line apart), of which ``text`` is a prefix; a block the clip removed has no entry."""
    flat: List[Tuple[Owner, str, str]] = []
    nonempty = [group for group in groups if group]
    for g, group in enumerate(nonempty):
        for b, (owner, block) in enumerate(group):
            if b < len(group) - 1:
                after = "\n"
            else:
                after = "\n\n" if g < len(nonempty) - 1 else ""
            flat.append((owner, block, after))
    used: Dict[Owner, Tuple[int, bool]] = {}
    size = len(text)
    at = 0
    for owner, block, after in flat:
        start, end, stop = at, at + len(block), at + len(block) + len(after)
        at = stop
        if start >= size:
            break
        used[owner] = (count_tokens(text[start : min(stop, size)]), end <= size)
    return used


def _after_clip(candidate: ExplainedCandidate, status: str) -> ExplainedCandidate:
    """A candidate of a turn the last-resort clip cut (``status`` "clipped") or removed ("dropped")."""
    if candidate.status == "dropped":
        return candidate
    return ExplainedCandidate(
        turn_id=candidate.turn_id,
        pool=candidate.pool,
        kind=candidate.kind,
        part=candidate.part,
        rank=candidate.rank,
        score=candidate.score,
        tokens=candidate.tokens,
        status=status,
        reason="clipped_at_end",
        side=candidate.side,
    )


def _clip_reason(candidates: Sequence[ExplainedCandidate]) -> str:
    """Why a turn shows only in part: a candidate cut to fit, a long user turn's excerpt, a summary's opening, or
    (a reply) some of its windows left out."""
    reasons = {c.reason for c in candidates if c.status == "clipped"}
    for reason in _CLIP_REASONS:
        if reason in reasons:
            return reason
    if any(c.kind == "opening" and c.status == "kept" for c in candidates):
        return "opening"
    return "windows"


def _drop_reason(candidates: Sequence[ExplainedCandidate]) -> str:
    """Why a turn is not in the text: dropped when the exact count ran over, else its best-ranked candidate's
    reason."""
    if not candidates:
        return "no_candidate"
    if any(c.reason == "dropped_at_fit" for c in candidates):
        return "dropped_at_fit"
    best = min(candidates, key=lambda c: (c.rank is None, c.rank or 0, c.part))
    return best.reason or "budget_full"
