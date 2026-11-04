"""Edge cases for ``Memory``: invariants over random histories, odd text, and dates and time zones.

The invariants are property tests: for any history, question and budget, ``search`` stays within its budget, gives
the same text every time, keeps no turn twice, returns stored turns as stored, and with ``explain=True`` names every
turn and accounts for every token. They run derandomized, so a CI failure reproduces locally.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from llmslim.memory import InMemoryStore, Memory, SQLiteStore
from llmslim.tokens import count_tokens, get_active_token_counter_name

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

T0 = datetime(2026, 3, 2, 9, 30, tzinfo=timezone.utc)
PROPERTY = settings(
    max_examples=60,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

# Text shapes a stored turn can take: prose in several scripts, code, tables, headings, JSON, odd characters.
SNIPPETS = [
    "I moved to Pune last month and the rent is lower.",
    "```python\ndef run():\n    return 42\n```",
    "| a | b |\n|---|---|\n| 1 | 2 |",
    "## Setup\nInstall the package first.",
    '{"key": "value", "nested": {"a": [1, 2, 3]}}',
    "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466 family emoji \U0001f1ee\U0001f1f3 flag",
    "été café with combining accents",
    "مرحبا بالعالم",  # Arabic
    "שלום עולם",  # Hebrew
    "我搬到了浦那。我喜欢番茄。",  # Chinese
    "मैं पुणे चला गया हूँ।",
    "zero​width‍joiner﻿bom⁠joiner",
    "line one\r\nline two\rline three\nline four",
    "nul\x00byte inside",
    "x" * 2500,
    "word " * 600,
    "I prefer tea over coffee.",
    "Always include the number of team members when I ask about projects.",
    "I have never been to Japan.",
    "I went to Japan last year.",
    "```\nan unterminated fence",
    "~~~\ntilde fence\n~~~",
]
WORDS = "garden tomato salary Pune moved apartment python deploy retry service allergic the a is my".split()
QUERIES = [
    "Where did I move to?",
    "Can you suggest a garden plan?",
    "Summarize what we discussed",
    "Have I ever been to Japan?",
    "In what order did I bring up topics?",
    "我搬到哪里了？",
    "मैं कहाँ गया?",
    "What is it?",
    "python deploy retry",
]
BUDGETS = [1, 2, 3, 5, 8, 13, 30, 60, 100, 250, 600, 2000, 100_000]

# Any character a turn can hold except lone surrogates (refused by every persistent store).
CHARS = st.characters(blacklist_categories=("Cs",))
CONTENT = st.one_of(
    st.sampled_from(SNIPPETS),
    st.lists(st.sampled_from(WORDS), min_size=1, max_size=40).map(lambda ws: " ".join(ws) + "."),
    st.text(CHARS, min_size=1, max_size=300),
    st.lists(st.sampled_from(SNIPPETS), min_size=2, max_size=4).map("\n".join),
)
TURN = st.tuples(
    st.sampled_from(["user", "assistant", "user", "assistant", "system", "tool"]),
    CONTENT,
    st.sampled_from([0, 0, 1, 30, 600, 1439, 1440, 2000]),  # minutes after the turn before
    st.sampled_from([None, None, "r1", "r2"]),
)
HISTORY = st.lists(TURN, min_size=0, max_size=18)
QUERY = st.one_of(st.sampled_from(QUERIES), st.text(CHARS, min_size=1, max_size=40))
BUDGET = st.one_of(st.sampled_from(BUDGETS), st.integers(min_value=1, max_value=3000))


def _fill(memory: Memory, history, uid: str = "u") -> None:
    when = T0
    for role, content, minutes, run_id in history:
        when += timedelta(minutes=minutes)
        memory.add([{"role": role, "content": content}], user_id=uid, run_id=run_id, timestamp=when)


def _check(memory: Memory, query: str, budget: int, uid: str = "u") -> None:
    stored = {item.id: item for item in memory.get_all(user_id=uid)}
    context = memory.search(query, user_id=uid, budget=budget)
    explained = memory.search(query, user_id=uid, budget=budget, explain=True)
    # within budget, and the count is the text's own
    assert context.tokens <= budget
    assert context.tokens == (count_tokens(context.text) if context.text else 0)
    # deterministic, and explaining changes nothing
    assert memory.search(query, user_id=uid, budget=budget).text == context.text
    assert explained.text == context.text and explained.tokens == context.tokens
    assert [t.item.id for t in explained.turns] == [t.item.id for t in context.turns]
    # no turn twice, each one as stored
    ids = [t.item.id for t in context.turns]
    assert len(ids) == len(set(ids))
    for turn in context.turns:
        assert stored[turn.item.id].content == turn.item.content
        assert 0.0 <= turn.score <= 1.0
    for section in (context.requests, context.preferences, context.conflicts):
        assert all(stored[t.item.id].content == t.item.content for t in section)
        assert all(t.item.role == "user" for t in section)
    # the explanation names every stored turn of the scope, oldest first, and accounts for every token
    explanation = explained.explanation
    assert [t.id for t in explanation.turns] == [item.id for item in stored.values()]
    attributed = sum(t.tokens for t in explanation.turns) + sum(
        s.tokens for s in explanation.sections
    )
    assert attributed + explanation.unattributed_tokens == context.tokens
    if get_active_token_counter_name() == "tiktoken":
        assert explanation.unattributed_tokens == 0
    for turn in explanation.turns:
        assert turn.status in ("kept", "clipped", "dropped")
        assert (turn.status == "dropped") == (turn.tokens == 0) or turn.reason == "clipped_at_end"
        assert turn.share == pytest.approx(turn.tokens / budget)
    if context.history_tokens <= budget:  # the whole history fits: every turn, whole
        assert explanation.mode == "whole_history"
        assert context.tokens == context.history_tokens
        assert {t.item.id for t in context.turns} == set(stored)


# ---------------------------------------------------------------- invariants (property tests)


@settings(parent=PROPERTY, max_examples=250)
@given(history=HISTORY, query=QUERY, budget=BUDGET)
def test_search_invariants_over_random_histories(history, query, budget):
    memory = Memory(InMemoryStore())
    _fill(memory, history)
    if not query.strip():
        with pytest.raises(ValueError):
            memory.search(query, user_id="u", budget=budget)
        return
    _check(memory, query, budget)


@settings(max_examples=25, deadline=None, derandomize=True)
@given(history=HISTORY, query=st.sampled_from(QUERIES), budget=st.sampled_from(BUDGETS))
def test_sqlite_and_the_in_memory_store_give_the_same_context(
    tmp_path_factory, history, query, budget
):
    in_memory = Memory(InMemoryStore())
    on_disk = Memory(SQLiteStore(tmp_path_factory.mktemp("db") / "memory.db"))
    _fill(in_memory, history)
    _fill(on_disk, history)
    try:
        a = in_memory.search(query, user_id="u", budget=budget)
        b = on_disk.search(query, user_id="u", budget=budget)
        assert a.text == b.text and a.tokens == b.tokens
        assert [t.item.content for t in a.turns] == [t.item.content for t in b.turns]
    finally:
        on_disk.store.close()


@PROPERTY
@given(
    history=HISTORY,
    query=st.sampled_from(QUERIES),
    budget=st.sampled_from(BUDGETS),
    date_format=st.sampled_from([None, "%Y-%m-%d"]),
    tz=st.sampled_from(["UTC", "Asia/Kolkata", "America/New_York", "Pacific/Kiritimati"]),
)
def test_invariants_hold_with_any_date_format_and_time_zone(
    history, query, budget, date_format, tz
):
    memory = Memory(InMemoryStore(), tz=ZoneInfo(tz), date_format=date_format)
    _fill(memory, history)
    _check(memory, query, budget)


@PROPERTY
@given(
    history=HISTORY,
    query=st.sampled_from(QUERIES),
    budget=st.sampled_from(BUDGETS),
    switches=st.tuples(st.booleans(), st.booleans(), st.booleans()),
    coverage=st.sampled_from(["auto", "always", "never"]),
)
def test_invariants_hold_with_every_section_switch(history, query, budget, switches, coverage):
    standing, preferences, conflicts = switches
    memory = Memory(
        InMemoryStore(),
        standing_requests=standing,
        preferences=preferences,
        conflicts=conflicts,
        coverage=coverage,
    )
    _fill(memory, history)
    _check(memory, query, budget)


@settings(max_examples=30, deadline=None, derandomize=True)
@given(history=HISTORY, budget=st.sampled_from(BUDGETS))
def test_a_time_window_only_narrows_what_is_read(history, budget):
    memory = Memory(InMemoryStore())
    _fill(memory, history)
    since, until = T0 + timedelta(minutes=30), T0 + timedelta(days=2)
    inside = memory.get_all(user_id="u", since=since, until=until)
    assert all(since <= item.created_at < until for item in inside)
    context = memory.search("garden", user_id="u", budget=budget, since=since, until=until)
    assert {t.item.id for t in context.turns} <= {item.id for item in inside}
    explained = memory.search(
        "garden", user_id="u", budget=budget, since=since, until=until, explain=True
    ).explanation
    outside = {t.id for t in explained.turns if t.reason == "outside_window"}
    assert outside == {item.id for item in memory.get_all(user_id="u")} - {i.id for i in inside}


# ---------------------------------------------------------------- shapes of history


def test_empty_memory_and_an_empty_scope():
    memory = Memory()
    memory.add("someone else's turn", user_id="other")
    for budget in (1, 2000):
        context = memory.search("anything", user_id="u", budget=budget, explain=True)
        assert context.text == "" and context.tokens == 0 and context.turns == ()
        assert context.sessions_total == context.sessions_kept == 0 and context.history_tokens == 0
        assert context.explanation.turns == ()
    with pytest.raises(ValueError):
        memory.search("x")  # no scope
    for query in ("", "   ", "\n\t"):
        with pytest.raises(ValueError):
            memory.search(query, user_id="u")
    for budget in (0, -1):
        with pytest.raises(ValueError):
            memory.search("x", user_id="u", budget=budget)


def test_turns_with_no_text_are_not_stored():
    memory = Memory()
    added = memory.add(
        [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "   \n\t"},
            {"role": "assistant", "content": None},
            {"role": "assistant", "content": [{"type": "image_url", "image_url": {"url": "x"}}]},
            {"role": "user", "content": [{"type": "text", "text": "kept"}, {"type": "image"}]},
        ],
        user_id="u",
    )
    assert [item.content for item in added] == ["kept"]
    with pytest.raises(ValueError):
        memory.add([{"role": "narrator", "content": "x"}], user_id="u")
    with pytest.raises(TypeError):
        memory.add([{"role": "user", "content": 42}], user_id="u")


@pytest.mark.parametrize("budget", [1, 2, 3, 5, 8, 20, 100])
def test_a_single_turn_at_any_budget(budget):
    memory = Memory(clock=lambda: T0)
    memory.add("I moved to Pune last month and the rent there is lower than in Delhi.", user_id="u")
    context = memory.search("Where did I move?", user_id="u", budget=budget, explain=True)
    assert context.tokens <= budget
    if context.history_tokens <= budget:
        assert context.text.endswith("lower than in Delhi.")
    for line in context.text.splitlines():
        assert line.startswith("[2026-03-02 (Mon) 09:30] user:") or not line


@pytest.mark.parametrize(
    "content",
    [
        "word " * 40_000,  # one very long turn with spaces
        "我喜欢番茄" * 20_000,  # no space anywhere
        "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466" * 5_000,  # one emoji sequence repeated
        "é" * 30_000,  # a letter and its combining accent
        "\U0001f1ee\U0001f1f3" * 10_000,  # flags: pairs of regional indicators
        "https://example.com/" + "a" * 60_000,  # a long URL
    ],
)
@pytest.mark.parametrize("budget", [12, 40, 300])
def test_a_very_long_single_turn_is_cut_to_the_budget_without_splitting_a_character(
    content, budget
):
    memory = Memory(clock=lambda: T0)
    memory.add(content, user_id="u")
    filler = "I like gardens and tomatoes. " * 200
    memory.add([{"role": "assistant", "content": filler}], user_id="u")
    context = memory.search("tomatoes and gardens", user_id="u", budget=budget)
    assert context.tokens <= budget
    assert context.tokens > 0 or budget < 20  # below a label and a few words, nothing may fit
    for line in context.text.split("\n"):
        body = re.sub(r"^\[[^\]]+\] (?:user|assistant): |^(?:user|assistant): ", "", line)
        body = body.removesuffix(" ...").removesuffix("...")
        for piece in body.split(" ... "):
            piece = piece.strip()
            if not piece:
                continue
            # what is shown of a turn is a stretch of it: no character sequence split, nothing invented
            assert piece in content or piece in filler or piece.replace(" ", "") in content
    # a cut never leaves half a sequence: no dangling joiner, accent or lone regional indicator at the cut
    for cut in re.finditer(r"(.)\s?\.\.\.", context.text):
        assert cut.group(1) not in ("‍", "́")


def test_many_sessions_and_many_identical_turns():
    memory = Memory()
    for k in range(300):  # 300 sessions of one exchange each
        memory.add(
            [
                {"role": "user", "content": f"Day {k}: I watered the tomatoes."},
                {"role": "assistant", "content": "Good. Tomatoes like water in the morning."},
            ],
            user_id="u",
            timestamp=T0 + timedelta(days=k),
        )
    context = memory.search("When did I water the tomatoes?", user_id="u", budget=500, explain=True)
    assert context.sessions_total == 300 and 0 < context.sessions_kept <= 300
    assert context.tokens <= 500
    # the same reply 300 times: near-duplicates are left out, so it shows at most a few times
    assert context.text.count("Tomatoes like water in the morning.") <= 2
    assert any(t.reason == "duplicate" for t in context.explanation.turns)
    assert len({t.item.id for t in context.turns}) == len(context.turns)


def test_identical_turns_at_one_time_keep_the_order_they_were_added_in(tmp_path):
    for store in (InMemoryStore(), SQLiteStore(tmp_path / "m.db")):
        memory = Memory(store)
        for k in range(20):
            memory.add(f"same moment {k}", user_id="u", timestamp=T0)
        memory.add(["again", "again", "again"], user_id="u", timestamp=T0)
        items = memory.get_all(user_id="u")
        assert [i.content for i in items] == [f"same moment {k}" for k in range(20)] + ["again"] * 3
        assert [i.seq for i in items] == sorted(i.seq for i in items)
        text = memory.search("moment", user_id="u", budget=100_000).text
        positions = [text.index(f"same moment {k}\n") for k in range(19)]
        assert positions == sorted(positions) and text.count("] user: again") == 3


# ---------------------------------------------------------------- text edge cases


@pytest.mark.parametrize("snippet", SNIPPETS)
def test_odd_text_is_stored_and_returned_verbatim(tmp_path, snippet):
    for store in (InMemoryStore(), SQLiteStore(tmp_path / "m.db")):
        memory = Memory(store, clock=lambda: T0)
        (item,) = memory.add([{"role": "assistant", "content": snippet}], user_id="u")
        assert item.content == snippet and memory.get(item.id).content == snippet
        context = memory.search("what was said", user_id="u", budget=100_000)
        assert context.text == f"[2026-03-02 (Mon) 09:30] assistant: {snippet}"
        assert [t.item.content for t in context.turns] == [snippet]


def test_lone_surrogates_are_refused_by_sqlite_and_by_time_parsing(tmp_path):
    memory = Memory(SQLiteStore(tmp_path / "m.db"))
    with pytest.raises(UnicodeEncodeError):
        memory.add(["fine", "half an emoji \ud83d"], user_id="u")
    assert memory.get_all(user_id="u") == []  # the batch is stored whole or not at all
    with pytest.raises(ValueError):
        memory.search("x", user_id="u", since="\ud800")
    # a question with one is still a question: no crash, within budget
    memory.add("I like tomatoes", user_id="u")
    assert memory.search("\ud800 tomatoes", user_id="u", budget=5).tokens <= 5


@pytest.mark.parametrize(
    "query",
    [
        "أين انتقلت؟",  # Arabic
        "לאן עברתי?",  # Hebrew
        "我搬到哪里了？",  # Chinese
        "मैं कहाँ गया?",  # Devanagari
        "\U0001f60a\U0001f60a\U0001f60a",  # emoji only
        "​‍﻿",  # zero-width only
        "\x00",
        "What is it?",  # common words only
    ],
)
def test_a_question_in_any_script_stays_within_budget(query):
    memory = Memory()
    _fill(
        memory,
        [("user", s, 60, None) for s in SNIPPETS] + [("assistant", s, 1, "r") for s in SNIPPETS],
    )
    if not query.strip():
        with pytest.raises(ValueError):
            memory.search(query, user_id="u")
        return
    for budget in (5, 60, 400):
        _check(memory, query, budget)


def test_a_question_in_its_own_script_finds_the_turn_written_in_it():
    memory = Memory()
    for day in range(30):
        memory.add(
            [
                {"role": "user", "content": f"Day {day}: what should I cook with lentils?"},
                {"role": "assistant", "content": "Lentils and rice make khichdi. " * 8},
            ],
            user_id="u",
            timestamp=T0 + timedelta(days=day),
        )
    hindi = "मैं पुणे चला गया हूँ।"
    chinese = "我搬到了浦那。"
    memory.add(hindi, user_id="u", timestamp=T0 + timedelta(days=3, hours=1))
    memory.add(chinese, user_id="u", timestamp=T0 + timedelta(days=5, hours=1))
    assert hindi in memory.search("पुणे गया?", user_id="u", budget=150).text
    assert chinese in memory.search("我搬到哪里？", user_id="u", budget=150).text


def test_code_fences_stay_balanced_in_a_selected_context():
    memory = Memory()
    reply = (
        "Run this first:\n```bash\npip install llmslim\n```\nThen this:\n~~~python\nprint('retry')\n~~~\n"
        "And a table:\n| a | b |\n|---|---|\n| 1 | 2 |\n"
        'The config is {"retry": 3, "backoff": "exponential"} in JSON.'
    )
    for day in range(25):
        memory.add(
            [
                {"role": "user", "content": "How do I deploy the retry service?"},
                {"role": "assistant", "content": reply},
            ],
            user_id="u",
            timestamp=T0 + timedelta(days=day),
        )
    memory.add(
        "```\nan unterminated fence from the user", user_id="u", timestamp=T0 + timedelta(days=30)
    )
    for budget in (40, 120, 400, 900):
        text = memory.search("deploy retry service config", user_id="u", budget=budget).text
        for fence in ("```", "~~~"):
            lines = [line for line in text.split("\n") if line.lstrip().startswith(fence)]
            assert len(lines) % 2 == 0, (budget, fence, text)


# ---------------------------------------------------------------- dates and time zones


def _labels(text):
    return re.findall(r"^(?:\[([^\]\n]+)\] )?(user|assistant):", text, re.M)


def _selected(memory, query="tomatoes", budget=120, uid="u"):
    """A search that has to select (the history is padded well past the budget)."""
    context = memory.search(query, user_id=uid, budget=budget)
    assert context.history_tokens > budget
    return context.text


def test_labels_across_a_daylight_saving_change():
    new_york = ZoneInfo("America/New_York")
    memory = Memory(tz=new_york)
    times = [
        "2026-03-08T06:59:00Z",
        "2026-03-08T07:01:00Z",
        "2026-11-01T05:30:00Z",
        "2026-11-01T06:30:00Z",
    ]
    for when in times:
        memory.add(
            f"tomatoes at {when}",
            user_id="u",
            run_id="spring" if "03-08" in when else "fall",
            timestamp=when,
        )
    text = memory.search("tomatoes", user_id="u", budget=100_000).text
    # local times, across the skipped hour in spring and the repeated one in the fall
    assert "[2026-03-08 (Sun) 01:59] user: tomatoes at 2026-03-08T06:59:00Z" in text
    assert "[2026-03-08 (Sun) 03:01] user: tomatoes at 2026-03-08T07:01:00Z" in text
    assert "[2026-11-01 (Sun) 01:30] user: tomatoes at 2026-11-01T05:30:00Z" in text
    assert "[2026-11-01 (Sun) 01:30] user: tomatoes at 2026-11-01T06:30:00Z" in text
    # in the order they happened, though the fall's two local times are the same
    assert text.index("05:30:00Z") < text.index("06:30:00Z")


def test_sessions_without_a_run_are_calendar_days_in_the_memorys_time_zone():
    # 18:00 and 19:00 UTC are one day in UTC, and two (23:30 and 00:30) in India
    for tz, sessions in (
        (timezone.utc, 1),
        (ZoneInfo("Asia/Kolkata"), 2),
        (timezone(timedelta(hours=-5)), 1),
    ):
        memory = Memory(tz=tz)
        memory.add("evening tomatoes", user_id="u", timestamp="2026-03-02T18:00:00Z")
        memory.add("late tomatoes", user_id="u", timestamp="2026-03-02T19:00:00Z")
        assert memory.search("tomatoes", user_id="u").sessions_total == sessions
    # a run is one session wherever its turns fall
    memory = Memory(tz=ZoneInfo("Asia/Kolkata"))
    memory.add("evening tomatoes", user_id="u", run_id="r", timestamp="2026-03-02T18:00:00Z")
    memory.add("late tomatoes", user_id="u", run_id="r", timestamp="2026-03-02T19:00:00Z")
    text = memory.search("tomatoes", user_id="u").text
    assert memory.search("tomatoes", user_id="u").sessions_total == 1
    assert (
        "[2026-03-02 (Mon) 23:30] user: evening" in text
        and "[2026-03-03 (Tue) 00:30] user: late" in text
    )


def _pad(memory, uid="u", days=12):
    for day in range(days):
        memory.add(
            [
                {"role": "user", "content": f"Day {day}: what should I cook with lentils?"},
                {"role": "assistant", "content": "Lentils and rice make khichdi. " * 10},
            ],
            user_id=uid,
            timestamp=T0 - timedelta(days=60 - day),
        )


def test_a_later_turn_at_the_same_time_shows_its_role_alone_and_a_new_time_its_stamp():
    memory = Memory()
    _pad(memory)
    memory.add(
        [
            {"role": "user", "content": "Do tomatoes need sun?"},
            {"role": "assistant", "content": "Tomatoes need sun."},
        ],
        user_id="u",
        run_id="r",
        timestamp=T0,
    )
    memory.add(
        "Thanks, more tomatoes tomorrow.", user_id="u", run_id="r", timestamp=T0 + timedelta(days=1)
    )
    labels = _labels(_selected(memory))
    assert ("2026-03-02 (Mon) 09:30", "user") in labels
    assert ("", "assistant") in labels  # same time as the turn above: the role alone
    assert (
        "2026-03-03 (Tue) 09:30",
        "user",
    ) in labels  # the next day, in the same run: its own stamp
    memory.date_format = "%Y-%m-%d"
    assert ("2026-03-02", "assistant") in _labels(_selected(memory))


@pytest.mark.parametrize(
    "when",
    [
        datetime(2026, 3, 2, 9, 30),  # naive: UTC
        datetime(2026, 3, 2, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 3, 2, 1, 30, tzinfo=ZoneInfo("America/Los_Angeles")),
        1772443800,  # epoch seconds
        1772443800.0,
        "2026-03-02T09:30:00Z",
        "2026-03-02T09:30:00z",
        "2026-03-02T09:30:00+00:00",
        "2026-03-02T15:00:00+05:30",
        "2026-03-02T04:30:00-05:00",
        "2026-03-02 09:30",  # no zone: UTC
        "  2026-03-02T09:30:00Z  ",
    ],
)
def test_every_form_of_a_time_means_the_same_instant(when):
    memory = Memory()
    (item,) = memory.add("tomatoes", user_id="u", timestamp=when)
    assert item.created_at == T0
    assert memory.get_all(user_id="u", since=when, until=T0 + timedelta(seconds=1)) == [item]
    assert memory.get_all(user_id="u", until=when) == []  # until is exclusive
    assert memory.search("tomatoes", user_id="u").text == "[2026-03-02 (Mon) 09:30] user: tomatoes"


@pytest.mark.parametrize(
    ("when", "error"),
    [
        (True, TypeError),  # a bool is not epoch seconds
        ([2026], TypeError),
        ("yesterday", ValueError),
        ("", ValueError),
        ("9999-12-31T23:59:00-01:00", ValueError),  # no UTC time
        ("0001-01-01T00:00:00+01:00", ValueError),
        (float("nan"), ValueError),
        (float("inf"), ValueError),
        (10**30, ValueError),
    ],
)
def test_a_time_that_cannot_be_read_is_refused_before_anything_is_stored(tmp_path, when, error):
    memory = Memory(SQLiteStore(tmp_path / "m.db"))
    with pytest.raises(error):
        memory.add(["one", "two"], user_id="u", timestamp=when)
    with pytest.raises(error):
        memory.add([{"role": "user", "content": "own time", "timestamp": when}], user_id="u")
    assert memory.get_all(user_id="u") == []
    with pytest.raises(error):
        memory.search("x", user_id="u", since=when)


def test_times_far_from_now_are_stored_and_shown(tmp_path):
    for store in (InMemoryStore(), SQLiteStore(tmp_path / "m.db")):
        memory = Memory(store)
        memory.add(
            "the moon landing",
            user_id="u",
            timestamp=datetime(1969, 7, 20, 20, 17, tzinfo=timezone.utc),
        )
        memory.add("the first flight", user_id="u", timestamp=datetime(1903, 12, 17, 15, 35))
        memory.add("far future", user_id="u", timestamp="9999-12-31T23:59:59Z")
        memory.add("just after the epoch", user_id="u", timestamp=1)
        items = memory.get_all(user_id="u")
        assert [i.content for i in items] == [
            "the first flight",
            "the moon landing",
            "just after the epoch",
            "far future",
        ]
        text = memory.search("when", user_id="u", budget=100_000).text
        assert "[1903-12-17 (Thu) 15:35] user: the first flight" in text
        assert "[9999-12-31 (Fri) 23:59] user: far future" in text
        window = memory.get_all(user_id="u", since="1960-01-01", until=0)
        assert [i.content for i in window] == ["the moon landing"]
