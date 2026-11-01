"""llmslim.proxy over HTTP: forwarding, streaming, errors, and a simulated agent loop with thinking bound to its prefix,
the way Anthropic's API checks it."""

from __future__ import annotations

import gzip
import hashlib
import json

import pytest

httpx = pytest.importorskip("httpx")
pytest.importorskip("starlette")
try:
    from starlette.testclient import TestClient
except RuntimeError:  # starlette 1.x needs httpx2 for its test client
    pytest.skip("starlette's test client is not available", allow_module_level=True)

from llmslim.proxy import ProxyStore  # noqa: E402
from llmslim.proxy.app import create_proxy_app  # noqa: E402

# The proxy answers only requests addressed to this machine, as Claude Code's are.
LOCAL = "http://127.0.0.1:8787"


def make_log(failures: int = 1, lines: int = 600) -> str:
    out = [f"tests/test_api.py::test_case_{i} PASSED" for i in range(lines)]
    for n in range(failures):
        out.insert(
            300 + n,
            f"tests/test_refund.py::test_rounding_{n} FAILED - AssertionError: 10.05 != 10.04",
        )
    out.append(f"=== {failures} failed, {lines} passed in 12.34s ===")
    return "\n".join(out)


def bash_call(call_id: str, command: str = "pytest -q") -> dict:
    return {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}
        ],
    }


def result(call_id: str, content, **extra) -> dict:
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": call_id, "content": content, **extra}],
    }


def request(*messages) -> dict:
    return {
        "model": "claude-haiku-5-5",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Run the tests."}, *messages],
    }


@pytest.fixture
def store():
    store = ProxyStore()
    yield store
    store.close()


class Chunks(httpx.AsyncByteStream):
    """A response body that arrives in pieces, as from the network (httpx pre-reads plain byte content)."""

    def __init__(self, *chunks: bytes):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


def streamed(status: int, payload, headers=None, chunks: int = 1) -> httpx.Response:
    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    size = max(1, len(data) // chunks)
    parts = [data[i : i + size] for i in range(0, len(data), size)]
    base = {} if isinstance(payload, bytes) else {"content-type": "application/json"}
    return httpx.Response(status, headers={**base, **(headers or {})}, stream=Chunks(*parts))


class FakeAnthropic:
    """An upstream that records requests, streams SSE, and binds 'thinking' to the exact prefix it was produced after,
    rejecting a replay whose prefix changed, like Anthropic's preserved-thinking check."""

    def __init__(self):
        self.requests = []

    @staticmethod
    def signature(messages) -> str:
        return hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()

    def bound_ok(self, messages) -> bool:
        """Every thinking block's signature matches the exact messages before it."""
        for index, message in enumerate(messages):
            content = message.get("content") if isinstance(message.get("content"), list) else []
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "thinking"
                    and block["signature"] != self.signature(messages[:index])
                ):
                    return False
        return True

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/v1/models":
            return streamed(200, {"data": [{"id": "claude-haiku-5-5"}]})
        if request.url.path == "/api/hello":
            return streamed(200, b"")
        body = json.loads(request.content)
        if request.url.path == "/v1/messages/count_tokens":
            return streamed(200, {"input_tokens": len(json.dumps(body["messages"])) // 4})
        messages = body["messages"]
        if not self.bound_ok(messages):
            return streamed(
                400,
                {
                    "type": "error",
                    "error": {
                        "type": "invalid_request_error",
                        "message": "The block is bound to a different conversation",
                    },
                },
            )
        reply = {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "...", "signature": self.signature(messages)},
                {"type": "text", "text": "ok"},
            ],
        }
        if body.get("stream"):
            events = f"event: message_start\ndata: {json.dumps({'type': 'message_start'})}\n\nevent: message_stop\ndata: {json.dumps({'type': 'message_stop', 'reply': reply})}\n\n"
            return streamed(200, events.encode(), {"content-type": "text/event-stream"}, chunks=4)
        return streamed(200, reply, {"request-id": "req_1"})


@pytest.fixture
def upstream():
    return FakeAnthropic()


@pytest.fixture
def proxy(upstream, store):
    app = create_proxy_app(
        store=store,
        upstream="https://api.example.test",
        transport=httpx.MockTransport(upstream.handler),
    )
    with TestClient(app, base_url=LOCAL) as client:
        yield client


HEADERS = {
    "x-api-key": "sk-test",
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "interleaved-thinking-2025-05-14",
}


def test_messages_are_rewritten_and_headers_forwarded(proxy, upstream):
    body = request(bash_call("c1"), result("c1", make_log()))
    response = proxy.post("/v1/messages?beta=true", json=body, headers=HEADERS)
    assert response.status_code == 200 and response.headers["request-id"] == "req_1"
    sent = upstream.requests[-1]
    assert sent.url.host == "api.example.test" and sent.url.query == b"beta=true"
    assert (
        sent.headers["x-api-key"] == "sk-test"
        and sent.headers["anthropic-beta"] == HEADERS["anthropic-beta"]
    )
    forwarded = json.loads(sent.content)["messages"][-1]["content"][0]["content"]
    assert forwarded.startswith("[LLMSlim") and len(forwarded) < len(make_log())


def test_a_whole_agent_loop_keeps_thinking_valid(proxy, upstream):
    """Turn 1 sends a long tool result; turn 2 replays it with the thinking the model produced after it. Without the
    byte-for-byte replay the fake API would reject turn 2, as Anthropic does."""
    turn1 = request(bash_call("c1"), result("c1", make_log()))
    reply = proxy.post("/v1/messages", json=turn1, headers=HEADERS).json()
    turn2 = {
        **turn1,
        "messages": [*turn1["messages"], reply, {"role": "user", "content": "Now fix it."}],
    }
    second = proxy.post("/v1/messages", json=turn2, headers=HEADERS)
    assert second.status_code == 200, second.text
    # The client resends the original long output; sent as it is, the thinking would no longer match its prefix:
    assert not upstream.bound_ok(turn2["messages"])
    assert upstream.bound_ok(json.loads(upstream.requests[-1].content)["messages"])


def test_streams_and_other_paths_pass_through(proxy, upstream):
    streamed = proxy.post("/v1/messages", json={**request(), "stream": True}, headers=HEADERS)
    assert (
        streamed.headers["content-type"].startswith("text/event-stream")
        and b"message_stop" in streamed.content
    )
    assert (
        proxy.get("/v1/models?limit=1000", headers=HEADERS).json()["data"][0]["id"]
        == "claude-haiku-5-5"
    )
    assert proxy.head("/api/hello").status_code == 200  # Claude Code's warm-up probe


def test_count_tokens_sees_the_same_rewrite_but_is_not_counted_twice(proxy, upstream, store):
    body = request(bash_call("c1"), result("c1", make_log()))
    proxy.post("/v1/messages/count_tokens", json=body, headers=HEADERS)
    counted = json.loads(upstream.requests[-1].content)["messages"][-1]["content"][0]["content"]
    proxy.post("/v1/messages", json=body, headers=HEADERS)
    sent = json.loads(upstream.requests[-1].content)["messages"][-1]["content"][0]["content"]
    assert counted == sent and counted.startswith("[LLMSlim")
    assert store.stats()["requests_changed"] == 1


def test_upstream_errors_and_bodies_pass_through(store):
    def handler(request):
        return streamed(
            429, {"type": "error", "error": {"type": "rate_limit_error"}}, {"retry-after": "3"}
        )

    app = create_proxy_app(
        store=store, upstream="https://api.example.test", transport=httpx.MockTransport(handler)
    )
    with TestClient(app, base_url=LOCAL) as client:
        response = client.post("/v1/messages", json=request(), headers=HEADERS)
    assert response.status_code == 429 and response.headers["retry-after"] == "3"
    assert response.json()["error"]["type"] == "rate_limit_error"


def test_compressed_responses_pass_through_as_bytes(store):
    payload = gzip.compress(b'{"ok": true}')

    def handler(request):
        return streamed(
            200, payload, {"content-encoding": "gzip", "content-type": "application/json"}
        )

    app = create_proxy_app(
        store=store, upstream="https://api.example.test", transport=httpx.MockTransport(handler)
    )
    with TestClient(app, base_url=LOCAL) as client:
        response = client.get("/v1/models")
    assert response.json() == {"ok": True}


def test_a_failed_rewrite_forwards_the_original(store, upstream, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr("llmslim.proxy.app.rewrite_request", broken)
    app = create_proxy_app(
        store=store,
        upstream="https://api.example.test",
        transport=httpx.MockTransport(upstream.handler),
    )
    body = request(bash_call("c1"), result("c1", make_log()))
    with TestClient(app, base_url=LOCAL) as client:
        assert client.post("/v1/messages", json=body, headers=HEADERS).status_code == 200
    assert json.loads(upstream.requests[-1].content) == body


def test_unreachable_upstream_is_a_clear_502(store):
    def handler(request):
        raise httpx.ConnectError("refused")

    app = create_proxy_app(
        store=store, upstream="https://api.example.test", transport=httpx.MockTransport(handler)
    )
    with TestClient(app, base_url=LOCAL) as client:
        response = client.post("/v1/messages", json=request(), headers=HEADERS)
    assert response.status_code == 502 and "could not reach" in response.json()["error"]["message"]


# ---------------------------------------------------------------- security (1.0 audit)


def test_dns_rebinding_and_cross_site_requests_never_reach_the_upstream(proxy, upstream):
    # A page on attacker.example rebound to 127.0.0.1 sends its own Host; a cross-site POST carries its Origin.
    for headers in (
        {"Host": "attacker.example:8787"},
        {"Host": "10.0.0.5:8787"},
        {"Origin": "https://attacker.example"},
        {"Origin": "null"},
    ):
        response = proxy.post("/v1/messages", json=request(), headers={**HEADERS, **headers})
        assert response.status_code == 403, headers
        assert response.json()["error"]["type"] == "permission_error"
    assert upstream.requests == []
    # Claude Code sends no Origin and addresses the proxy by its loopback address.
    for host in ("127.0.0.1:8787", "localhost:8787", "[::1]:8787"):
        response = proxy.post("/v1/messages", json=request(), headers={**HEADERS, "Host": host})
        assert response.status_code == 200, host


def test_the_upstream_is_fixed_whatever_the_path(upstream, store):
    app = create_proxy_app(
        store=store,
        upstream="https://api.example.test",
        transport=httpx.MockTransport(upstream.handler),
    )
    with TestClient(app, base_url=LOCAL, raise_server_exceptions=False) as client:
        for path in (
            "/@evil.example/v1/models",
            "/..%2F..%2Fv1/models",
            "/v1/models?u=http://evil",
        ):
            client.get(path, headers=HEADERS)
        # A path httpx can't send is a clean 400, not a 500.
        bad = client.get("/%2F%2Fevil.example/v1/models", headers=HEADERS)
    assert bad.status_code == 400 and bad.json()["error"]["type"] == "invalid_request_error"
    assert {r.url.host for r in upstream.requests} == {"api.example.test"}
    # The client's key goes to the configured upstream only.
    assert all(r.headers["x-api-key"] == "sk-test" for r in upstream.requests)


def test_allowed_hosts_and_remote_binding(store, upstream, monkeypatch):
    app = create_proxy_app(
        store=store,
        upstream="https://api.example.test",
        transport=httpx.MockTransport(upstream.handler),
        allowed_hosts=["host.docker.internal"],
    )
    with TestClient(app, base_url="http://host.docker.internal:8787") as client:
        assert client.post("/v1/messages", json=request(), headers=HEADERS).status_code == 200
    from llmslim.proxy import cli

    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("LLMSLIM_PROXY_UPSTREAM", raising=False)
    made = {}
    monkeypatch.setattr(cli, "create_proxy_app", lambda **kwargs: made.update(kwargs))
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: None)
    cli.main(["--db", ":memory:"])
    assert made["allowed_hosts"] == []
    cli.main(["--db", ":memory:", "--host", "0.0.0.0", "--allow-remote"])
    assert made["allowed_hosts"] == ["*"]
    cli.main(["--db", ":memory:", "--host", "0.0.0.0", "--allow-remote", "--allowed-host", "box"])
    assert made["allowed_hosts"] == ["box"]


# ---------------------------------------------------------------- the command line


def test_wrap_runs_the_agent_through_a_live_proxy(tmp_path, monkeypatch, capsys):
    from llmslim.proxy.cli import wrap

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    seen = {}

    def runner(command, env):
        seen["command"], seen["base"] = command, env["ANTHROPIC_BASE_URL"]
        seen["tool_search"] = env.get("ENABLE_TOOL_SEARCH")
        # The proxy is up while the agent runs; the upstream here is unreachable, so it answers 502.
        seen["status"] = httpx.get(env["ANTHROPIC_BASE_URL"] + "/v1/models").status_code
        return 7

    code = wrap(
        [
            "claude",
            "--upstream",
            "http://127.0.0.1:9",
            "--db",
            str(tmp_path / "p.db"),
            "--",
            "--continue",
        ],
        runner=runner,
    )
    assert code == 7 and seen["command"] == ["/usr/bin/claude", "--continue"]
    assert seen["base"].startswith("http://127.0.0.1:") and seen["status"] == 502
    # Claude Code keeps deferring tools behind tool search, as it does against the API directly.
    assert seen["tool_search"] == "true"


def test_proxy_refuses_remote_binding_and_stats_print(tmp_path, capsys):
    from llmslim.proxy.cli import main

    with pytest.raises(SystemExit, match="allow-remote"):
        main(["--host", "0.0.0.0"])
    with pytest.raises(SystemExit, match="this proxy itself"):
        main(
            [
                "--port",
                "8787",
                "--upstream",
                "http://localhost:8787",
                "--db",
                str(tmp_path / "p.db"),
            ]
        )
    assert main(["stats", "--db", str(tmp_path / "p.db"), "--price-per-mtok", "3"]) == 0
    out = capsys.readouterr().out
    assert "Tokens not sent:    0" in out and "At $3/MTok" in out


def test_wrap_keeps_the_users_tool_search_choice(tmp_path, monkeypatch):
    from llmslim.proxy.cli import wrap

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setenv("ENABLE_TOOL_SEARCH", "false")
    seen = {}

    def runner(command, env):
        seen["tool_search"] = env.get("ENABLE_TOOL_SEARCH")
        return 0

    wrap(
        ["claude", "--upstream", "http://127.0.0.1:9", "--db", str(tmp_path / "p.db")],
        runner=runner,
    )
    assert seen["tool_search"] == "false"


def test_print_mode_runs_keep_the_default_permission_mode(tmp_path):
    from llmslim.proxy.cli import claude_arguments

    config, project = tmp_path / "config", tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    config.mkdir()

    def args(*rest):
        return claude_arguments(list(rest), cwd=project, config_dir=config)

    # Through a proxy, `claude -p` would start in auto mode; keep it in default.
    assert args("-p", "fix it") == ["--permission-mode", "default", "-p", "fix it"]
    assert args("--print", "fix it")[:2] == ["--permission-mode", "default"]
    # Interactive sessions, and runs where the user chose a mode, are left alone.
    assert args("--continue") == ["--continue"]
    assert args("-p", "x", "--permission-mode", "plan") == ["-p", "x", "--permission-mode", "plan"]
    assert args("-p", "x", "--permission-mode=acceptEdits")[:1] == ["-p"]
    assert args("-p", "x", "--dangerously-skip-permissions")[:1] == ["-p"]
    assert args("-p", "x", "--settings", "s.json")[:1] == ["-p"]
    assert args("--", "-p")[:1] == ["--"]  # after --, "-p" is the prompt
    # A defaultMode in the user's settings decides, as it would without the proxy.
    (config / "settings.json").write_text(
        '{"permissions": {"defaultMode": "acceptEdits"}}', encoding="utf-8"
    )
    assert args("-p", "x") == ["-p", "x"]
    (config / "settings.json").unlink()
    # Claude Code ignores auto in project settings, so it doesn't count.
    (project / ".claude" / "settings.json").write_text(
        '{"permissions": {"defaultMode": "auto"}}', encoding="utf-8"
    )
    assert args("-p", "x")[:2] == ["--permission-mode", "default"]
    (project / ".claude" / "settings.local.json").write_text(
        '{"permissions": {"defaultMode": "plan"}}', encoding="utf-8"
    )
    assert args("-p", "x") == ["-p", "x"]
