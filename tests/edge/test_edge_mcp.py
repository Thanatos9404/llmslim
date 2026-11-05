"""Edge cases for ``llmslim mcp``: hostile and odd input over stdio and over HTTP.

Over stdio, one real ``python -m llmslim.cli mcp`` process is driven with raw JSON-RPC lines. Over HTTP, the app
``http_app`` builds runs on a real Uvicorn on 127.0.0.1. What must hold, whatever a client sends:

- over stdio, the server keeps running after bad input and answers the next good request;
- over HTTP, bad input is a 4xx (malformed JSON-RPC a 400 with a JSON-RPC error), never a 500, and nothing is stored;
- tool arguments can't widen the server's scope, a key is never echoed, and a database outage is a tool error that
  names no host or driver error, until the database is back.

Some answers below come from the MCP SDK itself (no reply to an unparsable stdio line, a plain-text 413, the
Content-Type checks); they are pinned so that a change in them is noticed.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("mcp")
pytest.importorskip("uvicorn")
hypothesis = pytest.importorskip("hypothesis")

import httpx2  # noqa: E402
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from llmslim import count_tokens  # noqa: E402
from llmslim.mcp_server import build_server, http_app  # noqa: E402
from llmslim.memory import InMemoryStore, Memory  # noqa: E402
from llmslim.memory._errors import UNAVAILABLE_MESSAGE  # noqa: E402
from mcp import Client  # noqa: E402
from tests.test_mcp_http import INITIALIZE, JSON_HEADERS, KEY, serving  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
VERSION = {"mcp-protocol-version": "2025-11-25"}
FIRST_ANSWER_SECONDS = (
    120  # the first answer waits for the interpreter, llmslim and the SDK to import
)
ANSWER_SECONDS = 30


def _text(result):
    return "\n".join(block.text for block in result.content if getattr(block, "text", None))


def _call(name, arguments, request_id=2):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


# --------------------------------------------------------------------------- stdio, with raw JSON-RPC lines


class StdioServer:
    """A real ``llmslim mcp`` process over stdio, fed raw lines; every line it prints is one JSON-RPC message."""

    def __init__(self, db: Path) -> None:
        env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")]),
        }
        for name in ("LLMSLIM_USER_ID", "LLMSLIM_AGENT_ID", "LLMSLIM_MEMORY_DB"):
            env.pop(name, None)
        self.process = subprocess.Popen(
            [sys.executable, "-m", "llmslim.cli", "mcp", "--db", str(db), "--user-id", "asha"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            cwd=str(REPO),
        )
        self.lines: "queue.Queue[bytes]" = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.next_id = 1000

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.put(line)

    def write(self, raw) -> None:
        if isinstance(raw, (dict, list)):
            raw = json.dumps(raw).encode("ascii")
        assert self.process.stdin is not None
        self.process.stdin.write(raw if raw.endswith(b"\n") else raw + b"\n")
        self.process.stdin.flush()

    def receive(self, timeout: float = ANSWER_SECONDS):
        try:
            return json.loads(self.lines.get(timeout=timeout))
        except queue.Empty:
            pytest.fail(f"no answer within {timeout} s (the server is {self.state()})")

    def state(self) -> str:
        return "running" if self.process.poll() is None else f"gone ({self.process.returncode})"

    def request(self, method, params=None, timeout: float = ANSWER_SECONDS):
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            message["params"] = params
        self.write(message)
        answer = self.receive(timeout)
        assert answer.get("id") == self.next_id, answer
        return answer

    def call(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})["result"]

    def assert_alive(self) -> None:
        """The server answers a ping. Anything it says before that answer must be an error (the SDK sends none for
        a line it can't parse today; a JSON-RPC parse error would be fine too), never a result."""
        self.next_id += 1
        self.write({"jsonrpc": "2.0", "id": self.next_id, "method": "ping"})
        while True:
            answer = self.receive()
            if answer.get("id") == self.next_id:
                break
            assert "error" in answer and "result" not in answer, answer
        assert answer == {"jsonrpc": "2.0", "id": self.next_id, "result": {}}
        assert self.process.poll() is None

    def close(self) -> None:
        assert self.process.stdin is not None
        self.process.stdin.close()
        try:
            self.process.wait(30)
        except subprocess.TimeoutExpired:  # pragma: no cover - only when the server hangs
            self.process.kill()
            raise


@pytest.fixture(scope="module")
def stdio(tmp_path_factory):
    db = tmp_path_factory.mktemp("stdio") / "memory.db"
    server = StdioServer(db)
    server.write(INITIALIZE)
    answer = server.receive(FIRST_ANSWER_SECONDS)
    assert answer["result"]["serverInfo"]["name"] == "llmslim", answer
    server.write({"jsonrpc": "2.0", "method": "notifications/initialized"})
    server.db = db
    yield server
    server.close()
    assert server.process.returncode == 0


@pytest.mark.parametrize(
    "line",
    [
        b"{not json",
        b"",
        b"   ",
        b"null",
        b"42",
        b'"text"',
        b"[]",
        b'[{"jsonrpc": "2.0", "id": 5, "method": "ping"}]',
        b'{"id": 5, "method": "ping"}',
        b'{"jsonrpc": "1.0", "id": 5, "method": "ping"}',
        b'{"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": [1, 2]}',
        b'{"jsonrpc": "2.0", "id": 5, "method": 5}',
        b'{"jsonrpc": "2.0", "id": 1.5, "method": "ping"}',
        b'{"jsonrpc": "2.0", "id": {"a": 1}, "method": "ping"}',
        b'{"jsonrpc": "2.0", "id": 5, "result": {}}',
        b'{"jsonrpc": "2.0", "id": 5, "error": {"code": 1, "message": "x"}}',
        b'{"jsonrpc": "2.0", "method": "notifications/initialized"}',
        b'{"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 424242}}',
        b'{"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}}',
        b'{"jsonrpc": "2.0", "method": "notifications/no-such-thing"}',
        # A lone surrogate is not valid Unicode: the line can't be parsed, so nothing reaches a store.
        b'{"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "remember", '
        b'"arguments": {"text": "bad \\ud800 text"}}}',
        b"[" * 100_000 + b"]" * 100_000,
        b"\xef\xbb\xbf" + json.dumps(INITIALIZE).encode(),  # a byte-order mark before the message
    ],
)
def test_stdio_survives_garbage_and_keeps_serving(stdio, line):
    """What can't be parsed as a request (or is a notification or a response) gets no result, at most an error, and
    the server answers the next request. (Today the SDK sends no JSON-RPC parse error over stdio: a client waiting
    for an answer to such a line waits until its own timeout.)"""
    stdio.write(line)
    stdio.assert_alive()
    assert "bad" not in json.dumps(stdio.call("list_memories", {"limit": 100}))


def test_stdio_takes_crlf_lines_and_invalid_utf8(stdio):
    """Windows clients end lines with CRLF; bytes that aren't UTF-8 become U+FFFD instead of breaking the stream."""
    stdio.next_id += 1
    stdio.write(
        json.dumps({"jsonrpc": "2.0", "id": stdio.next_id, "method": "ping"}).encode() + b"\r\n"
    )
    assert stdio.receive()["id"] == stdio.next_id
    stdio.next_id += 1
    message = _call("remember", {"text": "PLACEHOLDER"}, stdio.next_id)
    stdio.write(json.dumps(message).encode().replace(b"PLACEHOLDER", b"caf\xff latte"))
    answer = stdio.receive()
    assert answer["id"] == stdio.next_id and answer["result"]["isError"] is False
    stored = [item.content for item in Memory(stdio.db).get_all(user_id="asha")]
    assert "caf� latte" in stored


def test_stdio_repeated_initialize_and_protocol_versions(stdio):
    """Initialize may come again; a known version is kept, an unknown or future one gets the server's own."""
    params = dict(INITIALIZE["params"])
    answers = {}
    for version in (
        "2024-11-05",
        "2025-06-18",
        "2025-11-25",
        "2026-07-28",
        "2099-01-01",
        "garbage",
    ):
        answer = stdio.request("initialize", {**params, "protocolVersion": version})
        answers[version] = answer["result"]["protocolVersion"]
    assert answers["2024-11-05"] == "2024-11-05" and answers["2025-11-25"] == "2025-11-25"
    # A client on the 2026-07-28 revision doesn't initialize; one that does gets the newest initialize revision.
    assert answers["2099-01-01"] == answers["garbage"] == answers["2026-07-28"] == "2025-11-25"
    for bad in (
        {"capabilities": {}, "clientInfo": {"name": "x", "version": "1"}},
        {**params, "protocolVersion": 5},
    ):
        assert stdio.request("initialize", bad)["error"]["code"] == -32602
    stdio.assert_alive()


@pytest.mark.parametrize(
    "tool, arguments, message",
    [
        ("recall", {}, "query"),
        ("recall", {"query": "x", "budget": 1.5}, "budget"),
        ("recall", {"query": "x", "budget": "lots"}, "budget"),
        ("recall", {"query": "x", "budget": -1}, "budget must be a positive number of tokens"),
        ("recall", {"query": "x", "budget": 0}, "budget must be a positive number of tokens"),
        ("recall", {"query": " \t\n "}, "query must be non-empty text"),
        ("remember", {"text": 5}, "text"),
        ("remember", {"text": ["a"]}, "text"),
        ("remember", {"text": "x", "role": "system"}, "role must be one of user, assistant"),
        ("remember", {"text": "x", "role": "USER"}, "role must be one of user, assistant"),
        ("remember", {"text": "x", "session": 5}, "session"),
        ("forget", {"memory_id": 5}, "memory_id"),
        ("forget", {}, "memory_id"),
        ("list_memories", {"limit": "many"}, "limit"),
        (
            "fit_context",
            {"text": "Some text.", "budget": 0},
            "budget must be a positive number of tokens",
        ),
        ("fit_context", {"budget": 10}, "text"),
        ("no_such_tool", {}, "Unknown tool"),
    ],
)
def test_stdio_wrong_arguments_are_tool_errors(stdio, tool, arguments, message):
    result = stdio.call(tool, arguments)
    assert result["isError"] is True and message in result["content"][0]["text"], result


def test_stdio_arguments_that_are_not_an_object_are_invalid_params(stdio):
    for params in (
        {"name": "recall", "arguments": [1]},
        {"name": 5, "arguments": {}},
        {"arguments": {}},
    ):
        assert stdio.request("tools/call", params)["error"]["code"] == -32602
    stdio.assert_alive()


def test_stdio_stores_odd_text_verbatim_and_ignores_scope_arguments(stdio):
    odd = "nul \x00 byte, tab\tand ‮right-to-left, \U0001f469‍\U0001f4bb, नमस्ते"
    result = stdio.call(
        "remember", {"text": odd, "user_id": "ravi", "agent_id": "x", "session": "odd"}
    )
    assert result["isError"] is False
    memory_id = result["content"][0]["text"].removeprefix("Stored as ").rstrip(".")
    item = Memory(stdio.db).get(memory_id)
    assert (
        item.content == odd
        and item.user_id == "asha"
        and item.agent_id is None
        and item.run_id == "odd"
    )
    assert Memory(stdio.db).get_all(user_id="ravi") == []
    recalled = stdio.call("recall", {"query": "nul byte", "session": "odd"})["content"][0]["text"]
    assert odd in recalled and recalled.startswith("Recalled conversation history")


def test_stdio_huge_budgets_and_limits_are_bounded(stdio):
    assert stdio.call("recall", {"query": "x", "budget": 10**30})["isError"] is False
    assert (
        stdio.call("fit_context", {"text": "short text", "budget": 10**30})["content"][0]["text"]
        == "short text"
    )
    listed = stdio.call("list_memories", {"limit": 10**30})
    assert listed["isError"] is False
    assert len(stdio.call("list_memories", {"limit": -5})["content"][0]["text"].splitlines()) == 1


def test_stdio_answers_interleaved_requests_by_id(stdio):
    first = stdio.next_id + 1
    for offset in range(12):
        stdio.write(_call("remember", {"text": f"interleaved fact {offset}"}, first + offset))
    stdio.next_id = first + 11
    answers = [stdio.receive() for _ in range(12)]
    assert sorted(answer["id"] for answer in answers) == list(range(first, first + 12))
    assert not any(answer["result"]["isError"] for answer in answers)
    stdio.assert_alive()


def test_stdio_ids_of_any_json_rpc_shape_come_back_as_sent(stdio):
    for request_id in ("abc", "", -1, 0, 10**40):
        stdio.write({"jsonrpc": "2.0", "id": request_id, "method": "ping"})
        assert stdio.receive() == {"jsonrpc": "2.0", "id": request_id, "result": {}}


def test_stdio_large_arguments(stdio):
    """There is no body cap over stdio: a 1.5 MB message is stored whole, and fit_context holds its budget on text
    with no space to cut at."""
    big = "word " * 300_000
    result = stdio.call("remember", {"text": big, "session": "big"})
    assert result["isError"] is False
    assert [item.content for item in Memory(stdio.db).get_all(user_id="asha", run_id="big")] == [
        big
    ]
    blob = "z" * 300_000
    fitted = stdio.call("fit_context", {"text": blob, "budget": 50})["content"][0]["text"]
    assert count_tokens(fitted) <= 50 * 1.02 and blob.startswith(fitted)
    stdio.assert_alive()


# --------------------------------------------------------------------------- HTTP


def _app(memory, *, keys=(KEY,), **options):
    return http_app(build_server(memory, user_id="asha"), api_keys=list(keys), **options)


@pytest.fixture(scope="module")
def http():
    memory = Memory()
    with serving(_app(memory)) as base, httpx2.Client(timeout=30) as client:
        client.base = base
        client.memory = memory
        yield client


def _post(client, body, *, key=KEY, headers=None, path="/mcp"):
    sent = {**JSON_HEADERS, **VERSION}
    if key is not None:
        sent["Authorization"] = f"Bearer {key}"
    sent.update(headers or {})
    content = json.dumps(body) if isinstance(body, (dict, list)) else body
    return client.post(f"{client.base}{path}", content=content, headers=sent)


@pytest.mark.parametrize(
    "body",
    [
        b'{"id": 7, "method": "ping"}',
        b'{"jsonrpc": "1.0", "id": 7, "method": "ping"}',
        b'{"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": []}',
        b'{"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": "x"}',
        b'[{"jsonrpc": "2.0", "id": 7, "method": "ping"}, {"jsonrpc": "2.0", "id": 8, "method": "ping"}]',
        b"[]",
        b"{}",
        b"true",
        b"\x1f\x8b\x08\x00",  # a gzip header: request bodies are never decompressed
        b'{"jsonrpc": "2.0", "id": 7, "method": "ping"',  # cut short
        b'{"jsonrpc": "2.0", "id": 7, "method": "ping"}{"jsonrpc": "2.0", "id": 8, "method": "ping"}',
        b'{"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "remember", '
        b'"arguments": {"text": "x"}}, "jsonrpc": "1.0"}',
    ],
)
def test_http_malformed_json_rpc_is_a_400_with_a_json_rpc_error(http, body):
    response = _post(http, body)
    assert response.status_code == 400, (response.status_code, response.text)
    error = response.json()["error"]
    assert error["code"] in (-32700, -32600, -32602) and isinstance(error["message"], str)
    assert http.memory.get_all(user_id="asha") == []


@pytest.mark.parametrize(
    "body",
    [
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 99}},
        {"jsonrpc": "2.0", "method": "notifications/no-such-thing", "params": {"x": 1}},
        {"jsonrpc": "2.0", "id": 5, "result": {}},
        {"jsonrpc": "2.0", "id": 5, "error": {"code": 1, "message": "x"}},
        # An id JSON-RPC doesn't allow makes the message a notification to the SDK: accepted, never answered.
        {"jsonrpc": "2.0", "id": 1.5, "method": "ping"},
        {"jsonrpc": "2.0", "id": None, "method": "ping"},
        {"jsonrpc": "2.0", "id": {"a": 1}, "method": "ping"},
    ],
)
def test_http_notifications_and_responses_are_accepted_with_no_answer(http, body):
    response = _post(http, body)
    assert response.status_code == 202 and response.content == b""


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "x", "budget": 0},
        {"query": "x", "budget": -10},
        {"query": "x", "budget": 2.5},
        {"query": "x", "budget": [1]},
        {"query": ""},
        {"query": None},
        {},
    ],
)
def test_http_wrong_recall_arguments_are_tool_errors(http, arguments):
    response = _post(http, _call("recall", arguments))
    assert response.status_code == 200, response.text
    assert response.json()["result"]["isError"] is True


@pytest.mark.parametrize("literal", [b"NaN", b"Infinity", b"-Infinity", b"1e400"])
def test_http_non_finite_budgets_are_tool_errors(http, literal):
    for tool, arguments in (("recall", b'"query": "x", '), ("fit_context", b'"text": "x", ')):
        body = (
            b'{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "'
            + tool.encode()
            + b'", "arguments": {'
            + arguments
            + b'"budget": '
            + literal
            + b"}}}"
        )
        response = _post(http, body)
        assert response.status_code < 500, response.text
        if response.status_code == 200:
            assert response.json()["result"]["isError"] is True, response.text


def test_http_unknown_tools_and_methods(http):
    unknown_tool = _post(http, _call("dump_everything", {})).json()
    assert unknown_tool["result"]["isError"] is True
    for method in ("memories/dump", "", "tools/call/../list", "rpc.discover"):
        response = _post(http, {"jsonrpc": "2.0", "id": 9, "method": method})
        assert response.status_code < 500 and response.json()["error"]["code"] == -32601, method


def test_http_the_body_cap_is_exact(http):
    """1 MB is accepted, a byte more is a 413 (the SDK's, in plain text), and nothing of it is stored."""

    def body_of(size):
        text = "y" * (size - len(json.dumps(_call("remember", {"text": ""}))))
        body = json.dumps(_call("remember", {"text": text})).encode()
        assert len(body) == size
        return body

    accepted = _post(http, body_of(1_000_000))
    assert accepted.status_code == 200 and accepted.json()["result"]["isError"] is False
    refused = _post(http, body_of(1_000_001))
    assert refused.status_code == 413
    stored = [len(item.content) for item in http.memory.get_all(user_id="asha")]
    for item in http.memory.get_all(user_id="asha"):
        http.memory.delete(item.id)
    assert len(stored) == 1


@pytest.mark.parametrize(
    "content_type, status",
    [
        ("application/json; charset=utf-8", 200),
        ("application/json;charset=UTF-8", 200),
        ("APPLICATION/JSON", 415),
        ("application/json-rpc", 415),
        ("text/json", 400),
        ("text/plain", 400),
        ("application/x-www-form-urlencoded", 400),
        ("multipart/form-data; boundary=x", 400),
    ],
)
def test_http_content_types(http, content_type, status):
    """Only JSON bodies are read (the SDK compares the media type case-sensitively); none is ever a 500."""
    code = _post(http, INITIALIZE, headers={"content-type": content_type}).status_code
    assert code == status if status == 200 else 400 <= code < 500


def test_http_a_body_without_a_content_type_is_refused(http):
    headers = {"Authorization": f"Bearer {KEY}", "accept": JSON_HEADERS["accept"], **VERSION}
    response = http.post(f"{http.base}/mcp", content=json.dumps(INITIALIZE), headers=headers)
    assert response.status_code == 400


@pytest.mark.parametrize(
    "accept, status",
    [
        ("application/json", 200),
        ("*/*", 200),
        ("application/*", 200),
        ("text/event-stream", 406),
        ("text/html", 406),
        ("", 406),
    ],
)
def test_http_accept_headers(http, accept, status):
    """The server answers in JSON, never with an event stream: a client must accept JSON."""
    code = _post(http, INITIALIZE, headers={"accept": accept}).status_code
    assert code == status if status == 200 else 400 <= code < 500


def test_http_protocol_versions(http):
    for version in ("2024-11-05", "2025-06-18", "2025-11-25", "2099-01-01"):
        body = {**INITIALIZE, "params": {**INITIALIZE["params"], "protocolVersion": version}}
        response = _post(http, body)
        assert response.status_code == 200 and "result" in response.json(), version
    missing = {
        **INITIALIZE,
        "params": {"capabilities": {}, "clientInfo": {"name": "x", "version": "1"}},
    }
    assert _post(http, missing).json()["error"]["code"] == -32602
    listing = {"jsonrpc": "2.0", "id": 4, "method": "tools/list"}
    for header in ("2024-11-05", "2025-11-25"):
        assert (
            "tools"
            in _post(http, listing, headers={"mcp-protocol-version": header}).json()["result"]
        )
    for header in ("1999-01-01", "not-a-version"):
        assert (
            400 <= _post(http, listing, headers={"mcp-protocol-version": header}).status_code < 500
        )
    # The 2026-07-28 revision is stateless: each request carries its version and capabilities in params._meta.
    bare = _post(http, listing, headers={"mcp-protocol-version": "2026-07-28"})
    assert bare.status_code == 400 and bare.json()["error"]["code"] == -32602


@pytest.mark.parametrize(
    "authorization, status",
    [
        (f"bearer {KEY}", 200),
        (f"BEARER {KEY}", 200),
        (f"Bearer  {KEY}", 200),
        (f"Bearer\t{KEY}", 401),
        (KEY, 401),
        (f"Basic {KEY}", 401),
        (f"Token {KEY}", 401),
        (f"Bearer {KEY}x", 401),
        (f"Bearer {KEY[:-1]}", 401),
        (f"Bearer {KEY.upper()}", 401),
        ("Bearer", 401),
        ("", 401),
    ],
)
def test_http_authorization_variants_and_the_key_is_never_echoed(http, authorization, status):
    headers = {**JSON_HEADERS, **VERSION, "Authorization": authorization}
    response = http.post(f"{http.base}/mcp", content=json.dumps(INITIALIZE), headers=headers)
    assert response.status_code == status
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
        assert KEY[:12] not in response.text and KEY.upper()[:12] not in response.text
        assert response.json()["error"]["type"] == "unauthorized"


def test_http_methods_on_the_endpoint(http):
    auth = {"Authorization": f"Bearer {KEY}"}
    for method in ("GET", "HEAD", "OPTIONS", "DELETE", "PUT", "PATCH"):
        response = http.request(method, f"{http.base}/mcp", headers=auth)
        assert response.status_code == 405 and response.headers["allow"] == "POST", method
        assert http.request(method, f"{http.base}/mcp").status_code == 401, method
    # A query string doesn't change the endpoint; a trailing slash is redirected to it, never served elsewhere.
    assert _post(http, INITIALIZE, path="/mcp?probe=1").status_code == 200
    slash = _post(http, INITIALIZE, path="/mcp/")
    assert slash.status_code in (307, 308, 404)
    if slash.status_code != 404:
        assert slash.headers["location"].endswith("/mcp")
    for path in ("/", "/mcp/x", "/MCP", "/healthz/x"):
        assert _post(http, INITIALIZE, path=path).status_code == 404, path


def test_http_health_answers_without_a_key_and_nothing_else_does(http):
    assert http.get(f"{http.base}/healthz").json() == {"status": "ok"}
    for method, path in (("POST", "/healthz"), ("GET", "/healthz/"), ("GET", "/elsewhere")):
        response = http.request(method, f"{http.base}{path}")
        assert response.status_code == 401, (method, path)


def test_http_scope_arguments_are_dropped(http):
    stored = _post(http, _call("remember", {"text": "my locker code is 4417", "user_id": "ravi"}))
    memory_id = stored.json()["result"]["content"][0]["text"].removeprefix("Stored as ").rstrip(".")
    try:
        item = http.memory.get(memory_id)
        assert item.user_id == "asha" and http.memory.get_all(user_id="ravi") == []
        other = http.memory.add("ravi's own secret", user_id="ravi")[0]
        for arguments in ({"memory_id": other.id}, {"memory_id": other.id, "user_id": "ravi"}):
            answer = _post(http, _call("forget", arguments)).json()["result"]["content"][0]["text"]
            assert answer == f"No stored message has the id {other.id}."
        assert http.memory.get(other.id) is not None
        recalled = _post(http, _call("recall", {"query": "secret", "user_id": "ravi"})).text
        assert "ravi's own secret" not in recalled
    finally:
        http.memory.delete_all(user_id="asha")
        http.memory.delete_all(user_id="ravi")


@pytest.mark.parametrize(
    "host, status",
    [
        ("LOCALHOST", 200),
        ("localhost.", 200),
        ("127.0.0.1", 200),
        ("127.255.255.254:8000", 200),
        ("[::1]:8000", 200),
        ("app.localhost:8000", 200),
        ("0.0.0.0", 403),
        ("127.1", 403),
        ("localhost.evil.example", 403),
        ("evil.example#@localhost", 403),
        ("192.168.1.10", 403),
    ],
)
def test_http_keyless_host_names(host, status):
    memory = Memory()
    with serving(_app(memory, keys=())) as base, httpx2.Client(timeout=30) as client:
        client.base = base
        response = _post(client, INITIALIZE, key=None, headers={"Host": host})
    assert response.status_code == status
    if status == 403:
        assert response.json()["error"]["type"] == "forbidden"


def test_http_keyless_origins():
    memory = Memory()
    with serving(_app(memory, keys=())) as base, httpx2.Client(timeout=30) as client:
        client.base = base
        for origin, status in (
            ("http://localhost", 200),
            ("https://app.localhost:3000", 200),
            ("http://127.0.0.1:9", 200),
            ("null", 403),
            ("file://", 403),
            ("http://localhost.evil.example", 403),
            ("http://evil.example?localhost", 403),
            ("chrome-extension://abcdef", 403),
            ("http://[::1", 403),
        ):
            response = _post(client, INITIALIZE, key=None, headers={"Origin": origin})
            assert response.status_code == status, origin
        stored = _post(
            client,
            _call("remember", {"text": "x"}),
            key=None,
            headers={"Origin": "https://evil.example"},
        )
        assert stored.status_code == 403
    assert memory.get_all(user_id="asha") == []


def test_websocket_connections_never_reach_the_tools():
    """Only HTTP passes the key check; a WebSocket upgrade to the endpoint is closed without a handshake."""
    app = _app(Memory())
    sent = []

    async def run():
        messages = iter([{"type": "websocket.connect"}])

        async def receive():
            return next(messages, {"type": "websocket.disconnect", "code": 1000})

        async def send(message):
            sent.append(message)

        scope = {
            "type": "websocket",
            "path": "/mcp",
            "raw_path": b"/mcp",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1")],
            "scheme": "ws",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 50000),
            "subprotocols": [],
            "root_path": "",
        }
        await app(scope, receive, send)

    asyncio.run(run())
    assert sent and sent[0]["type"] == "websocket.close"
    assert not any(message["type"] == "websocket.accept" for message in sent)


# --------------------------------------------------------------------------- a database that is down


class _Flaky(InMemoryStore):
    """A store whose database is down until ``down`` is cleared, with an error that names its host and password."""

    def __init__(self, error):
        super().__init__()
        self.error = error
        self.down = True

    def _check(self):
        if self.down:
            raise self.error

    def add(self, items):
        self._check()
        return super().add(items)

    def list(self, scope, **window):
        self._check()
        return super().list(scope, **window)

    def get(self, item_id):
        self._check()
        return super().get(item_id)

    def delete(self, item_id):
        self._check()
        return super().delete(item_id)


def _outage_errors():
    """The outage errors of the database drivers installed here (none: the test is skipped)."""
    errors = []
    try:
        import pymongo.errors
    except ImportError:  # pragma: no cover - pymongo comes with the mongodb extra
        pass
    else:
        errors.append(
            pymongo.errors.ServerSelectionTimeoutError("db.example.com:27017 password=hunter2")
        )
    try:
        import psycopg
    except ImportError:  # pragma: no cover - psycopg comes with the postgres extra
        pass
    else:
        errors.append(
            psycopg.OperationalError("connection to db.example.com failed: password=hunter2")
        )
    return errors


@pytest.mark.parametrize("error", _outage_errors(), ids=lambda e: type(e).__name__)
def test_an_outage_is_a_tool_error_that_names_nothing_and_recovers(error):
    store = _Flaky(error)
    server = build_server(Memory(store), user_id="asha")

    async def run():
        async with Client(server) as client:
            down = {
                tool: await client.call_tool(tool, arguments)
                for tool, arguments in (
                    ("remember", {"text": "I moved to Pune."}),
                    ("recall", {"query": "Where do I live?"}),
                    ("list_memories", {}),
                    ("forget", {"memory_id": "abc"}),
                )
            }
            fitted = await client.call_tool("fit_context", {"text": "short", "budget": 10})
            store.down = False
            await client.call_tool("remember", {"text": "I moved to Pune."})
            back = await client.call_tool("recall", {"query": "Where do I live?"})
            return down, fitted, back

    down, fitted, back = asyncio.run(run())
    for tool, result in down.items():
        assert result.is_error and UNAVAILABLE_MESSAGE in _text(result), tool
        assert "hunter2" not in _text(result) and "db.example.com" not in _text(result), tool
    assert not fitted.is_error and _text(fitted) == "short"
    assert "Pune" in _text(back) and not back.is_error


def test_an_unexpected_store_error_does_not_reach_the_client():
    class Broken(InMemoryStore):
        def list(self, scope, **window):
            raise RuntimeError("postgresql://llmslim:hunter2@db.example.com/llmslim broke")

    server = build_server(Memory(Broken()), user_id="asha")

    async def run():
        async with Client(server) as client:
            return await client.call_tool("recall", {"query": "x"})

    result = asyncio.run(run())
    assert (
        result.is_error and "hunter2" not in _text(result) and "db.example.com" not in _text(result)
    )


# --------------------------------------------------------------------------- properties of the tools


_TEXT = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",)
    ),  # no lone surrogates: the transports refuse them
    min_size=1,
    max_size=400,
).filter(lambda text: text.strip())


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    texts=st.lists(_TEXT, min_size=1, max_size=6), budget=st.integers(min_value=1, max_value=400)
)
def test_remember_is_verbatim_and_recall_holds_its_budget(texts, budget):
    memory = Memory()
    server = build_server(memory, user_id="asha")

    async def run():
        async with Client(server) as client:
            ids = []
            for text in texts:
                result = await client.call_tool("remember", {"text": text})
                ids.append(_text(result).removeprefix("Stored as ").rstrip("."))
            recalled = await client.call_tool(
                "recall", {"query": "what did I say?", "budget": budget}
            )
            return ids, recalled

    ids, recalled = asyncio.run(run())
    assert [memory.get(memory_id).content for memory_id in ids] == texts
    answer = _text(recalled)
    assert not recalled.is_error
    if answer.startswith("Recalled conversation history"):
        body = answer.split("\n\n", 1)[1]
        assert count_tokens(body) <= budget
    else:
        assert answer.startswith("No stored message fits the")


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    text=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=3000),
    budget=st.integers(min_value=1, max_value=600),
)
def test_fit_context_stays_within_two_percent_of_its_budget(text, budget):
    server = build_server(Memory(), user_id="asha")

    async def run():
        async with Client(server) as client:
            return await client.call_tool("fit_context", {"text": text, "budget": budget})

    result = asyncio.run(run())
    assert not result.is_error
    fitted = _text(result)
    assert count_tokens(fitted) <= budget * 1.02
    if count_tokens(text) <= budget:
        assert fitted == text
