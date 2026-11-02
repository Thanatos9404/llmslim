"""Later statements on the same subject, for :meth:`llmslim.memory.Memory.search` (fixed rules, no model).

A history kept verbatim holds an earlier statement and the later one that corrects it ("I'm allergic to peanuts" ...
"It's not peanuts after all, it's tree nuts"). A question often shares words with the earlier statement only: the
correction says something new about the same subject, in other words. So when a turn ranks among the strongest for
a question, the later exchanges on its subject are brought along with it.

* **Exchange.** A user turn and the turns after it up to the next user turn (the replies to it).
* **Subject.** The terms of a statement that few exchanges of the history use: at most ``SUBJECT_SHARE`` of them,
  or ``SUBJECT_MIN`` when that is more, and never more than one in ``SUBJECT_RATIO`` (so a short history has no
  subject terms until it has enough exchanges to tell them apart). Names, numbers, tools and places are such terms;
  everyday words that many exchanges share say nothing about which ones are on the same subject, and nor do words
  of time and talk ("never", "now", "thanks"; ``NOT_SUBJECT``). A reply's subject includes the user turn it answers,
  so "I'll avoid them" is about what the user said they are allergic to.
* **Later exchanges.** The exchanges after the statement's own that share its subject, the closest first: by the
  rarity of the terms they share (each counts the log of how many exchanges there are per exchange that uses it),
  the latest first among equals. At most ``LATER`` of them; their turns that share a subject term are linked to the
  statement.

Selection ranks a linked turn just below the turn it is linked to, and a section shows it under the statement it
follows. The context is in date order, so the later statement reads after the earlier one.
"""

from __future__ import annotations

import math
from typing import Dict, FrozenSet, Iterable, List, Sequence, Set, Tuple

from ..focus import _cached_terms

SUBJECT_SHARE = 0.02  # a subject term is used by at most this share of the history's exchanges ...
SUBJECT_MIN = 3  # ... or by at most this many, when that is more ...
SUBJECT_RATIO = 10  # ... and by at most one exchange in this many
LATER = 2  # later exchanges linked to one statement
# Words that say when, how often or how sure, or keep a conversation going, never what it is about.
NOT_SUBJECT = frozenset(
    """never always ever now anymore again still already yet instead actually really please thank thanks okay ok
    sure yes yeah got noted though""".split()
)


def exchanges(roles: Sequence[str]) -> List[int]:
    """The exchange of each turn, numbered from 0: a user turn opens one, the turns after it join it."""
    out: List[int] = []
    current = -1
    for role in roles:
        if role == "user" or current < 0:
            current += 1
        out.append(current)
    return out


class Subjects:
    """The terms of each turn, the exchanges they form, and the terms rare enough to name a subject. ``texts`` and
    ``roles`` are the history's turns in date order."""

    def __init__(self, texts: Sequence[str], roles: Sequence[str]):
        self.terms: List[FrozenSet[str]] = [frozenset(_cached_terms(text)) for text in texts]
        self.roles = list(roles)
        self.exchange = exchanges(roles)
        self.members: Dict[int, List[int]] = {}
        for k, e in enumerate(self.exchange):
            self.members.setdefault(e, []).append(k)
        # The exchanges that use each term, in date order.
        self.used: Dict[str, List[int]] = {}
        for e, turns in self.members.items():
            for t in set().union(*(self.terms[k] for k in turns)):
                self.used.setdefault(t, []).append(e)
        count = len(self.members)
        limit = min(max(SUBJECT_MIN, int(count * SUBJECT_SHARE)), count // SUBJECT_RATIO)
        self.weight = {
            t: math.log(count / len(found))
            for t, found in self.used.items()
            if len(found) <= limit and t not in NOT_SUBJECT
        }

    def subject(self, turn: int, text: str = "") -> Set[str]:
        """The rare terms of ``text`` (``turn``'s own text when empty) and, for a reply, of the user turn it
        answers."""
        found = set(_cached_terms(text)) if text else set(self.terms[turn])
        opening = self.members[self.exchange[turn]][0]
        if opening != turn and self.roles[opening] == "user":
            found |= self.terms[opening]
        return {t for t in found if t in self.weight}

    def closest(self, turn: int, subject: Iterable[str]) -> List[Tuple[List[int], Set[str]]]:
        """The ``LATER`` exchanges after ``turn``'s that share most of ``subject`` (see the module docstring), the
        closest first: for each, its turns that share a subject term and the terms they share."""
        own = self.exchange[turn]
        wanted = set(subject)
        closeness: Dict[int, float] = {}
        for t in sorted(
            wanted
        ):  # summed in a fixed order, so ties break the same way in every process
            for e in self.used.get(t, ()):
                if e > own:
                    closeness[e] = closeness.get(e, 0.0) + self.weight[t]
        out = []
        for e in sorted(closeness, key=lambda e: (-closeness[e], -e))[:LATER]:
            linked = [k for k in self.members[e] if self.terms[k] & wanted]
            out.append((linked, {t for k in linked for t in self.terms[k] & wanted}))
        return out

    def later(self, turn: int, subject: Iterable[str]) -> Tuple[List[int], Set[str]]:
        """The turns of ``closest`` in date order, and the subject terms they share."""
        found = self.closest(turn, subject)
        return sorted(k for linked, _ in found for k in linked), set().union(
            *(shared for _, shared in found)
        )
