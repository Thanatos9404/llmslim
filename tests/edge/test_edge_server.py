"""Edge cases of the ``llmslim serve`` HTTP API (the memory and fit routes; the chat endpoint has its own tests).

Wrong types in every field, budgets at and past their bounds, body sizes at the limit, encodings and content types,
query strings, odd ids, Host, Origin and Authorization variants, a store that goes down and comes back, many clients
at once and a client that stalls. Every refusal is JSON with the documented ``type``, and nothing is stored by a
request that was refused.
"""

from __future__ import annotations

import gzip
import json
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection

import pytest

pytest.importorskip("starlette")
pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

from llmslim.memory import InMemoryStore, Memory  # noqa: E402
from llmslim.memory._errors import UNAVAILABLE_MESSAGE  # noqa: E402
from llmslim.server import MAX_BUDGET, create_app  # noqa: E402
from llmslim.tokens import count_tokens  # noqa: E402

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - hypothesis is a dev dependency
    given = None

KEY = "k" * 32
AUTH = {"Authorization": f"Bearer {KEY}"}
JSON = {**AUTH, "content-type": "application/json"}


def _clock():
    moments = iter(
        datetime(2026, 10, 1, 9, tzinfo=timezone.utc) + timedelta(minutes=m) for m in range(100_000)
    )
    return lambda: next(moments)


@pytest.fixture
def memory():
    return Memory(clock=_clock())


@pytest.fixture
def client(memory):
    return TestClient(create_app(memory, api_keys=[KEY]))


def _error(response, status, kind):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/json")
    error = response.json()["error"]
    assert error["type"] == kind and isinstance(error["message"], str) and error["message"]


# ----------------------------------------------------------------------------- wrong types in every field

ADD_FIELDS = [
    ("messages", 1),
    ("messages", True),
    ("messages", None),
    ("messages", 1.5),
    ("messages", [1]),
    ("messages", [None]),
    ("messages", [["user", "hi"]]),
    ("messages", {"role": 1, "content": "x"}),
    ("messages", {"role": None, "content": "x"}),
    ("messages", {"role": "wizard", "content": "x"}),
    ("messages", {"role": "user", "content": 5}),
    ("messages", {"role": "user", "content": {"text": "x"}}),
    ("messages", {"role": "user", "content": "x", "timestamp": "yesterday"}),
    ("messages", {"role": "user", "content": "x", "created_at": True}),
    ("user_id", 5),
    ("user_id", True),
    ("user_id", ["a"]),
    ("user_id", {"a": 1}),
    ("user_id", " "),
    ("user_id", "\n\t"),
    ("agent_id", 0),
    ("run_id", {}),
    ("timestamp", True),
    ("timestamp", "yesterday"),
    ("timestamp", "2026-13-01"),
    ("timestamp", 10**30),
    ("timestamp", -(10**30)),
    ("timestamp", [1]),
    ("timestamp", {}),
    ("metadata", []),
    ("metadata", "x"),
    ("metadata", 1),
    ("metadata", True),
]


@pytest.mark.parametrize("field,value", ADD_FIELDS)
def test_add_refuses_a_wrong_type_in_any_field_and_stores_nothing(memory, client, field, value):
    payload = {"messages": "hello", "user_id": "u", field: value}
    _error(client.post("/v1/memories", json=payload, headers=AUTH), 400, "invalid_request")
    assert memory.get_all(user_id="u") == []


SEARCH_FIELDS = [
    ("query", 5),
    ("query", None),
    ("query", ""),
    ("query", "   "),
    ("query", ["x"]),
    ("query", {"q": "x"}),
    ("budget", True),
    ("budget", False),
    ("budget", 1.0),
    ("budget", 1.5),
    ("budget", "100"),
    ("budget", [100]),
    ("budget", 0),
    ("budget", -1),
    ("budget", MAX_BUDGET + 1),
    ("budget", 10**400),
    ("relevance", "magic"),
    ("relevance", ["lexical"]),
    ("relevance", {}),
    ("relevance", 1),
    ("since", True),
    ("since", "bad"),
    ("since", []),
    ("until", 1e300),
    ("until", {}),
    ("explain", "true"),
    ("explain", 1),
    ("explain", [True]),
    ("user_id", 5),
    ("user_id", None),
    ("agent_id", ["a"]),
]


@pytest.mark.parametrize("field,value", SEARCH_FIELDS)
def test_search_refuses_a_wrong_type_in_any_field(client, field, value):
    client.post("/v1/memories", json={"messages": "hello there", "user_id": "u"}, headers=AUTH)
    payload = {"query": "hello", "user_id": "u", field: value}
    _error(client.post("/v1/memories/search", json=payload, headers=AUTH), 400, "invalid_request")


FIT_FIELDS = [
    ("text", None),
    ("text", 5),
    ("text", ["x"]),
    ("text", True),
    ("query", 5),
    ("query", ["x"]),
    ("budget", 0),
    ("budget", -5),
    ("budget", False),
    ("budget", 2.0),
    ("budget", "10"),
    ("budget", MAX_BUDGET + 1),
]


@pytest.mark.parametrize("field,value", FIT_FIELDS)
def test_fit_refuses_a_wrong_type_in_any_field(client, field, value):
    payload = {"text": "hello world", "budget": 10, field: value}
    _error(client.post("/v1/context/fit", json=payload, headers=AUTH), 400, "invalid_request")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content": None},
        {"metadata": None},
        {"content": None, "metadata": None},
        {"content": ""},
        {"content": " \n"},
        {"content": 5},
        {"content": ["x"]},
        {"metadata": []},
        {"metadata": "x"},
    ],
)
def test_patch_refuses_a_wrong_type_and_leaves_the_turn_as_it_was(memory, client, payload):
    item = memory.add("as it was", user_id="u", metadata={"k": 1})[0]
    response = client.patch(f"/v1/memories/{item.id}", json=payload, headers=AUTH)
    _error(response, 400, "invalid_request")
    stored = memory.get(item.id)
    assert stored.content == "as it was" and dict(stored.metadata) == {"k": 1}


def test_unknown_fields_are_ignored_on_every_route(memory, client):
    extra = {"unknown": [1, {"x": None}], "user": "someone-else", "id": "chosen"}
    added = client.post(
        "/v1/memories", json={"messages": "kept", "user_id": "u", **extra}, headers=AUTH
    )
    assert added.status_code == 201
    item = added.json()["items"][0]
    assert item["id"] != "chosen" and item["user_id"] == "u"
    searched = client.post(
        "/v1/memories/search", json={"query": "kept", "user_id": "u", **extra}, headers=AUTH
    )
    assert searched.status_code == 200 and "kept" in searched.json()["text"]
    fitted = client.post("/v1/context/fit", json={"text": "short", **extra}, headers=AUTH)
    assert fitted.json() == {"text": "short", "tokens": count_tokens("short"), "original_tokens": 1}
    patched = client.patch(
        f"/v1/memories/{item['id']}", json={"content": "fixed", **extra}, headers=AUTH
    )
    assert patched.status_code == 200 and patched.json()["content"] == "fixed"
    assert [i.content for i in memory.get_all(user_id="u")] == ["fixed"]


def test_messages_with_no_text_store_nothing_and_answer_an_empty_list(memory, client):
    for messages in (
        [],
        "   ",
        {"role": "assistant", "content": None},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]},
        [{"role": "user", "content": [1, None, {"type": "text", "text": 5}]}],
    ):
        response = client.post(
            "/v1/memories", json={"messages": messages, "user_id": "u"}, headers=AUTH
        )
        assert response.status_code == 201 and response.json() == {"items": []}, messages
    assert memory.get_all(user_id="u") == []


# ----------------------------------------------------------------------------- budgets


@pytest.mark.parametrize("budget", [1, 2, 7, MAX_BUDGET])
def test_search_holds_any_budget_from_one_to_the_maximum(client, budget):
    for day in range(40):
        client.post(
            "/v1/memories",
            json={
                "messages": f"Day {day}: I planted tomatoes and basil in bed {day}.",
                "user_id": "u",
            },
            headers=AUTH,
        )
    response = client.post(
        "/v1/memories/search",
        json={"query": "What did I plant in bed 7?", "user_id": "u", "budget": budget},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["budget"] == budget and body["tokens"] <= budget
    assert count_tokens(body["text"]) == body["tokens"] if body["text"] else body["tokens"] == 0


def test_fit_takes_budgets_one_and_the_maximum(client):
    text = "The quick brown fox jumps over the lazy dog. " * 60
    for budget in (1, MAX_BUDGET):
        body = client.post(
            "/v1/context/fit", json={"text": text, "budget": budget}, headers=AUTH
        ).json()
        assert body["tokens"] <= budget * 1.02 and body["original_tokens"] == count_tokens(text)
    assert client.post("/v1/context/fit", json={"text": text}, headers=AUTH).json()["text"] == text


def test_a_custom_max_budget_is_the_bound_the_api_enforces(memory):
    small = TestClient(create_app(memory, api_keys=[KEY], max_budget=50))
    assert small.get("/v1/info", headers=AUTH).json()["max_budget"] == 50
    fit = small.post("/v1/context/fit", json={"text": "x", "budget": 51}, headers=AUTH)
    _error(fit, 400, "invalid_request")
    assert "1 to 50" in fit.json()["error"]["message"]
    assert small.post("/v1/context/fit", json={"text": "x", "budget": 50}, headers=AUTH).is_success


# ----------------------------------------------------------------------------- bodies: size, encoding, type


def _body(size: int) -> bytes:
    head, tail = b'{"messages": "x", "user_id": "big", "metadata": {"pad": "', b'"}}'
    return head + b"a" * (size - len(head) - len(tail)) + tail


def test_a_body_of_exactly_the_limit_is_taken_and_one_byte_more_is_413(memory):
    limit = 400
    client = TestClient(create_app(memory, api_keys=[KEY], max_body_bytes=limit))
    exact = client.post("/v1/memories", content=_body(limit), headers=JSON)
    assert exact.status_code == 201, exact.text
    _error(
        client.post("/v1/memories", content=_body(limit + 1), headers=JSON),
        413,
        "payload_too_large",
    )

    def chunks(data: bytes):
        for at in range(0, len(data), 37):
            yield data[at : at + 37]

    # Without a Content-Length (chunked), the body is counted as it arrives.
    assert (
        client.post("/v1/memories", content=chunks(_body(limit)), headers=JSON).status_code == 201
    )
    _error(
        client.post("/v1/memories", content=chunks(_body(limit + 1)), headers=JSON),
        413,
        "payload_too_large",
    )
    assert len(memory.get_all(user_id="big")) == 2


def test_an_oversized_body_without_a_key_is_a_401_not_a_413(client):
    response = client.post("/v1/memories", content=_body(1_000_001))
    _error(response, 401, "unauthorized")


@pytest.mark.parametrize(
    "content_type",
    [None, "text/plain", "application/json; charset=utf-8", "application/x-www-form-urlencoded"],
)
def test_the_body_is_read_as_json_whatever_the_content_type_says(memory, client, content_type):
    headers = dict(AUTH)
    if content_type:
        headers["content-type"] = content_type
    raw = json.dumps({"messages": "typed", "user_id": "u"}).encode()
    assert client.post("/v1/memories", content=raw, headers=headers).status_code == 201
    assert [i.content for i in memory.get_all(user_id="u")] == ["typed"]


def test_a_utf8_byte_order_mark_is_accepted(memory, client):
    raw = b'\xef\xbb\xbf{"messages": "caf\xc3\xa9", "user_id": "u"}'
    assert client.post("/v1/memories", content=raw, headers=JSON).status_code == 201
    assert memory.get_all(user_id="u")[0].content == "caf\u00e9"


@pytest.mark.parametrize(
    "raw,headers",
    [
        ('{"messages": "caf\u00e9", "user_id": "u"}'.encode("latin-1"), {}),
        (gzip.compress(b'{"messages": "x", "user_id": "u"}'), {"content-encoding": "gzip"}),
        (b"--b\r\nContent-Disposition: form-data; name=f\r\n\r\nx\r\n--b--\r\n", {}),
        (b"messages=x&user_id=u", {"content-type": "application/x-www-form-urlencoded"}),
        (b'{"messages": "x", "user_id": "u"', {}),
        (b'{"messages": "x", "user_id": "u"}{}', {}),
        (b"\x00", {}),
    ],
)
def test_bodies_that_are_not_json_text_are_400_invalid_json(memory, client, raw, headers):
    _error(
        client.post("/v1/memories", content=raw, headers={**JSON, **headers}), 400, "invalid_json"
    )
    assert memory.get_all(user_id="u") == []


@pytest.mark.parametrize("raw", [b"[]", b'"x"', b"null", b"1", b"true"])
def test_a_body_that_is_json_but_not_an_object_is_400(client, raw):
    for path in ("/v1/memories", "/v1/memories/search", "/v1/context/fit"):
        _error(client.post(path, content=raw, headers=JSON), 400, "invalid_request")


def test_an_empty_body_reads_as_an_empty_object(client):
    response = client.post("/v1/memories", content=b"", headers=JSON)
    _error(response, 400, "invalid_request")
    assert response.json()["error"]["message"] == "messages is required"


def test_nesting_within_the_limit_is_stored_and_read_back(memory, client):
    nested = "[" * 50 + "]" * 50
    raw = f'{{"messages": "deep", "user_id": "u", "metadata": {{"x": {nested}}}}}'.encode()
    assert client.post("/v1/memories", content=raw, headers=JSON).status_code == 201
    listed = client.get("/v1/memories", params={"user_id": "u"}, headers=AUTH)
    assert listed.status_code == 200 and listed.json()["total"] == 1


def test_nesting_deeper_than_the_limit_is_refused_and_nothing_is_stored(memory, client):
    nested = "[" * 500 + "]" * 500
    raw = f'{{"messages": "deep", "user_id": "u", "metadata": {{"x": {nested}}}}}'.encode()
    response = client.post("/v1/memories", content=raw, headers=JSON)
    _error(response, 400, "invalid_json")
    assert "nested more than 64 levels deep" in response.json()["error"]["message"]
    listed = client.get("/v1/memories", params={"user_id": "u"}, headers=AUTH)
    assert listed.status_code == 200 and listed.json()["total"] == 0


# ----------------------------------------------------------------------------- query strings, paths, methods


@pytest.mark.parametrize(
    "query",
    [
        "",
        "user_id=",
        "agent_id=&run_id=",
        "user_id=%20",
        "user_id=u&limit=0",
        "user_id=u&limit=1001",
        "user_id=u&limit=-1",
        "user_id=u&limit=1e3",
        "user_id=u&limit=",
        "user_id=u&limit=%C2%B2",
        "user_id=u&limit=" + "9" * 5000,
        "user_id=u&offset=-1",
        "user_id=u&offset=1000000001",
        "user_id=u&since=bad",
        "user_id=u&until=1",
        "user_id=u&since=2026-02-30",
    ],
)
def test_list_refuses_bad_query_strings(client, query):
    _error(client.get(f"/v1/memories?{query}", headers=AUTH), 400, "invalid_request")


@pytest.mark.parametrize("query", ["", "user_id=", "agent_id=&run_id=", "user_id=%20"])
def test_scope_delete_refuses_an_empty_or_blank_scope_and_deletes_nothing(memory, client, query):
    memory.add("keep me", user_id="u")
    _error(client.delete(f"/v1/memories?{query}", headers=AUTH), 400, "invalid_request")
    assert len(memory.get_all(user_id="u")) == 1


def test_list_pages_and_time_windows_with_offsets(memory, client):
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    for hour in range(5):
        memory.add(f"turn {hour}", user_id="u", timestamp=base + timedelta(hours=hour))
    page = client.get(
        "/v1/memories", params={"user_id": "u", "limit": 2, "offset": 4}, headers=AUTH
    ).json()
    assert [i["content"] for i in page["items"]] == ["turn 4"] and page["total"] == 5
    beyond = client.get(
        "/v1/memories", params={"user_id": "u", "offset": 1_000_000_000}, headers=AUTH
    ).json()
    assert beyond["items"] == [] and beyond["total"] == 5
    # The same instant written with an offset: since is inclusive, until exclusive.
    window = client.get(
        "/v1/memories",
        params={
            "user_id": "u",
            "since": "2026-03-01T06:30:00+05:30",
            "until": "2026-03-01T03:00:00Z",
        },
        headers=AUTH,
    ).json()
    assert [i["content"] for i in window["items"]] == ["turn 1", "turn 2"]


@pytest.mark.parametrize("memory_id", ["x" * 5000, "%00", "%F0%9F%98%80", "a%20b", "search%3F"])
def test_odd_ids_are_a_json_404(client, memory_id):
    for method in ("GET", "DELETE"):
        _error(client.request(method, f"/v1/memories/{memory_id}", headers=AUTH), 404, "not_found")
    patched = client.patch(f"/v1/memories/{memory_id}", json={"content": "x"}, headers=AUTH)
    _error(patched, 404, "not_found")


@pytest.mark.parametrize("path", ["/healthz", "/v1/info", "/v1/memories?user_id=u"])
def test_head_on_a_get_route_answers_like_get_without_a_body(memory, client, path):
    memory.add("hello", user_id="u")
    response = client.head(path, headers=AUTH)
    assert response.status_code == 200 and response.content == b""


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/v1/memories/?user_id=u", None),
        ("POST", "/v1/memories/search/", {"query": "hello", "user_id": "u"}),
        ("POST", "/v1/context/fit/", {"text": "hello"}),
        ("GET", "/healthz/", None),
    ],
)
def test_a_trailing_slash_redirects_to_the_route_and_keeps_the_method(client, method, path, body):
    client.post("/v1/memories", json={"messages": "hello", "user_id": "u"}, headers=AUTH)
    redirect = client.request(method, path, json=body, headers=AUTH, follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"].split("?")[0].endswith(path.split("?")[0].rstrip("/"))
    followed = client.request(method, path, json=body, headers=AUTH)
    assert followed.status_code == 200, followed.text


# ----------------------------------------------------------------------------- Host, Origin, Authorization


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "LOCALHOST:8080",
        "localhost.",
        "localhost.:8080",
        "127.0.0.1.",
        "127.1.2.3:9",
        "[::1]",
        "::1",
        "Foo.LocalHost:3000",
    ],
)
def test_a_keyless_server_answers_loopback_names_in_any_spelling(memory, host):
    client = TestClient(create_app(memory))
    assert client.get("/v1/info", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize(
    "host",
    [
        "localhost.evil.example",
        "evil.example",
        "0x7f000001",
        "2130706433",
        "127.0.0.1@evil.example",
        "evil.example#@localhost",
        "localhost:80:80",
        "[]",
        "10.0.0.1",
    ],
)
def test_a_keyless_server_refuses_other_names_in_any_spelling(memory, host):
    memory.add("secret", user_id="u")
    client = TestClient(create_app(memory))
    for method, path in (("GET", "/v1/memories?user_id=u"), ("DELETE", "/v1/memories?user_id=u")):
        response = client.request(method, path, headers={"Host": host})
        _error(response, 403, "forbidden")
        assert "secret" not in response.text
    assert len(memory.get_all(user_id="u")) == 1


@pytest.mark.parametrize(
    "origin,allowed",
    [
        ("http://localhost:3000", True),
        ("HTTP://LOCALHOST", True),
        ("http://[::1]:8080", True),
        ("http://app.localhost", True),
        ("null", False),
        ("", False),
        ("file://", False),
        ("chrome-extension://abcdef", False),
        ("http://localhost.evil.example", False),
        ("http://127.0.0.1.evil.example", False),
        ("http://[bad", False),
        ("ws://localhost", False),
    ],
)
def test_a_keyless_server_checks_the_origin_of_browser_requests(memory, origin, allowed):
    client = TestClient(create_app(memory), base_url="http://127.0.0.1:8080")
    response = client.post(
        "/v1/memories",
        content=json.dumps({"messages": "planted", "user_id": "u"}),
        headers={"Content-Type": "text/plain", "Origin": origin},
    )
    if allowed:
        assert response.status_code == 201
    else:
        _error(response, 403, "forbidden")
        assert memory.get_all(user_id="u") == []


@pytest.mark.parametrize(
    "authorization,ok",
    [
        (f"Bearer {KEY}", True),
        (f"bearer {KEY}", True),
        (f"BEARER {KEY}", True),
        (f"Bearer  {KEY}", True),
        (f"Bearer {KEY} ", True),
        (f"Bearer\t{KEY}", False),
        (f"Bearer {KEY}x", False),
        (f"Bearer {KEY[:-1]}", False),
        (f"Bearer {KEY} {KEY}", False),
        (f"Token {KEY}", False),
        (f"Basic {KEY}", False),
        (KEY, False),
        ("Bearer", False),
        ("Bearer ", False),
        ("", False),
        (b"Bearer \xe9" + KEY.encode(), False),  # a byte that is not ASCII
    ],
)
def test_bearer_key_variants(client, authorization, ok):
    response = client.get("/v1/info", headers={"Authorization": authorization})
    if ok:
        assert response.status_code == 200
    else:
        _error(response, 401, "unauthorized")
        assert response.headers["www-authenticate"] == "Bearer"
        assert KEY not in response.text


def test_any_of_several_keys_works_and_a_refusal_never_echoes_one(memory):
    keys = ["a" * 16, "b" * 40, "c" * 64]
    client = TestClient(create_app(memory, api_keys=keys))
    for key in keys:
        assert client.get("/v1/info", headers={"Authorization": f"Bearer {key}"}).is_success
    refused = client.get("/v1/info", headers={"Authorization": "Bearer " + "a" * 15})
    _error(refused, 401, "unauthorized")
    assert not any(key in refused.text for key in keys)


# ----------------------------------------------------------------------------- a store that goes down and comes back


class FlakyStore(InMemoryStore):
    """An in-process store that raises what a driver raises while its database is unreachable, until ``up``."""

    def __init__(self, outage: BaseException) -> None:
        super().__init__()
        self.outage = outage
        self.down = False

    def _check(self) -> None:
        if self.down:
            raise self.outage

    def add(self, items):
        self._check()
        super().add(items)

    def list(self, scope, *, since=None, until=None):
        self._check()
        return super().list(scope, since=since, until=until)

    def get(self, item_id):
        self._check()
        return super().get(item_id)

    def update(self, item_id, *, content=None, metadata=None):
        self._check()
        return super().update(item_id, content=content, metadata=metadata)

    def delete(self, item_id):
        self._check()
        return super().delete(item_id)

    def delete_scope(self, scope):
        self._check()
        return super().delete_scope(scope)


def _outages():
    found = []
    try:
        from pymongo.errors import AutoReconnect, ServerSelectionTimeoutError

        found += [ServerSelectionTimeoutError("db.example.com:27017"), AutoReconnect("reset")]
    except ImportError:  # pragma: no cover - the mongodb extra
        pass
    try:
        import psycopg

        found.append(psycopg.OperationalError("server closed the connection unexpectedly"))
    except ImportError:  # pragma: no cover - the postgres extra
        pass
    return found


@pytest.mark.parametrize("outage", _outages(), ids=lambda e: type(e).__name__)
def test_every_route_answers_503_while_the_store_is_down_and_recovers_without_a_restart(outage):
    store = FlakyStore(outage)
    memory = Memory(store, clock=_clock())
    client = TestClient(create_app(memory, api_keys=[KEY]))
    kept = client.post(
        "/v1/memories", json={"messages": "I moved to Pune.", "user_id": "u"}, headers=AUTH
    ).json()["items"][0]["id"]
    calls = [
        ("POST", "/v1/memories", {"json": {"user_id": "u", "messages": "written while down"}}),
        ("GET", "/v1/memories", {"params": {"user_id": "u"}}),
        ("GET", f"/v1/memories/{kept}", {}),
        ("PATCH", f"/v1/memories/{kept}", {"json": {"content": "changed while down"}}),
        ("DELETE", f"/v1/memories/{kept}", {}),
        ("DELETE", "/v1/memories", {"params": {"user_id": "u"}}),
        ("POST", "/v1/memories/search", {"json": {"user_id": "u", "query": "Where?"}}),
        ("POST", "/v1/memories/search", {"json": {"user_id": "u", "query": "x", "explain": True}}),
    ]
    for _cycle in range(2):  # down, up, down again, up again
        store.down = True
        for method, path, options in calls:
            response = client.request(method, path, headers=AUTH, **options)
            _error(response, 503, "store_unavailable")
            assert response.headers["retry-after"] == "5"
            assert response.json()["error"]["message"] == UNAVAILABLE_MESSAGE
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.post("/v1/context/fit", json={"text": "fine"}, headers=AUTH).is_success
        store.down = False
        # Nothing a refused request carried was applied, and the same requests work again.
        assert [i.content for i in memory.get_all(user_id="u")] == ["I moved to Pune."]
        assert client.get(f"/v1/memories/{kept}", headers=AUTH).json()["content"] == (
            "I moved to Pune."
        )
        found = client.post(
            "/v1/memories/search", json={"user_id": "u", "query": "Where did I move?"}, headers=AUTH
        )
        assert found.status_code == 200 and "Pune" in found.json()["text"]
    added = client.post(
        "/v1/memories", json={"messages": "back again", "user_id": "u"}, headers=AUTH
    )
    assert added.status_code == 201
    assert client.delete("/v1/memories", params={"user_id": "u"}, headers=AUTH).json() == {
        "deleted": 2
    }


# ----------------------------------------------------------------------------- a real server: many clients, slow ones

uvicorn = pytest.importorskip("uvicorn")


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    """``llmslim serve``'s app on a real uvicorn on 127.0.0.1, over a SQLite file."""
    memory = Memory(str(tmp_path_factory.mktemp("serve") / "memory.db"))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(create_app(memory), log_level="critical", timeout_keep_alive=1)
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.01)
    yield memory, sock.getsockname()[1]
    server.should_exit = True
    thread.join(10)


def _call(port, method, path, payload=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=20)
    try:
        body = json.dumps(payload).encode() if payload is not None else None
        connection.request(method, path, body=body, headers={"Host": "localhost"})
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def test_many_concurrent_clients_on_one_sqlite_file(live):
    memory, port = live

    def work(n):
        added = _call(
            port,
            "POST",
            "/v1/memories",
            {"messages": f"note {n}: the tea is oolong", "user_id": f"c{n % 4}"},
        )
        found = _call(
            port,
            "POST",
            "/v1/memories/search",
            {"query": "tea", "user_id": f"c{n % 4}", "budget": 40},
        )
        return added[0], found[0], json.loads(found[1])["tokens"]

    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(work, range(160)))
    assert {(a, s) for a, s, _ in results} == {(201, 200)}
    assert all(tokens <= 40 for _, _, tokens in results)
    stored = [item for k in range(4) for item in memory.get_all(user_id=f"c{k}")]
    assert len(stored) == 160
    assert len({item.seq for item in stored}) == 160 and len({item.id for item in stored}) == 160
    assert sorted(item.content for item in stored) == sorted(
        f"note {n}: the tea is oolong" for n in range(160)
    )


def test_a_client_that_stalls_mid_body_holds_up_no_one_and_stores_nothing(live):
    memory, port = live
    stalled = socket.create_connection(("127.0.0.1", port))
    try:
        stalled.sendall(
            b"POST /v1/memories HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
            b'Content-Length: 200\r\n\r\n{"messages": "half", "user_id": "stall'
        )
        started = time.monotonic()
        assert _call(port, "GET", "/healthz")[0] == 200
        assert _call(port, "POST", "/v1/memories", {"messages": "x", "user_id": "other"})[0] == 201
        assert time.monotonic() - started < 5
    finally:
        stalled.close()
    time.sleep(0.2)
    assert memory.get_all(user_id="stall") == []


def test_a_chunked_body_over_the_limit_is_cut_off_with_a_413(live):
    memory, port = live
    connection = socket.create_connection(("127.0.0.1", port), timeout=20)
    try:
        connection.sendall(
            b"POST /v1/memories HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n"
        )
        chunk = b"a" * 65_536
        try:
            for _ in range(20):  # 1.3 MB, past the 1 MB limit
                connection.sendall(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            connection.sendall(b"0\r\n\r\n")
        except OSError:  # the server may answer and close before the rest is sent
            pass
        answer = connection.recv(65_536)
    finally:
        connection.close()
    assert answer.startswith(b"HTTP/1.1 413")
    assert b'"payload_too_large"' in answer or b"application/json" in answer


# ----------------------------------------------------------------------------- fit's budget on hostile text

if given is not None:
    _PIECES = st.sampled_from(
        list("ab c\n\t.!?`#|-*")
        + [
            "```",
            "\u200d",
            "\u0301",
            "\U0001f469\u200d\U0001f4bb",
            "\u4e2d\u6587",
            "\u0645\u0631\u062d\u0628\u0627",
        ]
        + [
            "\x00",
            "\r\n",
            "    ",
            "\u65e5\u672c\u8a9e\u3002",
            "\U0001f1ee\U0001f1f3",
            "word ",
            "Sentence. ",
        ]
    )

    @settings(max_examples=150, deadline=None, suppress_health_check=list(HealthCheck))
    @given(
        st.one_of(
            st.lists(_PIECES, max_size=300).map("".join),
            st.text(st.characters(blacklist_categories=("Cs",)), max_size=1500),
        ),
        st.integers(1, 120),
        st.one_of(st.none(), st.text(st.characters(blacklist_categories=("Cs",)), max_size=30)),
    )
    def test_fit_is_at_most_two_percent_over_for_any_text(text, budget, query):
        from llmslim._fit import fit_text

        fitted = fit_text(text, budget, query)
        assert count_tokens(fitted) <= budget * 1.02
        if count_tokens(text) <= budget:
            assert fitted == text


def test_fit_over_http_holds_the_budget_for_hostile_shapes(client):
    for text in (
        "\u200d" * 20_000,
        "\U0001f469\u200d\U0001f4bb" * 5_000,
        "a" * 100_000,
        "\x00 " * 20_000,
        "|" * 50_000 + "\n" + "| a | b |\n" * 2_000,
        "```" * 10_000,
        "\u0645\u0631\u062d\u0628\u0627 " * 10_000,
    ):
        body = client.post("/v1/context/fit", json={"text": text, "budget": 50}, headers=AUTH)
        assert body.status_code == 200
        assert body.json()["tokens"] <= 50 * 1.02, (text[:20], body.json()["tokens"])
