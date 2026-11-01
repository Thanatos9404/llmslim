"""Hostile request bodies get clean 4xx answers from every website function, never a 500.

Covers web/api/_shared.py and the five functions that use it: deeply nested JSON
(``RecursionError``), integers past Python's digit limit and ``NaN`` (``ValueError``), and lone
surrogates that would fail later when encoded. None of them may reach Sentry. Also checks that the
per-instance rate-limit tables stay bounded.
"""

from __future__ import annotations

import importlib
import importlib.util
import itertools
import json
import re
import sys
import threading
from collections import deque
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "web" / "api"
if str(API_DIR) not in sys.path:
    sys.path.append(str(API_DIR))
shared = importlib.import_module("_shared")
sentry = importlib.import_module("_sentry")
FUNCTIONS = ("studio", "compress", "plan", "context", "sarvam_answer")
_addresses = itertools.count(1)


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"request_safety_{name}", API_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULES = {name: load(name) for name in FUNCTIONS}

HOSTILE = [
    pytest.param(b"[" * 20_000 + b"]" * 20_000, 400, "invalid_json", id="recursion"),
    pytest.param(b'{"text": ' + b"[" * 40 + b"]" * 40 + b"}", 400, "invalid_json", id="too-deep"),
    pytest.param(b'{"text": ' + b"7" * 4_400 + b"}", 400, "invalid_json", id="huge-integer"),
    pytest.param(b'{"text": NaN}', 400, "invalid_json", id="nan"),
    pytest.param(b'{"text": Infinity}', 400, "invalid_json", id="infinity"),
    pytest.param(b'{"text": "a\\udc00b", "question": "q"}', 422, "invalid_text", id="surrogate"),
    pytest.param(b'{"\\ud800": "x"}', 422, "invalid_text", id="surrogate-key"),
    pytest.param(b"\xff\xfe\x00", 400, "invalid_json", id="not-utf8"),
]


@pytest.fixture()
def reports(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    monkeypatch.setattr(
        sentry, "capture", lambda error, *, function, now=None: seen.append(function)
    )
    return seen


def post(module: Any, body: bytes, extra: dict[str, str]) -> tuple[int, dict[str, Any]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=60)
        headers = {
            "content-type": "application/json",
            "x-forwarded-for": f"203.0.113.{next(_addresses) % 250 + 1}",
            **extra,
        }
        connection.request("POST", f"/api/{module.__name__}", body=body, headers=headers)
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("name", ["studio", "compress", "plan", "context"])
@pytest.mark.parametrize(("body", "status", "code"), HOSTILE)
def test_hostile_bodies_are_clean_client_errors(
    reports: list[str], name: str, body: bytes, status: int, code: str
) -> None:
    got, payload = post(MODULES[name], body, {})
    assert (got, payload["error"]["code"]) == (status, code)
    assert reports == []


@pytest.mark.parametrize(("body", "status", "code"), HOSTILE)
def test_hostile_bodies_are_clean_client_errors_for_the_answer_step(
    reports: list[str], monkeypatch: pytest.MonkeyPatch, body: bytes, status: int, code: str
) -> None:
    answer = MODULES["sarvam_answer"]
    for key, value in {
        "LLMSLIM_HOSTED_SARVAM_ENABLED": "true",
        "SARVAM_API_KEY": "sk_fake_key_for_tests_only_0000",
        "MONGODB_URI": "mongodb://fake.invalid",
        "LLMSLIM_RATE_LIMIT_HMAC_SECRET": "h" * 40,
        "LLMSLIM_ALLOWED_ORIGINS": "https://www.llmslim.app",
        "LLMSLIM_SARVAM_MAX_BODY_BYTES": "100000",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(answer, "_dependencies_available", lambda: True)

    class Store:
        def consume_rate(self, **_: Any) -> bool:
            return True

        def record_event(self, *_: Any, **__: Any) -> None:
            return None

    monkeypatch.setattr(
        answer, "make_service", lambda config: answer.HostedSarvamService(config, Store())
    )
    got, payload = post(answer, body, {"origin": "https://www.llmslim.app"})
    assert (got, payload["error"]["code"]) == (status, code)
    assert reports == []


def test_decode_json_object_accepts_ordinary_json() -> None:
    value = shared.decode_json_object('{"a": [1, {"b": "नमस्ते 😀"}], "c": 1.5}'.encode())
    assert value == {"a": [1, {"b": "नमस्ते 😀"}], "c": 1.5}
    nested = {"x": {"y": {"z": [[["ok"]]]}}}
    assert shared.decode_json_object(json.dumps(nested).encode()) == nested
    with pytest.raises(shared.BodyError) as error:
        shared.decode_json_object(b"[]")
    assert error.value.code == "object_required" and error.value.status == 400


def test_existing_error_codes_are_kept() -> None:
    # studio.py has always answered a non-object body with invalid_json.
    with pytest.raises(MODULES["studio"].RequestProblem) as studio_error:
        MODULES["studio"].parse_json_body(b"[1]", "application/json")
    assert studio_error.value.code == "invalid_json"
    with pytest.raises(MODULES["plan"].RequestProblem) as plan_error:
        MODULES["plan"].parse_json_body(b"[1]", "application/json")
    assert plan_error.value.code == "object_required"


@pytest.mark.parametrize("name", ["studio", "compress", "plan", "context"])
def test_rate_limit_tables_stay_bounded(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    module = MODULES[name]
    allow = getattr(module, "allow_request", None) or module._allow_request
    monkeypatch.setattr(module, "_request_windows", module._request_windows.__class__(deque))
    original = shared.bound_windows

    def bounded(windows: Any, cutoff: float, limit: int = 50) -> None:
        original(windows, cutoff, limit)

    monkeypatch.setattr(shared, "bound_windows", bounded)
    for index in range(500):
        assert allow(f"client-{index}", 1_000.0 + index * 0.001)
    assert len(module._request_windows) <= 51
    # The newest clients are kept, and limits still apply to them.
    assert "client-499" in module._request_windows


def test_bound_windows_drops_idle_clients_before_active_ones() -> None:
    windows: dict[str, deque[float]] = {f"idle-{i}": deque([1.0]) for i in range(5)}
    windows.update({f"active-{i}": deque([100.0]) for i in range(5)})
    shared.bound_windows(windows, cutoff=50.0, limit=6)
    assert sorted(windows) == [f"active-{i}" for i in range(5)]
    shared.bound_windows(windows, cutoff=50.0, limit=3)
    assert list(windows) == ["active-2", "active-3", "active-4"]
    small = {"a": deque([1.0])}
    shared.bound_windows(small, cutoff=50.0, limit=3)
    assert small == {"a": deque([1.0])}


def test_privacy_page_lists_every_analytics_event() -> None:
    analytics = (ROOT / "web" / "src" / "lib" / "analytics.ts").read_text(encoding="utf-8")
    block = analytics[analytics.index("const EVENTS = {") : analytics.index("} as const")]
    events = set(re.findall(r"^\s+([a-z_]+):", block, re.M))
    privacy = (ROOT / "web" / "src" / "app" / "privacy" / "page.tsx").read_text(encoding="utf-8")
    described = {
        "homepage_view": "homepage",
        "platform_page_view": "Vault page",
        "results_page_view": "Results page",
        "core_docs_clicked": "Core documentation",
        "studio_clicked": "Studio",
        "platform_beta_clicked": "Vault beta",
        "beta_request_submitted": "beta request form",
        "startup_program_clicked": "startup program",
        "studio_sarvam_answer": "Answer with Sarvam",
        "pricing_cta_clicked": "plan button",
    }
    assert events == set(described), "describe new analytics events on the privacy page"
    for event, phrase in described.items():
        assert phrase in privacy, event


def test_client_key_counts_an_ipv6_client_by_its_64() -> None:
    key = shared.client_key
    assert key("198.51.100.23") == key("198.51.100.23, 10.0.0.1") == "198.51.100.23"
    assert key("198.51.100.23") != key("198.51.100.24")
    assert key("::ffff:198.51.100.23") == "198.51.100.23"
    # Changing the interface identifier, which any IPv6 subscriber can do per request, is the same client.
    assert key("2001:db8:1:2::1") == key("2001:db8:1:2:ffff:ffff:ffff:fffe") == "2001:db8:1:2::/64"
    assert key("2001:db8:1:2::1") != key("2001:db8:1:3::1")
    for junk in ("", "not an address", "unknown", "1.2.3.4.5"):
        assert key(junk) == "anonymous"


@pytest.mark.parametrize("name", ["studio", "compress", "plan", "context"])
def test_rotating_ipv6_addresses_does_not_reset_the_rate_limit(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = MODULES[name]
    monkeypatch.setattr(module, "_request_windows", module._request_windows.__class__(deque))
    limit = module.RATE_LIMIT_MAX_REQUESTS
    statuses = []
    for host in range(limit + 1):
        status, _ = post(module, b"{}", {"x-forwarded-for": f"2001:db8:aa:bb::{host + 1:x}"})
        statuses.append(status)
    assert 429 not in statuses[:limit]
    assert statuses[limit] == 429
    # Another /64 is another client.
    status, _ = post(module, b"{}", {"x-forwarded-for": "2001:db8:aa:cc::1"})
    assert status != 429
