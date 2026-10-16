"""llmslim serve: the HTTP API over llmslim.memory, its authentication and its limits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("starlette")
pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

from llmslim import count_tokens  # noqa: E402
from llmslim.memory import Memory  # noqa: E402
from llmslim.server import api_keys_from, create_app, is_loopback, main  # noqa: E402

KEY = "k" * 32
AUTH = {"Authorization": f"Bearer {KEY}"}


def _clock():
    moments = iter(
        datetime(2026, 10, 1, 9, tzinfo=timezone.utc) + timedelta(minutes=m) for m in range(10_000)
    )
    return lambda: next(moments)


@pytest.fixture
def memory():
    return Memory(clock=_clock())


@pytest.fixture
def client(memory):
    return TestClient(create_app(memory, api_keys=[KEY]))


def _add(client, content, **scope):
    response = client.post("/v1/memories", json={"messages": content, **scope}, headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()["items"]


def test_health_needs_no_key_but_v1_does(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    for headers in (
        {},
        {"Authorization": "Bearer wrong-key-wrong-key-1234"},
        {"Authorization": f"Basic {KEY}"},
    ):
        response = client.get("/v1/info", headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"]["type"] == "unauthorized"
    assert client.get("/v1/info", headers=AUTH).json()["name"] == "llmslim"


def test_add_search_and_the_answer_comes_back(client):
    _add(
        client,
        [
            {"role": "user", "content": "I'm allergic to peanuts."},
            {"role": "assistant", "content": "Noted."},
        ],
        user_id="asha",
    )
    for day in range(30):
        _add(client, f"Day {day}: what should I cook with lentils tonight?", user_id="asha")
    response = client.post(
        "/v1/memories/search",
        json={"query": "Am I allergic to anything?", "user_id": "asha", "budget": 60},
        headers=AUTH,
    )
    body = response.json()
    assert response.status_code == 200
    assert "peanuts" in body["text"] and body["tokens"] <= 60 * 1.02
    assert body["history_tokens"] > 60 and body["sessions_total"] >= 1
    assert any(turn["content"] == "I'm allergic to peanuts." for turn in body["turns"])


def test_items_list_get_update_delete(client):
    first, second = _add(
        client,
        [{"role": "user", "content": "one"}, {"role": "user", "content": "two"}],
        user_id="u",
    )
    listing = client.get(
        "/v1/memories", params={"user_id": "u", "limit": 1, "offset": 1}, headers=AUTH
    ).json()
    assert listing["total"] == 2 and [item["content"] for item in listing["items"]] == ["two"]
    assert client.get(f"/v1/memories/{first['id']}", headers=AUTH).json()["content"] == "one"
    patched = client.patch(
        f"/v1/memories/{first['id']}",
        json={"content": "uno", "metadata": {"lang": "es"}},
        headers=AUTH,
    )
    assert patched.json()["content"] == "uno" and patched.json()["metadata"] == {"lang": "es"}
    assert client.delete(f"/v1/memories/{second['id']}", headers=AUTH).json() == {"deleted": 1}
    assert client.get(f"/v1/memories/{second['id']}", headers=AUTH).status_code == 404
    assert client.delete(f"/v1/memories/{second['id']}", headers=AUTH).status_code == 404
    assert (
        client.patch("/v1/memories/missing", json={"content": "x"}, headers=AUTH).status_code == 404
    )


def test_scope_delete_needs_a_scope(client):
    _add(client, "keep me", user_id="a")
    _add(client, "drop me", user_id="b")
    assert client.delete("/v1/memories", headers=AUTH).status_code == 400
    assert client.delete("/v1/memories", params={"user_id": "b"}, headers=AUTH).json() == {
        "deleted": 1
    }
    assert [
        i["content"]
        for i in client.get("/v1/memories", params={"user_id": "a"}, headers=AUTH).json()["items"]
    ] == ["keep me"]


def test_fit_holds_the_budget(client):
    filler = " ".join(
        f"Paragraph {i}: the committee reviewed routine depot maintenance." for i in range(150)
    )
    text = filler + " The backup generator failed because its fuel filter was clogged. " + filler
    body = client.post(
        "/v1/context/fit",
        json={"text": text, "budget": 120, "query": "Why did the generator fail?"},
        headers=AUTH,
    ).json()
    assert body["tokens"] <= 120 * 1.02 and "fuel filter" in body["text"]
    assert body["original_tokens"] == count_tokens(text) and body["tokens"] == count_tokens(
        body["text"]
    )


@pytest.mark.parametrize(
    "method, path, payload, status, kind",
    [
        ("post", "/v1/memories", {"messages": "no scope"}, 400, "invalid_request"),
        ("post", "/v1/memories", {"user_id": "u"}, 400, "invalid_request"),
        ("post", "/v1/memories", {"messages": "x", "user_id": 7}, 400, "invalid_request"),
        (
            "post",
            "/v1/memories",
            {"messages": "x", "user_id": "u", "metadata": [1]},
            400,
            "invalid_request",
        ),
        (
            "post",
            "/v1/memories",
            {"messages": [{"role": "wizard", "content": "x"}], "user_id": "u"},
            400,
            "invalid_request",
        ),
        ("post", "/v1/memories/search", {"query": "", "user_id": "u"}, 400, "invalid_request"),
        (
            "post",
            "/v1/memories/search",
            {"query": "q", "user_id": "u", "budget": 0},
            400,
            "invalid_request",
        ),
        (
            "post",
            "/v1/memories/search",
            {"query": "q", "user_id": "u", "budget": 10**9},
            400,
            "invalid_request",
        ),
        (
            "post",
            "/v1/memories/search",
            {"query": "q", "user_id": "u", "budget": True},
            400,
            "invalid_request",
        ),
        (
            "post",
            "/v1/memories/search",
            {"query": "q", "user_id": "u", "relevance": "magic"},
            400,
            "invalid_request",
        ),
        ("post", "/v1/context/fit", {"text": 5}, 400, "invalid_request"),
        ("patch", "/v1/memories/x", {}, 400, "invalid_request"),
        ("patch", "/v1/memories/x", {"content": 3}, 400, "invalid_request"),
    ],
)
def test_bad_requests_get_clear_errors(client, method, path, payload, status, kind):
    response = getattr(client, method)(path, json=payload, headers=AUTH)
    assert response.status_code == status, response.text
    assert response.json()["error"]["type"] == kind and response.json()["error"]["message"]


def test_malformed_and_oversized_bodies(memory):
    client = TestClient(create_app(memory, api_keys=[KEY], max_body_bytes=200))
    bad_json = client.post(
        "/v1/memories", content=b"{nope", headers={**AUTH, "content-type": "application/json"}
    )
    assert bad_json.status_code == 400 and bad_json.json()["error"]["type"] == "invalid_json"
    array = client.post("/v1/memories", json=[1, 2], headers=AUTH)
    assert array.status_code == 400
    big = client.post("/v1/memories", json={"messages": "x" * 500, "user_id": "u"}, headers=AUTH)
    assert big.status_code == 413 and big.json()["error"]["type"] == "payload_too_large"
    assert memory.get_all(user_id="u") == []


def test_list_paging_is_validated(client):
    for params in (
        {"user_id": "u", "limit": "0"},
        {"user_id": "u", "limit": "5000"},
        {"user_id": "u", "offset": "-1"},
    ):
        assert client.get("/v1/memories", params=params, headers=AUTH).status_code == 400


def test_semantic_without_the_extra_is_a_clear_501(client, monkeypatch):
    _add(client, "hello", user_id="u")

    def missing(*args, **kwargs):
        raise ImportError('semantic relevance needs pip install "llmslim[semantic]"')

    monkeypatch.setattr(Memory, "search", missing)
    response = client.post(
        "/v1/memories/search",
        json={"query": "hi", "user_id": "u", "relevance": "semantic"},
        headers=AUTH,
    )
    assert (
        response.status_code == 501 and "llmslim[semantic]" in response.json()["error"]["message"]
    )


def test_without_keys_every_route_is_open(memory):
    client = TestClient(create_app(memory))
    assert client.get("/v1/info").status_code == 200


def test_loopback_detection():
    assert all(is_loopback(h) for h in ("127.0.0.1", "localhost", "::1", "[::1]", "127.5.0.1"))
    assert not any(is_loopback(h) for h in ("0.0.0.0", "::", "192.168.1.4", "example.com"))


def test_api_keys_come_from_flags_or_environment():
    assert api_keys_from([KEY], {}) == [KEY]
    assert api_keys_from([], {"LLMSLIM_API_KEYS": f" {KEY} , {'z' * 20} ,"}) == [KEY, "z" * 20]
    assert api_keys_from([], {}) == []
    with pytest.raises(ValueError, match="at least 16"):
        api_keys_from(["short"], {})


def test_main_refuses_a_public_interface_without_a_key(monkeypatch, tmp_path):
    monkeypatch.delenv("LLMSLIM_API_KEYS", raising=False)
    with pytest.raises(SystemExit, match="without an API key"):
        main(["--host", "0.0.0.0", "--db", str(tmp_path / "m.db")])
    with pytest.raises(SystemExit, match="at least 16"):
        main(["--host", "0.0.0.0", "--api-key", "short"])
    with pytest.raises(SystemExit):
        main(["--budget", "0"])


def test_main_starts_uvicorn_with_the_app(monkeypatch, tmp_path):
    started = {}
    monkeypatch.setattr(
        "uvicorn.run", lambda app, host, port: started.update(host=host, port=port, app=app)
    )
    monkeypatch.delenv("LLMSLIM_API_KEYS", raising=False)
    from llmslim.cli import main as cli_main

    assert cli_main(["serve", "--db", str(tmp_path / "d" / "m.db"), "--port", "9090"]) == 0
    assert (
        started["host"] == "127.0.0.1"
        and started["port"] == 9090
        and (tmp_path / "d" / "m.db").exists()
    )
    assert main(["--host", "0.0.0.0", "--api-key", KEY, "--db", str(tmp_path / "m2.db")]) == 0
    assert started["host"] == "0.0.0.0"


def test_new_key_prints_a_strong_key(capsys):
    assert main(["--new-key"]) == 0
    key = capsys.readouterr().out.strip()
    assert len(key) >= 40 and api_keys_from([key], {}) == [key]
