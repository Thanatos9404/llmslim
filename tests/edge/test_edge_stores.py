"""Edge cases of the SQLite memory store: concurrent writers, a crash in the middle of a write, read-only files,
odd paths, and text and times that must come back exactly as stored.

Postgres and MongoDB have their own concurrency tests in tests/test_memory_postgres.py and
tests/test_memory_mongo.py (run in CI against real servers). Several processes opening a *new* SQLite file at once
is covered with its fix (tests/test_memory.py); every process test here opens a file that already exists.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import sqlite3
import stat
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from llmslim.memory import InMemoryStore, Memory, MemoryItem, Scope, SQLiteStore, import_history

UTC = timezone.utc
T0 = datetime(2026, 3, 2, 9, 30, tzinfo=UTC)
SPAWN = multiprocessing.get_context("spawn")


def _item(item_id: str, content: str = "x", when: datetime = T0, **fields) -> MemoryItem:
    fields.setdefault("user_id", "u")
    return MemoryItem(id=item_id, role="user", content=content, created_at=when, **fields)


def _new_file(path: Path) -> str:
    SQLiteStore(path).close()
    return str(path)


# --------------------------------------------------------------------------- several writers


def test_threads_writing_and_searching_one_store(tmp_path):
    memory = Memory(str(tmp_path / "threads.db"))
    errors = []

    def write(worker: int) -> None:
        try:
            for k in range(25):
                memory.add(
                    [
                        {"role": "user", "content": f"worker {worker} question {k}"},
                        {"role": "assistant", "content": f"worker {worker} answer {k}"},
                    ],
                    user_id="u",
                    run_id=f"w{worker}",
                )
                memory.search(f"question {k}", user_id="u", budget=200)
        except Exception as error:  # reported below
            errors.append(error)

    threads = [threading.Thread(target=write, args=(w,)) for w in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    items = memory.get_all(user_id="u")
    assert len(items) == 400 and len({item.seq for item in items}) == 400
    for w in range(8):  # each worker's turns keep their order
        mine = [item.content for item in memory.get_all(user_id="u", run_id=f"w{w}")]
        assert mine[:2] == [f"worker {w} question 0", f"worker {w} answer 0"] and len(mine) == 50


def _write_many(path: str, worker: int, count: int, results) -> None:
    try:
        store = SQLiteStore(path)
        for k in range(count):
            store.add([_item(f"p{worker}-{k}", f"process {worker} turn {k}")])
        store.close()
        results.put("ok")
    except Exception as error:  # reported to the test, which fails on it
        results.put(f"{type(error).__name__}: {error}")


def test_processes_writing_one_existing_file_lose_nothing(tmp_path):
    path = _new_file(tmp_path / "shared.db")
    results = SPAWN.Queue()
    workers = [SPAWN.Process(target=_write_many, args=(path, w, 40, results)) for w in range(3)]
    for worker in workers:
        worker.start()
    outcomes = [results.get(timeout=120) for _ in workers]
    for worker in workers:
        worker.join(timeout=60)
    assert outcomes == ["ok"] * 3
    store = SQLiteStore(path)
    items = store.list(Scope("u"))
    store.close()
    assert len(items) == 120 and len({item.seq for item in items}) == 120


def _import_once(source: str, db: str, barrier, results) -> None:
    barrier.wait()
    try:
        report = import_history(source, db, format="jsonl")
        results.put((report.imported, report.duplicates, list(report.errors)))
    except Exception as error:  # reported to the test, which fails on it
        results.put(f"{type(error).__name__}: {error}")


def test_two_imports_of_one_file_at_once_store_each_turn_once(tmp_path):
    source = tmp_path / "h.jsonl"
    source.write_text(
        "".join(
            json.dumps({"role": "user", "content": f"turn {k}", "session_id": f"s{k % 7}"}) + "\n"
            for k in range(1500)
        ),
        encoding="utf-8",
    )
    db = _new_file(tmp_path / "m.db")
    barrier, results = SPAWN.Barrier(2), SPAWN.Queue()
    workers = [
        SPAWN.Process(target=_import_once, args=(str(source), db, barrier, results))
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    outcomes = [results.get(timeout=120) for _ in workers]
    for worker in workers:
        worker.join(timeout=60)
    assert all(isinstance(outcome, tuple) for outcome in outcomes), outcomes
    assert sum(imported for imported, _, _ in outcomes) == 1500
    assert sum(duplicates for _, duplicates, _ in outcomes) == 1500
    assert all(errors == [] for _, _, errors in outcomes)
    assert len(Memory(db).get_all(user_id="default")) == 1500


# --------------------------------------------------------------------------- a crash in the middle of a write


def _write_batches(path: str, progress) -> None:
    store = SQLiteStore(path)
    for batch in range(10_000):
        store.add([_item(f"b{batch}-{k}", "y" * 200) for k in range(100)])
        progress.put(batch)


def test_a_process_killed_while_writing_leaves_only_whole_batches(tmp_path):
    path = _new_file(tmp_path / "crash.db")
    progress = SPAWN.Queue()
    writer = SPAWN.Process(target=_write_batches, args=(path, progress))
    writer.start()
    for _ in range(3):
        progress.get(timeout=120)
    writer.terminate()  # a hard kill on Windows, SIGTERM elsewhere: mid-transaction either way
    writer.join(timeout=60)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    store = SQLiteStore(path)  # reopens, replaying or discarding the write-ahead log
    count = len(store.list(Scope("u")))
    store.add([_item("after-the-crash")])
    store.close()
    assert count >= 300 and count % 100 == 0


@pytest.mark.parametrize(
    "bad",
    [
        _item("i2", "an id already in the batch"),
        _item("lone", "x\ud800"),
        _item("future", when=datetime(9999, 12, 31, 23, tzinfo=timezone(timedelta(hours=-2)))),
        _item("meta", metadata={"when": datetime(2026, 1, 1)}),
    ],
    ids=["duplicate-id", "lone-surrogate", "no-utc-time", "metadata-not-json"],
)
def test_a_batch_that_fails_partway_stores_nothing(tmp_path, bad):
    store = SQLiteStore(tmp_path / "batch.db")
    batch = [_item(f"i{k}") for k in range(5)]
    with pytest.raises((sqlite3.Error, UnicodeEncodeError, OverflowError, TypeError, ValueError)):
        store.add([*batch[:3], bad, *batch[3:]])
    assert store.list(Scope("u")) == []
    store.add(batch)  # and the store still works
    assert [item.id for item in store.list(Scope("u"))] == [f"i{k}" for k in range(5)]
    store.close()


# --------------------------------------------------------------------------- the file itself


def test_a_read_only_file_can_be_searched_but_not_written(tmp_path):
    path = tmp_path / "ro.db"
    memory = Memory(str(path))
    memory.add("I moved to Pune.", user_id="u", timestamp=T0)
    memory.store.close()
    os.chmod(path, stat.S_IREAD)
    try:
        if os.access(path, os.W_OK):
            pytest.skip("this user can write read-only files (root)")
        reader = Memory(str(path))
        assert "Pune" in reader.search("Where did I move?", user_id="u").text
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.add("more", user_id="u")
        assert len(reader.get_all(user_id="u")) == 1
        reader.store.close()
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


@pytest.mark.parametrize(
    "name",
    ["with space/mem ory.db", "ünïcödé/日本語 記憶.db", "hash #1/per%20cent.db"],
)
def test_odd_paths_open_store_and_reopen(tmp_path, name):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    first = Memory(str(path))
    (stored,) = first.add("kept", user_id="u", timestamp=T0)
    first.store.close()
    again = Memory(path)
    assert again.get(stored.id).content == "kept"
    again.store.close()


def test_scope_values_and_ids_are_data_not_sql(tmp_path):
    store = SQLiteStore(tmp_path / "sql.db")
    odd = ["'; DROP TABLE llmslim_memory; --", "%", "_", "a\x00b", "ü" * 300, '"quoted"']
    for k, value in enumerate(odd):
        store.add([_item(value, f"turn {k}", user_id=value, run_id=value)])
    for value in odd:
        assert [item.id for item in store.list(Scope(value))] == [value]
        assert store.get(value).user_id == value
    assert store.delete_scope(Scope("%")) == 1 and store.delete_scope(Scope("_")) == 1
    assert len(store.list(Scope(agent_id=None, user_id=odd[0]))) == 1
    store.close()


# --------------------------------------------------------------------------- what comes back


_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=200)


@settings(
    max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    contents=st.lists(_TEXT, min_size=1, max_size=5),
    metadata=st.dictionaries(_TEXT, st.one_of(_TEXT, st.integers(), st.booleans(), st.none())),
)
def test_text_and_metadata_come_back_exactly(tmp_path_factory, contents, metadata):
    path = tmp_path_factory.mktemp("roundtrip") / "m.db"
    store = SQLiteStore(path)
    store.add([_item(f"t{k}", text, metadata=metadata) for k, text in enumerate(contents)])
    store.close()
    store = SQLiteStore(path)
    back = store.list(Scope("u"))
    store.close()
    assert [item.content for item in back] == contents
    assert all(dict(item.metadata) == metadata for item in back)


def test_a_megabyte_turn_with_mixed_newlines_comes_back_exactly(tmp_path):
    text = ("line one\r\nline two\rline three\n" + "x" * 1000 + "\u2028") * 1000
    memory = Memory(str(tmp_path / "big.db"))
    (stored,) = memory.add(text, user_id="u", timestamp=T0)
    assert memory.get(stored.id).content == text
    context = memory.search("line three", user_id="u", budget=100)
    assert 0 < context.tokens <= 100


_OFFSETS = st.sampled_from(
    [0, 330, -300, 345, -720, 840, 59, -1]
)  # minutes, India and Nepal included
_MOMENTS = st.builds(
    lambda base, micro, offset: (base + timedelta(microseconds=micro)).replace(
        tzinfo=timezone(timedelta(minutes=offset))
    ),
    st.datetimes(min_value=datetime(1900, 1, 2), max_value=datetime(2200, 1, 1)),
    st.sampled_from([0, 1, 500000, 999999]),
    _OFFSETS,
)


@settings(
    max_examples=80, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    moments=st.lists(_MOMENTS, min_size=1, max_size=8),
    since=st.one_of(st.none(), _MOMENTS),
    until=st.one_of(st.none(), _MOMENTS),
)
def test_sqlite_orders_and_windows_times_as_the_in_memory_store_does(
    tmp_path_factory, moments, since, until
):
    # SQLite compares times as UTC ISO-8601 text, with and without microseconds, before 1970 and after 2038.
    sqlite = SQLiteStore(tmp_path_factory.mktemp("times") / "m.db")
    reference = InMemoryStore()
    items = [_item(f"t{k}", when=moment) for k, moment in enumerate(moments)]
    sqlite.add(items)
    reference.add(items)
    window = {"since": since, "until": until}
    got = [(item.id, item.created_at) for item in sqlite.list(Scope("u"), **window)]
    want = [(item.id, item.created_at) for item in reference.list(Scope("u"), **window)]
    sqlite.close()
    assert got == want
