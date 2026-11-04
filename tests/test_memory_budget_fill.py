"""llmslim.memory read path: selection fills the budget it is given, and never more.

Selection charges the first kept part of a turn what it adds to the context, counted where it meets it
(``Selection.opening_cost``): its label against the first word it opens, the line break after the turn against its
last word, and the gap marks around a partial window. Counted on their own, a label's closing space and a line break
after a full stop were a token each that the rendered context did not use, so a context of short turns came out about
6% under its budget."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest

from llmslim.memory import Memory, _turns
from llmslim.tokens import count_tokens

T0 = datetime(2026, 4, 6, 8, 0, tzinfo=timezone.utc)
WORDS = (
    "plan garden budget trip paris tokyo salary rent python deploy tests database index coffee tea marathon knee "
    "doctor sister wedding thesis deadline review meeting client invoice laptop"
).split()
NAMES = ("Caroline", "Melanie", "Jon", "Gina", "Ravi", "Ana")
CJK = "我喜欢在周末去公园散步并且和朋友一起喝茶聊天讨论最近读过的书"


def clock():
    return T0


def _chat(rng, sessions=40, turns=12):
    """A conversation between two people stored as user and assistant, each turn opening with the speaker's name."""
    memory = Memory(clock=clock)
    for s in range(sessions):
        memory.add(
            [
                {
                    "role": "user" if k % 2 == 0 else "assistant",
                    "content": f"{NAMES[k % 2]}: "
                    + " ".join(rng.choice(WORDS) for _ in range(rng.randint(5, 14))).capitalize()
                    + rng.choice([".", "!", "?"]),
                }
                for k in range(turns)
            ],
            user_id="u",
            run_id=f"s{s}",
            timestamp=T0 + timedelta(days=s),
        )
    return memory


@pytest.mark.parametrize("budget", [300, 1200, 2500])
def test_no_turn_left_out_would_have_fitted_in_the_room_left(budget):
    # Before: 31, 130 and 305 tokens of these budgets were left unused (10-12%), enough for several more turns.
    memory = _chat(random.Random(budget))
    context = memory.search("What did Caroline say about the garden?", user_id="u", budget=budget)
    assert context.compressed and context.tokens == count_tokens(context.text) <= budget
    kept = {turn.item.id for turn in context.turns}
    # A left-out turn would cost at most its block with its full stamp (the line break after it joins its "." / "!").
    cheapest = min(
        count_tokens(f"[{item.created_at:%Y-%m-%d (%a) %H:%M}] {item.role}: {item.content}")
        for item in memory.get_all(user_id="u")
        if item.id not in kept
    )
    assert budget - context.tokens < cheapest


def test_what_selection_charges_is_what_the_context_uses(monkeypatch):
    seen = []
    fit = _turns.fit

    def counted(chosen, budget, prefix, *args):
        out = fit(chosen, budget, prefix, *args)
        seen.append((chosen.used, out[2]))
        return out

    monkeypatch.setattr(_turns, "fit", counted)
    memory = _chat(random.Random(7))
    for budget in (300, 1200, 2500):
        memory.search("What did Melanie say about the wedding?", user_id="u", budget=budget)
    # Every kept turn here is whole: the charges add up to the rendered count, the last line break aside.
    assert seen and all(0 <= used - tokens <= 1 for used, tokens in seen), seen


def _message(rng):
    parts = []
    for _ in range(rng.randint(1, 7)):
        roll = rng.random()
        words = " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 30)))
        if roll < 0.08:
            parts.append(f"## {words.title()}\n{words}.")
        elif roll < 0.15:
            parts.append(f"```python\nprint('{words}')\n```")
        elif roll < 0.19:
            parts.append(f"| a | b |\n|---|---|\n| {words} | 1 |")
        elif roll < 0.23:
            parts.append(CJK * rng.randint(1, 8))
        elif roll < 0.25:
            parts.append("token_" + "x" * rng.randint(50, 900))
        elif roll < 0.30:
            parts.append(f"Always include the {rng.choice(WORDS)} when I ask about {words}.")
        elif roll < 0.34:
            parts.append(f"{rng.randint(1, 2026)} {words}.")
        elif roll < 0.36:
            parts.append("[2026-01-01 (Thu) 09:00] user: a line that looks like a label")
        elif roll < 0.38:
            parts.append("user: a line that looks like a role")
        else:
            name = rng.choice(NAMES)
            end = rng.choice([".", "!", "?", "", " 42.", "..."])
            parts.append(f"{name}: {words.capitalize()}{end}")
    return rng.choice(["\n\n", " ", "\n"]).join(parts)


QUESTIONS = (
    "What did I say about the {w}?",
    "Can you suggest a plan for my {w}?",
    "Summarize what we discussed about {w}.",
    "Have I ever tried {w}?",
    "{w}",
    "我喜欢什么",
)


@pytest.mark.parametrize("seed", range(10))
def test_random_histories_never_exceed_the_budget(seed):
    rng = random.Random(seed)
    memory = Memory(clock=clock, date_format=rng.choice([None, "%Y-%m-%d"]))
    moment = T0
    for k in range(rng.randint(5, 80)):
        moment += timedelta(minutes=rng.choice([0, 0, 1, 30, 1440]))
        role = "user" if k % 2 == 0 else rng.choice(["assistant", "assistant", "tool"])
        memory.add(
            [{"role": role, "content": _message(rng)}],
            user_id="u",
            run_id=rng.choice([None, "s1", f"s{k // 6}"]),
            timestamp=moment,
        )
    for template in QUESTIONS:
        question = template.format(w=rng.choice(WORDS))
        for budget in sorted(rng.sample(range(1, 3000), 6)) + [5000]:
            context = memory.search(question, user_id="u", budget=budget)
            assert context.tokens <= budget, (seed, question, budget)
            assert count_tokens(context.text) == context.tokens, (seed, question, budget)
