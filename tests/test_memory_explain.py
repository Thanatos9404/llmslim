"""Memory.search(..., explain=True): why each turn and section was kept, cut or left out.

The histories and searches are in tests/_memory_search_cases.py. Their output with ``explain`` off is pinned in a
golden file recorded before search had an ``explain`` argument, so these tests also prove that leaving it off (or
turning it on) changes nothing else.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import pytest

from llmslim.memory import (
    ExplainedCandidate,
    ExplainedSection,
    ExplainedTurn,
    InMemoryStore,
    Memory,
    SearchExplanation,
    SQLiteStore,
)
from llmslim.tokens import count_tokens, get_active_token_counter_name
from tests import _memory_search_cases as cases

GOLDEN = json.loads(cases.GOLDEN.read_text(encoding="utf-8"))
TIKTOKEN = get_active_token_counter_name() == "tiktoken"
needs_tiktoken = pytest.mark.skipif(
    not TIKTOKEN, reason="the golden output and exact token sums need tiktoken's cl100k_base"
)
CASE_IDS = [case[0] for case in cases.CASES]
CASE = dict(zip(CASE_IDS, cases.CASES))
MEMORY_DOC = (Path(__file__).resolve().parents[1] / "docs" / "MEMORY.md").read_text(
    encoding="utf-8"
)

STATUSES = {"kept", "clipped", "dropped"}
# Every reason the explanation can give, as docs/MEMORY.md lists them.
TURN_REASONS = {
    "outside_window",
    "over_budget",
    "over_share",
    "budget_full",
    "share_full",
    "duplicate",
    "dropped_at_fit",
    "detail_kept",
    "no_candidate",
    "user_turn_cap",
    "windows",
    "opening",
    "last_resort",
    "cut_at_fit",
    "clipped_at_end",
}
STATEMENT_REASONS = {
    "limit",
    "per_side_limit",
    "not_in_pool",
    "no_match",
    "no_disagreement",
    "one_sided",
    "shown_as_request",
    "duplicate",
    "over_share",
    "clipped_at_end",
}
SECTION_REASONS = {
    "history_fits",
    "disabled",
    "route",
    "not_history_check",
    "no_candidates",
    "no_match",
    "no_disagreement",
    "one_sided",
    "nothing_fit",
    "clipped_at_end",
}
# A kept turn's label at the start of a line ("[2026-03-02 (Mon) 09:30] user: " or "[2026-03-02] user: ").
LABEL = re.compile(
    r"^\[\d{4}-\d{2}-\d{2}(?: \(\w{3}\) \d{2}:\d{2})?\] (?:user|assistant|system|tool): ", re.M
)


@pytest.fixture(autouse=True)
def splitter():
    """The golden output was recorded with LLMSlim's own sentence splitter, so every test here uses it."""
    with cases.builtin_splitter():
        yield


def store_for(kind, path):
    return InMemoryStore() if kind == "memory" else SQLiteStore(path)


def explained(name, **extra):
    """The context of case ``name`` with its explanation."""
    context = cases.run(CASE[name], explain=True, **extra)
    assert isinstance(context.explanation, SearchExplanation)
    return context, context.explanation


def by_id(explanation):
    return {turn.id: turn for turn in explanation.turns}


# ---------------------------------------------------------------- explain off: the output is unchanged


def test_every_case_is_pinned():
    assert sorted(GOLDEN) == sorted(CASE_IDS)


@needs_tiktoken
@pytest.mark.parametrize("kind", ["memory", "sqlite"])
@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_search_output_matches_the_golden_file(case, kind, tmp_path):
    expected = GOLDEN[case[0]]
    for extra in ({}, {"explain": False}):
        context = cases.run(case, store_for(kind, tmp_path / f"memory{len(extra)}.db"), **extra)
        assert context.explanation is None
        pinned = cases.pinned(context)
        assert pinned["text"] == expected["text"]
        assert pinned == expected


@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_explain_adds_the_explanation_and_changes_nothing_else(case):
    off = cases.run(case, explain=False)
    on = cases.run(case, explain=True)
    assert off.explanation is None and on.explanation is not None
    assert "explanation" not in off.to_dict() and "explanation=" not in repr(off)
    with_it = cases.output(on)
    assert with_it.pop("explanation") == on.explanation.to_dict()
    assert with_it == cases.output(off)
    assert str(on) == str(off) and on.turns == off.turns
    assert (on.requests, on.preferences, on.conflicts) == (
        off.requests,
        off.preferences,
        off.conflicts,
    )


# ---------------------------------------------------------------- invariants on every case


@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_tokens_and_shares_add_up_to_the_returned_text(case):
    context = cases.run(case, explain=True)
    explanation = context.explanation
    assert explanation.tokens == context.tokens == count_tokens(context.text)
    assert (explanation.budget, explanation.history_tokens) == (
        context.budget,
        context.history_tokens,
    )
    turns = sum(turn.tokens for turn in explanation.turns)
    sections = sum(section.tokens for section in explanation.sections)
    assert turns + sections + explanation.unattributed_tokens == context.tokens
    if TIKTOKEN:
        assert explanation.unattributed_tokens == 0
    shares = [t.share for t in explanation.turns] + [s.share for s in explanation.sections]
    assert sum(shares) == pytest.approx((turns + sections) / context.budget, abs=1e-9)
    for part in (*explanation.turns, *explanation.sections):
        assert part.share == part.tokens / context.budget
    for turn in explanation.turns:
        assert (turn.tokens > 0) == (turn.status != "dropped"), turn


@needs_tiktoken
@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_each_turns_tokens_are_its_block_in_the_text(case):
    """Counted again from the text: the sections above the first turn, then each turn's block up to the next."""
    context = cases.run(case, explain=True)
    explanation = context.explanation
    starts = [m.start() for m in LABEL.finditer(context.text)]
    assert len(starts) == len(context.turns)
    ends = starts[1:] + [len(context.text)]
    blocks = [count_tokens(context.text[a:b]) for a, b in zip(starts, ends)]
    turns = by_id(explanation)
    assert [turns[t.item.id].tokens for t in context.turns] == blocks
    above = count_tokens(context.text[: starts[0]] if starts else context.text)
    assert sum(section.tokens for section in explanation.sections) == above


@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_kept_turns_and_statements_are_the_ones_the_context_lists(case):
    context = cases.run(case, explain=True)
    explanation = context.explanation
    turns = by_id(explanation)
    shown = {
        turn.id: turn.status == "clipped" for turn in explanation.turns if turn.status != "dropped"
    }
    assert shown == {t.item.id: t.partial for t in context.turns}
    for t in context.turns:
        assert turns[t.item.id].session is not None
    for section, recalled in zip(
        explanation.sections, (context.requests, context.preferences, context.conflicts)
    ):
        kept = sorted(c.turn_id for c in section.candidates if c.status != "dropped")
        assert kept == sorted(t.item.id for t in recalled)
        assert section.shown == bool(recalled)
        assert (section.reason is None) == section.shown
        assert (section.tokens > 0) == section.shown


@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_explanation_round_trips_through_json(case):
    context = cases.run(case, explain=True)
    explanation = context.explanation
    text = json.dumps(context.to_dict(), ensure_ascii=False)
    again = SearchExplanation.from_dict(json.loads(text)["explanation"])
    assert again == explanation
    assert again.to_dict() == explanation.to_dict()
    assert json.loads(json.dumps(explanation.to_dict())) == explanation.to_dict()
    for turn in explanation.turns:
        assert ExplainedTurn.from_dict(json.loads(json.dumps(turn.to_dict()))) == turn
    for section in explanation.sections:
        assert ExplainedSection.from_dict(json.loads(json.dumps(section.to_dict()))) == section
        for candidate in section.candidates:
            assert ExplainedCandidate.from_dict(candidate.to_dict()) == candidate


@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_statuses_and_reasons_come_from_the_documented_lists(case):
    explanation = cases.run(case, explain=True).explanation
    assert explanation.mode in {"whole_history", "turns", "digest"}
    assert explanation.route in {None, "lookup", "advice", "overview", "other"}
    assert [s.name for s in explanation.sections] == ["requests", "preferences", "conflicts"]
    for turn in explanation.turns:
        assert turn.status in STATUSES and turn.pool in {None, "user", "reply"}
        assert (turn.reason is None) == (turn.status == "kept"), turn
        assert turn.reason is None or turn.reason in TURN_REASONS
        for candidate in turn.candidates:
            assert candidate.turn_id == turn.id
            assert candidate.status in STATUSES
            assert candidate.pool in {"user", "reply", "detail"}
            assert candidate.kind in {"turn", "window", "opening"}
            assert candidate.reason is None or candidate.reason in TURN_REASONS
            assert (candidate.reason is None) == (candidate.status == "kept")
    for section in explanation.sections:
        assert section.reason is None or section.reason in SECTION_REASONS
        for candidate in section.candidates:
            assert candidate.pool == section.name and candidate.kind == "statement"
            assert candidate.status in STATUSES
            assert candidate.reason is None or candidate.reason in STATEMENT_REASONS
            assert candidate.side in {None, "denies", "affirms"}


def test_every_reason_is_documented():
    for reason in TURN_REASONS | STATEMENT_REASONS | SECTION_REASONS:
        assert f"`{reason}`" in MEMORY_DOC, f"docs/MEMORY.md does not explain the reason {reason!r}"


@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_ranks_follow_the_scores_within_each_pool(case):
    explanation = cases.run(case, explain=True).explanation
    order = {turn.id: k for k, turn in enumerate(explanation.turns)}
    pools = defaultdict(list)
    for turn in explanation.turns:
        for candidate in turn.candidates:
            pools[candidate.pool].append(candidate)
    for section in explanation.sections:
        pools[section.name].extend(section.candidates)
    for pool, candidates in pools.items():
        ranked = sorted((c for c in candidates if c.rank is not None), key=lambda c: c.rank)
        assert [c.rank for c in ranked] == list(range(1, len(ranked) + 1)), pool
        assert all((c.score is None) == (c.rank is None) for c in candidates)
        # Higher scores first; equal scores in date order (sections tie on time, then order of statements).
        for before, after in zip(ranked, ranked[1:]):
            assert before.score >= after.score, pool
            if before.score == after.score and pool in {"user", "reply", "detail"}:
                assert (order[before.turn_id], before.part) < (order[after.turn_id], after.part)


SWEEP = [
    (cases.lentils, "Where did I move to?"),
    (cases.dinner_preferences, "Can you suggest a quick dinner for tonight?"),
    (cases.skydiving, "Have I ever gone skydiving?"),
    (cases.long_thesis, "Summarize my thesis progress"),
    (cases.huge, "How do I configure the cache size?"),
    (cases.chinese, "我的猫叫什么名字？"),
]


@pytest.mark.parametrize("build, question", SWEEP, ids=[b.__name__ for b, _ in SWEEP])
def test_the_invariants_hold_at_every_budget(build, question):
    """From one token up: the explanation always adds up to the text and agrees with the context."""
    memory = build().memory
    for budget in [*range(1, 60), *range(60, 700, 23)]:
        context = memory.search(question, user_id="u1", budget=budget, explain=True)
        explanation = context.explanation
        total = sum(t.tokens for t in explanation.turns) + sum(
            s.tokens for s in explanation.sections
        )
        assert total + explanation.unattributed_tokens == context.tokens <= budget, budget
        if TIKTOKEN:
            assert explanation.unattributed_tokens == 0, budget
        shown = {t.id: t.status == "clipped" for t in explanation.turns if t.status != "dropped"}
        assert shown == {t.item.id: t.partial for t in context.turns}, budget
        for turn in explanation.turns:
            assert (turn.status == "kept") == (turn.reason is None), (budget, turn)


# ---------------------------------------------------------------- the edges


def test_an_empty_memory_explains_an_empty_context():
    context, explanation = explained("empty")
    assert context.text == "" and explanation.turns == ()
    assert (explanation.mode, explanation.route, explanation.tokens) == ("whole_history", None, 0)
    assert [(s.shown, s.reason, s.candidates) for s in explanation.sections] == [
        (False, "history_fits", ())
    ] * 3
    assert explanation.to_dict()["turns"] == []


def test_a_budget_of_zero_is_refused_and_one_token_keeps_nothing():
    memory = cases.lentils().memory
    for explain in (False, True):
        with pytest.raises(ValueError, match="budget"):
            memory.search("Where did I move to?", user_id="u1", budget=0, explain=explain)
    context, explanation = explained("lookup_budget_1")
    assert context.text == "" and context.tokens == 0 and explanation.room == 1
    assert all(t.status == "dropped" and t.tokens == 0 and t.share == 0 for t in explanation.turns)
    reasons = {t.reason for t in explanation.turns}
    assert reasons <= {"budget_full", "over_budget", "over_share", "dropped_at_fit"}
    # The best piece was cut to fit as a last resort, then dropped: not even that fitted one token.
    assert "dropped_at_fit" in reasons
    # A budget of one token with nothing stored is the whole (empty) history.
    assert explained("empty", budget=1)[1].mode == "whole_history"


def test_a_turn_far_larger_than_the_budget():
    context, explanation = explained("huge_user")
    story, reply = explanation.turns
    assert story.status == "clipped" and story.reason == "user_turn_cap"
    (candidate,) = story.candidates
    assert candidate.tokens > context.budget > story.tokens > 0
    assert explanation.user_turn_cap == 120 and "4417" in context.text
    assert reply.reason == "windows" and len(reply.candidates) > 5
    assert {c.status for c in reply.candidates} == {"kept", "dropped"}
    # Smaller budgets: the best piece is cut to fit as a last resort, or cut short by the exact count.
    memory = cases.huge().memory
    question = CASE["huge_user"][2]
    for budget, reason in ((19, "last_resort"), (32, "cut_at_fit")):
        explanation = memory.search(question, user_id="u1", budget=budget, explain=True).explanation
        clipped = [t for t in explanation.turns if t.status == "clipped"]
        assert [t.reason for t in clipped] == [reason]
        assert explanation.tokens <= budget
    dropped = explained("huge_tiny")[1]
    assert {t.reason for t in dropped.turns} == {"dropped_at_fit", "over_budget"}


def test_ties_are_ranked_in_date_order():
    context, explanation = explained("ties")
    meeting = [t for t in explanation.turns if t.id in {"m0001", "m0003", "m0005", "m0007"}]
    scores = {t.candidates[0].score for t in meeting}
    assert len(scores) == 1 and scores.pop() > 0  # the same note, the same score
    assert [t.candidates[0].rank for t in meeting] == [1, 2, 3, 4]  # earliest first
    assert meeting[0].status == "kept" and all(t.status == "dropped" for t in meeting[1:])
    # With room for more, the same note again adds nothing: it is a duplicate.
    roomy = cases.ties().memory.search(CASE["ties"][2], user_id="u1", budget=200, explain=True)
    again = [by_id(roomy.explanation)[i] for i in ("m0003", "m0005", "m0007")]
    assert [(t.status, t.reason) for t in again] == [("dropped", "duplicate")] * 3


def test_duplicate_turns_are_left_out_as_duplicates():
    context, explanation = explained("duplicates")
    turns = by_id(explanation)
    assert turns["m0011"].status == "kept" and "Koregaon Park" in context.text
    assert (turns["m0012"].status, turns["m0012"].reason) == ("dropped", "duplicate")
    # The same words in other case and punctuation is a duplicate too, but this one never got that far: there was
    # no room left for it, and room is checked first.
    assert (turns["m0013"].status, turns["m0013"].reason) == ("dropped", "over_budget")
    assert turns["m0012"].candidates[0].score == turns["m0011"].candidates[0].score


def test_non_latin_questions_are_explained_on_their_letters():
    context, explanation = explained("chinese")
    cat = by_id(explanation)["m0025"]  # "My cat is called Xiaobai", asked in Chinese
    assert cat.status == "kept" and "小白" in context.text
    (candidate,) = cat.candidates
    assert candidate.pool == "user" and candidate.rank == 1 and candidate.score > 0
    # The best match for the Russian question is longer than its 40-token budget can hold with its label: the
    # explanation says so, and with more room it is kept.
    context, explanation = explained("russian")
    best = by_id(explanation)["m0027"]
    assert (best.status, best.reason, best.candidates[0].rank) == ("dropped", "over_budget", 1)
    assert best.candidates[0].score > 0 and "Москве" not in context.text
    roomy = cases.chinese().memory.search(CASE["russian"][2], user_id="u1", budget=80, explain=True)
    assert by_id(roomy.explanation)["m0027"].status == "kept" and "Москве" in roomy.text
    if TIKTOKEN:
        assert explanation.unattributed_tokens == roomy.explanation.unattributed_tokens == 0


def test_turns_outside_the_time_window_are_named():
    context, explanation = explained("window")
    since, until = cases.T0 + timedelta(days=3), cases.T0 + timedelta(days=7)
    assert len(explanation.turns) == 20  # the whole scope, not only the window
    for turn in explanation.turns:
        inside = since <= turn.created_at < until
        assert (turn.reason == "outside_window") == (not inside), turn
        assert (turn.session is None) == (not inside)
        if not inside:
            assert (turn.status, turn.tokens, turn.pool, turn.candidates) == (
                "dropped",
                0,
                None,
                (),
            )
    # until is exclusive: the turns of day 7 are outside
    assert {t.created_at for t in explanation.turns if t.reason == "outside_window"} >= {until}
    whole = explained("window_fits")[1]
    assert whole.mode == "whole_history"
    assert sum(t.status == "kept" for t in whole.turns) == 4
    assert sum(t.reason == "outside_window" for t in whole.turns) == 16


def test_a_turn_stored_between_the_two_reads_is_not_named():
    """With a time window the scope is read twice. A turn stored in the window in between was never a candidate:
    it is not named, and the explanation still matches the context."""
    from llmslim.memory import MemoryItem

    class Busy(InMemoryStore):
        def list(self, scope, *, since=None, until=None):
            if since is None and until is None and self.get("late") is None:
                self.add(
                    [
                        MemoryItem(
                            "late",
                            "user",
                            "Project 5 moved to room 999.",
                            cases.T0 + timedelta(days=5),
                            user_id="u1",
                        )
                    ]
                )
            return super().list(scope, since=since, until=until)

    store = Busy()
    context = cases.run(CASE["window"], store, explain=True)
    ids = [t.id for t in context.explanation.turns]
    assert "late" not in ids and store.get("late") is not None and len(ids) == 20
    assert "room 999" not in context.text


def test_only_the_scopes_turns_are_explained():
    context, explanation = explained("people")
    asha = {item.id for item in cases.people().memory.get_all(user_id="asha")}
    assert {t.id for t in explanation.turns} == asha
    assert {t.session for t in explanation.turns} == set(range(context.sessions_total))
    kept_sessions = {t.session for t in explanation.turns if t.status != "dropped"}
    assert len(kept_sessions) == context.sessions_kept
    run = explained("people_run")[1]
    assert [t.id for t in run.turns] == [
        i.id for i in cases.people().memory.get_all(user_id="asha", run_id="r2")
    ]
    assert run.mode == "whole_history" and all(t.session == 0 for t in run.turns)


def test_conflicting_statements_are_weighed_side_by_side():
    context, explanation = explained("conflicts")
    conflicts = explanation.sections[2]
    assert conflicts.shown and conflicts.cap == int(300 * 0.08)
    first, second, *rest = conflicts.candidates
    assert {(first.side, first.status), (second.side, second.status)} == {
        ("denies", "kept"),
        ("affirms", "kept"),
    }
    assert {c.turn_id for c in (first, second)} == {t.item.id for t in context.conflicts}
    assert all(c.reason == "not_in_pool" and c.side is None for c in rest)
    # On a smaller budget only one side fits, so the section is not shown at all; on a tiny one, neither does.
    memory = cases.skydiving().memory
    one = memory.search("Have I ever gone skydiving?", user_id="u1", budget=200, explain=True)
    section = one.explanation.sections[2]
    assert (section.shown, section.reason, section.tokens) == (False, "one_sided", 0)
    sides = {c.side: c.reason for c in section.candidates[:2]}
    assert sides == {"denies": "one_sided", "affirms": "over_share"}
    small = explained("conflicts_small")[1].sections[2]
    assert (small.shown, small.reason, small.tokens) == (False, "nothing_fit", 0)
    assert [c.reason for c in small.candidates[:2]] == ["over_share", "over_share"]


def test_a_changed_fact_is_not_reconciled_away():
    """Memory keeps both turns of a fact that changed and lets the model see which is newer: no turn is dropped as
    superseded, and the two statements agree (neither denies), so there is no conflicts section."""
    context, explanation = explained("moved")
    turns = by_id(explanation)
    delhi, pune = turns["m0033"], turns["m0035"]
    assert delhi.status == pune.status == "kept"
    conflicts = explanation.sections[2]
    assert (conflicts.shown, conflicts.reason) == (False, "no_disagreement")
    sides = {c.turn_id: c.side for c in conflicts.candidates if c.side}
    assert sides == {"m0033": "affirms", "m0035": "affirms"}
    reasons = {t.reason for t in explanation.turns}
    assert "superseded" not in reasons
    lookup = explained("moved_lookup")[1]
    assert by_id(lookup)["m0035"].status == "kept"


def test_sections_explain_each_statement():
    context, explanation = explained("advice")
    requests, preferences, conflicts = explanation.sections
    assert explanation.route == "advice" and requests.shown and preferences.shown
    assert [c.turn_id for c in requests.candidates if c.status == "kept"] == ["m0053", "m0055"]
    reasons = {c.turn_id: c.reason for c in preferences.candidates}
    assert reasons["m0049"] is None  # kept
    assert reasons["m0057"] == "duplicate"  # the same preference, said again later
    assert reasons["m0053"] == "shown_as_request"  # its turn is already in the requests section
    assert reasons["m0051"] == "over_share"
    assert preferences.cap == 40 and requests.cap == 60
    assert (conflicts.reason, conflicts.cap) == ("route", 0)
    # The room the sections left for turns is what the turns were selected in.
    assert explanation.room == 400 - count_tokens(context.text[: context.text.index("\n\n[") + 2])
    off = explained("advice_sections_off")[1]
    assert [s.reason for s in off.sections] == ["disabled", "disabled", "route"]
    assert off.room == 400 and off.user_room == 220
    lookup = explained("lookup")[1]
    assert [s.reason for s in lookup.sections] == ["route", "route", "not_history_check"]


def test_digests_explain_openings_and_passages():
    context, explanation = explained("summary")
    assert (explanation.mode, explanation.route) == ("digest", "overview")
    system = [t for t in explanation.turns if t.role == "system"]
    assert [(t.status, t.reason) for t in system] == [("dropped", "no_candidate")]
    others = [t for t in explanation.turns if t.role != "system"]
    assert all(t.status == "clipped" and t.reason == "opening" for t in others)
    assert all(c.kind == "opening" and c.rank is not None for t in others for c in t.candidates)
    assert explanation.user_room == int(1200 * 0.3)
    # With room for every opening, none is ranked.
    roomy = cases.thesis().memory.search(
        CASE["summary"][2], user_id="u1", budget=1500, explain=True
    )
    openings = [c for t in roomy.explanation.turns for c in t.candidates]
    assert openings and all(c.rank is None and c.score is None for c in openings)
    assert roomy.explanation.user_room is None and roomy.explanation.mode == "digest"
    small = explained("summary_small")[1]
    assert small.user_room == int(150 * 0.3)
    assert any(c.rank == 1 for t in small.turns for c in t.candidates)
    detail = explained("summary_detail")[1]
    windows = [c for t in detail.turns for c in t.candidates if c.pool == "detail"]
    assert windows and any(c.status == "kept" for c in windows)
    set_aside = [c for t in detail.turns for c in t.candidates if c.reason == "detail_kept"]
    assert set_aside and all(c.kind == "opening" and c.rank is None for c in set_aside)
    ordering = explained("ordering")[1]
    assert ordering.user_room == int(400 * 0.8)


def test_the_last_resort_clip_is_explained(monkeypatch):
    """With every label free during selection and a fit that never drops, the picks run over the budget and search
    clips the text to whole words: the explanation says which blocks the clip cut or removed."""
    import llmslim.memory._turns as turns

    fit = turns.fit
    monkeypatch.setattr(
        turns, "fit", lambda chosen, budget, prefix: fit(chosen, budget * 10, prefix)
    )
    monkeypatch.setattr(turns.Selection, "label_cost", lambda self, turn: 0)
    memory = cases.lentils().memory
    for budget in (15, 40, 90):
        context = memory.search("Where did I move to?", user_id="u1", budget=budget, explain=True)
        explanation = context.explanation
        assert explanation.clipped and context.tokens <= budget
        total = sum(t.tokens for t in explanation.turns) + sum(
            s.tokens for s in explanation.sections
        )
        assert total + explanation.unattributed_tokens == context.tokens
        if TIKTOKEN:
            assert explanation.unattributed_tokens == 0
        cut = [t for t in explanation.turns if t.reason == "clipped_at_end"]
        assert cut and all(t.status in {"clipped", "dropped"} for t in cut)
        assert all(
            c.reason == "clipped_at_end" for t in cut for c in t.candidates if c.status != "dropped"
        )
        # A turn the context lists is in the text; the explanation also counts a block cut to a few words.
        shown = {t.id for t in explanation.turns if t.status != "dropped"}
        assert {t.item.id for t in context.turns} <= shown


def test_the_estimate_counter_reports_what_it_cannot_attribute(monkeypatch):
    """Without tiktoken, tokens are characters over four, rounded, so counting blocks one by one can differ from
    the whole by a few: the difference is reported, not hidden."""
    from llmslim import tokens
    from llmslim.memory import _core, _turns

    monkeypatch.setattr(tokens, "_ENCODER", None)
    monkeypatch.setattr(tokens, "_ENCODER_LOAD_ATTEMPTED", True)
    _turns.tokens_of.cache_clear()
    _core._document_tokens.cache_clear()
    try:
        for name in ("lookup", "advice", "summary_small", "fits"):
            context, explanation = explained(name)
            assert explanation.tokens == context.tokens == count_tokens(context.text)
            total = sum(t.tokens for t in explanation.turns)
            total += sum(s.tokens for s in explanation.sections)
            assert total + explanation.unattributed_tokens == context.tokens
            assert abs(explanation.unattributed_tokens) <= len(explanation.turns) + 3
    finally:
        _turns.tokens_of.cache_clear()
        _core._document_tokens.cache_clear()


def test_explain_with_a_custom_scorer_reports_its_scores():
    context, explanation = explained("custom_scorer")
    soup = {item.id for item in cases.ties().memory.get_all(user_id="u1") if "soup" in item.content}
    for turn in explanation.turns:
        (candidate,) = turn.candidates
        assert candidate.score == (1.0 if turn.id in soup else 0.0)
    (kept,) = [t for t in explanation.turns if t.status == "kept"]
    assert kept.id in soup and kept.candidates[0].rank == 1


def test_a_whole_history_is_kept_whole_and_named_turn_by_turn():
    context, explanation = explained("fits")
    assert explanation.mode == "whole_history" and explanation.route is None
    assert explanation.room == 500 and explanation.user_room is None
    assert [(t.status, t.reason, t.pool, t.candidates) for t in explanation.turns] == [
        ("kept", None, None, ())
    ] * 2
    first, second = explanation.turns
    assert first.tokens == count_tokens(context.text.split("\n")[0] + "\n")
    assert first.tokens + second.tokens == context.tokens


def test_the_explanation_names_turns_not_their_text():
    context, explanation = explained("advice")
    data = json.dumps(explanation.to_dict())
    for turn in context.turns:
        assert turn.item.content not in data
    assert "vegetarian" not in data and "Koregaon" not in json.dumps(
        explained("lookup")[1].to_dict()
    )


def test_memory_search_signature_and_defaults():
    import inspect

    parameter = inspect.signature(Memory.search).parameters["explain"]
    assert parameter.default is False and parameter.kind is inspect.Parameter.KEYWORD_ONLY
