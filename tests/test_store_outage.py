"""When the memory's database is down: llmslim serve answers a clean 503, the MCP tools a clean tool error, and both
commands refuse to start with one line instead of a traceback. Nothing shows the driver's message, a host or a URL.

These run without a database: the stores below raise what PyMongo and psycopg raise when the server can't be reached.
The end-to-end tests in tests/e2e stop and restart a real MongoDB."""

from __future__ import annotations

import asyncio
import logging
import sys

import pytest

from llmslim.memory import Memory
from llmslim.memory._errors import UNAVAILABLE_MESSAGE, store_unavailable

KEY = "k" * 32
AUTH = {"Authorization": f"Bearer {KEY}"}
# What a driver's message may name, none of which a client or the log should see.
LEAKS = ("db.example.com", "27017", "hunter2", "mongodb://", "postgresql://", "Traceback")


def _mongo_outage() -> BaseException:
    errors = pytest.importorskip("pymongo.errors")
    return errors.ServerSelectionTimeoutError(
        "db.example.com:27017: [Errno 111] Connection refused, Timeout: 30s, "
        "Topology Description: <seen mongodb://shop:hunter2@db.example.com:27017/app>"
    )


def _postgres_outage() -> BaseException:
    psycopg = pytest.importorskip("psycopg")
    return psycopg.OperationalError(
        'connection to server at "db.example.com", port 5432 failed: postgresql://shop:hunter2@db.example.com'
    )


class DownStore:
    """A store whose database is unreachable: every call raises ``error``."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def add(self, items):
        raise self.error

    def list(self, scope, *, since=None, until=None):
        raise self.error

    def get(self, item_id):
        raise self.error

    def update(self, item_id, *, content=None, metadata=None):
        raise self.error

    def delete(self, item_id):
        raise self.error

    def delete_scope(self, scope):
        raise self.error


def test_what_counts_as_an_unreachable_store():
    errors = pytest.importorskip("pymongo.errors")
    assert store_unavailable(_mongo_outage())
    assert store_unavailable(errors.AutoReconnect("db.example.com:27017: connection closed"))
    assert store_unavailable(errors.NetworkTimeout("timed out"))
    assert store_unavailable(errors.NotPrimaryError("not primary"))
    assert not store_unavailable(errors.OperationFailure("WriteConflict", code=112))
    labelled = {"errorLabels": ["TransientTransactionError"]}
    assert store_unavailable(errors.OperationFailure("WriteConflict", code=112, details=labelled))
    # A request MongoDB refused for good is not an outage.
    assert not store_unavailable(errors.OperationFailure("not authorized on app", code=13))
    assert not store_unavailable(errors.DuplicateKeyError("E11000"))
    assert not store_unavailable(ValueError("bad input"))
    assert not store_unavailable(RuntimeError("a bug"))


def test_a_postgres_connection_error_or_pool_timeout_is_an_outage():
    assert store_unavailable(_postgres_outage())
    pool = pytest.importorskip("psycopg_pool")
    assert store_unavailable(pool.PoolTimeout("couldn't get a connection after 30.00 sec"))
    psycopg = pytest.importorskip("psycopg")
    assert not store_unavailable(psycopg.errors.UniqueViolation("duplicate key"))


def test_drivers_that_were_never_imported_are_not_looked_at(monkeypatch):
    for module in ("pymongo.errors", "psycopg"):
        monkeypatch.setitem(sys.modules, module, None)
    assert not store_unavailable(ConnectionError("down"))


@pytest.mark.parametrize("outage", [_mongo_outage, _postgres_outage])
def test_the_server_answers_503_without_the_drivers_message(outage, caplog):
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    from llmslim.server import create_app

    client = TestClient(create_app(Memory(DownStore(outage())), api_keys=[KEY]))
    calls = [
        ("POST", "/v1/memories", {"json": {"user_id": "u", "messages": "I moved to Pune."}}),
        ("GET", "/v1/memories", {"params": {"user_id": "u"}}),
        ("GET", "/v1/memories/abc", {}),
        ("PATCH", "/v1/memories/abc", {"json": {"content": "fixed"}}),
        ("DELETE", "/v1/memories/abc", {}),
        ("DELETE", "/v1/memories", {"params": {"user_id": "u"}}),
        ("POST", "/v1/memories/search", {"json": {"user_id": "u", "query": "Where?"}}),
        ("POST", "/v1/memories/search", {"json": {"user_id": "u", "query": "x", "explain": True}}),
    ]
    with caplog.at_level(logging.DEBUG):
        for method, path, options in calls:
            response = client.request(method, path, headers=AUTH, **options)
            assert response.status_code == 503, (method, path, response.text)
            assert response.headers["retry-after"] == "5"
            assert response.json() == {
                "error": {"type": "store_unavailable", "message": UNAVAILABLE_MESSAGE}
            }
            assert not any(leak in response.text for leak in LEAKS)
    # The log says what happened, once per request, without a traceback or the driver's message.
    logged = [r for r in caplog.records if r.name == "llmslim.server"]
    assert len(logged) == len(calls)
    assert all(r.levelno == logging.WARNING and r.exc_info is None for r in logged)
    assert not any(leak in r.getMessage() for r in logged for leak in LEAKS)
    # Liveness and the routes that don't touch memory still answer.
    assert client.get("/healthz").json() == {"status": "ok"}
    fitted = client.post("/v1/context/fit", json={"text": "Short.", "budget": 50}, headers=AUTH)
    assert fitted.status_code == 200


def test_an_unexpected_failure_is_a_json_500_and_logged_in_full(caplog):
    pytest.importorskip("starlette")
    from starlette.testclient import TestClient

    from llmslim.server import create_app

    store = DownStore(RuntimeError("bug at db.example.com"))
    client = TestClient(create_app(Memory(store), api_keys=[KEY]))
    with caplog.at_level(logging.ERROR):
        response = client.get("/v1/memories", params={"user_id": "u"}, headers=AUTH)
    assert response.status_code == 500
    assert response.json() == {"error": {"type": "server_error", "message": "the request failed"}}
    assert "db.example.com" not in response.text
    # The operator gets the traceback in the server's log.
    assert any(r.exc_info and r.name == "llmslim.server" for r in caplog.records)


def test_mcp_tools_fail_with_a_message_the_model_can_act_on(caplog):
    pytest.importorskip("mcp")
    from llmslim.mcp_server import build_server
    from mcp import Client

    server = build_server(Memory(DownStore(_mongo_outage())), user_id="asha")

    async def run():
        async with Client(server) as client:
            return [
                await client.call_tool(tool, arguments)
                for tool, arguments in (
                    ("remember", {"text": "I moved to Pune."}),
                    ("recall", {"query": "Where do I live?"}),
                    ("list_memories", {}),
                    ("forget", {"memory_id": "abc"}),
                )
            ] + [await client.call_tool("fit_context", {"text": "Short.", "budget": 50})]

    with caplog.at_level(logging.DEBUG):
        *failed, fitted = asyncio.run(run())
    for result in failed:
        text = "\n".join(block.text for block in result.content)
        assert result.is_error and UNAVAILABLE_MESSAGE in text, text
        assert not any(leak in text for leak in LEAKS)
    assert not fitted.is_error  # fitting text needs no database
    assert not any(r.exc_info for r in caplog.records)  # an outage is not logged as a crash


def test_serve_and_mcp_refuse_to_start_on_a_store_they_cannot_open_in_one_line(monkeypatch):
    pytest.importorskip("pymongo")
    pytest.importorskip("mcp")
    from llmslim import mcp_server, server

    monkeypatch.setattr("uvicorn.run", lambda *a, **k: pytest.fail("the server started"))
    monkeypatch.setattr("uvicorn.Server.run", lambda *a, **k: pytest.fail("the server started"))
    url = "mongodb://shop:hunter2@127.0.0.1:1/app?serverSelectionTimeoutMS=50"
    for program, run in (
        ("llmslim serve", lambda: server.main(["--db", url])),
        ("llmslim mcp", lambda: mcp_server.main(["--db", url])),
        ("llmslim mcp", lambda: mcp_server.main(["--transport", "http", "--db", url])),
    ):
        with pytest.raises(SystemExit) as caught:
            run()
        message = str(caught.value.code)
        assert message.startswith(f"{program}: could not open the memory store: ")
        assert "ServerSelectionTimeoutError" in message and "\n" not in message.strip()
        assert "hunter2" not in message and "mongodb://" not in message
        assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_a_missing_driver_names_the_extra_to_install(monkeypatch):
    from llmslim import server

    for module in ("pymongo", "pymongo.database", "bson", "bson.codec_options"):
        monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(SystemExit) as caught:
        server.main(["--db", "mongodb://127.0.0.1:1/app"])
    assert 'pip install "llmslim[mongodb]"' in str(caught.value.code)


def test_a_driver_message_that_echoes_the_url_loses_its_password(monkeypatch):
    from llmslim import server

    def echoing(target, **_):
        raise ValueError(f"invalid connection option in {target} (password hunter2)")

    monkeypatch.setattr(server, "Memory", echoing)
    url = "postgresql://shop:hunter2@db.example.com:5432/app?sslpassword=k3y"
    with pytest.raises(SystemExit) as caught:
        server.open_memory(url, budget=100, program="llmslim serve")
    message = str(caught.value.code)
    assert "hunter2" not in message and "k3y" not in message
    assert message == (
        "llmslim serve: could not open the memory store: ValueError: invalid connection option in "
        "postgresql://shop:<redacted>@db.example.com:5432/app?sslpassword=<redacted> (password <redacted>)"
    )
