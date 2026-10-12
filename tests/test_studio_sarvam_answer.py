"""Security and quota tests for the Studio "Answer with Sarvam" function (web/api/sarvam_answer.py).

Restored from the hosted Sarvam route tests removed in the 0.8 redesign and adapted to the new
function. Every test uses a fake quota store and a fake provider: nothing reaches Sarvam or MongoDB.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from collections.abc import Iterator
from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from llmslim.hosted import (
    ConcurrencyLease,
    HostedQuotaStoreError,
    HostedSarvamConfig,
    HostedSarvamService,
    ReservationDecision,
    UsageReservation,
)
from llmslim.integrations.sarvam import SarvamAuthenticationError, SarvamUsage
from llmslim.tokens import count_tokens

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "web" / "api" / "sarvam_answer.py"
SPEC = importlib.util.spec_from_file_location("studio_sarvam_answer_api", API_PATH)
assert SPEC is not None and SPEC.loader is not None
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
SECRET_KEY = "sk_studio_secret_never_return_0123456789"
MONGODB_URI = "mongodb+srv://ledger-user:ledger-password@cluster.example.invalid"
HMAC_SECRET = "h" * 40
ORIGIN = "https://www.llmslim.app"
CLIENT_IP = "198.51.100.23"
CONTEXT = (
    "Session 13. User: I moved to Pune. Ship any new card to Koregaon Park, Pune. Agent: Updated.\n"
    "Session 14. User: Can I set a monthly spending limit? Agent: Yes, from Card settings."
)
QUESTION = "Where should the replacement card be shipped?"


class FakeQuotaStore:
    def __init__(self) -> None:
        self.rate_allowed = True
        self.acquire_allowed = True
        self.reserve_reason: Optional[str] = None
        self.fail_store = False
        self.calls: list[tuple[str, Any]] = []
        self.settled: list[tuple[UsageReservation, Optional[int], Optional[int]]] = []
        self.released: list[ConcurrencyLease] = []

    def consume_rate(self, **kwargs: Any) -> bool:
        self.calls.append(("rate", kwargs))
        return self.rate_allowed

    def acquire_concurrency(self, **kwargs: Any) -> Optional[ConcurrencyLease]:
        self.calls.append(("acquire", kwargs))
        if not self.acquire_allowed:
            return None
        return ConcurrencyLease("lease", 0, 0, kwargs["client_hash"])

    def release_concurrency(self, lease: ConcurrencyLease) -> None:
        self.released.append(lease)

    def reserve_usage(self, **kwargs: Any) -> ReservationDecision:
        self.calls.append(("reserve", kwargs))
        if self.fail_store:
            raise HostedQuotaStoreError(MONGODB_URI)
        if self.reserve_reason:
            return ReservationDecision(None, self.reserve_reason)
        return ReservationDecision(
            UsageReservation(
                kwargs["request_id"],
                kwargs["identity_hash"],
                "2026-10-12",
                "2026-10",
                kwargs["estimated_input_tokens"],
                kwargs["estimated_cost_micros"],
            )
        )

    def settle_usage(
        self,
        reservation: UsageReservation,
        *,
        actual_input_tokens: Optional[int],
        actual_cost_micros: Optional[int],
    ) -> None:
        self.settled.append((reservation, actual_input_tokens, actual_cost_micros))

    def record_event(self, event: str, **kwargs: Any) -> None:
        self.calls.append(("event", (event, kwargs)))

    def events(self) -> list[str]:
        return [call[1][0] for call in self.calls if call[0] == "event"]


class FakeProvider:
    def __init__(
        self, usage: Optional[SarvamUsage] = None, error: Optional[Exception] = None
    ) -> None:
        self.last_usage = usage
        self.error = error
        self.messages: Any = None
        self.max_tokens: Optional[int] = None
        self.calls = 0

    def chat(self, messages: Any, *, max_tokens: Optional[int] = None) -> str:
        self.calls += 1
        self.messages = messages
        self.max_tokens = max_tokens
        if self.error:
            raise self.error
        return "Ship it to Koregaon Park, Pune."


class Harness:
    def __init__(self) -> None:
        self.store = FakeQuotaStore()
        self.provider = FakeProvider(SarvamUsage(180, 12, 192))
        self.services = 0
        self.raise_on_make: Optional[Exception] = None

    def make_service(self, config: HostedSarvamConfig) -> HostedSarvamService:
        self.services += 1
        if self.raise_on_make is not None:
            raise self.raise_on_make
        return HostedSarvamService(
            config,
            self.store,  # type: ignore[arg-type]
            provider_factory=lambda _model, _maximum, _timeout: self.provider,  # type: ignore[arg-type,return-value]
            clock=lambda: NOW,
        )


@pytest.fixture()
def ready_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    monkeypatch.setenv("LLMSLIM_HOSTED_SARVAM_ENABLED", "true")
    monkeypatch.setenv("SARVAM_API_KEY", SECRET_KEY)
    monkeypatch.setenv("MONGODB_URI", MONGODB_URI)
    monkeypatch.setenv("LLMSLIM_RATE_LIMIT_HMAC_SECRET", HMAC_SECRET)
    monkeypatch.setenv("LLMSLIM_ALLOWED_ORIGINS", f"{ORIGIN}, http://localhost:3000/")
    for name in (
        "LLMSLIM_SARVAM_MAX_BODY_BYTES",
        "LLMSLIM_SARVAM_MAX_TOTAL_CHARS",
        "LLMSLIM_SARVAM_MAX_REQUEST_COST_INR",
        "LLMSLIM_SARVAM_DAILY_BUDGET_INR",
        "LLMSLIM_SARVAM_MONTHLY_BUDGET_INR",
        "LLMSLIM_SARVAM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(api, "_dependencies_available", lambda: True)
    return monkeypatch


@pytest.fixture()
def harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    value = Harness()
    monkeypatch.setattr(api, "make_service", value.make_service)
    return value


Response = tuple[int, dict[str, str], dict[str, Any], bytes]


@pytest.fixture()
def call() -> Iterator[Callable[..., Response]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(
        method: str = "POST",
        body: Any = None,
        *,
        headers: Optional[dict[str, Optional[str]]] = None,
        raw: Optional[bytes] = None,
    ) -> Response:
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
        defaults = {
            "content-type": "application/json",
            "origin": ORIGIN,
            "x-forwarded-for": CLIENT_IP,
        }
        merged: dict[str, Optional[str]] = {**defaults, **(headers or {})}
        sent = {name: value for name, value in merged.items() if value is not None}
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        connection.request(method, "/api/sarvam_answer", body=data, headers=sent)
        response = connection.getresponse()
        payload = response.read()
        result = (
            response.status,
            {name.lower(): value for name, value in response.getheaders()},
            json.loads(payload),
            payload,
        )
        connection.close()
        return result

    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()


def answer_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"context": CONTEXT, "question": QUESTION}
    body.update(overrides)
    return body


# --------------------------------------------------------------------------------- readiness


def test_get_reports_ready_with_public_limits_only(ready_env: pytest.MonkeyPatch, call) -> None:
    status, headers, payload, raw = call("GET")
    assert status == 200
    assert payload["ready"] is True
    assert payload["model"] == "sarvam-105b"
    assert payload["max_context_tokens"] == api.max_context_tokens(HostedSarvamConfig(enabled=True))
    assert payload["max_question_chars"] == api.MAX_QUESTION_CHARS
    assert headers["cache-control"] == "no-store, private"
    assert "budget" not in raw.decode()


@pytest.mark.parametrize(
    "change",
    [
        ("delenv", "SARVAM_API_KEY"),
        ("delenv", "MONGODB_URI"),
        ("setenv", "LLMSLIM_RATE_LIMIT_HMAC_SECRET", "too-short"),
        ("setenv", "LLMSLIM_ALLOWED_ORIGINS", " , "),
        ("setenv", "LLMSLIM_HOSTED_SARVAM_ENABLED", "false"),
        ("delenv", "LLMSLIM_HOSTED_SARVAM_ENABLED"),
        ("setenv", "LLMSLIM_HOSTED_SARVAM_ENABLED", "maybe"),
        ("setenv", "LLMSLIM_SARVAM_MAX_REQUEST_COST_INR", "500"),
        ("packages", None),
    ],
)
def test_every_missing_requirement_keeps_the_step_hidden_and_post_closed(
    ready_env: pytest.MonkeyPatch, harness: Harness, call, change: tuple[Any, ...]
) -> None:
    if change[0] == "delenv":
        ready_env.delenv(change[1])
    elif change[0] == "setenv":
        ready_env.setenv(change[1], change[2])
    else:
        ready_env.setattr(api, "_dependencies_available", lambda: False)
    status, _, payload, _ = call("GET")
    assert status == 200
    assert payload == {"status": "ok", "service": api.SERVICE, "ready": False}

    status, headers, payload, _ = call("POST", answer_body())
    assert status == 503
    assert payload["error"]["code"] in {"hosted_disabled", "invalid_server_config"}
    assert headers.get("connection") != "close"
    assert harness.services == 0
    assert harness.provider.calls == 0


def test_dependencies_are_checked_by_import_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def find_spec(name: str) -> Optional[object]:
        seen.append(name)
        return None if name == "pymongo" else object()

    monkeypatch.setattr(api.importlib.util, "find_spec", find_spec)
    assert api._dependencies_available() is False
    assert seen == ["sarvamai", "pymongo"]


# ---------------------------------------------------------------------------------- origins


@pytest.mark.parametrize(
    "origin",
    [
        None,
        "https://evil.example",
        "https://www.llmslim.app.evil.example",
        "null",
        "http://www.llmslim.app",
    ],
)
def test_requests_from_other_origins_are_refused_before_quota_work(
    ready_env: pytest.MonkeyPatch, harness: Harness, call, origin: Optional[str]
) -> None:
    status, _, payload, _ = call("POST", answer_body(), headers={"origin": origin})
    assert status == 403
    assert payload["error"]["code"] == "origin_not_allowed"
    assert harness.services == 0


def test_origin_allow_list_is_exact_and_ignores_trailing_slashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environ = {"LLMSLIM_ALLOWED_ORIGINS": "https://www.llmslim.app/, http://localhost:3000"}
    assert api.origin_allowed("https://www.llmslim.app", environ)
    assert api.origin_allowed("http://localhost:3000/", environ)
    assert not api.origin_allowed("https://llmslim.app", environ)
    assert not api.origin_allowed(None, environ)
    assert not api.origin_allowed("https://www.llmslim.app", {})


# ---------------------------------------------------------------------------------- success


def test_answer_returns_tokens_cost_and_sets_a_pseudonymous_session(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    status, headers, payload, raw = call("POST", answer_body())
    assert status == 200, payload
    data = payload["data"]
    assert data["answer"] == "Ship it to Koregaon Park, Pune."
    assert data["model"] == "sarvam-105b"
    assert data["context"]["submitted_tokens"] == count_tokens(CONTEXT)
    assert isinstance(data["context"]["sent_tokens"], int) and data["context"]["sent_tokens"] > 0
    assert data["context"]["further_compressed"] is False
    usage = data["usage"]
    assert usage["provider_reported"]["prompt_tokens"] == 180
    assert usage["provider_reported"]["completion_tokens"] == 12
    assert usage["provider_reported"]["total_tokens"] == 192
    assert usage["provider_reported"]["cost_inr"] > 0
    assert usage["estimated"]["max_cost_inr"] > 0
    assert usage["accounting_basis"] == "PROVIDER_REPORTED"
    # Only the answer and counts come back, not the planned context.
    assert "plan" not in data and "final_context" not in raw.decode()

    cookie = headers["set-cookie"]
    assert cookie.startswith(f"{api.SESSION_COOKIE}=")
    for flag in (
        "HttpOnly",
        "Secure",
        "SameSite=Strict",
        f"Path={api.COOKIE_PATH}",
        "Max-Age=86400",
    ):
        assert flag in cookie
    assert headers["cache-control"] == "no-store, private"
    assert headers["content-security-policy"] == "default-src 'none'"
    assert headers["x-content-type-options"] == "nosniff"

    sent = json.dumps(harness.provider.messages)
    assert "Koregaon Park" in sent and QUESTION in sent
    assert "Never claim to have executed a tool" in sent
    assert harness.provider.max_tokens == api.ANSWER_MAX_OUTPUT_TOKENS
    assert harness.store.settled and harness.store.released
    assert {"accepted", "success"} <= set(harness.store.events())

    session = cookie.split(";", 1)[0]
    status, headers, _, _ = call("POST", answer_body(), headers={"cookie": session})
    assert status == 200
    assert "set-cookie" not in headers


def test_server_fixes_model_output_budget_and_policy() -> None:
    config = HostedSarvamConfig(enabled=True, max_output_tokens=64)
    request, tokens = api.build_request({"context": " text ", "question": " why? "}, config)
    assert request == {
        "documents": [" text "],
        "query": "why?",
        "model": "sarvam-105b",
        "max_input_tokens": config.max_input_tokens,
        "max_output_tokens": 64,
        "policy": "balanced",
    }
    assert tokens == count_tokens(" text ")


def test_oversized_context_is_fitted_by_the_planner_and_reported() -> None:
    result = {
        "answer": "ok",
        "request_id": "r",
        "plan": {"metrics": {"tokens_by_kind": {"rag_document": 90}, "items_compressed": 1}},
        "usage": {},
    }
    public = api.public_result(result, 120, "sarvam-105b")
    assert public["context"] == {
        "submitted_tokens": 120,
        "sent_tokens": 90,
        "further_compressed": True,
    }
    fallback = api.public_result(
        {"answer": "ok", "plan": {"metrics": {"planned_tokens": 70}}}, 80, "m"
    )
    assert fallback["context"]["sent_tokens"] == 70
    assert (
        api.public_result({"answer": "ok", "plan": None}, 1, "m")["context"]["sent_tokens"] is None
    )


# ------------------------------------------------------------------------ payload validation


def test_oversize_bodies_are_refused_and_counted(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    ready_env.setenv("LLMSLIM_SARVAM_MAX_BODY_BYTES", "2048")
    status, headers, payload, _ = call("POST", raw=b"x" * 4096)
    assert status == 413
    assert payload["error"]["code"] == "body_too_large"
    assert headers.get("connection") != "close"
    assert "oversized_request" in harness.store.events()
    assert harness.provider.calls == 0


def test_contexts_over_the_token_or_character_limit_are_refused(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    limit = api.max_context_tokens(HostedSarvamConfig(enabled=True))
    long_context = "word " * (limit + 200)
    assert count_tokens(long_context) > limit
    assert len(long_context) < HostedSarvamConfig().max_total_chars
    status, _, payload, _ = call("POST", answer_body(context=long_context))
    assert status == 413
    assert payload["error"]["code"] == "context_too_large"
    assert f"{limit:,}" in payload["error"]["message"]

    ready_env.setenv("LLMSLIM_SARVAM_MAX_TOTAL_CHARS", "1000")
    status, _, payload, _ = call("POST", answer_body(context="y" * 1_500))
    assert status == 413
    assert payload["error"]["code"] == "input_too_large"
    assert harness.provider.calls == 0
    assert harness.store.events().count("oversized_request") == 2


@pytest.mark.parametrize(
    ("raw", "content_type", "status", "code"),
    [
        (b"{not json", "application/json", 400, "invalid_json"),
        (b"\xff\xfe", "application/json", 400, "invalid_json"),
        (b"[1, 2]", "application/json", 400, "object_required"),
        (b'{"context": "a", "question": "b"}', "text/plain", 415, "json_required"),
        (
            b'{"context": "a", "question": "b", "api_key": "x"}',
            "application/json",
            400,
            "unsupported_field",
        ),
        (
            b'{"context": "a", "question": "b", "model": "x"}',
            "application/json",
            400,
            "unsupported_field",
        ),
        (b'{"context": "", "question": "b"}', "application/json", 422, "invalid_context"),
        (b'{"context": ["a"], "question": "b"}', "application/json", 422, "invalid_context"),
        (b'{"context": "a", "question": "  "}', "application/json", 422, "invalid_question"),
        (b'{"context": "a"}', "application/json", 422, "invalid_question"),
    ],
)
def test_malformed_requests_get_clean_json_errors(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    raw: bytes,
    content_type: str,
    status: int,
    code: str,
) -> None:
    got, _, payload, _ = call("POST", raw=raw, headers={"content-type": content_type})
    assert got == status
    assert payload == {"error": {"code": code, "message": payload["error"]["message"]}}
    assert "invalid_request" in harness.store.events()
    assert harness.provider.calls == 0


def test_question_length_is_bounded(ready_env: pytest.MonkeyPatch, harness: Harness, call) -> None:
    status, _, payload, _ = call("POST", answer_body(question="q" * (api.MAX_QUESTION_CHARS + 1)))
    assert status == 422
    assert payload["error"]["code"] == "invalid_question"


@pytest.mark.parametrize("declared", [None, "not-a-number", str(api.DISCARD_LIMIT_BYTES + 1)])
def test_unknown_or_huge_bodies_are_refused_unread_and_the_connection_closed(
    ready_env: pytest.MonkeyPatch, harness: Harness, declared: Optional[str]
) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
        connection.putrequest("POST", "/api/sarvam_answer")
        connection.putheader("origin", ORIGIN)
        connection.putheader("content-type", "application/json")
        if declared is not None:
            connection.putheader("content-length", declared)
        connection.endheaders()
        response = connection.getresponse()
        assert response.status == 413
        assert response.getheader("Connection") == "close"
        assert json.loads(response.read())["error"]["code"] == "body_too_large"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()


# ------------------------------------------------------------------- rate limits and budgets


def test_rate_limits_return_429_with_retry_after(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    harness.store.rate_allowed = False
    status, headers, payload, _ = call("POST", answer_body())
    assert status == 429
    assert payload["error"]["code"] == "rate_limited"
    assert int(headers["retry-after"]) >= 1
    assert harness.provider.calls == 0


@pytest.mark.parametrize(
    ("setup", "status", "code"),
    [
        (
            lambda h, env: setattr(h.store, "reserve_reason", "global_spend_quota"),
            503,
            "hosted_budget_exhausted",
        ),
        (
            lambda h, env: setattr(h.store, "reserve_reason", "identity_token_quota"),
            429,
            "daily_quota_reached",
        ),
        (lambda h, env: setattr(h.store, "acquire_allowed", False), 429, "concurrency_limited"),
        (
            lambda h, env: env.setenv("LLMSLIM_SARVAM_MAX_REQUEST_COST_INR", "0.000001"),
            429,
            "request_cost_limit",
        ),
    ],
)
def test_budget_and_quota_exhaustion_fail_closed_with_clean_json(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    setup: Callable[[Harness, pytest.MonkeyPatch], None],
    status: int,
    code: str,
) -> None:
    setup(harness, ready_env)
    got, headers, payload, _ = call("POST", answer_body())
    assert got == status
    assert payload["error"]["code"] == code
    assert int(headers["retry-after"]) >= 1
    assert harness.provider.calls == 0


# ------------------------------------------------------------------ failures and secrecy


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError(SECRET_KEY),
        SarvamAuthenticationError(f"bad key {SECRET_KEY}"),
        TimeoutError(MONGODB_URI),
    ],
)
def test_provider_errors_are_sanitized(
    ready_env: pytest.MonkeyPatch, harness: Harness, call, error: Exception
) -> None:
    harness.provider = FakeProvider(error=error)
    status, _, payload, raw = call("POST", answer_body())
    assert status == 502
    assert payload["error"]["code"] == "provider_unavailable"
    assert SECRET_KEY not in raw.decode() and "ledger-password" not in raw.decode()
    assert harness.store.settled[0][1:] == (None, None)
    assert harness.store.released


def test_quota_store_outage_is_a_clean_503_and_is_reported(
    ready_env: pytest.MonkeyPatch, harness: Harness, call, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[BaseException, str]] = []
    monkeypatch.setattr(
        api._sentry, "capture", lambda error, *, function: captured.append((error, function))
    )
    harness.raise_on_make = HostedQuotaStoreError("durable quota store unavailable")
    status, _, payload, raw = call("POST", answer_body())
    assert status == 503
    assert payload["error"]["code"] == "quota_store_unavailable"
    assert captured and captured[0][1] == "sarvam_answer"

    harness.raise_on_make = None
    harness.store.fail_store = True
    status, _, payload, raw = call("POST", answer_body())
    assert status == 503
    assert payload["error"]["code"] == "quota_store_unavailable"
    assert "ledger-password" not in raw.decode() and "mongodb" not in raw.decode().lower()


def test_unexpected_errors_are_500_and_reported_without_details(
    ready_env: pytest.MonkeyPatch, harness: Harness, call, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str] = []
    monkeypatch.setattr(
        api._sentry, "capture", lambda error, *, function: captured.append(function)
    )

    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError(f"leaked {SECRET_KEY}")

    monkeypatch.setattr(api, "build_request", explode)
    status, _, payload, raw = call("POST", answer_body())
    assert status == 500
    assert payload["error"]["code"] == "answer_failed"
    assert SECRET_KEY not in raw.decode()
    assert captured == ["sarvam_answer"]


def test_no_secret_or_client_address_reaches_a_response_or_a_log(
    ready_env: pytest.MonkeyPatch, harness: Harness, call, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = [
        call("GET"),
        call("POST", answer_body()),
        call("POST", answer_body(question="")),
        call("POST", raw=b"{oops"),
        call("POST", answer_body(), headers={"origin": "https://evil.example"}),
        call(
            "POST",
            answer_body(),
            headers={"x-sarvam-api-key": SECRET_KEY, "authorization": f"Bearer {SECRET_KEY}"},
        ),
    ]
    harness.provider = FakeProvider(error=RuntimeError(SECRET_KEY))
    responses.append(call("POST", answer_body()))
    for _status, headers, _payload, raw in responses:
        blob = raw.decode() + json.dumps(headers)
        for secret in (SECRET_KEY, "ledger-password", HMAC_SECRET, CLIENT_IP):
            assert secret not in blob
    out, err = capsys.readouterr()
    assert out == "" and err == ""


def test_identity_is_hashed_and_rotates_invalid_sessions(ready_env: pytest.MonkeyPatch) -> None:
    identity = api.identity_for(
        {"x-vercel-forwarded-for": CLIENT_IP, "cookie": f"{api.SESSION_COOKIE}={'S' * 24}"}
    )
    assert CLIENT_IP not in repr(identity) and HMAC_SECRET not in repr(identity)
    assert identity.is_new_session is False
    forged = api.identity_for({"x-forwarded-for": CLIENT_IP, "cookie": f"{api.SESSION_COOKIE}=bad"})
    assert forged.is_new_session is True
    assert forged.ip_hash == identity.ip_hash
    assert api._session_from_cookie("=;;\x00broken") is None
    assert api._session_from_cookie(None) is None


# ------------------------------------------------------------------------- the website side


def test_answer_step_in_the_browser_holds_no_secret_or_storage() -> None:
    source = (ROOT / "web" / "src" / "components" / "studio" / "SarvamAnswer.tsx").read_text(
        encoding="utf-8"
    )
    assert "/api/sarvam_answer" in source
    for forbidden in (
        "SARVAM_API_KEY",
        "NEXT_PUBLIC_",
        "localStorage",
        "sessionStorage",
        "x-sarvam-api-key",
    ):
        assert forbidden not in source


def test_local_dev_reroutes_the_answer_function() -> None:
    config = (ROOT / "web" / "next.config.ts").read_text(encoding="utf-8")
    assert '"sarvam_answer"' in config


def test_production_installs_the_hosted_extras_from_pypi() -> None:
    lines = (ROOT / "web" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pinned = next(line for line in lines if line.startswith("llmslim"))
    assert pinned.startswith("llmslim[") and "sarvam" in pinned and "mongodb" in pinned
    assert pinned.endswith("==0.8.1")
