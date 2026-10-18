"""llmslim.memory: verbatim storage, scoped reads, read-time selection, and the Mem0-compatible facade."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from llmslim.memory import InMemoryStore, Memory, MemoryItem, PostgresStore, Scope, SQLiteStore
from llmslim.memory.compat import Mem0Memory
from llmslim.tokens import count_tokens

T0 = datetime(2026, 3, 2, 9, 30, tzinfo=timezone.utc)


def clock():
    return T0


POSTGRES_URL = os.environ.get("LLMSLIM_TEST_POSTGRES_URL")
STORES = ["memory", "sqlite"] + (["postgres"] if POSTGRES_URL else [])


@pytest.fixture
def postgres_table():
    """A fresh table name in the test database, dropped afterwards."""
    psycopg = pytest.importorskip("psycopg")
    table = f"llmslim_test_{uuid.uuid4().hex[:12]}"
    yield table
    with psycopg.connect(POSTGRES_URL, autocommit=True) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {table}, {table}_meta")


@pytest.fixture(params=STORES)
def memory(request, tmp_path):
    if request.param == "memory":
        return Memory(InMemoryStore(), clock=clock)
    if request.param == "sqlite":
        return Memory(SQLiteStore(tmp_path / "memory.db"), clock=clock)
    table = request.getfixturevalue("postgres_table")
    store = PostgresStore(POSTGRES_URL, table=table, max_size=2)
    request.addfinalizer(store.close)
    return Memory(store, clock=clock)


def chat(day: int, user: str, assistant: str):
    when = T0 + timedelta(days=day)
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}], when


# ---------------------------------------------------------------- writing and reading


def test_add_keeps_turns_verbatim_and_in_order(memory):
    items = memory.add(
        [
            {"role": "user", "content": "  I moved to Pune.  "},
            {"role": "assistant", "content": "Noted!"},
        ],
        user_id="u1",
    )
    assert [i.role for i in items] == ["user", "assistant"]
    assert items[0].content == "  I moved to Pune.  "  # verbatim, whitespace included
    assert items[0].seq < items[1].seq
    assert [i.id for i in memory.get_all(user_id="u1")] == [i.id for i in items]


def test_add_accepts_strings_aliases_and_content_parts(memory):
    memory.add("hello there", user_id="u1")
    memory.add(
        {"role": "human", "content": [{"type": "text", "text": "part one"}, {"type": "image_url"}]},
        user_id="u1",
    )
    memory.add(
        [{"role": "ai", "content": "reply"}, {"role": "developer", "content": "rule"}], user_id="u1"
    )
    memory.add(
        [{"role": "assistant", "content": None}, {"role": "user", "content": "   "}], user_id="u1"
    )
    roles = [(i.role, i.content) for i in memory.get_all(user_id="u1")]
    assert roles == [
        ("user", "hello there"),
        ("user", "part one"),
        ("assistant", "reply"),
        ("system", "rule"),
    ]


def test_unknown_role_and_empty_scope_are_refused(memory):
    with pytest.raises(ValueError, match="unknown message role"):
        memory.add({"role": "narrator", "content": "x"}, user_id="u1")
    with pytest.raises(ValueError, match="at least one"):
        memory.add("x")
    with pytest.raises(ValueError, match="at least one"):
        memory.search("x")
    with pytest.raises(ValueError, match="at least one"):
        memory.delete_all()


def test_timestamps_from_datetime_epoch_iso_and_per_message(memory):
    memory.add("naive", user_id="u1", timestamp=datetime(2026, 1, 1, 12, 0))
    memory.add("epoch", user_id="u1", timestamp=0)
    memory.add("iso", user_id="u1", timestamp="2026-02-01T08:00:00Z")
    memory.add(
        [{"role": "user", "content": "own", "timestamp": "2025-12-31T23:00:00+05:30"}], user_id="u1"
    )
    by_text = {i.content: i.created_at for i in memory.get_all(user_id="u1")}
    assert by_text["naive"] == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert by_text["epoch"] == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert by_text["iso"] == datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc)
    assert by_text["own"] == datetime(2025, 12, 31, 17, 30, tzinfo=timezone.utc)


def test_scopes_isolate_users_and_match_as_wildcards(memory):
    memory.add("alice in run a", user_id="alice", run_id="a")
    memory.add("alice in run b", user_id="alice", run_id="b", agent_id="bot")
    memory.add("bob", user_id="bob")
    assert {i.content for i in memory.get_all(user_id="alice")} == {
        "alice in run a",
        "alice in run b",
    }
    assert [i.content for i in memory.get_all(user_id="alice", agent_id="bot")] == [
        "alice in run b"
    ]
    assert [i.content for i in memory.get_all(user_id="bob")] == ["bob"]
    assert "bob" not in memory.search("bob", user_id="alice").text
    assert memory.delete_all(user_id="alice") == 2
    assert memory.get_all(user_id="alice") == [] and len(memory.get_all(user_id="bob")) == 1


def test_get_update_delete(memory):
    (item,) = memory.add("I live in Delhi", user_id="u1", metadata={"source": "chat"})
    assert memory.get(item.id).metadata == {"source": "chat"}
    updated = memory.update(item.id, "I live in Pune", metadata={"source": "fix"})
    assert (
        updated.content == "I live in Pune"
        and updated.metadata == {"source": "fix"}
        and updated.updated_at
    )
    assert memory.update("missing", "x") is None
    with pytest.raises(ValueError):
        memory.update(item.id, "  ")
    assert memory.delete(item.id) is True and memory.delete(item.id) is False
    assert memory.get(item.id) is None


def test_time_window(memory):
    for day in range(5):
        memory.add(f"day {day}", user_id="u1", timestamp=T0 + timedelta(days=day))
    window = memory.get_all(
        user_id="u1", since=T0 + timedelta(days=1), until=T0 + timedelta(days=3)
    )
    assert [i.content for i in window] == ["day 1", "day 2"]
    assert "day 4" not in memory.search("day", user_id="u1", until=T0 + timedelta(days=4)).text


# ---------------------------------------------------------------- search


def test_search_returns_everything_when_the_history_fits(memory):
    messages, when = chat(0, "My dog is called Bruno.", "What a good name!")
    memory.add(messages, user_id="u1", timestamp=when)
    context = memory.search("What is my dog called?", user_id="u1", budget=500)
    assert not context.compressed
    assert (
        context.text
        == "[2026-03-02 (Mon) 09:30] user: My dog is called Bruno.\n[2026-03-02 (Mon) 09:30] assistant: What a good name!"
    )
    assert [t.item.content for t in context.turns] == [
        "My dog is called Bruno.",
        "What a good name!",
    ]
    assert context.sessions_total == context.sessions_kept == 1


def test_search_selects_the_answer_from_a_long_history(memory):
    for day in range(40):
        messages, when = chat(
            day,
            f"Day {day}: can you suggest a recipe with lentils and rice for dinner tonight?",
            f"Day {day}: try a simple khichdi with ghee, cumin and a side of pickle.",
        )
        memory.add(messages, user_id="u1", timestamp=when)
    messages, when = chat(
        41,
        "By the way, I moved to 14 Lane 5, Koregaon Park, Pune last month.",
        "Thanks, I have noted your new address in Koregaon Park.",
    )
    memory.add(messages, user_id="u1", timestamp=when)
    context = memory.search("Where did I move to?", user_id="u1", budget=200)
    assert context.compressed and context.history_tokens > 200
    assert context.tokens <= 200 * 1.02
    assert "Koregaon Park" in context.text
    assert any("Koregaon Park" in t.item.content and not t.partial for t in context.turns)
    assert context.sessions_kept < context.sessions_total
    assert context.tokens == count_tokens(context.text)


def _long_history_with_a_request(memory, request: str, request_day: int = 3):
    for day in range(40):
        messages, when = chat(
            day,
            f"Day {day}: can you suggest a recipe with lentils and rice for dinner tonight?",
            f"Day {day}: try a simple khichdi with ghee, cumin and a side of pickle.",
        )
        memory.add(messages, user_id="u1", timestamp=when)
        if day == request_day:
            messages, when = chat(day, request, "Understood.")
            memory.add(messages, user_id="u1", timestamp=when + timedelta(minutes=5))


def test_standing_requests_come_first_in_their_own_section(memory):
    request = "Always include comparative analysis of multiple solution methods when I ask about triangle area."
    _long_history_with_a_request(memory, request)
    context = memory.search(
        "How do I find the area of a triangle from its medians?", user_id="u1", budget=200
    )
    assert context.compressed
    assert context.text.startswith("Requests the user made earlier:\n- [")
    assert request in context.text.split("\n\n")[0]
    assert [t.item.content for t in context.requests] == [request]
    assert context.tokens <= 200 * 1.02 and context.tokens == count_tokens(context.text)
    assert context.to_dict()["requests"][0]["content"] == request
    off = memory.search(
        "How do I find the area of a triangle from its medians?",
        user_id="u1",
        budget=200,
        standing_requests=False,
    )
    assert off.requests == () and not off.text.startswith("Requests the user made earlier:")


def test_explicit_requests_are_kept_without_a_shared_term(memory):
    _long_history_with_a_request(memory, "Always answer in metric units.")
    asked = "I'd like you to always use bullet points when I ask about recipes."
    told = "Going forward, you should never use cups."
    for day, said in ((6, "I always cook on Sundays."), (8, asked), (9, told)):
        messages, when = chat(day, said, "Noted.")
        memory.add(messages, user_id="u1", timestamp=when + timedelta(minutes=5))
    memory.add(
        [{"role": "assistant", "content": "I will always mention the triangle inequality."}],
        user_id="u1",
        timestamp=T0 + timedelta(days=5),
    )
    context = memory.search("What is the triangle inequality about?", user_id="u1", budget=600)
    # Explicit requests (opening with the directive, addressed to the assistant, or saying when they apply) are kept
    # though they share no term with the question; a passing "always" is not a request; assistant turns never are.
    assert [t.item.content for t in context.requests] == [
        "Always answer in metric units.",
        asked,
        told,
    ]
    assert "Sundays" not in context.text.split("\n\n")[0]


def test_passing_mentions_are_not_requests_even_when_they_match(memory):
    _long_history_with_a_request(memory, "Never use cups for flour in recipes.", request_day=2)
    messages, when = chat(
        9, "I always buy flour and rice in bulk for my recipes because it is cheaper.", "Smart."
    )
    memory.add(messages, user_id="u1", timestamp=when + timedelta(minutes=5))
    context = memory.search(
        "How much flour and rice for the recipes this week?", user_id="u1", budget=2000
    )
    assert [t.item.content for t in context.requests] == ["Never use cups for flour in recipes."]


def test_long_requests_are_cut_short(memory):
    rambling = (
        "Always explain " + " ".join(f"step {k} of the recipe in detail" for k in range(60)) + "."
    )
    _long_history_with_a_request(memory, rambling)
    context = memory.search("How do I make khichdi?", user_id="u1", budget=800)
    line = context.text.split("\n\n")[0].splitlines()[1]
    assert line.endswith(" ...") and count_tokens(line) < 130
    assert context.requests[0].partial


def test_requests_are_ranked_with_the_search_relevance(memory):
    _long_history_with_a_request(memory, "Always answer in metric units.")
    messages, when = chat(7, "Always suggest a vegetarian option.", "Will do.")
    memory.add(messages, user_id="u1", timestamp=when + timedelta(minutes=5))

    def scorer(query, texts):  # stands in for a semantic model: prefers the vegetarian request
        return [1.0 if "vegetarian" in text else 0.0 for text in texts]

    # With a 30-token share only the top request fits; the scorer, not shared words, decides which it is.
    context = memory.search(
        "What should I cook tonight?", user_id="u1", budget=200, relevance=scorer
    )
    assert [t.item.content for t in context.requests] == ["Always suggest a vegetarian option."]


def test_standing_requests_show_only_the_request_sentences_in_date_order(memory):
    _long_history_with_a_request(
        memory,
        "I like cooking. Always use grams for flour in recipes. My oven is small.",
        request_day=2,
    )
    messages, when = chat(10, "From now on, use cups for flour in recipes instead.", "Sure.")
    memory.add(messages, user_id="u1", timestamp=when + timedelta(minutes=5))
    context = memory.search("How much flour for the bread recipe?", user_id="u1", budget=800)
    section = context.text.split("\n\n")[0].splitlines()
    assert section[1].endswith(
        "Always use grams for flour in recipes."
    )  # the request sentence only
    assert section[2].endswith(
        "From now on, use cups for flour in recipes instead."
    )  # the update reads last
    assert context.requests[0].partial and not context.requests[1].partial


def test_no_requests_section_when_the_whole_history_fits(memory):
    messages, when = chat(0, "Always reply in French.", "D'accord.")
    memory.add(messages, user_id="u1", timestamp=when)
    context = memory.search("Reply to this in French please", user_id="u1", budget=1000)
    assert not context.compressed and context.requests == ()


def _thesis_history(memory, days: int = 12):
    chatter = " ".join(
        f"Side note {k}: the weather was mild and the train ran late again." for k in range(12)
    )
    code = "```python\nimport pandas as pd\nflows = pd.read_csv('river.csv')\n```"
    for day in range(days):
        messages, when = chat(
            day,
            f"Day {day}: today I finished chapter {day} of my thesis on river ecology. {code}",
            f"For chapter {day} of your thesis, keep the sediment section short. {code} {chatter}",
        )
        memory.add(messages, user_id="u1", timestamp=when)


def test_overview_questions_are_answered_from_the_opening_of_each_turn(memory):
    _thesis_history(memory)
    for question in (
        "Can you summarize what we discussed about my thesis?",
        "In what order did I finish the chapters of my thesis?",
    ):
        context = memory.search(question, user_id="u1", budget=1200)
        assert context.compressed and context.tokens <= 1200 * 1.02
        # every exchange is there, as the user's request and the start of the reply, without code or later detail
        assert context.text.count("I finished chapter") == 12
        assert context.text.count("keep the sediment section short") == 12
        assert "read_csv" not in context.text and "Side note 11" not in context.text
        assert all(turn.partial for turn in context.turns if turn.item.role == "assistant")
        ranked = memory.search(question, user_id="u1", budget=1200, coverage="never")
        assert "Side note 11" in ranked.text  # relevance ranking spends the budget on whole replies


def test_long_openings_are_cut_short():
    from llmslim.memory._core import _lead

    assert _lead("One two three four five six seven eight nine ten eleven twelve.", 4).endswith(
        " ..."
    )
    assert _lead("Short one. Second sentence here. Third.", 8) == "Short one. Second sentence here."
    assert _lead("```\ncode only\n```", 10) == ""
    # a short opener does not crowd out the sentence that says what the reply is about
    lead = _lead(
        "Of course! Let's create a detailed schedule so you meet the April deadline for the whole MVP.",
        12,
    )
    assert lead.startswith("Of course! Let's create a detailed") and lead.endswith(" ...")


def test_reply_outlines_name_the_points_made():
    from llmslim.memory._core import _outline

    reply = (
        "Here is the plan.\n\n### Key Points\n\n1. **Use SQLAlchemy**: it simplifies queries.\n"
        "2. **Step 2**\n- **`app.py`**: the entry point.\n3. **Use SQLAlchemy**: again.\n"
        "```python\n# Not a heading\n```\n"
    )
    assert _outline(reply, 30) == "Key Points; Use SQLAlchemy"
    assert _outline("No structure at all.", 30) == ""


def test_overviews_carry_each_replys_outline(memory):
    for day in range(30):
        messages, when = chat(
            day,
            f"Day {day}: how should I structure chapter {day} of my thesis?",
            f"Good question. {'Background detail. ' * 40}\n\n1. **Lead with the sediment data**: it is the core.\n"
            f"2. **Keep chapter {day} under ten pages**: examiners skim.",
        )
        memory.add(messages, user_id="u1", timestamp=when)
    context = memory.search(
        "Summarize what we discussed about my thesis chapters", user_id="u1", budget=2500
    )
    assert (
        context.compressed and "Background detail. " * 12 not in context.text
    )  # the reply's body is left out
    assert context.text.count("Outline: Lead with the sediment data; Keep chapter") >= 10


def test_other_questions_are_unchanged_by_coverage(memory):
    _thesis_history(memory)
    question = "Which chapter did I finish on day 7?"
    assert memory.search(question, user_id="u1", budget=400).text == (
        memory.search(question, user_id="u1", budget=400, coverage="never").text
    )
    assert (
        "read_csv" not in memory.search(question, user_id="u1", budget=400, coverage="always").text
    )
    with pytest.raises(ValueError):
        memory.search(question, user_id="u1", coverage="sometimes")
    with pytest.raises(ValueError):
        Memory(coverage="sometimes")


def test_overview_selects_among_openings_when_they_do_not_fit(memory):
    _thesis_history(memory, days=40)
    context = memory.search("Summarize my thesis progress", user_id="u1", budget=150)
    assert 0 < context.tokens <= 150 * 1.02
    assert "read_csv" not in context.text and context.sessions_kept < context.sessions_total


def test_sessions_group_by_run_or_by_day_and_keep_the_date_once(memory):
    memory.add(
        [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
        user_id="u1",
        run_id="r1",
    )
    memory.add("same day, no run", user_id="u1", timestamp=T0 + timedelta(hours=1))
    memory.add("next day, no run", user_id="u1", timestamp=T0 + timedelta(days=1))
    context = memory.search("anything", user_id="u1", budget=1000)
    assert context.sessions_total == 3


def test_search_validates_inputs(memory):
    memory.add("x", user_id="u1")
    with pytest.raises(ValueError):
        memory.search("  ", user_id="u1")
    with pytest.raises(ValueError):
        memory.search("x", user_id="u1", budget=0)
    with pytest.raises(ValueError):
        Memory(budget=0)


def test_empty_scope_search_is_empty(memory):
    context = memory.search("anything", user_id="nobody")
    assert (
        context.text == ""
        and context.turns == ()
        and context.tokens == 0
        and context.sessions_total == 0
    )


def test_search_is_deterministic(memory):
    for day in range(30):
        messages, when = chat(
            day, f"Note {day}: the meeting room for project {day} is room {day + 100}.", "Got it."
        )
        memory.add(messages, user_id="u1", timestamp=when)
    first = memory.search("Which room is project 7 in?", user_id="u1", budget=150)
    second = memory.search("Which room is project 7 in?", user_id="u1", budget=150)
    assert first.text == second.text and "room 107" in first.text


def test_custom_scorer_is_used(memory):
    for day in range(30):
        messages, when = chat(day, f"Fact {day} about topic {day}.", "Okay.")
        memory.add(messages, user_id="u1", timestamp=when)
    calls = []

    def scorer(query, texts):
        calls.append(len(texts))
        return [1.0 if "Fact 3 " in text else 0.0 for text in texts]

    context = memory.search("anything", user_id="u1", budget=60, relevance=scorer)
    assert calls and "Fact 3 " in context.text


def test_context_to_dict_round_trips_turns(memory):
    memory.add("I like tea", user_id="u1")
    data = memory.search("tea", user_id="u1").to_dict()
    assert data["turns"][0]["content"] == "I like tea" and "score" in data["turns"][0]


# ---------------------------------------------------------------- stores


def test_sqlite_store_persists_across_instances(tmp_path):
    path = tmp_path / "m.db"
    first = Memory(path, clock=clock)
    (item,) = first.add("remember me", user_id="u1", metadata={"k": "ü"})
    first.store.close()
    second = Memory(str(path))
    assert second.get(item.id).content == "remember me"
    assert second.get(item.id).metadata == {"k": "ü"}
    second.store.close()


def test_sqlite_store_refuses_a_newer_schema(tmp_path):
    path = tmp_path / "m.db"
    SQLiteStore(path).close()
    conn = sqlite3.connect(path)
    conn.execute("UPDATE llmslim_meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="schema 99"):
        SQLiteStore(path)


def test_in_memory_store_refuses_duplicate_ids():
    store = InMemoryStore()
    item = MemoryItem(id="x", role="user", content="a", created_at=T0, user_id="u1")
    store.add([item])
    with pytest.raises(ValueError):
        store.add([item])


def test_types_validate():
    with pytest.raises(ValueError):
        Scope(user_id="  ")
    with pytest.raises(ValueError):
        MemoryItem(id="x", role="narrator", content="a", created_at=T0)
    with pytest.raises(ValueError):
        MemoryItem(id="x", role="user", content="a", created_at=datetime(2026, 1, 1))


# ---------------------------------------------------------------- Mem0 compatibility


@pytest.fixture
def mem0():
    return Mem0Memory(clock=clock)


def test_mem0_add_and_search_shapes(mem0):
    added = mem0.add(
        [{"role": "user", "content": "I am allergic to peanuts."}], user_id="alice", infer=True
    )
    assert (
        added["results"][0]["event"] == "ADD"
        and added["results"][0]["memory"] == "I am allergic to peanuts."
    )
    found = mem0.search("What am I allergic to?", filters={"user_id": "alice"})
    hit = found["results"][0]
    assert hit["memory"] == "I am allergic to peanuts." and 0 <= hit["score"] <= 1
    assert set(hit) >= {"id", "memory", "score", "metadata", "created_at", "user_id"}
    assert "peanuts" in found["context"]


def test_mem0_search_rules(mem0):
    mem0.add("x", user_id="alice")
    with pytest.raises(ValueError, match="inside filters"):
        mem0.search("x", user_id="alice")
    with pytest.raises(ValueError, match="at least one"):
        mem0.search("x", filters={})
    with pytest.raises(ValueError, match="unsupported"):
        mem0.search("x", filters={"user_id": "alice", "category": "food"})
    with pytest.raises(ValueError):
        mem0.search("x", filters={"user_id": "alice"}, reference_date="2026-01-01")
    with pytest.raises(ValueError):
        mem0.add("x", user_id="alice", expiration_date="2027-01-01")


def test_mem0_top_k_get_all_update_delete_history(mem0):
    for n in range(5):
        mem0.add(f"fact number {n}", user_id="alice", timestamp=T0 + timedelta(minutes=n))
    assert len(mem0.search("fact", filters={"user_id": "alice"}, top_k=2)["results"]) == 2
    everything = mem0.get_all(filters={"user_id": "alice"}, top_k=3)["results"]
    assert [r["memory"] for r in everything] == ["fact number 4", "fact number 3", "fact number 2"]
    memory_id = everything[0]["id"]
    assert mem0.update(memory_id, "fact number four")["message"] == "Memory updated successfully!"
    assert mem0.get(memory_id)["memory"] == "fact number four"
    assert mem0.history(memory_id)[0]["memory"] == "fact number four"
    assert mem0.delete(memory_id)["message"] == "Memory deleted successfully!"
    with pytest.raises(ValueError):
        mem0.delete(memory_id)
    assert mem0.delete_all(user_id="alice")["message"] == "Memories deleted successfully!"
    assert mem0.get_all(filters={"user_id": "alice"})["results"] == []
    with pytest.raises(NotImplementedError):
        mem0.reset()


def test_mem0_from_config_uses_a_sqlite_store(tmp_path):
    memory = Mem0Memory.from_config(
        {"store": str(tmp_path / "m.db"), "llm": {"provider": "ignored"}}
    )
    assert isinstance(memory.memory.store, SQLiteStore)
    memory.memory.store.close()
