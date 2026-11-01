"""The built wheel against a real MongoDB, as a user runs it: ``llmslim serve``, ``llmslim mcp --transport http``,
``llmslim import`` and the chat endpoint, each a separate process, driven over HTTP, MCP and the command line.

Nothing here imports llmslim: the commands come from the environment the wheel was installed into, which CI builds
from ``python -m build`` (not an editable install). Run with that environment's pytest and ``--import-mode=importlib``
so the checkout is never on ``sys.path``:

    LLMSLIM_E2E_BIN=/venv/bin LLMSLIM_TEST_MONGODB_URL=mongodb://... /venv/bin/pytest tests/e2e --import-mode=importlib

``LLMSLIM_E2E_MONGODB_CONTAINER`` names the Docker container of that MongoDB, for the restart and outage tests, and
``LLMSLIM_E2E_BIG_IMPORT`` a number of turns for the large-import test (CI runs 20,000 on the replica set).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import random
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import pytest

BIN = os.environ.get("LLMSLIM_E2E_BIN")
URL = os.environ.get("LLMSLIM_TEST_MONGODB_URL")
CONTAINER = os.environ.get("LLMSLIM_E2E_MONGODB_CONTAINER")
BIG_IMPORT = int(os.environ.get("LLMSLIM_E2E_BIG_IMPORT") or 0)

pytestmark = pytest.mark.skipif(
    not (BIN and URL),
    reason="set LLMSLIM_E2E_BIN (an environment with the wheel installed) and LLMSLIM_TEST_MONGODB_URL",
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "import"
KEY = "e2e-" + "k" * 40
UPSTREAM_KEY = "e2e-upstream-" + "u" * 30
START_TIMEOUT = 60
# Everything a command printed or answered, checked for the URL's password after each test.
SEEN: List[str] = []


def _secrets() -> List[str]:
    password = urlsplit(URL or "").password
    return [password, unquote(password)] if password else []


def _with(url: str, *, database: Optional[str] = None, **options: str) -> str:
    """``url`` with another database, more options, or both."""
    parts = urlsplit(url)
    path = f"/{database}" if database is not None else parts.path
    query = urlencode([*parse_qsl(parts.query), *options.items()])
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def _exe(name: str) -> str:
    found = shutil.which(name, path=BIN)
    assert found, f"{name} is not in {BIN}"
    return found


def _env(**extra: str) -> Dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("LLMSLIM_") and key not in ("PYTHONPATH", "PYTHONHOME")
    }
    env["PYTHONUNBUFFERED"] = "1"
    env.update(extra)
    return env


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run(*args: str, timeout: float = 300, cwd: Optional[Path] = None, **env: str):
    """Run an llmslim command to the end; its output is kept for the password check."""
    done = subprocess.run(
        [_exe("llmslim"), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd or Path.home(),
        env=_env(**env),
    )
    SEEN.extend([done.stdout, done.stderr])
    return done


class Server:
    """A long-running llmslim command (serve or mcp), its output in a log file."""

    def __init__(self, tmp: Path, *args: str, **env: str) -> None:
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.log = tmp / f"server-{self.port}.log"
        self._out = self.log.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [_exe("llmslim"), *args, "--port", str(self.port)],
            stdout=self._out,
            stderr=subprocess.STDOUT,
            cwd=tmp,
            env=_env(**env),
        )
        self._wait()

    def _wait(self) -> None:
        import httpx

        deadline = time.monotonic() + START_TIMEOUT
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise AssertionError(
                    f"the server exited ({self.proc.returncode}):\n{self.output()}"
                )
            try:
                if httpx.get(f"{self.base}/healthz", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.3)
        raise AssertionError(f"the server did not start:\n{self.output()}")

    def output(self) -> str:
        if not self._out.closed:
            self._out.flush()
        return self.log.read_text(encoding="utf-8", errors="replace")

    def stop(self) -> str:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self._out.close()
        text = self.output()
        SEEN.append(text)
        return text


@contextmanager
def serving(tmp: Path, *args: str, **env: str) -> Iterator[Server]:
    server = Server(tmp, *args, **env)
    try:
        yield server
    finally:
        server.stop()


def _client():
    import pymongo

    return pymongo.MongoClient(URL, serverSelectionTimeoutMS=60_000)


@pytest.fixture
def database() -> Iterator[str]:
    """A MongoDB URL on a database of this test's own, dropped afterwards."""
    name = f"llmslim_e2e_{uuid.uuid4().hex[:10]}"
    yield _with(URL or "", database=name)
    with _client() as client:
        client.drop_database(name)


def _collection(url: str, name: str = "llmslim_memory"):
    """The turns collection the commands write, read straight from MongoDB."""
    client = _client()
    return client, client[urlsplit(url).path.lstrip("/")][name]


@pytest.fixture(autouse=True)
def _no_password_anywhere():
    start = len(SEEN)
    yield
    for text in SEEN[start:]:
        for secret in _secrets():
            assert secret not in text, "the MongoDB password was printed or answered"


def _http(method: str, base: str, path: str, *, key: Optional[str] = KEY, **kwargs: Any):
    import httpx

    headers = dict(kwargs.pop("headers", {}))
    if key:
        headers["Authorization"] = f"Bearer {key}"
    response = httpx.request(method, base + path, headers=headers, timeout=120, **kwargs)
    SEEN.append(response.text)
    return response


# --------------------------------------------------------------------------- the installation


def test_the_commands_come_from_the_installed_wheel(tmp_path):
    python = _exe("python")
    probe = (
        "import importlib.metadata as m, json, llmslim, pymongo, dns.resolver, starlette, uvicorn, mcp;"
        "d = m.distribution('llmslim');"
        "print(json.dumps({'file': llmslim.__file__, 'version': llmslim.__version__,"
        " 'direct_url': d.read_text('direct_url.json'), 'pymongo': pymongo.version}))"
    )
    done = subprocess.run(
        [python, "-I", "-c", probe], capture_output=True, text=True, cwd=tmp_path, env=_env()
    )
    assert done.returncode == 0, done.stderr
    found = json.loads(done.stdout)
    repo = Path(__file__).resolve().parents[2]
    installed = Path(found["file"]).resolve()
    assert "site-packages" in installed.parts and repo not in installed.parents
    # Installed from a wheel file, not as an editable checkout.
    direct = json.loads(found["direct_url"] or "{}")
    assert not direct.get("dir_info", {}).get("editable"), direct
    assert direct.get("url", "").endswith(".whl"), direct
    # This test process doesn't see the checkout's llmslim either.
    spec = importlib.util.find_spec("llmslim")
    assert spec is None or repo not in Path(spec.origin or "").resolve().parents
    print(f"llmslim {found['version']} from {installed}, pymongo {found['pymongo']}")


# --------------------------------------------------------------------------- llmslim serve


def test_serve_stores_finds_explains_lists_corrects_and_deletes(tmp_path, database):
    with serving(tmp_path, "serve", "--db", database, LLMSLIM_API_KEYS=KEY) as server:
        base = server.base
        assert _http("GET", base, "/v1/info", key=None).status_code == 401
        info = _http("GET", base, "/v1/info").json()
        assert info["name"] == "llmslim"
        added = _http(
            "POST",
            base,
            "/v1/memories",
            json={
                "user_id": "asha",
                "run_id": "trip",
                "messages": [
                    {"role": "user", "content": "I moved to Pune last month."},
                    {"role": "assistant", "content": "Pune is lovely in the monsoon."},
                ],
            },
        )
        assert added.status_code == 201, added.text
        first, reply = (item["id"] for item in added.json()["items"])
        hostile = {"$where": "sleep(100)", "a.b": {"$ne": None}, "plain": [1, "two"]}
        sister = _http(
            "POST",
            base,
            "/v1/memories",
            json={
                "user_id": "asha",
                "messages": "My sister Meera lives in Delhi.",
                "metadata": hostile,
            },
        ).json()["items"][0]
        assert sister["metadata"] == hostile

        found = _http(
            "POST",
            base,
            "/v1/memories/search",
            json={"user_id": "asha", "query": "Where did I move to?"},
        ).json()
        assert "Pune" in found["text"] and "explanation" not in found
        explained = _http(
            "POST",
            base,
            "/v1/memories/search",
            json={"user_id": "asha", "query": "Where did I move to?", "explain": True},
        ).json()
        assert explained["text"] == found["text"]
        turns = explained["explanation"]["turns"]
        assert {turn["id"] for turn in turns} == {first, reply, sister["id"]}
        assert all(turn["status"] in ("kept", "clipped", "dropped") for turn in turns)

        listed = _http("GET", base, "/v1/memories", params={"user_id": "asha"}).json()
        assert listed["total"] == 3
        assert [item["id"] for item in listed["items"]] == [first, reply, sister["id"]]
        assert _http("GET", base, f"/v1/memories/{sister['id']}").json()["metadata"] == hostile
        fixed = _http(
            "PATCH", base, f"/v1/memories/{first}", json={"content": "I moved to Pune in March."}
        ).json()
        assert fixed["content"] == "I moved to Pune in March." and fixed["updated_at"]

        client, turns_collection = _collection(database)
        with client:
            stored = {row["_id"]: row for row in turns_collection.find({"user_id": "asha"})}
            assert set(stored) == {first, reply, sister["id"]}
            assert stored[first]["content"] == "I moved to Pune in March."
            assert stored[first]["run_id"] == "trip"
            # Operator-like metadata keys are kept as text, so MongoDB never reads them as operators.
            assert "metadata_json" in stored[sister["id"]]
            indexes = set(turns_collection.index_information())
            assert {"llmslim_memory_user_id", "llmslim_memory_seq"} <= indexes

            assert _http("DELETE", base, f"/v1/memories/{reply}").json() == {"deleted": 1}
            assert _http("GET", base, f"/v1/memories/{reply}").status_code == 404
            assert _http("DELETE", base, f"/v1/memories/{reply}").status_code == 404
            assert turns_collection.count_documents({"user_id": "asha"}) == 2
            gone = _http("DELETE", base, "/v1/memories", params={"user_id": "asha"}).json()
            assert gone == {"deleted": 2}
            assert turns_collection.count_documents({}) == 0
    assert "Traceback" not in server.output()


def test_two_servers_share_one_memory(tmp_path, database):
    with (
        serving(tmp_path, "serve", "--db", database, LLMSLIM_API_KEYS=KEY) as one,
        serving(tmp_path, "serve", LLMSLIM_MEMORY_DB=database, LLMSLIM_API_KEYS=KEY) as two,
    ):
        for n in range(20):
            server = (one, two)[n % 2]
            body = {"user_id": "team", "messages": f"note {n} from {server.port}"}
            assert _http("POST", server.base, "/v1/memories", json=body).status_code == 201
        for server in (one, two):
            listed = _http("GET", server.base, "/v1/memories", params={"user_id": "team"}).json()
            assert [item["content"].split()[1] for item in listed["items"]] == [
                str(n) for n in range(20)
            ]


# --------------------------------------------------------------------------- llmslim mcp --transport http


def _mcp(url: str, key: Optional[str], calls: List[tuple]) -> List[Any]:
    import httpx2
    from mcp.client.streamable_http import streamable_http_client

    from mcp import Client

    async def go() -> List[Any]:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        async with httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(120)) as http:
            async with Client(streamable_http_client(url, http_client=http)) as client:
                results = []
                for tool, arguments in calls:
                    if tool == "list_tools":
                        results.append(sorted(t.name for t in (await client.list_tools()).tools))
                    else:
                        results.append(await client.call_tool(tool, arguments))
                return results

    return asyncio.run(go())


def _text(result: Any) -> str:
    text = "\n".join(block.text for block in result.content if getattr(block, "text", None))
    SEEN.append(text)
    return text


def test_mcp_over_http_remembers_recalls_and_forgets(tmp_path, database):
    with (
        serving(
            tmp_path,
            "mcp",
            "--transport",
            "http",
            "--db",
            database,
            "--user-id",
            "asha",
            LLMSLIM_MCP_API_KEYS=KEY,
        ) as laptop,
        serving(
            tmp_path,
            "mcp",
            "--transport",
            "http",
            "--db",
            database,
            "--user-id",
            "asha",
            LLMSLIM_MCP_API_KEYS=KEY,
        ) as desktop,
    ):
        refused = _http(
            "POST",
            laptop.base,
            "/mcp",
            key=None,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"accept": "application/json, text/event-stream"},
        )
        assert refused.status_code == 401
        tools, stored = _mcp(
            f"{laptop.base}/mcp",
            KEY,
            [
                ("list_tools", None),
                ("remember", {"text": "I'm allergic to peanuts.", "session": "food"}),
            ],
        )
        assert tools == ["fit_context", "forget", "list_memories", "recall", "remember"]
        stored_text = _text(stored)
        assert stored_text.startswith("Stored as ")
        memory_id = stored_text.removeprefix("Stored as ").rstrip(".")
        client, turns = _collection(database)
        with client:
            row = turns.find_one({"_id": memory_id})
            assert row and row["user_id"] == "asha" and row["run_id"] == "food"
            # Another machine's server on the same database sees it, and can forget it.
            recalled, listed, forgotten, again = _mcp(
                f"{desktop.base}/mcp",
                KEY,
                [
                    ("recall", {"query": "Am I allergic to anything?"}),
                    ("list_memories", {}),
                    ("forget", {"memory_id": memory_id}),
                    ("recall", {"query": "Am I allergic to anything?"}),
                ],
            )
            assert "peanuts" in _text(recalled) and memory_id in _text(listed)
            assert _text(forgotten) == f"Deleted {memory_id}."
            assert "peanuts" not in _text(again)
            assert turns.count_documents({}) == 0
    for server in (laptop, desktop):
        assert "Traceback" not in server.output() and KEY not in server.output()


# --------------------------------------------------------------------------- llmslim import


SOURCES = [
    ("claude-code", FIXTURES / "claude-code" / "projects"),
    ("chatgpt", FIXTURES / "chatgpt" / "conversations.json"),
    ("claude-ai", FIXTURES / "claude-ai" / "conversations.json"),
    ("mem0", FIXTURES / "mem0" / "export.json"),
    ("jsonl", FIXTURES / "jsonl" / "history.jsonl"),
]


def test_import_every_format_stores_what_sqlite_stores(tmp_path, database):
    sqlite_db = tmp_path / "same.db"
    client, turns = _collection(database)
    with client:
        for fmt, source in SOURCES:
            first = run("import", fmt, str(source), "--db", database, "--json")
            assert first.returncode == 0, first.stderr
            report = json.loads(first.stdout)
            assert report["imported"] > 0 and not report["errors"], report
            again = run("import", fmt, str(source), "--db", database, "--json")
            assert again.returncode == 0, again.stderr
            repeat = json.loads(again.stdout)
            assert repeat["imported"] == 0 and repeat["duplicates"] == report["imported"]
            reference = run("import", fmt, str(source), "--db", str(sqlite_db), "--json")
            assert json.loads(reference.stdout)["imported"] == report["imported"]
        with sqlite3.connect(sqlite_db) as conn:
            expected = {
                row[0]: row[1:]
                for row in conn.execute(
                    "SELECT id, role, content, user_id, agent_id, run_id FROM llmslim_memory"
                )
            }
        stored = {
            row["_id"]: (
                row["role"],
                row["content"],
                row["user_id"],
                row["agent_id"],
                row["run_id"],
            )
            for row in turns.find()
        }
        assert stored == expected
        dry = run("import", "jsonl", str(SOURCES[-1][1]), "--db", database, "--dry-run", "--json")
        assert json.loads(dry.stdout)["imported"] == 0 and json.loads(dry.stdout)["dry_run"]
    # The human summary names the store, never the URL.
    shown = run("import", "jsonl", str(SOURCES[-1][1]), "--db", database)
    assert shown.returncode == 0 and "into:        a MongoDB database" in shown.stdout
    assert database not in shown.stdout + shown.stderr


# One session of short turns, written 500, 500 and 200 at a time (the turn bound), and one of turns of about 180 KB
# each: 11.5 MB, written in three (the 4 MB bound).
LONG_SESSION = 1_200
HEAVY_SESSION = 64


def _history(path: Path, turns: int) -> Dict[str, int]:
    """A JSONL history of ``turns`` turns: sessions of 200 with a long reply (90,000 characters, two bytes each in
    UTF-8) every 100 turns, then one session of 1,200 short turns and one of 64 long ones. Returns the turns per
    session."""
    rng = random.Random(7)
    words = (
        "pune delhi train invoice deploy staging allergy peanuts sister meera budget review".split()
    )
    ordinary = turns - LONG_SESSION - HEAVY_SESSION
    assert ordinary > 0, "the large import needs more than 1,264 turns"
    sessions: Dict[str, int] = {}
    with path.open("w", encoding="utf-8") as out:
        for n in range(turns):
            if n < ordinary:
                session, long = f"s{n // 200:04d}", n % 100 == 99
            else:
                session = "long" if n < ordinary + LONG_SESSION else "heavy"
                long = session == "heavy"
            sessions[session] = sessions.get(session, 0) + 1
            if long:
                text = f"long reply {n}: " + "é" * 90_000
            else:
                text = f"turn {n}: " + " ".join(
                    rng.choice(words) for _ in range(rng.randint(20, 200))
                )
            record = {
                "role": "user" if n % 2 == 0 else "assistant",
                "content": text,
                "session_id": session,
                "timestamp": 1_700_000_000 + n,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
    return sessions


def _transactions(client) -> Dict[str, int]:
    status = client.admin.command("serverStatus").get("transactions") or {}
    return {key: int(status.get(key, 0)) for key in ("totalCommitted", "totalAborted")}


@pytest.mark.skipif(not BIG_IMPORT, reason="set LLMSLIM_E2E_BIG_IMPORT to a number of turns")
def test_a_large_history_imports_in_bounded_transactions(tmp_path, database):
    path = tmp_path / "large.jsonl"
    sessions = _history(path, BIG_IMPORT)
    client, turns = _collection(database)
    with client:
        replica_set = bool(client.admin.command("hello").get("setName"))
        before = _transactions(client)
        started = time.monotonic()
        first = run("import", "jsonl", str(path), "--db", database, "--json", timeout=1_800)
        took = time.monotonic() - started
        assert first.returncode == 0, first.stderr[-2000:]
        report = json.loads(first.stdout)
        assert report["imported"] == BIG_IMPORT and report["skipped"] == {}, report
        after = _transactions(client)
        assert turns.count_documents({}) == BIG_IMPORT
        assert len(turns.distinct("seq")) == BIG_IMPORT
        for session, count in sessions.items():
            assert turns.count_documents({"run_id": session}) == count
        if replica_set:
            # One transaction per write, none aborted. A session of 200 turns (two of them 180 KB) is one write;
            # the one of 1,200 short turns is three (the 500-turn bound), and so is the 11.5 MB one (the 4 MB
            # bound), which a single transaction held whole before.
            assert after["totalAborted"] == before["totalAborted"]
            writes = (len(sessions) - 2) + 3 + 3
            assert after["totalCommitted"] - before["totalCommitted"] == writes
        started = time.monotonic()
        again = run("import", "jsonl", str(path), "--db", database, "--json", timeout=1_800)
        took_again = time.monotonic() - started
        assert again.returncode == 0, again.stderr[-2000:]
        repeat = json.loads(again.stdout)
        assert repeat["imported"] == 0 and repeat["duplicates"] == BIG_IMPORT
        assert turns.count_documents({}) == BIG_IMPORT
    print(
        f"{BIG_IMPORT} turns into {'a replica set' if replica_set else 'a standalone server'}: "
        f"{took:.1f}s, again (nothing new) {took_again:.1f}s"
    )


# --------------------------------------------------------------------------- the chat endpoint


class Upstream:
    """A small OpenAI-compatible server: answers every chat request with a fixed reply, JSON or streamed, and keeps
    what it was sent."""

    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def do_GET(self) -> None:
                self._json({"object": "list", "data": [{"id": "fake-model", "object": "model"}]})

            def do_POST(self) -> None:
                length = int(self.headers.get("content-length") or 0)
                body = json.loads(self.rfile.read(length))
                upstream.requests.append(
                    {"body": body, "authorization": self.headers.get("authorization")}
                )
                question = body["messages"][-1]["content"]
                reply = "You live in Pune." if "live" in question else "Noted: you moved to Pune."
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("content-type", "text/event-stream")
                    self.end_headers()
                    for part in (reply[:8], reply[8:]):
                        chunk = {
                            "id": "chatcmpl-e2e",
                            "object": "chat.completion.chunk",
                            "model": "fake-model",
                            "choices": [{"index": 0, "delta": {"content": part}}],
                        }
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                        self.wfile.flush()
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                self._json(
                    {
                        "id": "chatcmpl-e2e",
                        "object": "chat.completion",
                        "model": "fake-model",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": reply},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                )

            def _json(self, payload: Dict[str, Any]) -> None:
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def upstream() -> Iterator[Upstream]:
    fake = Upstream()
    yield fake
    fake.close()


def _until(check, timeout: float = 30.0):
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value or time.monotonic() > deadline:
            return value
        time.sleep(0.2)


def _chat(base: str, content: str, *, stream: bool = False):
    return _http(
        "POST",
        base,
        "/v1/chat/completions",
        json={
            "model": "fake-model",
            "stream": stream,
            "messages": [{"role": "user", "content": content}],
        },
        headers={"X-LLMSlim-User-Id": "caller", "X-LLMSlim-Session-Id": "call-1"},
    )


def test_the_chat_endpoint_stores_each_turn_in_mongodb_and_recalls_it(tmp_path, database, upstream):
    with serving(
        tmp_path,
        "serve",
        "--db",
        database,
        "--upstream-url",
        upstream.url,
        LLMSLIM_API_KEYS=KEY,
        LLMSLIM_UPSTREAM_API_KEY=UPSTREAM_KEY,
    ) as server:
        client, turns = _collection(database)
        with client:
            answered = _chat(server.base, "I just moved to Pune.")
            assert answered.status_code == 200, answered.text
            assert (
                answered.json()["choices"][0]["message"]["content"] == "Noted: you moved to Pune."
            )
            # The turns are stored after the answer has gone out.
            assert _until(lambda: turns.count_documents({"user_id": "caller"}) == 2)
            stored = list(turns.find({"user_id": "caller"}).sort("seq", 1))
            assert [(row["role"], row["content"], row["run_id"]) for row in stored] == [
                ("user", "I just moved to Pune.", "call-1"),
                ("assistant", "Noted: you moved to Pune.", "call-1"),
            ]
            assert stored[0]["metadata"] == {"source": "chat"}

            streamed = _chat(server.base, "Where do I live now?", stream=True)
            assert streamed.status_code == 200 and "You live" in streamed.text
            assert streamed.headers["x-llmslim-recall"] == "injected"
            sent = upstream.requests[-1]
            recalled = [
                m["content"]
                for m in sent["body"]["messages"]
                if "<llmslim_context " in str(m["content"])
            ]
            assert recalled and "Pune" in recalled[0]  # read back from MongoDB
            # The upstream gets the server's key, never the client's.
            assert sent["authorization"] == f"Bearer {UPSTREAM_KEY}"
            assert _until(lambda: turns.count_documents({"user_id": "caller"}) == 4)
            models = _http("GET", server.base, "/v1/models").json()
            assert models["data"][0]["id"] == "fake-model"
    assert UPSTREAM_KEY not in server.output() and "Traceback" not in server.output()


# --------------------------------------------------------------------------- failures


def _wrong(url: str, **options: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.rpartition("@")[2]
    return urlunsplit(
        (
            parts.scheme,
            f"e2e_nobody:Wr0ng-p%40ss@{host}",
            parts.path,
            urlencode([*parse_qsl(parts.query), *options.items()]),
            "",
        )
    )


def test_commands_that_cannot_reach_or_log_in_fail_in_one_line():
    # Nothing is created: neither URL gets as far as the database.
    unreachable = (
        "mongodb://e2e:Unre4chable-pw@127.0.0.1:1/llmslim_e2e?serverSelectionTimeoutMS=1000"
    )
    wrong = _wrong(_with(URL or "", database="llmslim_e2e"), serverSelectionTimeoutMS="10000")
    secrets = ["Wr0ng-p%40ss", "Wr0ng-p@ss", "Unre4chable-pw", *_secrets()]
    for url in (wrong, unreachable):
        for args in (
            ["serve", "--db", url, "--port", str(_free_port())],
            ["mcp", "--db", url],
            ["mcp", "--transport", "http", "--db", url, "--port", str(_free_port())],
            ["import", "jsonl", str(SOURCES[-1][1]), "--db", url],
        ):
            done = run(*args, timeout=120)
            shown = done.stdout + done.stderr
            assert done.returncode != 0, (args, shown)
            assert "Traceback" not in shown, shown
            assert not any(secret in shown for secret in secrets), shown
            assert "mongodb://" not in shown, shown
            if args[0] != "import":
                assert "could not open the memory store" in shown, shown
            else:
                assert "llmslim import: error:" in shown, shown


def _docker(*args: str) -> None:
    subprocess.run(["docker", *args], check=True, capture_output=True, timeout=180)


def _primary_ready() -> bool:
    import pymongo

    try:
        with pymongo.MongoClient(URL, serverSelectionTimeoutMS=2000) as client:
            reply = client.admin.command("hello")
            return bool(reply.get("isWritablePrimary"))
    except pymongo.errors.PyMongoError:
        return False


@pytest.mark.skipif(not CONTAINER, reason="set LLMSLIM_E2E_MONGODB_CONTAINER to restart MongoDB")
def test_the_servers_survive_a_mongodb_restart_and_report_an_outage_cleanly(
    tmp_path, database, upstream
):
    # A short server selection timeout, so a request during the outage answers in seconds rather than 30.
    url = _with(database, serverSelectionTimeoutMS="5000")
    leaks = [
        "Traceback",
        "mongodb://",
        "ServerSelectionTimeoutError",
        "27017",
        "27018",
        *_secrets(),
    ]
    with (
        serving(
            tmp_path, "serve", "--db", url, "--upstream-url", upstream.url, LLMSLIM_API_KEYS=KEY
        ) as server,
        serving(
            tmp_path,
            "mcp",
            "--transport",
            "http",
            "--db",
            url,
            "--user-id",
            "asha",
            LLMSLIM_MCP_API_KEYS=KEY,
        ) as mcp_server,
    ):
        base = server.base
        body = {"user_id": "asha", "messages": "I moved to Pune last month."}
        assert _http("POST", base, "/v1/memories", json=body).status_code == 201
        question = {"user_id": "asha", "query": "Where did I move to?"}

        def search_until_ok() -> Any:
            """Search until MongoDB answers again; every answer before that is a clean 503."""
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                response = _http("POST", base, "/v1/memories/search", json=question)
                if response.status_code == 200:
                    return response.json()
                assert response.status_code == 503, response.text
                assert response.json()["error"]["type"] == "store_unavailable"
                time.sleep(1)
            raise AssertionError("the server did not recover after MongoDB came back")

        _docker("restart", CONTAINER or "")
        assert _until(_primary_ready, 120), "MongoDB did not come back after a restart"
        assert "Pune" in search_until_ok()["text"]
        (recalled,) = _mcp(
            f"{mcp_server.base}/mcp", KEY, [("recall", {"query": "Where did I move?"})]
        )
        assert "Pune" in _text(recalled)

        _docker("stop", CONTAINER or "")
        try:
            for method, path, payload in (
                ("POST", "/v1/memories", body),
                ("POST", "/v1/memories/search", question),
                ("GET", "/v1/memories?user_id=asha", None),
            ):
                response = _http(method, base, path, json=payload)
                assert response.status_code == 503, response.text
                assert response.headers["retry-after"] == "5"
                assert response.json()["error"]["type"] == "store_unavailable"
                assert not any(leak in response.text for leak in leaks), response.text
            assert _http("GET", base, "/healthz", key=None).status_code == 200
            (failed,) = _mcp(f"{mcp_server.base}/mcp", KEY, [("recall", {"query": "Where?"})])
            failed_text = _text(failed)
            assert failed.is_error and "can't be reached" in failed_text, failed_text
            assert not any(leak in failed_text for leak in leaks), failed_text
            # The chat endpoint goes on without memory: the caller still gets an answer.
            answered = _chat(base, "Hello again.")
            assert answered.status_code == 200 and answered.headers["x-llmslim-recall"] == "failed"
        finally:
            _docker("start", CONTAINER or "")
        assert _until(_primary_ready, 120), "MongoDB did not come back"
        assert "Pune" in search_until_ok()["text"]
        assert _http("POST", base, "/v1/memories", json=body).status_code == 201
        (stored,) = _mcp(f"{mcp_server.base}/mcp", KEY, [("remember", {"text": "Back online."})])
        assert _text(stored).startswith("Stored as ")
    for log in (server.output(), mcp_server.output()):
        assert "Traceback" not in log, log
    assert "memory store unavailable (ServerSelectionTimeoutError): answered 503" in server.output()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "--import-mode=importlib", "-q", "-rs"]))
