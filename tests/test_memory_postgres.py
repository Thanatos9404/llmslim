"""PostgresStore: the same MemoryStore contract on Postgres, plus what only a shared database has (several processes,
pools, time zones). Needs LLMSLIM_TEST_POSTGRES_URL (CI starts a Postgres service); the URL-free parts run anywhere
psycopg is installed."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

psycopg = pytest.importorskip("psycopg")

from llmslim.memory import Memory, MemoryItem, PostgresStore, Scope  # noqa: E402
from llmslim.memory._core import storage_target  # noqa: E402
from llmslim.memory.postgres import is_postgres_url  # noqa: E402

URL = os.environ.get("LLMSLIM_TEST_POSTGRES_URL")
needs_db = pytest.mark.skipif(
    not URL, reason="set LLMSLIM_TEST_POSTGRES_URL to run against Postgres"
)
T0 = datetime(2026, 3, 2, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def table():
    name = f"llmslim_test_{uuid.uuid4().hex[:12]}"
    yield name
    if URL:
        with psycopg.connect(URL, autocommit=True) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {name}, {name}_meta")


def item(content: str, **fields) -> MemoryItem:
    defaults = {"id": uuid.uuid4().hex, "role": "user", "created_at": T0, "user_id": "u1"}
    return MemoryItem(content=content, **{**defaults, **fields})


def test_url_detection_and_storage_target(tmp_path):
    assert is_postgres_url("postgresql://u@h/db") and is_postgres_url("postgres://u@h/db")
    assert not is_postgres_url("memory.db") and not is_postgres_url(None)
    assert storage_target("postgresql://u:secret@h/db") == "postgresql://u:secret@h/db"
    target = storage_target(str(tmp_path / "nested" / "dir" / "m.db"))
    assert (tmp_path / "nested" / "dir").is_dir() and str(target).endswith("m.db")


@pytest.mark.parametrize("name", ["", "1table", "memory; DROP TABLE x", "a-b", "x" * 60])
def test_table_names_are_checked_before_connecting(name):
    with pytest.raises(ValueError, match="letters, digits and underscores"):
        PostgresStore("postgresql://nobody@127.0.0.1:1/none", table=name)


def test_other_inputs_are_refused():
    with pytest.raises(TypeError):
        PostgresStore(42)


@needs_db
def test_memory_opens_postgres_from_a_url_and_persists(table):
    first = Memory(PostgresStore(URL, table=table))
    first.add("I moved to Pune last month.", user_id="asha", timestamp=T0)
    first.store.close()
    again = PostgresStore(URL, table=table)
    try:
        assert [i.content for i in again.list(Scope(user_id="asha"))] == [
            "I moved to Pune last month."
        ]
    finally:
        again.close()
    via_url = Memory(URL)
    try:
        assert isinstance(via_url.store, PostgresStore) and via_url.store.table == "llmslim_memory"
    finally:
        via_url.store.close()
        with psycopg.connect(URL, autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS llmslim_memory, llmslim_memory_meta")


@needs_db
def test_duplicate_ids_and_a_newer_schema_are_refused(table):
    store = PostgresStore(URL, table=table)
    try:
        first = item("a")
        store.add([first])
        with pytest.raises(ValueError, match="already exists"):
            store.add([item("b"), first])
        assert [i.content for i in store.list(Scope(user_id="u1"))] == [
            "a"
        ]  # the batch rolled back
    finally:
        store.close()
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(f"UPDATE {table}_meta SET value = '99' WHERE key = 'schema_version'")
    with pytest.raises(RuntimeError, match="schema 99"):
        PostgresStore(URL, table=table)


@needs_db
def test_a_pool_or_an_autocommit_connection_can_be_passed_in(table):
    from psycopg_pool import ConnectionPool

    with ConnectionPool(URL, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
        store = PostgresStore(pool, table=table)
        store.add([item("from a pool")])
        store.close()  # leaves the caller's pool open
        assert pool.closed is False
    with psycopg.connect(URL, autocommit=True) as conn:
        store = PostgresStore(conn, table=table)
        assert [i.content for i in store.list(Scope(user_id="u1"))] == ["from a pool"]
    with psycopg.connect(URL) as conn, pytest.raises(ValueError, match="autocommit"):
        PostgresStore(conn, table=table)


@needs_db
def test_times_come_back_in_utc_whatever_the_session_time_zone(table):
    sep = "&" if "?" in URL else "?"
    store = PostgresStore(f"{URL}{sep}options=-c%20TimeZone%3DAsia%2FKolkata", table=table)
    try:
        when = datetime(2026, 3, 2, 23, 45, 12, 345678, tzinfo=timezone(timedelta(hours=-5)))
        store.add([item("late call", created_at=when)])
        (got,) = store.list(Scope(user_id="u1"))
        assert got.created_at == when and got.created_at.tzinfo == timezone.utc
        assert store.list(Scope(user_id="u1"), since=when + timedelta(microseconds=1)) == []
        updated = store.update(got.id, metadata={"tag": "café"})
        assert updated.metadata == {"tag": "café"} and updated.updated_at.tzinfo == timezone.utc
    finally:
        store.close()


@needs_db
def test_concurrent_writers_keep_every_turn_and_one_order(table):
    store = PostgresStore(URL, table=table, max_size=4)
    try:

        def write(worker: int) -> None:
            for n in range(25):
                store.add([item(f"w{worker}-{n}", created_at=T0, run_id="shared")])

        threads = [threading.Thread(target=write, args=(w,)) for w in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stored = store.list(Scope(run_id="shared"))
        assert len(stored) == 200 and len({i.seq for i in stored}) == 200
        assert [i.seq for i in stored] == sorted(i.seq for i in stored)
        for worker in range(8):  # each writer's turns stay in the order it added them
            mine = [
                int(i.content.split("-")[1]) for i in stored if i.content.startswith(f"w{worker}-")
            ]
            assert mine == list(range(25))
    finally:
        store.close()


@needs_db
def test_several_processes_can_create_the_schema_at_once(table):
    errors = []

    def start() -> None:
        try:
            PostgresStore(URL, table=table, max_size=1).close()
        except Exception as error:  # pragma: no cover - the failure being guarded against
            errors.append(error)

    threads = [threading.Thread(target=start) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


@needs_db
def test_the_http_server_runs_on_postgres(table):
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    from llmslim.server import create_app

    store = PostgresStore(URL, table=table)
    try:
        client = TestClient(create_app(Memory(store)))
        client.post(
            "/v1/memories", json={"user_id": "asha", "messages": "I moved to Pune last month."}
        )
        found = client.post(
            "/v1/memories/search", json={"user_id": "asha", "query": "Where did I move to?"}
        ).json()
        assert "Pune" in found["text"]
        assert client.delete("/v1/memories", params={"user_id": "asha"}).json() == {"deleted": 1}
    finally:
        store.close()
