"""MongoStore: the same MemoryStore contract on MongoDB, plus what only a shared document database has (several
processes, exact times past BSON's milliseconds, values that MongoDB could read as operators, credentials in URLs).

The tests that need a server run when LLMSLIM_TEST_MONGODB_URL is set (CI starts a MongoDB service and a one-node
replica set); the rest run anywhere pymongo is installed, and the missing-driver test runs without it."""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import threading
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from llmslim.memory import InMemoryStore, Memory, MemoryItem, MongoStore, Scope, SQLiteStore, _core
from llmslim.memory._core import storage_target
from llmslim.memory.mongo import (
    _from_micros,
    _metadata_fields,
    _micros,
    _scrubbed,
    _url_secrets,
    is_mongodb_url,
)

URL = os.environ.get("LLMSLIM_TEST_MONGODB_URL")
needs_pymongo = pytest.mark.skipif(
    __import__("importlib").util.find_spec("pymongo") is None, reason="needs pymongo"
)
needs_db = pytest.mark.skipif(not URL, reason="set LLMSLIM_TEST_MONGODB_URL to run against MongoDB")
T0 = datetime(2026, 3, 2, 9, 30, tzinfo=timezone.utc)
UTC = timezone.utc
# Values a careless store would read as MongoDB operators, paths or JavaScript.
HOSTILE = [
    "$where",
    "$ne",
    "$gt",
    "a.b",
    "$",
    ".",
    '{"$ne": null}',
    "this.user_id == 'x' || true",
    "' || '1'=='1",
    "$regex",
    "__proto__",
]


def clock():
    return T0


def _database(client):
    return client.get_default_database("llmslim")


def _drop(name: str) -> None:
    import pymongo

    with pymongo.MongoClient(URL) as client:
        db = _database(client)
        db.drop_collection(name)
        db.drop_collection(f"{name}_meta")


@pytest.fixture
def collection():
    name = f"llmslim_test_{uuid.uuid4().hex[:12]}"
    yield name
    if URL:
        _drop(name)


@pytest.fixture
def store(collection):
    opened = MongoStore(URL, collection=collection)
    yield opened
    opened.close()


@pytest.fixture
def raw(collection):
    """The test collection itself, through pymongo, to see what the store wrote."""
    import pymongo

    with pymongo.MongoClient(URL, tz_aware=True) as client:
        yield _database(client)[collection]


def item(content: str, **fields) -> MemoryItem:
    defaults = {"id": uuid.uuid4().hex, "role": "user", "created_at": T0, "user_id": "u1"}
    return MemoryItem(content=content, **{**defaults, **fields})


def contents(items):
    return [i.content for i in items]


# ---------------------------------------------------------------- without a server


def test_url_detection_storage_target_and_memory_wiring(monkeypatch):
    assert is_mongodb_url("mongodb://u@h/db") and is_mongodb_url(
        "mongodb+srv://u:p@cluster0.example.net/"
    )
    for value in (
        None,
        "memory.db",
        "MONGODB://h",
        "mongodb:/h",
        "postgresql://h/db",
        b"mongodb://h",
        5,
    ):
        assert not is_mongodb_url(value)
    secret_url = "mongodb://u:secret@h:27017/db"
    assert storage_target(secret_url) == secret_url  # passed through, not turned into a SQLite path
    opened = []
    monkeypatch.setattr(_core, "MongoStore", lambda url: opened.append(url) or InMemoryStore())
    Memory("mongodb+srv://u:p@cluster0.example.net/app")
    assert opened == ["mongodb+srv://u:p@cluster0.example.net/app"]


@needs_pymongo
@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"collection": ""}, "letters, digits and underscores"),
        ({"collection": "1turns"}, "letters, digits and underscores"),
        ({"collection": "turns; db.dropDatabase()"}, "letters, digits and underscores"),
        ({"collection": "a.b"}, "letters, digits and underscores"),
        ({"collection": "$cmd"}, "letters, digits and underscores"),
        ({"collection": "x" * 60}, "letters, digits and underscores"),
        ({"database": ""}, "1 to 63"),
        ({"database": "a.b"}, "1 to 63"),
        ({"database": "a/b"}, "1 to 63"),
        ({"database": "$where"}, "1 to 63"),
        ({"database": "d" * 64}, "1 to 63"),
        ({"database": "admin"}, "authSource=admin"),
        ({"database": "local"}, "of your own"),
        ({"database": "config"}, "of your own"),
    ],
)
def test_names_are_checked_before_connecting(kwargs, message):
    with pytest.raises(ValueError, match=message):
        MongoStore("mongodb://nobody@127.0.0.1:1/?serverSelectionTimeoutMS=1", **kwargs)


@needs_pymongo
def test_the_url_database_is_checked_too():
    # The login database in the URL path would put the memory next to the users; nothing is sent to the server.
    with pytest.raises(ValueError, match="authSource=admin"):
        MongoStore("mongodb://u:pw@127.0.0.1:1/admin?serverSelectionTimeoutMS=1")


@needs_pymongo
def test_other_inputs_are_refused():
    import pymongo

    with pytest.raises(TypeError, match="mongodb:// URL"):
        MongoStore(42)
    with pytest.raises(ValueError, match="must start with mongodb://"):
        MongoStore("postgresql://u@h/db")
    async_client = pymongo.AsyncMongoClient("mongodb://127.0.0.1:1", connect=False)
    with pytest.raises(TypeError):
        MongoStore(async_client)
    client = pymongo.MongoClient("mongodb://127.0.0.1:1", connect=False)
    try:
        with pytest.raises(ValueError, match="not with a Database"):
            MongoStore(client["app"], database="other")
        with pytest.raises(ValueError, match="of your own"):
            MongoStore(client["admin"])
    finally:
        client.close()


def test_a_missing_pymongo_names_the_extra(monkeypatch):
    for module in ("pymongo", "pymongo.database", "bson", "bson.codec_options"):
        monkeypatch.setitem(sys.modules, module, None)
    for open_store in (
        lambda: MongoStore("mongodb://127.0.0.1:1/app"),
        lambda: Memory("mongodb://127.0.0.1:1/app"),
    ):
        with pytest.raises(ImportError, match=r'pip install "llmslim\[mongodb\]"'):
            open_store()


def test_secrets_in_a_url_are_found_as_written_and_decoded():
    assert _url_secrets("mongodb://user:p%40ss%2Fw0rd@h1:27017,h2/db?authSource=admin") == [
        "p%40ss%2Fw0rd",
        "p@ss/w0rd",
    ]
    found = _url_secrets(
        "mongodb+srv://u:pw@cluster0.example.net/app?tlsCertificateKeyFilePassword=k3y%21"
        "&authMechanismProperties=AWS_SESSION_TOKEN:t0ken&appName=shop"
    )
    assert {"pw", "k3y%21", "k3y!", "AWS_SESSION_TOKEN:t0ken"} <= set(found)
    assert "shop" not in found and "u" not in found
    assert _url_secrets("mongodb://127.0.0.1:27017/app") == []


def _secretless(error: BaseException, *secrets: str) -> None:
    """No secret in the error, its arguments or any error chained to it (what a log of the traceback would show)."""
    shown = []
    current: BaseException | None = error
    while current is not None:
        shown += traceback.format_exception_only(type(current), current)
        shown += [repr(current), repr(current.args)]
        current = current.__cause__ or current.__context__
    for secret in secrets:
        assert not any(secret in text for text in shown), secret


@needs_pymongo
def test_driver_errors_that_echo_the_url_lose_its_secrets(monkeypatch):
    import pymongo
    from pymongo.errors import ConfigurationError

    url = "mongodb://shop:hunter%3A2@db.example.com/app?tlsCertificateKeyFilePassword=s3cr3t"

    class EchoingClient:
        def __init__(self, given, **_):
            raise ConfigurationError(f"cannot use {given} (password hunter:2, key s3cr3t)")

    monkeypatch.setattr(pymongo, "MongoClient", EchoingClient)
    with pytest.raises(ConfigurationError) as caught:
        MongoStore(url)
    error = caught.value
    _secretless(error, "hunter%3A2", "hunter:2", "s3cr3t")
    assert "<redacted>" in str(error) and "db.example.com" in str(error)
    assert (
        error.__cause__ is None and error.__context__ is None
    )  # the original message is not chained


def test_an_error_that_cannot_be_rebuilt_becomes_a_runtime_error():
    class Picky(Exception):
        def __init__(self, first, second):
            super().__init__(f"{first} {second}")

    original = Picky("password", "hunter2")
    rebuilt = _scrubbed(original, ["hunter2"])
    assert isinstance(rebuilt, RuntimeError) and "hunter2" not in str(rebuilt)
    plain = ValueError("nothing secret")
    assert (
        _scrubbed(plain, ["hunter2"]) is plain
    )  # nothing to hide: the original error, traceback and all


@needs_pymongo
def test_a_failed_connection_does_not_show_the_password():
    from pymongo.errors import ServerSelectionTimeoutError

    with pytest.raises(ServerSelectionTimeoutError) as caught:
        MongoStore("mongodb://shop:Tr0ub4dor%263@127.0.0.1:1/app?serverSelectionTimeoutMS=50")
    _secretless(caught.value, "Tr0ub4dor%263", "Tr0ub4dor&3")


def test_metadata_is_a_document_unless_mongodb_would_read_its_keys():
    assert _metadata_fields({"source": "chat", "n": 3, "tags": ["a", {"b": None}]}) == {
        "metadata": {"source": "chat", "n": 3, "tags": ["a", {"b": None}]}
    }
    deep: dict = {}
    level = deep
    for _ in range(40):
        level["x"] = {}
        level = level["x"]
    for metadata in (
        {"$where": "sleep(1000)"},
        {"a.b": 1},
        {"outer": {"$ne": None}},
        {"list": [{"$gt": ""}]},
        {"": 1},
        {"nul\x00key": 1},
        {"big": 2**64},
        {"small": -(2**63) - 1},
        deep,
    ):
        stored = _metadata_fields(metadata)
        assert set(stored) == {"metadata_json"}
        assert json.loads(stored["metadata_json"]) == metadata
    assert _metadata_fields({"edge": 2**63 - 1}) == {"metadata": {"edge": 2**63 - 1}}


def test_metadata_holds_what_the_sql_stores_hold(tmp_path):
    # The same JSON data model as SQLiteStore: tuples come back as lists and numeric keys as text.
    assert _metadata_fields({"pair": (1, 2), 7: "seven"}) == {
        "metadata": {"pair": [1, 2], "7": "seven"}
    }
    sqlite = SQLiteStore(tmp_path / "m.db")
    try:
        for bad in ({"when": T0}, {"set": {1, 2}}, {"blob": b"x"}):
            with pytest.raises(TypeError):
                _metadata_fields(bad)
            with pytest.raises(TypeError):
                sqlite.add([item("x", metadata=bad)])
    finally:
        sqlite.close()
    with pytest.raises(TypeError):
        _metadata_fields(["not", "a", "mapping"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "when",
    [
        datetime(1, 1, 1, tzinfo=UTC),
        datetime(9999, 12, 31, 23, 59, 59, 999_999, tzinfo=UTC),
        datetime(1970, 1, 1, tzinfo=UTC),
        datetime(1969, 12, 31, 23, 59, 59, 999_999, tzinfo=UTC),
        datetime(1900, 6, 1, 12, 0, 0, 1, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 3, 2, 23, 45, 12, 345_678, tzinfo=timezone(timedelta(hours=-5))),
    ],
)
def test_times_convert_to_exact_microseconds_and_back(when):
    back = _from_micros(_micros(when, "t"))
    assert back == when and back.tzinfo is UTC


def test_times_that_have_no_utc_value_or_no_zone_are_refused():
    for when in (
        datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=5))),
        datetime(9999, 12, 31, 23, 59, tzinfo=timezone(timedelta(hours=-1))),
    ):
        with pytest.raises(ValueError, match="out of range"):
            _micros(when, "created_at")
    with pytest.raises(ValueError, match="timezone-aware"):
        _micros(datetime(2026, 1, 1), "since")
    with pytest.raises(TypeError, match="datetime"):
        _micros("2026-01-01T00:00:00Z", "since")


# ---------------------------------------------------------------- opening and closing


@needs_db
def test_memory_opens_mongodb_from_a_url_and_persists(collection):
    first = Memory(MongoStore(URL, collection=collection))
    first.add("I moved to Pune last month.", user_id="asha", timestamp=T0)
    first.store.close()
    again = MongoStore(URL, collection=collection)
    try:
        assert contents(again.list(Scope(user_id="asha"))) == ["I moved to Pune last month."]
    finally:
        again.close()
    via_url = Memory(URL)
    try:
        assert isinstance(via_url.store, MongoStore)
        assert via_url.store.collection == "llmslim_memory"
        assert via_url.store.database == _url_database()
        assert repr(via_url.store) == (
            f"MongoStore(database={_url_database()!r}, collection='llmslim_memory')"
        )
    finally:
        via_url.store.close()
        _drop("llmslim_memory")
    explicit = MongoStore(URL, database="llmslim_test_named", collection=collection)
    try:  # database= wins over the URL's database
        explicit.add([item("in the named database")])
        assert explicit.database == "llmslim_test_named"
        assert explicit._turns.database.name == "llmslim_test_named"
    finally:
        explicit.close()
        import pymongo

        with pymongo.MongoClient(URL) as client:
            client.drop_database("llmslim_test_named")


def _url_database() -> str:
    import pymongo

    with pymongo.MongoClient(URL) as client:
        return _database(client).name


@needs_db
def test_a_client_or_a_database_can_be_passed_in(collection):
    import pymongo

    with pymongo.MongoClient(
        URL
    ) as client:  # tz_aware=False: the store still reads aware UTC times
        store = MongoStore(client, collection=collection)
        store.add([item("from a client")])
        store.close()  # leaves the caller's client open
        assert client.admin.command("ping")["ok"] == 1
        store = MongoStore(_database(client), collection=collection)
        (got,) = store.list(Scope(user_id="u1"))
        assert (
            got.content == "from a client" and got.created_at == T0 and got.created_at.tzinfo is UTC
        )
        named = MongoStore(client, database=_database(client).name, collection=collection)
        assert contents(named.list(Scope(user_id="u1"))) == ["from a client"]


@needs_db
def test_wrong_credentials_fail_without_showing_them():
    from pymongo.uri_parser import parse_uri

    host, port = parse_uri(URL)["nodelist"][0]
    url = f"mongodb://llmslim_nobody:N0t-th3-p%40ss@{host}:{port}/llmslim_test?serverSelectionTimeoutMS=5000"
    with pytest.raises(Exception) as caught:
        MongoStore(url, collection="never_created")
    _secretless(caught.value, "N0t-th3-p%40ss", "N0t-th3-p@ss")


@needs_db
def test_duplicate_ids_leave_nothing_behind_and_a_newer_schema_is_refused(store, collection, raw):
    first = item("a")
    store.add([first])
    for batch in (
        [item("b"), first],  # the duplicate comes second: "b" is written, then undone
        [item("c"), item("d"), first, item("e")],
        [item("f", id="same"), item("g", id="same")],  # duplicates within one batch
    ):
        with pytest.raises(ValueError, match="already exists"):
            store.add(batch)
    assert contents(store.list(Scope(user_id="u1"))) == ["a"]
    assert raw.count_documents({}) == 1
    store.add([item("h")])  # the order counter moved on; nothing collides
    assert contents(store.list(Scope(user_id="u1"))) == ["a", "h"]
    raw.database[f"{collection}_meta"].update_one(
        {"_id": "schema_version"}, {"$set": {"value": 99}}
    )
    with pytest.raises(RuntimeError, match="schema 99"):
        MongoStore(URL, collection=collection)


@needs_db
def test_indexes_are_created_once_and_serve_the_reads(store, collection, raw):
    expected = {
        "_id_": [("_id", 1)],
        f"{collection}_user_id": [("user_id", 1), ("created_at_us", 1), ("seq", 1)],
        f"{collection}_agent_id": [("agent_id", 1), ("created_at_us", 1), ("seq", 1)],
        f"{collection}_run_id": [("run_id", 1), ("created_at_us", 1), ("seq", 1)],
        f"{collection}_seq": [("seq", 1)],
    }

    def indexes():
        return {index["name"]: list(index["key"].items()) for index in raw.list_indexes()}

    assert indexes() == expected
    assert raw.index_information()[f"{collection}_seq"]["unique"] is True
    for _ in range(3):
        MongoStore(URL, collection=collection).close()
    assert indexes() == expected
    store.add([item(f"t{n}", created_at=T0 + timedelta(seconds=n % 7)) for n in range(40)])
    plan = json.dumps(
        raw.find({"user_id": {"$eq": "u1"}}).sort([("created_at_us", 1), ("seq", 1)]).explain(),
        default=str,
    )
    assert "IXSCAN" in plan and '"stage": "SORT"' not in plan  # the index gives the order
    # Someone indexed the same keys under another name: reopening is still fine.
    raw.drop_index(f"{collection}_run_id")
    raw.create_index([("run_id", 1), ("created_at_us", 1), ("seq", 1)], name="theirs")
    MongoStore(URL, collection=collection).close()
    # Our name on different keys is not ours: refuse rather than read with the wrong index.
    raw.drop_index(f"{collection}_agent_id")
    raw.create_index([("agent_id", -1)], name=f"{collection}_agent_id")
    from pymongo.errors import OperationFailure

    with pytest.raises(OperationFailure):
        MongoStore(URL, collection=collection)


@needs_db
def test_the_order_counter_is_rebuilt_if_it_is_removed(store, collection, raw):
    store.add([item("one"), item("two")])
    raw.database[f"{collection}_meta"].delete_one({"_id": "seq"})
    store.add([item("three")])  # rebuilt from the stored turns, so no seq is reused
    reopened = MongoStore(URL, collection=collection)
    try:
        raw.database[f"{collection}_meta"].update_one({"_id": "seq"}, {"$set": {"value": 1}})
        MongoStore(URL, collection=collection).close()  # opening raises a counter that fell behind
        reopened.add([item("four")])
        seqs = [i.seq for i in reopened.list(Scope(user_id="u1"))]
        assert contents(reopened.list(Scope(user_id="u1"))) == ["one", "two", "three", "four"]
        assert seqs == sorted(set(seqs))
    finally:
        reopened.close()


# ---------------------------------------------------------------- order and scope


@needs_db
def test_ties_keep_the_order_they_were_added_in(store, tmp_path):
    sqlite = SQLiteStore(tmp_path / "m.db")
    try:
        rng = random.Random(7)
        batches = []
        for n in range(30):
            size = rng.randint(1, 4)
            batches.append(
                [
                    item(
                        f"turn {n}.{k}",
                        created_at=T0 + timedelta(minutes=rng.choice([0, 0, 0, 1, 2])),
                        run_id=rng.choice(["r1", "r2"]),
                    )
                    for k in range(size)
                ]
            )
        for batch in batches:
            store.add(batch)
            sqlite.add(batch)
        for scope in (Scope(user_id="u1"), Scope(run_id="r1"), Scope(user_id="u1", run_id="r2")):
            mongo_order = store.list(scope)
            assert (
                contents(mongo_order)
                == contents(sqlite.list(scope))
                == contents(sorted(mongo_order, key=lambda i: (i.created_at, i.seq)))
            )
            assert [i.seq for i in mongo_order if i.created_at == T0] == sorted(
                i.seq for i in mongo_order if i.created_at == T0
            )
    finally:
        sqlite.close()


@needs_db
def test_turns_a_microsecond_apart_keep_their_order_and_window(store, raw):
    # BSON dates keep milliseconds, so these share one; the exact time decides.
    times = [T0 + timedelta(microseconds=us) for us in (999, 1, 500, 0, 2)]
    store.add([item(f"at {when.microsecond}", created_at=when) for when in times])
    listed = store.list(Scope(user_id="u1"))
    assert contents(listed) == ["at 0", "at 1", "at 2", "at 500", "at 999"]
    assert [i.created_at for i in listed] == sorted(times)
    assert {doc["created_at"] for doc in raw.find()} == {T0}  # what people see in the collection
    middle = T0 + timedelta(microseconds=2)
    assert contents(store.list(Scope(user_id="u1"), since=middle)) == ["at 2", "at 500", "at 999"]
    assert contents(store.list(Scope(user_id="u1"), until=middle)) == ["at 0", "at 1"]
    assert contents(
        store.list(Scope(user_id="u1"), since=middle, until=middle + timedelta(microseconds=1))
    ) == ["at 2"]


@needs_db
def test_times_come_back_exactly_in_utc(store, raw):
    cases = {
        "offset": datetime(2026, 3, 2, 23, 45, 12, 345_678, tzinfo=timezone(timedelta(hours=-5))),
        # One microsecond after "offset", written in another zone.
        "india": datetime(
            2026, 3, 3, 10, 15, 12, 345_679, tzinfo=timezone(timedelta(hours=5, minutes=30))
        ),
        "before 1970": datetime(1969, 7, 20, 20, 17, 40, 123_456, tzinfo=UTC),
        "first": datetime(1, 1, 1, tzinfo=UTC),
        "last": datetime(9999, 12, 31, 23, 59, 59, 999_999, tzinfo=UTC),
    }
    store.add([item(name, created_at=when) for name, when in cases.items()])
    by_name = {i.content: i for i in store.list(Scope(user_id="u1"))}
    for name, when in cases.items():
        got = by_name[name].created_at
        assert got == when and got.tzinfo is UTC, name
    assert contents(store.list(Scope(user_id="u1"))) == [
        "first",
        "before 1970",
        "offset",
        "india",
        "last",
    ]
    when = cases["offset"]
    assert store.list(Scope(user_id="u1"), since=when + timedelta(microseconds=1), until=when) == []
    doc = raw.find_one({"content": "offset"})
    assert (
        doc["created_at"] == when.replace(microsecond=345_000)
        and doc["created_at"].tzinfo is not None
    )
    updated = store.update(by_name["offset"].id, metadata={"tag": "café"})
    assert updated.metadata == {"tag": "café"} and updated.updated_at.tzinfo is UTC
    assert updated.updated_at == store.get(updated.id).updated_at  # microseconds kept
    assert updated.created_at == when
    for bad, error in (
        (datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=5))), ValueError),
        (datetime(2026, 1, 1), ValueError),
    ):
        with pytest.raises(error):
            store.add([item("never stored"), MemoryItem("x", "user", "x", T0, updated_at=bad)])
    with pytest.raises(ValueError, match="out of range"):
        store.add(
            [
                item(
                    "never stored",
                    created_at=datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=5))),
                )
            ]
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        store.list(Scope(user_id="u1"), since=datetime(2026, 1, 1))
    assert "never stored" not in contents(store.list(Scope(user_id="u1")))


@needs_db
def test_scopes_are_isolated_and_delete_scope_deletes_exactly_the_scope(store):
    reference = InMemoryStore()
    turns = [
        item(f"{user}/{agent}/{run}", user_id=user, agent_id=agent, run_id=run)
        for user in ("alice", "bob", None)
        for agent in ("bot", "helper", None)
        for run in ("r1", "r2", None)
        if user or agent or run
    ]
    store.add(turns)
    reference.add(turns)
    scopes = [
        Scope(user_id=user, agent_id=agent, run_id=run)
        for user in ("alice", "bob", "carol", None)
        for agent in ("bot", "helper", None)
        for run in ("r1", "r2", None)
        if user or agent or run
    ]
    for scope in scopes:
        assert contents(store.list(scope)) == contents(reference.list(scope)), scope
    for scope in (
        Scope(user_id="alice", run_id="r1"),
        Scope(agent_id="helper"),
        Scope(run_id="r2"),
    ):
        assert store.delete_scope(scope) == reference.delete_scope(scope) > 0
        for other in scopes:
            assert contents(store.list(other)) == contents(reference.list(other)), (scope, other)
    assert store.delete_scope(Scope(user_id="carol")) == 0


# ---------------------------------------------------------------- caller values are data


@needs_db
def test_hostile_ids_scopes_and_text_are_stored_and_matched_literally(store, raw):
    memory = Memory(store, clock=clock)
    for value in HOSTILE:
        memory.add(f"said by {value}", user_id=value, agent_id=value, run_id=value)
        store.add([item(f"id {value}", id=value, user_id="ids")])
    for value in HOSTILE:
        assert contents(memory.get_all(user_id=value)) == [f"said by {value}"]
        assert contents(memory.get_all(agent_id=value, run_id=value)) == [f"said by {value}"]
        assert store.get(value).content == f"id {value}"
    assert raw.count_documents({}) == 2 * len(HOSTILE)
    assert memory.delete_all(user_id="$ne") == 1 and raw.count_documents({}) == 2 * len(HOSTILE) - 1
    assert store.delete("$where") is True and store.get("$where") is None
    assert store.update("a.b", content="{$set: {content: 'x'}}").content == "{$set: {content: 'x'}}"


@needs_db
def test_operator_documents_in_place_of_strings_are_refused(store, raw):
    store.add([item("keep me", id="real")])
    for value in ({"$ne": None}, {"$gt": ""}, {"$regex": ".*"}, ["real"], 1):
        with pytest.raises(TypeError, match="must be a string"):
            store.get(value)
        with pytest.raises(TypeError, match="must be a string"):
            store.delete(value)
        with pytest.raises(TypeError, match="must be a string"):
            store.update(value, content="pwned")
        for field in ("user_id", "agent_id", "run_id"):
            # A Scope refuses these itself; a look-alike object reaches the store and is refused there.
            look_alike = SimpleNamespace(
                **{"user_id": None, "agent_id": None, "run_id": None, field: value}
            )
            with pytest.raises(TypeError, match="must be a string"):
                store.list(look_alike)
            with pytest.raises(TypeError, match="must be a string"):
                store.delete_scope(look_alike)
            with pytest.raises(TypeError, match="must be a string"):
                store.add([item("planted", **{field: value})])
        with pytest.raises(TypeError, match="must be a string"):
            store.add([item("planted", id=value)])
        with pytest.raises(TypeError, match="datetime"):
            store.list(Scope(user_id="u1"), since=value)
    with pytest.raises(ValueError, match="at least one"):
        store.delete_scope(SimpleNamespace(user_id=None, agent_id=None, run_id=None))
    with pytest.raises(ValueError):
        Scope(user_id={"$ne": None})
    assert [doc["content"] for doc in raw.find()] == ["keep me"]


@needs_db
def test_metadata_that_looks_like_operators_comes_back_as_given(store, raw):
    cases = {
        "operators": {"$where": "sleep(5000)", "$set": {"role": "system"}},
        "paths": {"a.b": 1, "user.id": "x"},
        "nested": {"filter": {"user_id": {"$ne": None}}, "list": [{"$gt": ""}]},
        "plain": {"source": "chat", "score": 0.5, "tags": ["x", "y"], "n": 2**40, "none": None},
        "big": {"id": 2**80},
        "empty key": {"": "blank"},
    }
    for name, metadata in cases.items():
        store.add([item(name, id=name, metadata=metadata)])
    for name, metadata in cases.items():
        got = dict(store.get(name).metadata)
        assert got == metadata and json.dumps(got, sort_keys=True) == json.dumps(
            metadata, sort_keys=True
        )
    stored = {doc["_id"]: doc for doc in raw.find()}
    assert stored["plain"]["metadata"]["n"] == 2**40 and "metadata_json" not in stored["plain"]
    for name in ("operators", "paths", "nested", "big", "empty key"):
        assert set(stored[name]) & {"metadata", "metadata_json"} == {"metadata_json"}, name
    # An update switches between the two forms and leaves no stale copy behind.
    assert store.update("plain", metadata={"$inc": {"seq": 1}}).metadata == {"$inc": {"seq": 1}}
    assert store.update("operators", metadata={"safe": True}).metadata == {"safe": True}
    switched = {doc["_id"]: doc for doc in raw.find({"_id": {"$in": ["plain", "operators"]}})}
    assert "metadata" not in switched["plain"] and "metadata_json" not in switched["operators"]
    assert [i.seq for i in store.list(Scope(user_id="u1"))] == sorted(
        i.seq for i in store.list(Scope(user_id="u1"))
    )


# ---------------------------------------------------------------- text


@needs_db
def test_unicode_round_trips_exactly(store):
    texts = {
        "cjk": "我上个月搬到了浦那。来月、東京に引っ越します。서울에서 왔어요.",
        "emoji": "Family 👨‍👩‍👧‍👦, flag 🇮🇳, skin tone 👍🏽, keycap 1️⃣ 🧪",
        "combining": "é vs é, Zalgo z̶̧a̵l̴g̷o, Hangul 가",
        "rtl": "שלום ‏مرحبا‎ mixed with English ‮evil‬",
        "invisible": "zero​width‍joiner﻿bom nbsp",
        "control": "nul\x00in the middle and a tab\t",
        "astral": "\U0001d54f\U0001f600\U00010348",
    }
    store.add(
        [
            item(text, id=name, user_id=f"ユーザー-{name}", metadata={"κλειδί": text, "😀": [text]})
            for name, text in texts.items()
        ]
    )
    for name, text in texts.items():
        got = store.get(name)
        assert got.content == text and got.user_id == f"ユーザー-{name}"
        assert got.metadata == {"κλειδί": text, "😀": [text]}
        assert contents(store.list(Scope(user_id=f"ユーザー-{name}"))) == [text]
    memory = Memory(store, clock=clock)
    assert "浦那" in memory.search("我搬到哪里了?", user_id="ユーザー-cjk").text


@needs_db
def test_lone_surrogates_are_refused_like_sqlite_and_nothing_is_stored(store, raw, tmp_path):
    sqlite = SQLiteStore(tmp_path / "m.db")
    try:
        bad_items = [
            item("x\ud800"),
            item("x", id="id\udc00"),
            item("x", user_id="u\udfff"),
            item("x", agent_id="a\ud83d"),
            item("x", run_id="r\udc00"),
            item("x", metadata={"\ud800": 1}),
            item("x", metadata={"k": ["fine", {"deep": "\udfff"}]}),
        ]
        for bad in bad_items:
            for target in (store, sqlite):
                with pytest.raises(UnicodeEncodeError):
                    target.add([item("good, but in the same batch"), bad])
        memory = Memory(store, clock=clock)
        with pytest.raises(UnicodeEncodeError):
            memory.add(
                [{"role": "user", "content": "fine"}, {"role": "user", "content": "x\ud800"}],
                user_id="u1",
            )
        assert raw.count_documents({}) == 0
        store.add([item("kept", id="kept")])
        for target in (store, sqlite):
            with pytest.raises(UnicodeEncodeError):
                target.get("kept\ud800")
            with pytest.raises(UnicodeEncodeError):
                target.list(Scope(user_id="u\udc00"))
        with pytest.raises(UnicodeEncodeError):
            store.update("kept", content="y\ud800")
        with pytest.raises(UnicodeEncodeError):
            store.update("kept", metadata={"k": "\udc00"})
        assert store.get("kept").content == "kept" and store.get("kept").metadata == {}
        assert contents(memory.get_all(user_id="u1")) == ["kept"]  # the scope still reads
    finally:
        sqlite.close()


@needs_db
def test_long_and_empty_text(store, raw):
    long_ascii = (
        "The quick brown fox jumps over the lazy dog. " * 22_000
    )  # about 1 MB, the server's request limit
    long_cjk = "我上个月搬到了浦那。" * 30_000  # 300,000 characters, 900 KB of UTF-8
    store.add([item(long_ascii, id="ascii"), item(long_cjk, id="cjk"), item("", id="empty")])
    assert store.get("ascii").content == long_ascii and store.get("cjk").content == long_cjk
    assert store.get("empty").content == ""
    assert store.update("empty", content="   ").content == "   "
    memory = Memory(store, clock=clock)
    found = memory.search("Where is the lazy dog?", user_id="u1", budget=300)
    assert 0 < found.tokens <= 300 and "lazy dog" in found.text
    too_big = "x" * (16 * 1024 * 1024)
    with pytest.raises(ValueError, match="16 MB"):
        store.add([item("small and first", id="first"), item(too_big)])
    with pytest.raises(ValueError, match="16 MB"):
        store.update("ascii", content=too_big)
    assert store.get("first") is None and store.get("ascii").content == long_ascii
    assert raw.count_documents({}) == 3


# ---------------------------------------------------------------- several writers


@needs_db
def test_concurrent_writers_keep_every_turn_and_one_order(store):
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
        mine = [int(i.content.split("-")[1]) for i in stored if i.content.startswith(f"w{worker}-")]
        assert mine == list(range(25))


WRITER = """
import sys, uuid
from datetime import datetime, timezone
from llmslim.memory import MemoryItem, MongoStore
url, collection, worker = sys.argv[1], sys.argv[2], sys.argv[3]
store = MongoStore(url, collection=collection)
when = datetime(2026, 3, 2, 9, 30, tzinfo=timezone.utc)
for n in range(0, 40, 2):
    store.add([
        MemoryItem(id=uuid.uuid4().hex, role="user", content=f"p{worker}-{n + k}", created_at=when, run_id="shared")
        for k in range(2)
    ])
store.close()
"""


@needs_db
def test_several_processes_open_and_write_one_collection_at_once(collection):
    writers = [
        subprocess.Popen(
            [sys.executable, "-c", WRITER, URL, collection, str(w)], stderr=subprocess.PIPE
        )
        for w in range(4)
    ]
    errors = [writer.communicate(timeout=120)[1].decode() for writer in writers]
    assert [writer.returncode for writer in writers] == [0] * 4, errors
    store = MongoStore(URL, collection=collection)
    try:
        stored = store.list(Scope(run_id="shared"))
        assert len(stored) == 160 and len({i.seq for i in stored}) == 160
        for worker in range(4):
            mine = [
                int(i.content.split("-")[1]) for i in stored if i.content.startswith(f"p{worker}-")
            ]
            assert mine == list(range(40))
    finally:
        store.close()


@needs_db
def test_several_stores_can_create_the_collection_at_once(collection):
    errors = []

    def start() -> None:
        try:
            opened = MongoStore(URL, collection=collection)
            opened.add([item("hello")])
            opened.close()
        except Exception as error:  # pragma: no cover - the failure being guarded against
            errors.append(error)

    threads = [threading.Thread(target=start) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    store = MongoStore(URL, collection=collection)
    try:
        assert len({i.seq for i in store.list(Scope(user_id="u1"))}) == 6
    finally:
        store.close()


# ---------------------------------------------------------------- the same answers as SQLite


WORDS = (
    "pune move flat rent garden tomatoes tea coffee trip goa train budget laptop python rust deadline "
    "manager review piano lessons sister wedding allergy peanuts doctor running marathon knee recipe "
    "dal curry sourdough bread oven project launch invoice client meeting tuesday friday"
).split()


def _history(rng: random.Random):
    turns = []
    for k in range(140):
        words = " ".join(rng.choice(WORDS) for _ in range(rng.randint(4, 40)))
        roll = rng.random()
        if roll < 0.1:
            words = f"## {words.title()}\n{words}.\n\n```python\nprint('{words[:20]}')\n```"
        elif roll < 0.15:
            words = f"I prefer {words}. Always mention {rng.choice(WORDS)} when I ask about {rng.choice(WORDS)}."
        elif roll < 0.2:
            words = f"{words} 我喜欢喝茶。"
        when = T0 + timedelta(hours=rng.choice([0, 0, 5, 30, 200]) + k)
        run = rng.choice([None, None, "trip", "work"])
        turns.append((rng.choice(["user", "assistant"]), words, when, run))
    return turns


@needs_db
def test_search_on_mongodb_selects_what_sqlite_selects(store, tmp_path):
    sqlite = SQLiteStore(tmp_path / "m.db")
    try:
        memories = [Memory(store, clock=clock), Memory(sqlite, clock=clock)]
        for user, seed in (("asha", 1), ("ravi", 2)):
            for role, text, when, run in _history(random.Random(seed)):
                for memory in memories:
                    memory.add(
                        [{"role": role, "content": text}], user_id=user, run_id=run, timestamp=when
                    )
        for user in ("asha", "ravi"):
            on_mongo, on_sqlite = (m.get_all(user_id=user) for m in memories)
            assert [(i.role, i.content, i.created_at, i.run_id) for i in on_mongo] == [
                (i.role, i.content, i.created_at, i.run_id) for i in on_sqlite
            ]
            for question in (
                "Where did I move to?",
                "Can you suggest a plan for my garden?",
                "Have I ever tried coffee?",
                "Summarize what we discussed about the trip.",
                "我喜欢喝什么?",
            ):
                for budget in (80, 400, 2000):
                    for scope in ({"user_id": user}, {"user_id": user, "run_id": "trip"}):
                        mongo, lite = (m.search(question, budget=budget, **scope) for m in memories)
                        assert mongo.text == lite.text, (user, question, budget, scope)
                        assert (mongo.tokens, mongo.sessions_total, mongo.sessions_kept) == (
                            lite.tokens,
                            lite.sessions_total,
                            lite.sessions_kept,
                        )
                        assert [t.item.content for t in mongo.turns] == [
                            t.item.content for t in lite.turns
                        ]
            window = {"since": T0 + timedelta(days=2), "until": T0 + timedelta(days=5)}
            assert contents(memories[0].get_all(user_id=user, **window)) == contents(
                memories[1].get_all(user_id=user, **window)
            )
    finally:
        sqlite.close()


# ---------------------------------------------------------------- llmslim serve and llmslim mcp


@needs_db
def test_the_http_server_runs_on_mongodb_and_pages_in_order(store):
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    from llmslim.server import create_app

    # Keyless, so it answers only loopback names, as it would on 127.0.0.1.
    client = TestClient(create_app(Memory(store, clock=clock)), base_url="http://127.0.0.1:8080")
    client.post("/v1/memories", json={"user_id": "asha", "messages": "I moved to Pune last month."})
    client.post(
        "/v1/memories",
        json={
            "user_id": "asha",
            "messages": [{"role": "user", "content": f"note {n}"} for n in range(25)],
        },
    )
    found = client.post(
        "/v1/memories/search", json={"user_id": "asha", "query": "Where did I move to?"}
    ).json()
    assert "Pune" in found["text"]
    pages = []
    for offset in range(0, 26, 7):
        page = client.get(
            "/v1/memories", params={"user_id": "asha", "limit": 7, "offset": offset}
        ).json()
        assert page["total"] == 26
        pages += [entry["content"] for entry in page["items"]]
    assert pages == ["I moved to Pune last month."] + [f"note {n}" for n in range(25)]
    refused = client.post(
        "/v1/memories",
        content=b'{"user_id": "asha", "messages": "x", "metadata": {"\\ud800": 1}}',
        headers={"content-type": "application/json"},
    )
    assert refused.status_code == 400
    assert client.delete("/v1/memories", params={"user_id": "asha"}).json() == {"deleted": 26}


@needs_db
def test_serve_and_mcp_open_mongodb_from_db(monkeypatch):
    from llmslim import mcp_server, server

    for parser in (server.build_parser(), mcp_server.build_parser()):
        assert "mongodb://" in parser.format_help()
        args = parser.parse_args(["--db", URL])
        memory = Memory(storage_target(args.db))
        try:
            assert isinstance(memory.store, MongoStore)
        finally:
            memory.store.close()
    monkeypatch.setenv("LLMSLIM_MEMORY_DB", URL)
    assert server.build_parser().parse_args([]).db == URL
    _drop("llmslim_memory")


@needs_db
def test_llmslim_import_writes_to_mongodb_without_printing_the_url(capsys):
    from pathlib import Path

    from llmslim.cli import main

    history = Path(__file__).parent / "fixtures" / "import" / "jsonl" / "history.jsonl"
    try:
        assert main(["import", "jsonl", str(history), "--db", URL]) == 0
        first = capsys.readouterr()
        assert "4 imported" in first.out and "MongoDB" in first.out + first.err
        assert main(["import", "jsonl", str(history), "--db", URL]) == 0
        again = capsys.readouterr()
        assert "0 imported, 4 already there" in again.out
        for shown in (first, again):
            assert URL not in shown.out + shown.err
        store = MongoStore(URL)
        try:
            assert [i.run_id for i in store.list(Scope(run_id="s-1"))] == ["s-1", "s-1"]
        finally:
            store.close()
    finally:
        _drop("llmslim_memory")
