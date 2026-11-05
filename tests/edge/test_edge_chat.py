"""Edge cases of llmslim serve's chat endpoint (POST /v1/chat/completions, GET /v1/models), against stand-in upstreams.

Most tests use the httpx MockTransport upstream of tests/test_server_chat.py. A few run a stand-in upstream on
127.0.0.1 (a raw asyncio server that can hang, break a chunked body or close early), and one runs the app under
uvicorn, so a real client can hang up mid-stream. Nothing reaches any other host, and every key is fake.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional

import pytest

pytest.importorskip("starlette")
httpx = pytest.importorskip("httpx")
hypothesis = pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from llmslim import _openai_chat as chat_module  # noqa: E402
from llmslim._openai_chat import RECALL_PREAMBLE, StreamReader  # noqa: E402
from llmslim.memory import Memory  # noqa: E402
from llmslim.server import ChatUpstream, create_app  # noqa: E402
from tests.test_server_chat import (  # noqa: E402
    ASHA,
    AUTH,
    KEY,
    UPSTREAM,
    Chunks,
    FakeUpstream,
    Transport,
    _clock,
    _cut_off,
    _raise,
    _scope,
    chunk,
    completion,
    sse,
    stored,
    streamed,
)

FAKE_KEY = "sk-test-EDGE-0123456789abcdefABCDEF"  # never a real key
SETTINGS = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
APP_SETTINGS = settings(
    max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow]
)


def make_app(memory: Memory, fake: Optional[FakeUpstream] = None, **options: Any) -> Any:
    app_options = {
        name: options.pop(name) for name in ("max_budget", "max_body_bytes") if name in options
    }
    url = options.pop("url", UPSTREAM)
    if fake is not None:
        options["transport"] = Transport(fake)
    config = ChatUpstream(url, api_key=options.pop("api_key", FAKE_KEY), **options)
    return create_app(memory, api_keys=[KEY], chat=config, **app_options)


@pytest.fixture
def memory() -> Memory:
    return Memory(clock=_clock())


@pytest.fixture
def fake() -> FakeUpstream:
    return FakeUpstream()


@pytest.fixture
def client(memory, fake):
    with TestClient(make_app(memory, fake)) as test_client:
        yield test_client


def post(client: Any, messages: Any, *, headers: Any = None, **body: Any) -> Any:
    payload = {"model": "m", "messages": messages, **body}
    return client.post("/v1/chat/completions", json=payload, headers={**AUTH, **(headers or {})})


def hi(text: str = "hi") -> List[Dict[str, Any]]:
    return [{"role": "user", "content": text}]


# --------------------------------------------------------------------------- reading a stream


# Pieces of a reply, so a cut can fall inside any of them: JSON escapes, emoji with joiners, RTL, CJK and Indic.
TEXT = st.lists(
    st.sampled_from(
        ["a", "b", " ", ".", "\n", "\t", '"', "\\", "{}", "[]", ":", ","]
        + ["\u00e9", "\U0001f44b", "\U0001f468\u200d\U0001f469\u200d\U0001f467", "\u4e2d\u6587"]
        + [
            "\u05e2\u05d1\u05e8\u05d9\u05ea",
            "\u0639\u0631\u0628\u064a",
            "\u0928\u092e\u0938\u094d\u0924\u0947",
        ]
        + ["\u200b", "\x00"]
    ),
    max_size=6,
).map("".join)


@SETTINGS
@given(
    texts=st.lists(TEXT, min_size=1, max_size=8),
    crlf=st.booleans(),
    noise=st.booleans(),
    raw=st.booleans(),
    cuts=st.lists(st.integers(min_value=0, max_value=4000), max_size=12),
)
def test_any_chunking_of_a_stream_reads_the_same_reply(texts, crlf, noise, raw, cuts):
    parts = sse(*texts)
    if raw:  # UTF-8 as it is rather than \u escapes, so a cut can fall inside a character's bytes
        parts = [
            b"data: " + json.dumps(json.loads(p[6:]), ensure_ascii=False).encode() + b"\n\n"
            if p.startswith(b"data: {")
            else p
            for p in parts
        ]
    if noise:  # keep-alive comments and the fields a reader skips, between events
        parts = [p + b": keep-alive\n\nevent: message\nid: 7\nretry: 1000\n\n" for p in parts]
    stream = b"".join(parts)
    if crlf:
        stream = stream.replace(b"\n", b"\r\n")
    reader = StreamReader()
    previous = 0
    for cut in sorted({c % (len(stream) + 1) for c in cuts}):
        reader.feed(stream[previous:cut])
        previous = cut
    reader.feed(stream[previous:])
    reader.close()
    assert reader.complete and reader.text == "".join(texts)


def test_finish_reason_or_done_alone_each_count_as_finished():
    for parts in (sse("x", done=False), sse("x", finish=False)):
        reader = StreamReader()
        for part in parts:
            reader.feed(part)
        reader.close()
        assert reader.complete and reader.text == "x"


def test_a_long_stream_is_relayed_whole_and_stored_once(client, fake, memory):
    parts = sse(*[f"w{i} " for i in range(2000)])
    fake.replies.append(lambda request: streamed(list(parts)))
    started = time.perf_counter()
    response = post(client, hi("long"), headers=ASHA, stream=True)
    assert time.perf_counter() - started < 20
    assert response.content == b"".join(parts)
    assert stored(memory, user_id="asha") == [
        ("user", "long"),
        ("assistant", "".join(f"w{i} " for i in range(2000))),
    ]


def test_an_event_just_under_the_line_limit_is_read_in_any_chunking(client, fake, memory):
    text = "y" * (chat_module.MAX_EVENT_BYTES - 500)
    whole = b"".join(sse(text))
    pieces = [whole[i : i + 65536] for i in range(0, len(whole), 65536)]
    fake.replies.append(lambda request: streamed(pieces))
    response = post(client, hi("big"), headers=ASHA, stream=True)
    assert response.content == whole
    assert stored(memory, user_id="asha")[-1] == ("assistant", text)


@pytest.mark.parametrize(
    "tail",
    [
        b'event: error\ndata: {"error": {"message": "overloaded", "type": "server_error"}}\n\n',
        b'data: {"error": "boom"}\n\n',
        b"data: 42\n\n",  # not an object
        b'data: {"choices": [{"index": 0, "delta": {"content": "x"}}]',  # cut before its newline
    ],
)
def test_a_stream_with_an_error_or_a_broken_last_event_is_not_stored(client, fake, memory, tail):
    parts = [*sse("partial", finish=False, done=False), tail]
    fake.replies.append(lambda request: streamed(parts))
    response = post(client, hi(), headers=ASHA, stream=True)
    assert response.status_code == 200 and response.content == b"".join(parts)
    assert memory.get_all(user_id="asha") == []


def test_streamed_choices_other_than_the_first_and_usage_chunks_are_not_stored(
    client, fake, memory
):
    parts = [
        chunk({"role": "assistant", "content": ""}),
        chunk({"content": "one"}, index=1),
        chunk({"content": "zero"}),
        chunk({"content": " more"}, index=1),
        chunk({}, "stop", index=1),
        chunk({}, "stop"),
        b'data: {"id": "c", "choices": [], "usage": {"total_tokens": 3}}\n\n',
        b"data: [DONE]\n\n",
    ]
    fake.replies.append(lambda request: streamed(parts))
    post(client, hi(), headers=ASHA, stream=True, n=2, stream_options={"include_usage": True})
    assert stored(memory, user_id="asha") == [("user", "hi"), ("assistant", "zero")]
    assert fake.last["n"] == 2 and fake.last["stream_options"] == {"include_usage": True}


# --------------------------------------------------------------------------- answers and errors from the upstream


def test_non_streamed_choices_are_read_by_their_index(client, fake, memory):
    answer = {
        "choices": [
            {"index": 1, "message": {"role": "assistant", "content": "second"}},
            {
                "index": 0,
                "message": {"role": "assistant", "content": [{"type": "text", "text": "a"}]},
            },
        ]
    }
    fake.replies.append(lambda request: httpx.Response(200, json=answer))
    response = post(client, hi(), headers=ASHA, n=2)
    assert response.json() == answer  # passed on as it came
    assert stored(memory, user_id="asha") == [("user", "hi"), ("assistant", "a")]


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("stream", [False, True])
def test_redirects_are_502s_that_name_no_location(client, fake, memory, status, stream):
    fake.replies.append(
        lambda request: httpx.Response(status, headers={"location": "https://elsewhere.test/v1"})
    )
    response = post(client, hi(), headers=ASHA, stream=stream)
    assert response.status_code == 502 and "elsewhere" not in response.text
    assert "location" not in response.headers
    assert response.json()["error"]["type"] == "upstream_error"
    assert len(fake.requests) == 1 and memory.get_all(user_id="asha") == []


@pytest.mark.parametrize(
    "status, expected", [(401, 502), (403, 502), (407, 502), (500, 502), (501, 502), (505, 502)]
)
@pytest.mark.parametrize("stream", [False, True])
def test_upstream_failures_map_to_a_sane_status(client, fake, memory, status, expected, stream):
    fake.replies.append(
        lambda request: (
            streamed([b'{"error": {"message": "nope"}}'], status=status)
            if stream
            else httpx.Response(status, json={"error": {"message": "nope"}})
        )
    )
    response = post(client, hi(), headers=ASHA, stream=stream)
    assert response.status_code == expected
    assert response.headers["content-type"].startswith("application/json")
    kind = "upstream_auth_error" if status in (401, 403, 407) else "upstream_error"
    assert response.json()["error"]["type"] == kind
    assert memory.get_all(user_id="asha") == []


@pytest.mark.parametrize(
    "retry_after, kept",
    [
        ("30", True),
        ("Wed, 21 Oct 2026 07:28:00 GMT", True),
        ("<script>", False),
        ("9" * 65, False),
        ("1; rm -rf /", False),
    ],
)
def test_retry_after_is_kept_only_when_it_looks_like_one(client, fake, retry_after, kept):
    for status in (429, 503):
        fake.replies.append(
            lambda request, s=status: httpx.Response(
                s, json={"error": {"message": "slow down"}}, headers={"retry-after": retry_after}
            )
        )
        response = post(client, hi(), headers=ASHA)
        assert response.status_code == status
        assert response.headers.get("retry-after") == (retry_after if kept else None)
    # Not on other statuses, where it means nothing to the client.
    fake.replies.append(lambda request: httpx.Response(500, headers={"retry-after": "30"}))
    assert "retry-after" not in post(client, hi(), headers=ASHA).headers


def test_an_upstream_error_body_too_large_to_read_keeps_its_status(client, fake):
    huge = json.dumps({"error": {"message": "x" * (chat_module.MAX_ERROR_BYTES + 10)}})
    fake.replies.append(lambda request: httpx.Response(400, content=huge.encode()))
    response = post(client, hi(), headers=ASHA)
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "the upstream answered HTTP 400"


def test_answers_at_and_over_eight_megabytes(client, fake, memory):
    body = json.dumps(completion("fits")).encode()
    exact = body[:-1] + b" " * (chat_module.MAX_UPSTREAM_BYTES - len(body)) + b"}"
    assert len(exact) == chat_module.MAX_UPSTREAM_BYTES
    fake.replies.append(lambda request: httpx.Response(200, content=exact))
    response = post(client, hi(), headers=ASHA)
    assert response.status_code == 200 and len(response.content) == len(exact)
    assert stored(memory, user_id="asha")[-1] == ("assistant", "fits")
    over = exact + b" "
    fake.replies.append(lambda request: httpx.Response(200, content=over))
    response = post(client, hi("again"), headers=ASHA)
    assert response.status_code == 502 and "too large" in response.json()["error"]["message"]
    assert stored(memory, user_id="asha")[-1] == ("assistant", "fits")  # nothing new


def test_a_200_that_is_not_json_is_passed_on_and_not_stored(client, fake, memory):
    fake.replies.append(
        lambda request: httpx.Response(
            200, content=b"<p>hi</p>", headers={"content-type": "text/html"}
        )
    )
    response = post(client, hi(), headers=ASHA)
    assert response.status_code == 200 and response.content == b"<p>hi</p>"
    assert memory.get_all(user_id="asha") == []


# --------------------------------------------------------------------------- the upstream key never leaks


def test_the_upstream_key_is_redacted_from_every_field_and_never_logged(
    client, fake, memory, caplog
):
    echoes = [
        lambda request: httpx.Response(
            400,
            json={
                "error": {
                    "message": f"key {FAKE_KEY} rejected",
                    "type": FAKE_KEY,
                    "param": f"auth={FAKE_KEY}",
                    "code": FAKE_KEY,
                }
            },
        ),
        lambda request: httpx.Response(429, json={"error": FAKE_KEY}, headers={"retry-after": "3"}),
        lambda request: httpx.Response(404, content=f"no route for {FAKE_KEY}".encode()),
        lambda request: httpx.Response(200, json={"choices": [], "echo": FAKE_KEY}),
        lambda request: streamed(
            [*sse("ok")[:2], f": comment {FAKE_KEY}\n\n".encode(), *sse()[1:]]
        ),
        lambda request: streamed([f"data: {FAKE_KEY}".encode()]),  # the very first chunk
    ]
    fake.replies += echoes
    with caplog.at_level(logging.DEBUG):
        responses = [
            post(client, hi(), headers=ASHA, stream=index >= 4) for index in range(len(echoes))
        ]
        fake.replies.append(lambda request: httpx.Response(200, json={"data": [{"id": FAKE_KEY}]}))
        responses.append(client.get("/v1/models", headers=AUTH))
    assert [r.status_code for r in responses] == [400, 429, 404, 502, 200, 200, 502]
    assert responses[1].headers["retry-after"] == "3"
    assert responses[0].json()["error"]["type"] == "[redacted]"
    for response in responses:
        assert FAKE_KEY not in response.text
        assert FAKE_KEY not in json.dumps(dict(response.headers))
    logged = "\n".join(
        f"{record.getMessage()} {record.exc_text or ''} {record.args!r}"
        for record in caplog.records
    )
    assert FAKE_KEY not in logged
    assert memory.get_all(user_id="asha") == []


def test_the_client_key_never_reaches_the_upstream(client, fake):
    post(client, hi(), headers={**ASHA, "X-Api-Key": "client-secret", "Cookie": "s=1"})
    sent = dict(fake.requests[-1].headers)
    assert sent["authorization"] == f"Bearer {FAKE_KEY}"
    assert KEY not in json.dumps(sent) and "client-secret" not in json.dumps(sent)
    assert "cookie" not in sent and "x-llmslim-user-id" not in sent


# --------------------------------------------------------------------------- a stand-in upstream on 127.0.0.1


Script = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]


class StandIn:
    """An upstream on 127.0.0.1 that answers each connection with the next script (raw HTTP/1.1 bytes)."""

    def __init__(self, *scripts: Script) -> None:
        self.scripts = list(scripts)
        self.closed = threading.Event()  # a connection's client hung up
        self.loop = asyncio.new_event_loop()
        ready = threading.Event()

        async def start() -> None:
            self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
            self.port = self.server.sockets[0].getsockname()[1]
            ready.set()

        def run() -> None:
            self.loop.run_until_complete(start())
            self.loop.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert ready.wait(5)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            length = re.search(rb"(?i)content-length:\s*(\d+)", head)
            if length:
                await reader.readexactly(int(length.group(1)))
            await self.scripts.pop(0)(reader, writer)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    def stop(self) -> None:
        async def close() -> None:
            self.server.close()

        asyncio.run_coroutine_threadsafe(close(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)


SSE_HEAD = (
    b"HTTP/1.1 200 OK\r\ncontent-type: text/event-stream\r\ntransfer-encoding: chunked\r\n"
    b"connection: close\r\n\r\n"
)


def _chunked(data: bytes) -> bytes:
    return b"%x\r\n%s\r\n" % (len(data), data)


async def _wait_for_hangup(reader: asyncio.StreamReader, events: StandIn) -> None:
    """Holds the connection open, as a slow model does, until the client hangs up."""
    await reader.read()
    events.closed.set()


@pytest.fixture
def stand_in():
    servers: List[StandIn] = []

    def start(*scripts: Script) -> StandIn:
        servers.append(StandIn(*scripts))
        return servers[-1]

    yield start
    for server in servers:
        server.stop()


def test_a_real_upstream_that_never_answers_is_a_504(memory, stand_in):
    upstream = stand_in(lambda reader, writer: _wait_for_hangup(reader, upstream))
    with TestClient(make_app(memory, url=upstream.url, read_timeout=0.3)) as client:
        started = time.perf_counter()
        response = post(client, hi(), headers=ASHA)
    assert time.perf_counter() - started < 5
    assert response.status_code == 504 and response.json()["error"]["type"] == "upstream_timeout"
    assert upstream.closed.wait(5)  # the server let go of the upstream connection
    assert memory.get_all(user_id="asha") == []


def test_a_real_upstream_that_stalls_or_closes_mid_stream_is_not_stored(memory, stand_in):
    async def stalls(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(SSE_HEAD + b"".join(_chunked(p) for p in sse("Hello")[:2]))
        await writer.drain()
        await _wait_for_hangup(reader, upstream)

    async def closes(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(SSE_HEAD + b"".join(_chunked(p) for p in sse("Hello")[:2]))
        await writer.drain()  # and closes without the last chunk

    async def closes_mid_chunk(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # The chunk says 1,024 bytes and the connection ends after one whole event of them. (A break inside a
        # line is fix/edge-chat-endpoint's: there the error event was glued to the half line.)
        writer.write(SSE_HEAD + b"400\r\n" + sse("Hello")[0])
        await writer.drain()

    async def closes_at_once(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        return None

    upstream = stand_in(stalls, closes, closes_mid_chunk, closes_at_once)
    with TestClient(make_app(memory, url=upstream.url, read_timeout=0.3)) as client:
        for _ in range(3):
            response = post(client, hi(), headers=ASHA, stream=True)
            assert response.status_code == 200
            assert response.content.startswith(sse("Hello")[0])
            last = response.content.rstrip().split(b"\n")[-1]
            assert json.loads(last[len(b"data: ") :])["error"]["type"] == "upstream_error"
            assert b"[DONE]" not in response.content
        response = post(client, hi(), headers=ASHA, stream=True)
        assert response.status_code == 502
        assert response.json()["error"]["type"] == "upstream_unreachable"
    assert upstream.closed.is_set()
    assert memory.get_all(user_id="asha") == []


def test_a_port_with_nothing_listening_is_a_clean_502_or_504(memory):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]  # closed again before the request: nothing listens there
    with TestClient(
        make_app(memory, url=f"http://127.0.0.1:{port}/v1", connect_timeout=0.2)
    ) as client:
        answers = [post(client, hi(), headers=ASHA), client.get("/v1/models", headers=AUTH)]
    # Linux refuses at once (502); Windows retries a refused connection until the connect timeout (504).
    for response in answers:
        assert (response.status_code, response.json()["error"]["type"]) in (
            (502, "upstream_unreachable"),
            (504, "upstream_timeout"),
        )
        assert str(port) not in response.text and "127.0.0.1" not in response.text
    assert memory.get_all(user_id="asha") == []


def test_a_client_that_hangs_up_under_uvicorn_keeps_its_turn_once(memory, stand_in):
    uvicorn = pytest.importorskip("uvicorn")

    async def slow(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(SSE_HEAD + b"".join(_chunked(p) for p in sse("Once")[:2]))
        await writer.drain()
        await _wait_for_hangup(reader, upstream)

    async def whole(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(
            SSE_HEAD + b"".join(_chunked(p) for p in sse("Once upon a time")) + b"0\r\n\r\n"
        )
        await writer.drain()

    upstream = stand_in(slow, whole)
    app = make_app(memory, url=upstream.url)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        body = json.dumps(
            {"model": "m", "stream": True, "messages": hi("Tell me a story")}
        ).encode()
        head = (
            f"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
            f"Authorization: Bearer {KEY}\r\nX-LLMSlim-User-Id: asha\r\n"
            f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        ).encode()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as caller:
            caller.sendall(head + body)
            got = b""
            while b'"Once"' not in got:
                got += caller.recv(4096)
        # The caller hung up mid-reply: the server lets go of the upstream and keeps what the caller said.
        assert upstream.closed.wait(5)
        while not memory.get_all(user_id="asha") and time.monotonic() < deadline:
            time.sleep(0.02)
        assert stored(memory, user_id="asha") == [("user", "Tell me a story")]
        # The caller asks again and hears the whole reply: only the reply is new.
        answer = httpx.post(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            content=body,
            headers={**AUTH, **ASHA, "content-type": "application/json"},
            timeout=5,
        )
        assert answer.status_code == 200 and b"[DONE]" in answer.content
        while len(memory.get_all(user_id="asha")) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert stored(memory, user_id="asha") == [
            ("user", "Tell me a story"),
            ("assistant", "Once upon a time"),
        ]
    finally:
        server.should_exit = True
        thread.join(10)


# --------------------------------------------------------------------------- cut off, then retried


def _story(*history: Dict[str, Any]) -> bytes:
    return json.dumps({"model": "m", "stream": True, "messages": list(history)}).encode()


def test_a_retry_after_the_window_stores_the_turn_again(memory, fake, monkeypatch):
    now = [5000.0]
    # The relay's own clock only: patching time.monotonic itself would move the event loop's clock too.
    monkeypatch.setattr(chat_module, "time", SimpleNamespace(monotonic=lambda: now[0]))
    app = make_app(memory, fake)
    body = _story({"role": "user", "content": "Tell me a story"})

    async def scenario() -> None:
        await _cut_off(app, fake, body)
        now[0] += (
            chat_module.CUT_OFF_RETRY_SECONDS - 1
        )  # inside the window: the turn is not stored again
        await _cut_off(app, fake, body)
        now[0] += chat_module.CUT_OFF_RETRY_SECONDS  # past it: a new turn
        await _cut_off(app, fake, body)

    asyncio.run(asyncio.wait_for(scenario(), 10))
    assert stored(memory, user_id="asha") == [("user", "Tell me a story")] * 2


def test_cut_off_requests_with_the_same_words_but_another_history_or_session_are_new_turns(
    memory, fake
):
    app = make_app(memory, fake)
    ask = {"role": "user", "content": "And then?"}

    async def scenario() -> None:
        await _cut_off(app, fake, _story(ask))
        await _cut_off(app, fake, _story({"role": "user", "content": "A story"}, ask))
        await _cut_off(app, fake, _story(ask), headers=[(b"x-llmslim-session-id", b"call-2")])
        await _cut_off(app, fake, _story(ask))  # the first one again: a retry, not stored

    asyncio.run(asyncio.wait_for(scenario(), 10))
    assert [i.content for i in memory.get_all(user_id="asha")] == ["And then?"] * 3


# --------------------------------------------------------------------------- what a request carries


def test_a_thousand_messages_are_fine_and_one_more_is_a_400(client, fake):
    many = [{"role": "user" if i % 2 else "assistant", "content": f"m{i}"} for i in range(1000)]
    assert post(client, many, headers=ASHA).status_code == 200
    response = post(client, [*many, {"role": "user", "content": "one more"}], headers=ASHA)
    assert response.status_code == 400 and "more than 1000" in response.json()["error"]["message"]
    assert len(fake.requests) == 1


@pytest.mark.parametrize(
    "content",
    [
        None,
        "",
        "   ",
        [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}],
        [],
    ],
)
def test_a_latest_user_message_without_text_recalls_and_stores_no_user_turn(
    client, fake, memory, content
):
    memory.add("I live in Pune.", user_id="asha")
    messages = [{"role": "user", "content": content}]
    response = post(client, messages, headers=ASHA)
    assert response.status_code == 200 and response.headers["x-llmslim-recall"] == "none"
    assert fake.last["messages"] == messages  # forwarded as sent, images included
    assert stored(memory, user_id="asha") == [("user", "I live in Pune."), ("assistant", "reply 1")]


def test_text_parts_are_stored_and_other_parts_forwarded_untouched(client, fake, memory):
    parts = [
        {"type": "text", "text": "What is in"},
        {"type": "image_url", "image_url": {"url": "https://img.test/a.png", "detail": "low"}},
        {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
        {"type": "text", "text": "this picture?"},
        {"type": "file", "file": {"file_id": "f1"}},
    ]
    post(client, [{"role": "user", "content": parts}], headers=ASHA)
    assert fake.last["messages"][-1] == {"role": "user", "content": parts}
    assert stored(memory, user_id="asha")[0] == ("user", "What is in\nthis picture?")


def test_tool_messages_and_unknown_roles_are_forwarded_but_never_stored(client, fake, memory):
    call = {"id": "c1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
    messages = [
        {"role": "developer", "content": "Be brief."},
        {"role": "user", "content": "Look it up"},
        {"role": "assistant", "content": None, "tool_calls": [call]},
        {"role": "tool", "tool_call_id": "c1", "content": "secret tool output"},
        {"role": "critic", "content": "a role this server doesn't know"},
    ]
    response = post(client, messages, headers=ASHA)
    assert response.status_code == 200
    assert fake.last["messages"] == messages  # nothing recalled yet, so nothing added
    # The latest user message is not the last one, so it is history and is not stored; the reply is.
    assert stored(memory, user_id="asha") == [("assistant", "reply 1")]


ROLES = st.sampled_from(["system", "developer", "user", "assistant", "tool", "tool_call"])


@APP_SETTINGS
@given(roles=st.lists(ROLES, min_size=1, max_size=12))
def test_recall_goes_right_before_the_latest_user_message_whatever_the_history(roles):
    memory = Memory(clock=_clock())
    memory.add("My favourite colour is teal.", user_id="asha", run_id="before")
    fake = FakeUpstream()
    client = TestClient(make_app(memory, fake))
    call = {"id": "c", "type": "function", "function": {"name": "f", "arguments": "{}"}}
    messages: List[Dict[str, Any]] = []
    for k, role in enumerate(roles):
        if role == "tool_call":
            messages.append({"role": "assistant", "content": None, "tool_calls": [call]})
        elif role == "tool":
            messages.append({"role": "tool", "tool_call_id": "c", "content": f"result {k}"})
        elif role == "user":
            messages.append({"role": "user", "content": f"What is my favourite colour? ({k})"})
        else:
            messages.append({"role": role, "content": f"{role} {k}"})
    assert post(client, messages, headers=ASHA).status_code == 200
    forwarded = fake.last["messages"]
    users = [k for k, m in enumerate(messages) if m["role"] == "user"]
    if not users:
        assert forwarded == messages
        return
    latest = users[-1]
    assert len(forwarded) == len(messages) + 1
    assert forwarded[:latest] == messages[:latest] and forwarded[latest + 1 :] == messages[latest:]
    recalled = forwarded[latest]
    assert recalled["role"] == "user" and recalled["content"].startswith(RECALL_PREAMBLE)
    assert "teal" in recalled["content"]
    # Never between an assistant's tool call and that call's result.
    assert not (latest < len(messages) and messages[latest]["role"] == "tool")


JSON = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-(10**30), max_value=10**30)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=20),
    lambda inner: (
        st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=8), inner, max_size=4)
    ),
    max_leaves=12,
)


@APP_SETTINGS
@given(
    extra=st.dictionaries(
        st.text(min_size=1, max_size=10).map(lambda k: "x_" + k), JSON, max_size=5
    )
)
def test_fields_the_server_does_not_use_reach_the_upstream_unchanged(extra):
    fake = FakeUpstream()
    client = TestClient(make_app(Memory(clock=_clock()), fake))
    payload = {"model": "m", "messages": hi(), **extra}
    for headers in (
        {},
        ASHA,
    ):  # without a scope the body is not touched; with one only messages may change
        response = client.post(
            "/v1/chat/completions",
            content=json.dumps(payload).encode(),
            headers={**AUTH, **headers, "content-type": "application/json"},
        )
        assert response.status_code == 200
        sent = fake.last
        assert {k: v for k, v in sent.items() if k != "messages"} == {
            k: v for k, v in payload.items() if k != "messages"
        }


# --------------------------------------------------------------------------- headers and scope


def test_the_header_wins_over_the_user_field_and_the_field_may_be_any_text(client, fake, memory):
    post(client, hi("one"), headers=ASHA, user="ravi")
    post(client, hi("two"), user="रवि-é-👋")
    assert [i.content for i in memory.get_all(user_id="asha")] == ["one", "reply 1"]
    assert [i.content for i in memory.get_all(user_id="ravi")] == []
    assert [i.content for i in memory.get_all(user_id="रवि-é-👋")] == ["two", "reply 2"]
    assert fake.last["user"] == "रवि-é-👋"  # the field still reaches the upstream


@pytest.mark.parametrize("size, status", [(1, 200), (256, 200), (257, 400)])
def test_scope_ids_are_one_to_256_characters(client, size, status):
    for headers, body in (
        ({"X-LLMSlim-User-Id": "u" * size}, {}),
        ({"X-LLMSlim-Agent-Id": "a" * size}, {}),
        ({**ASHA, "X-LLMSlim-Session-Id": "s" * size}, {}),
        ({}, {"user": "b" * size}),
    ):
        assert post(client, hi(), headers=headers, **body).status_code == status


def test_a_session_alone_selects_no_memory_and_an_agent_alone_does(client, fake, memory):
    payload = {"model": "m", "messages": hi("x"), "temperature": 0.5}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    response = client.post(
        "/v1/chat/completions",
        content=raw,
        headers={**AUTH, "X-LLMSlim-Session-Id": "s1", "content-type": "application/json"},
    )
    assert response.headers["x-llmslim-recall"] == "no-scope"
    assert fake.requests[-1].content == raw  # byte for byte
    assert memory.get_all(run_id="s1") == []
    post(client, hi("y"), headers={"X-LLMSlim-Agent-Id": "coach"})
    assert [i.content for i in memory.get_all(agent_id="coach")] == ["y", "reply 2"]


@pytest.mark.parametrize(
    "value, recall, store",
    [
        ("ON", "none", True),
        (" Store-Only ", "off", True),
        ("RECALL-ONLY", "none", False),
        ("off", "off", False),
        ("", "none", True),
        ("   ", "none", True),
    ],
)
def test_the_memory_header_is_read_without_regard_to_case_or_spaces(
    client, memory, value, recall, store
):
    response = post(client, hi(), headers={**ASHA, "X-LLMSlim-Memory": value})
    assert response.status_code == 200 and response.headers["x-llmslim-recall"] == recall
    assert bool(memory.get_all(user_id="asha")) is store


@pytest.mark.parametrize("value", ["none", "true", "store_only", "on,off", "1"])
def test_other_memory_header_values_are_400s(client, fake, value):
    response = post(client, hi(), headers={**ASHA, "X-LLMSlim-Memory": value})
    assert response.status_code == 400 and fake.requests == []


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5", "", " ", "4001", "1e3", "0x10"])
def test_out_of_range_memory_budgets_are_400s(memory, fake, value):
    client = TestClient(make_app(memory, fake, max_budget=4000))
    response = post(client, hi(), headers={**ASHA, "X-LLMSlim-Memory-Budget": value})
    assert response.status_code == 400 and response.json()["error"]["type"] == "invalid_request"
    assert fake.requests == []


@pytest.mark.parametrize("value", ["1", "007", "4000", " 12 "])
def test_memory_budgets_in_range_are_used(memory, fake, value):
    memory.add("x " * 3000 + "teal is my colour", user_id="asha")
    client = TestClient(make_app(memory, fake, max_budget=4000))
    response = post(client, hi("What colour?"), headers={**ASHA, "X-LLMSlim-Memory-Budget": value})
    assert response.status_code == 200
    assert int(response.headers.get("x-llmslim-recall-tokens", 0)) <= int(value)


# --------------------------------------------------------------------------- many at once, and GET /v1/models


def test_concurrent_requests_each_store_their_own_turns_once(memory, fake):
    app = make_app(memory, fake)

    async def call(user: str, stream: bool) -> int:
        body = json.dumps({"model": "m", "stream": stream, "messages": hi(f"I am {user}")}).encode()
        scope = _scope(body, "2.3")
        scope["headers"] = [h for h in scope["headers"] if h[0] != b"x-llmslim-user-id"]
        scope["headers"].append((b"x-llmslim-user-id", user.encode()))
        status = []
        sent = False

        async def receive() -> Dict[str, Any]:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.Event().wait()
            return {"type": "http.disconnect"}  # pragma: no cover

        async def send(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status.append(message["status"])

        await app(scope, receive, send)
        return status[0]

    async def scenario() -> List[int]:
        return await asyncio.gather(*(call(f"u{k}", k % 2 == 0) for k in range(40)))

    assert asyncio.run(asyncio.wait_for(scenario(), 30)) == [200] * 40
    for k in range(40):
        turns = memory.get_all(user_id=f"u{k}")
        assert [(t.role, t.content) for t in turns][0] == ("user", f"I am u{k}")
        assert len(turns) == 2 and turns[1].role == "assistant"


@pytest.mark.parametrize(
    "answer, status",
    [
        (lambda request: httpx.Response(401, json={"error": {"message": "bad key"}}), 502),
        (lambda request: httpx.Response(302, headers={"location": "https://x.test"}), 502),
        (
            lambda request: httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            ),
            200,
        ),
        (lambda request: httpx.Response(200, json={"data": [{"id": "m"}], "object": "list"}), 200),
    ],
)
def test_models_pass_through_or_fail_cleanly(client, fake, answer, status):
    fake.replies.append(answer)
    response = client.get("/v1/models", headers=AUTH)
    assert response.status_code == status
    assert fake.requests[-1].method == "GET" and str(fake.requests[-1].url) == f"{UPSTREAM}/models"


def test_models_time_out_with_a_504_whether_before_or_while_answering(client, fake):
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    stalls = Chunks([b'{"data": [', _raise(httpx.ReadTimeout("slow"))])
    fake.replies += [
        slow,
        lambda request: httpx.Response(
            200, headers={"content-type": "application/json"}, stream=stalls
        ),
    ]
    for _ in range(2):
        response = client.get("/v1/models", headers=AUTH)
        assert response.status_code == 504
        assert response.json()["error"]["type"] == "upstream_timeout"
    assert stalls.closed
