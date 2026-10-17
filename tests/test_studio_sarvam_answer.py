"""Security and quota tests for the Studio "Answer with Sarvam" function (web/api/sarvam_answer.py).

Restored from the hosted Sarvam route tests removed in the 0.8 redesign and adapted to the new
function. Every test uses a fake quota store and a fake Sarvam SDK client (or the real SDK on an
in-memory transport): nothing reaches Sarvam or MongoDB.
"""

from __future__ import annotations

import importlib.util
import json
import threading
from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

import pytest

import llmslim.hosted as hosted_module
from llmslim.hosted import (
    ConcurrencyLease,
    HostedQuotaStoreError,
    HostedSarvamConfig,
    HostedSarvamService,
    ReservationDecision,
    UsageReservation,
    estimate_sarvam_cost_micros,
)
from llmslim.tokens import count_tokens

ROOT = Path(__file__).resolve().parents[1]
# Production runs PyPI llmslim 0.9.0; CI imports the repository's Core. Both have the two behaviours
# below. The endpoint must also stay safe on an older Core (0.8.x), so tests that depend on
# llmslim.hosted's own accounting branch on what it can do:
# - EXACT_BOUND: hosted reserves an exact UTF-8 byte bound of the messages it sends and refuses
#   (413) anything above max_input_tokens. 0.8.x reserves min(max_input_tokens, planned x multiplier),
#   which the endpoint pins to its own (larger) byte bound.
# - RELEASES_UNBILLED: hosted releases the reservation for errors Sarvam returns without billing.
EXACT_BOUND = hasattr(hosted_module, "sarvam_prompt_token_bound")
RELEASES_UNBILLED = hasattr(hosted_module, "is_unbilled")
# Template tokens a chat model may add per message on top of the content's bytes.
PER_MESSAGE_TOKENS = 16
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
ANSWER = "Ship it to Koregaon Park, Pune."


class FakeQuotaStore:
    """Records calls; ``counting=True`` enforces the limits like the MongoDB store does."""

    def __init__(self, counting: bool = False) -> None:
        self.counting = counting
        self.rate_allowed = True
        self.acquire_allowed = True
        self.reserve_reason: Optional[str] = None
        self.fail_store = False
        self.calls: list[tuple[str, Any]] = []
        self.settled: list[tuple[UsageReservation, Optional[int], Optional[int]]] = []
        self.released: list[ConcurrencyLease] = []
        self.rates: dict[tuple[str, str], int] = defaultdict(int)
        self.tokens: dict[str, int] = defaultdict(int)

    def consume_rate(self, **kwargs: Any) -> bool:
        self.calls.append(("rate", kwargs))
        if not self.counting:
            return self.rate_allowed
        key = (kwargs["scope"], kwargs["subject"])
        if self.rates[key] >= kwargs["limit"]:
            return False
        self.rates[key] += 1
        return True

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
        identity, tokens = kwargs["identity_hash"], kwargs["estimated_input_tokens"]
        if self.counting:
            if self.tokens[identity] + tokens > kwargs["input_tokens_per_day"]:
                return ReservationDecision(None, "identity_token_quota")
            self.tokens[identity] += tokens
        return ReservationDecision(
            UsageReservation(
                kwargs["request_id"],
                identity,
                "2026-10-12",
                "2026-10",
                tokens,
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

    def reservations(self) -> list[dict[str, Any]]:
        return [call[1] for call in self.calls if call[0] == "reserve"]


class FakeChat:
    def __init__(self, sdk: "FakeSdk") -> None:
        self.sdk = sdk

    def completions(self, **kwargs: Any) -> Any:
        self.sdk.calls.append(kwargs)
        if self.sdk.error is not None:
            raise self.sdk.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=ANSWER))],
            usage=SimpleNamespace(prompt_tokens=180, completion_tokens=12, total_tokens=192),
        )


class FakeSdk:
    """Stands in for ``sarvamai.SarvamAI``: only ``chat.completions`` is used."""

    def __init__(self, error: Optional[Exception] = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.chat = FakeChat(self)


class Harness:
    def __init__(self) -> None:
        self.store = FakeQuotaStore()
        self.sdk = FakeSdk()
        self.services = 0
        self.timeouts: list[float] = []
        self.raise_on_make: Optional[Exception] = None

    def make_service(self, config: HostedSarvamConfig) -> HostedSarvamService:
        self.services += 1
        if self.raise_on_make is not None:
            raise self.raise_on_make
        return HostedSarvamService(config, self.store, clock=lambda: NOW)  # type: ignore[arg-type]

    def sdk_client(self, timeout: float) -> FakeSdk:
        self.timeouts.append(timeout)
        return self.sdk


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
        "LLMSLIM_SARVAM_MAX_INPUT_TOKENS",
        "LLMSLIM_SARVAM_LEASE_SECONDS",
        "LLMSLIM_SARVAM_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(api, "_dependencies_available", lambda: True)
    return monkeypatch


@pytest.fixture()
def harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    value = Harness()
    monkeypatch.setattr(api, "make_service", value.make_service)
    monkeypatch.setattr(api, "_sdk_client", value.sdk_client)
    return value


@pytest.fixture()
def reports(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, BaseException, str]]:
    seen: list[tuple[str, BaseException, str]] = []
    monkeypatch.setattr(
        api._sentry,
        "capture",
        lambda error, *, function, now=None: seen.append(("error", error, function)),
    )
    monkeypatch.setattr(
        api._sentry,
        "capture_provider_failure",
        lambda error, *, function, now=None: seen.append(("provider", error, function)),
    )
    return seen


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


def default_config(**overrides: Any) -> HostedSarvamConfig:
    return HostedSarvamConfig(enabled=True, **overrides)


# --------------------------------------------------------------------------------- readiness


def test_get_reports_ready_with_public_limits_and_the_installed_price_table(
    ready_env: pytest.MonkeyPatch, call
) -> None:
    status, headers, payload, raw = call("GET")
    assert status == 200
    assert payload["ready"] is True
    assert payload["model"] == "sarvam-105b"
    assert payload["max_prompt_bytes"] == api.max_prompt_bytes(default_config(), {})
    assert payload["max_prompt_bytes"] == (
        api.DEFAULT_INPUT_BUDGET_TOKENS - api.FRAMING_BYTES - api.TEMPLATE_TOKENS
    )
    assert payload["max_question_chars"] == api.MAX_QUESTION_CHARS
    prices = payload["pricing"]
    assert prices["core_version"] == api.llmslim.__version__
    assert prices["as_of"] and prices["currency"] == "INR"
    assert prices["input_per_million"] > 0 and prices["output_per_million"] > 0
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
        # Not even the smallest request's output fits a 1-paisa cap.
        ("setenv", "LLMSLIM_SARVAM_MAX_REQUEST_COST_INR", "0.01"),
        # A lease shorter than one provider call, or longer than the function may live.
        ("setenv", "LLMSLIM_SARVAM_LEASE_SECONDS", "20"),
        ("setenv", "LLMSLIM_SARVAM_LEASE_SECONDS", "120"),
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
    assert harness.sdk.calls == []


def test_readiness_is_reported_only_to_allowed_origins(ready_env: pytest.MonkeyPatch, call) -> None:
    # Browsers omit Origin on same-origin GETs, so the host decides: a preview deployment that is
    # not in the allow-list hides the step instead of offering one that would fail.
    preview = {
        "origin": None,
        "host": "llmslim-git-feature.vercel.app",
        "x-forwarded-proto": "https",
    }
    assert call("GET", headers=preview)[2]["ready"] is False
    production = {"origin": None, "host": "www.llmslim.app", "x-forwarded-proto": "https"}
    assert call("GET", headers=production)[2]["ready"] is True
    assert call("GET", headers={"origin": "https://evil.example"})[2]["ready"] is False


def test_request_origin_falls_back_to_the_forwarded_host() -> None:
    assert api.request_origin({"origin": "https://a.example"}) == "https://a.example"
    assert (
        api.request_origin({"x-forwarded-host": "b.example, c", "x-forwarded-proto": "https"})
        == "https://b.example"
    )
    assert api.request_origin({"host": "localhost:3000", "x-forwarded-proto": "http"}) == (
        "http://localhost:3000"
    )
    assert api.request_origin({}) is None
    # next dev forwards the host without the scheme; local hosts are plain HTTP.
    assert api.request_origin({"x-forwarded-host": "localhost:3123"}) == "http://localhost:3123"
    assert api.request_origin({"host": "[::1]:3000"}) == "http://[::1]:3000"
    assert api.request_origin({"host": "www.llmslim.app"}) == "https://www.llmslim.app"


def test_dependencies_are_checked_by_import_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def find_spec(name: str) -> Optional[object]:
        seen.append(name)
        return None if name == "pymongo" else object()

    monkeypatch.setattr(api.importlib.util, "find_spec", find_spec)
    assert api._dependencies_available() is False
    assert seen == ["sarvamai", "pymongo"]


def test_lease_outlives_the_call_and_the_function_outlives_the_lease() -> None:
    config = default_config()
    timeout = api.provider_timeout(config)
    assert timeout <= api.MAX_PROVIDER_TIMEOUT_SECONDS
    assert config.lease_seconds >= timeout + api.CONNECT_TIMEOUT_SECONDS + api.LEASE_MARGIN_SECONDS
    vercel = json.loads((ROOT / "web" / "vercel.json").read_text(encoding="utf-8"))
    max_duration = vercel["functions"]["api/sarvam_answer.py"]["maxDuration"]
    assert max_duration == api.MAX_DURATION_SECONDS
    assert max_duration >= config.lease_seconds + api.STARTUP_ALLOWANCE_SECONDS
    assert api.timing_ok(config)
    assert not api.timing_ok(default_config(lease_seconds=30))
    assert api.provider_timeout(default_config(provider_timeout_seconds=300.0)) == 25.0


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


def test_origin_allow_list_is_exact_and_ignores_trailing_slashes() -> None:
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
    assert data["answer"] == ANSWER
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
    assert data["pricing"]["core_version"] == api.llmslim.__version__
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

    (sent,) = harness.sdk.calls
    assert "Koregaon Park" in json.dumps(sent["messages"]) and QUESTION in json.dumps(sent)
    assert "Never claim to have executed a tool" in json.dumps(sent["messages"])
    assert sent["max_tokens"] == api.ANSWER_MAX_OUTPUT_TOKENS
    # One attempt only: the SDK's default two retries are switched off on every call.
    assert sent["request_options"] == {"max_retries": 0}
    assert harness.timeouts == [api.provider_timeout(default_config())]
    assert harness.store.settled and harness.store.released
    assert {"accepted", "success"} <= set(harness.store.events())

    session = cookie.split(";", 1)[0]
    status, headers, _, _ = call(
        "POST", answer_body(question=QUESTION + " Today?"), headers={"cookie": session}
    )
    assert status == 200
    assert "set-cookie" not in headers


def test_server_fixes_model_output_budget_and_policy() -> None:
    config = default_config(max_output_tokens=64)
    request, tokens, reserved = api.build_request(
        {"context": " text ", "question": " why? "}, config, {}
    )
    assert reserved == api.prompt_bound_tokens(" text ", "why?") >= api.MIN_RESERVED_INPUT_TOKENS
    assert request == {
        "documents": [" text "],
        "query": "why?",
        "model": "sarvam-105b",
        "max_input_tokens": reserved,
        "max_output_tokens": 64,
        "policy": "balanced",
    }
    assert tokens == count_tokens(" text ")


def test_public_result_reports_what_reached_sarvam() -> None:
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
        {"answer": "ok", "plan": {"metrics": {"planned_tokens": 70}}}, 80, "sarvam-105b"
    )
    assert fallback["context"]["sent_tokens"] == 70
    assert (
        api.public_result({"answer": "ok", "plan": None}, 1, "sarvam-105b")["context"][
            "sent_tokens"
        ]
        is None
    )


# ------------------------------------------------------------- the byte bound and the ledger


def test_the_ledger_reserves_the_byte_bound_which_covers_any_bill(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    # 2,000 emoji: Core without tiktoken counts ~500 tokens; a byte-level tokenizer can bill 8,000.
    context = "Card goes to Koregaon Park. " + "😀" * 2_000
    status, _, payload, _ = call("POST", answer_body(context=context))
    assert status == 200, payload
    (reservation,) = harness.store.reservations()
    reserved = reservation["estimated_input_tokens"]
    bound = api.prompt_bound_tokens(context, QUESTION)
    assert bound >= len(context.encode("utf-8")) > count_tokens(context)
    (sent,) = harness.sdk.calls
    sent_bytes = sum(len(message["content"].encode("utf-8")) for message in sent["messages"])
    # Never below any possible bill: each token covers at least one byte, plus template tokens.
    assert reserved >= sent_bytes + PER_MESSAGE_TOKENS * len(sent["messages"])
    # Never above the bound the endpoint checked against the budget and the cost cap before spend.
    assert reserved <= bound
    if EXACT_BOUND:
        assert reserved == hosted_module.sarvam_prompt_token_bound(sent["messages"])
    else:
        assert reserved == bound
    assert api.messages_bound_tokens(sent["messages"]) <= bound
    assert reservation["estimated_cost_micros"] == estimate_sarvam_cost_micros(
        "sarvam-105b", reserved, api.ANSWER_MAX_OUTPUT_TOKENS
    )
    # Settlement refunds down to what Sarvam reported.
    assert harness.store.settled[0][1] == 180


def test_dense_text_past_the_byte_budget_is_refused_before_any_spend(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    # The reviewer's case: 23,000 emoji counted as ~7,259 tokens but billed as ~61,000.
    body = json.dumps(answer_body(context="😀" * 23_000), ensure_ascii=False).encode()
    status, _, payload, _ = call("POST", raw=body)
    assert status == 413
    assert payload["error"]["code"] == "context_too_large"
    assert harness.store.reservations() == []
    assert harness.sdk.calls == []
    assert "oversized_request" in harness.store.events()


def test_the_per_request_cost_cap_bounds_the_byte_budget(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    config = default_config()
    cap_tokens = 4_000
    cap = Decimal(
        estimate_sarvam_cost_micros("sarvam-105b", cap_tokens, api.ANSWER_MAX_OUTPUT_TOKENS)
    ) / Decimal(1_000_000)
    ready_env.setenv("LLMSLIM_SARVAM_MAX_REQUEST_COST_INR", str(cap))
    capped = HostedSarvamConfig.from_env()
    assert api.max_reserved_tokens(capped) == cap_tokens
    assert api.max_reserved_tokens(config, {}) == api.DEFAULT_INPUT_BUDGET_TOKENS
    fits = "a" * (cap_tokens - 2 * len(QUESTION) - api.FRAMING_BYTES - api.TEMPLATE_TOKENS)
    assert call("POST", answer_body(context=fits))[0] == 200
    status, _, payload, _ = call("POST", answer_body(context=fits + "a"))
    assert status == 413 and payload["error"]["code"] == "context_too_large"
    assert call("GET")[2]["max_prompt_bytes"] == len(fits) + 2 * len(QUESTION)


def test_the_budget_follows_the_operator_setting(ready_env: pytest.MonkeyPatch) -> None:
    ready_env.setenv("LLMSLIM_SARVAM_MAX_INPUT_TOKENS", "4096")
    config = HostedSarvamConfig.from_env()
    assert api.input_budget(config) == 4096
    assert api.max_prompt_bytes(config) == 4096 - api.FRAMING_BYTES - api.TEMPLATE_TOKENS


def test_normal_english_and_indic_contexts_fit_the_default_budget() -> None:
    config = default_config()
    english = "The customer moved to Pune and wants the card at Koregaon Park. " * 200  # ~13 KB
    hindi = "ग्राहक पुणे चला गया और कार्ड कोरेगांव पार्क भेजना है। " * 80  # ~11 KB
    for context in (english, hindi):
        request, _, reserved = api.build_request(
            {"context": context, "question": "कार्ड कहाँ भेजें?"}, config, {}
        )
        assert reserved <= api.DEFAULT_INPUT_BUDGET_TOKENS
        assert api.cost_ok(config, reserved)


def test_a_prompt_larger_than_the_reservation_is_never_sent(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    reports: list[tuple[str, BaseException, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pretend the framing estimate were wrong: the last check before the SDK still holds.
    monkeypatch.setattr(api, "prompt_bound_tokens", lambda context, question: 10)
    status, _, payload, _ = call("POST", answer_body(context="word " * 400))
    assert harness.sdk.calls == []
    if EXACT_BOUND:
        # 0.9.0 measures the exact messages and refuses before reserving.
        assert (status, payload["error"]["code"]) == (413, "input_too_large")
        assert harness.store.reservations() == []
    else:
        # 0.8.x would send it; the endpoint's last check refuses instead, and the conservative
        # reservation stays charged although nothing was billed.
        assert (status, payload["error"]["code"]) == (502, "provider_unavailable")
        assert any(isinstance(error, api.PromptBoundExceeded) for _, error, _ in reports)
        assert harness.store.settled[0][1:] == (None, None)


def test_the_last_check_refuses_a_prompt_above_its_limit() -> None:
    sdk = FakeSdk()
    chat = api._GuardedClient(sdk, prompt_limit=100).chat
    with pytest.raises(api.PromptBoundExceeded):
        chat.completions(messages=[{"role": "user", "content": "x" * 100}])
    assert sdk.calls == []
    chat.completions(messages=[{"role": "user", "content": "x" * (100 - api.TEMPLATE_TOKENS)}])
    assert len(sdk.calls) == 1


# ------------------------------------------------------------------ identity and cookies


def counting_env(env: pytest.MonkeyPatch, tokens_per_day: int = 100_000) -> None:
    for name, value in {
        "LLMSLIM_SARVAM_BURST_REQUESTS": "20",
        "LLMSLIM_SARVAM_MAX_REQUESTS_PER_MINUTE": "60",
        "LLMSLIM_SARVAM_MAX_REQUESTS_PER_HOUR": "1000",
        "LLMSLIM_SARVAM_MAX_REQUESTS_PER_DAY": "5000",
        "LLMSLIM_SARVAM_MAX_INPUT_TOKENS_PER_DAY": str(tokens_per_day),
    }.items():
        env.setenv(name, value)


@pytest.mark.parametrize("keeps_cookie", [True, False])
def test_dropping_the_cookie_does_not_reset_the_daily_token_quota(
    ready_env: pytest.MonkeyPatch, harness: Harness, call, keeps_cookie: bool
) -> None:
    # Measure one request's reservation (it depends on the installed Core), then allow exactly
    # three a day on this network. Every question below has the same length.
    assert call("POST", answer_body(question=f"{QUESTION} (9)"))[0] == 200
    reserved = harness.store.reservations()[0]["estimated_input_tokens"]
    counting_env(ready_env, 3 * reserved + 10)
    harness.store = FakeQuotaStore(counting=True)
    cookie: Optional[str] = None
    statuses = []
    for attempt in range(5):
        headers = {"cookie": cookie} if cookie else {}
        status, response_headers, payload, _ = call(
            "POST", answer_body(question=f"{QUESTION} ({attempt})"), headers=headers
        )
        statuses.append((status, payload.get("error", {}).get("code")))
        if keeps_cookie and "set-cookie" in response_headers:
            cookie = response_headers["set-cookie"].split(";", 1)[0]
    # Three reservations fit the network's allowance; the fourth is refused either way.
    assert statuses[:3] == [(200, None)] * 3
    assert statuses[3:] == [(429, "daily_quota_reached")] * 2


def test_repeat_limiter_and_concurrency_key_on_the_network(
    ready_env: pytest.MonkeyPatch, harness: Harness, call
) -> None:
    counting_env(ready_env)
    harness.store = FakeQuotaStore(counting=True)
    codes = [call("POST", answer_body())[2].get("error", {}).get("code") for _ in range(5)]
    repeats = default_config().high_cost_repeats_per_hour
    assert codes[:repeats] == [None] * repeats
    assert codes[repeats] == "repeated_high_cost_request"
    acquired = {call_[1]["client_hash"] for call_ in harness.store.calls if call_[0] == "acquire"}
    reserved = {call_["identity_hash"] for call_ in harness.store.reservations()}
    ip_hash = api.identity_for({"x-forwarded-for": CLIENT_IP}).ip_hash
    assert acquired == reserved == {ip_hash}


def test_identity_is_hashed_keys_quotas_on_the_network_and_rotates_bad_sessions(
    ready_env: pytest.MonkeyPatch,
) -> None:
    identity = api.identity_for(
        {"x-vercel-forwarded-for": CLIENT_IP, "cookie": f"{api.SESSION_COOKIE}={'S' * 24}"}
    )
    assert CLIENT_IP not in repr(identity) and HMAC_SECRET not in repr(identity)
    assert identity.is_new_session is False
    assert identity.combined_hash == identity.ip_hash
    fresh = api.identity_for({"x-forwarded-for": CLIENT_IP, "cookie": f"{api.SESSION_COOKIE}=bad"})
    assert fresh.is_new_session is True
    assert fresh.combined_hash == identity.combined_hash
    assert fresh.session_hash != identity.session_hash


def test_ipv6_clients_are_limited_per_64_prefix(ready_env: pytest.MonkeyPatch) -> None:
    def ip_hash(address: str) -> str:
        return api.identity_for({"x-forwarded-for": address}).ip_hash

    assert ip_hash("2001:db8:1:2::1") == ip_hash("2001:db8:1:2:ffff:ffff:ffff:fffe")
    assert ip_hash("2001:db8:1:2::1") != ip_hash("2001:db8:1:3::1")
    assert ip_hash("::ffff:198.51.100.23") == ip_hash("198.51.100.23")
    assert ip_hash("198.51.100.23") != ip_hash("198.51.100.24")
    assert api.network_address("2001:db8:1:2:aaaa::1, 10.0.0.1") == "2001:db8:1:2::"
    assert api.network_address("not an address") == "unknown"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (f"{api.SESSION_COOKIE}={'S' * 24}", "S" * 24),
        # A malformed cookie before ours must not hide ours (SimpleCookie drops everything after it).
        (f'bad"cookie=1; other=\\x; {api.SESSION_COOKIE}={"A" * 30}', "A" * 30),
        (f"  theme=dark ;{api.SESSION_COOKIE}={'b' * 20};x=1", "b" * 20),
        (f"x{api.SESSION_COOKIE}={'S' * 24}", None),
        (f"{api.SESSION_COOKIE}={'S' * 19}", None),
        (f"{api.SESSION_COOKIE}={'S' * 24}!", None),
        (f'{api.SESSION_COOKIE}="{"S" * 24}"', None),
        (f"{api.SESSION_COOKIE}={'S' * 24}; " + "z=" + "y" * 5_000, None),
        ("=;;\x00broken", None),
        (None, None),
        ("", None),
    ],
)
def test_session_cookie_is_parsed_strictly(header: Optional[str], expected: Optional[str]) -> None:
    assert api._session_from_cookie(header) == expected


def test_cookie_parsing_is_linear_on_hostile_headers() -> None:
    import time

    hostile = '"' + "\\" * 4_000 + ";" * 90
    started = time.perf_counter()
    for _ in range(200):
        api._session_from_cookie(hostile)
    assert time.perf_counter() - started < 1.0


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
    assert harness.sdk.calls == []


@pytest.mark.parametrize(
    ("raw", "content_type", "status", "code"),
    [
        (b"{not json", "application/json", 400, "invalid_json"),
        (b"\xff\xfe", "application/json", 400, "invalid_json"),
        (b"[1, 2]", "application/json", 400, "object_required"),
        (b"[" * 50_000 + b"]" * 50_000, "application/json", 400, "invalid_json"),
        (b'{"context": ' + b"[" * 40 + b"]" * 40 + b"}", "application/json", 400, "invalid_json"),
        (
            b'{"context": ' + b"9" * 4_400 + b', "question": "q"}',
            "application/json",
            400,
            "invalid_json",
        ),
        (b'{"context": NaN, "question": "q"}', "application/json", 400, "invalid_json"),
        (b'{"context": "a\\ud800b", "question": "q"}', "application/json", 422, "invalid_text"),
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
    ids=lambda value: value[:24] if isinstance(value, bytes) else str(value),
)
def test_malformed_requests_get_clean_json_errors_and_no_report(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    reports: list[tuple[str, BaseException, str]],
    raw: bytes,
    content_type: str,
    status: int,
    code: str,
) -> None:
    ready_env.setenv("LLMSLIM_SARVAM_MAX_BODY_BYTES", "200000")
    got, _, payload, _ = call("POST", raw=raw, headers={"content-type": content_type})
    assert got == status
    assert payload == {"error": {"code": code, "message": payload["error"]["message"]}}
    assert "invalid_request" in harness.store.events()
    assert harness.sdk.calls == []
    assert reports == []


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
    assert harness.sdk.calls == []


@pytest.mark.parametrize(
    ("setup", "status", "code"),
    [
        (
            lambda h: setattr(h.store, "reserve_reason", "global_spend_quota"),
            503,
            "hosted_budget_exhausted",
        ),
        (
            lambda h: setattr(h.store, "reserve_reason", "identity_token_quota"),
            429,
            "daily_quota_reached",
        ),
        (lambda h: setattr(h.store, "acquire_allowed", False), 429, "concurrency_limited"),
    ],
)
def test_budget_and_quota_exhaustion_fail_closed_with_clean_json(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    setup: Callable[[Harness], None],
    status: int,
    code: str,
) -> None:
    setup(harness)
    got, headers, payload, _ = call("POST", answer_body())
    assert got == status
    assert payload["error"]["code"] == code
    assert int(headers["retry-after"]) >= 1
    assert harness.sdk.calls == []


# ------------------------------------------------------------------ failures and secrecy


class ApiError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.parametrize(
    ("error", "settlement"),
    [
        # May have been billed: the conservative reservation stays charged.
        (RuntimeError(SECRET_KEY), (None, None)),
        (TimeoutError(MONGODB_URI), (None, None)),
        # Sarvam refused without doing any work: 0.9.0 releases the reservation; 0.8.x keeps
        # it charged in every case.
        (ApiError(f"bad key {SECRET_KEY}", 403), (0, 0) if RELEASES_UNBILLED else (None, None)),
        (ApiError("insufficient credit", 402), (0, 0) if RELEASES_UNBILLED else (None, None)),
    ],
)
def test_provider_errors_are_sanitized_and_reported_without_content(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    reports: list[tuple[str, BaseException, str]],
    error: Exception,
    settlement: Any,
) -> None:
    harness.sdk.error = error
    status, _, payload, raw = call("POST", answer_body())
    assert status == 502
    assert payload["error"]["code"] == "provider_unavailable"
    assert SECRET_KEY not in raw.decode() and "ledger-password" not in raw.decode()
    assert len(harness.sdk.calls) == 1
    assert harness.store.settled[0][1:] == settlement
    assert harness.store.released
    assert reports == [("provider", error, "sarvam_answer")]


def test_quota_store_outage_is_a_clean_503_and_is_reported(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    reports: list[tuple[str, BaseException, str]],
) -> None:
    harness.raise_on_make = HostedQuotaStoreError("durable quota store unavailable")
    status, _, payload, raw = call("POST", answer_body())
    assert status == 503
    assert payload["error"]["code"] == "quota_store_unavailable"
    assert reports and reports[0][2] == "sarvam_answer"

    harness.raise_on_make = None
    harness.store.fail_store = True
    status, _, payload, raw = call("POST", answer_body())
    assert status == 503
    assert payload["error"]["code"] == "quota_store_unavailable"
    assert "ledger-password" not in raw.decode() and "mongodb" not in raw.decode().lower()


def test_unexpected_errors_are_500_and_reported_without_details(
    ready_env: pytest.MonkeyPatch,
    harness: Harness,
    call,
    reports: list[tuple[str, BaseException, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError(f"leaked {SECRET_KEY}")

    monkeypatch.setattr(api, "build_request", explode)
    status, _, payload, raw = call("POST", answer_body())
    assert status == 500
    assert payload["error"]["code"] == "answer_failed"
    assert SECRET_KEY not in raw.decode()
    assert [function for _, _, function in reports] == ["sarvam_answer"]


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
            answer_body(question="Again?"),
            headers={"x-sarvam-api-key": SECRET_KEY, "authorization": f"Bearer {SECRET_KEY}"},
        ),
    ]
    harness.sdk.error = RuntimeError(SECRET_KEY)
    responses.append(call("POST", answer_body(question="Once more?")))
    for _status, headers, _payload, raw in responses:
        blob = raw.decode() + json.dumps(headers)
        for secret in (SECRET_KEY, "ledger-password", HMAC_SECRET, CLIENT_IP):
            assert secret not in blob
    out, err = capsys.readouterr()
    assert out == "" and err == ""


# --------------------------------------------------------------- the real SDK, no network


def test_the_real_sdk_client_never_retries_or_follows_redirects(
    ready_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    httpx = pytest.importorskip("httpx")
    pytest.importorskip("sarvamai")
    seen: list[str] = []

    def transport(request: Any) -> Any:
        seen.append(str(request.url))
        if "redirected" in str(request.url):
            raise AssertionError("a redirect was followed")
        if len(seen) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": "slow down"})
        return httpx.Response(307, headers={"location": "https://evil.example/redirected"})

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs),
    )
    monkeypatch.setattr(api, "_client_state", dict.fromkeys(("key", "timeout", "client", "http")))
    provider = api.make_provider("sarvam-105b", 16, 20.0, prompt_limit=10_000)
    messages = [{"role": "user", "content": "Where is the card going?"}]
    with pytest.raises(Exception):  # noqa: B017 - the provider's sanitized error type varies
        provider.chat(messages)
    assert len(seen) == 1  # the 429 was not retried
    with pytest.raises(Exception):  # noqa: B017
        provider.chat(messages)
    assert len(seen) == 2  # the 307 was not followed
    http = api._client_state["http"]
    assert http.follow_redirects is False
    assert http.timeout.read == 20.0 and http.timeout.connect == api.CONNECT_TIMEOUT_SECONDS


def test_the_sdk_client_is_reused_and_rebuilt_only_when_settings_change(
    ready_env: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("sarvamai")
    monkeypatch.setattr(api, "_client_state", dict.fromkeys(("key", "timeout", "client", "http")))
    first = api._sdk_client(20.0)
    assert api._sdk_client(20.0) is first
    old_http = api._client_state["http"]
    second = api._sdk_client(15.0)
    assert second is not first and old_http.is_closed
    ready_env.setenv("SARVAM_API_KEY", SECRET_KEY + "-rotated")
    assert api._sdk_client(15.0) is not second
    assert SECRET_KEY not in repr(api._client_state["key"])
    ready_env.delenv("SARVAM_API_KEY")
    with pytest.raises(api.HostedSarvamError):
        api._sdk_client(15.0)


def test_guarded_chat_forces_one_attempt_and_reports_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reported: list[BaseException] = []
    monkeypatch.setattr(
        api._sentry,
        "capture_provider_failure",
        lambda error, *, function, now=None: reported.append(error),
    )
    sdk = FakeSdk()
    chat = api._GuardedClient(sdk, prompt_limit=1_000).chat
    chat.completions(
        messages=[{"role": "user", "content": "hi"}],
        request_options={"max_retries": 5, "timeout_in_seconds": 3},
    )
    assert sdk.calls[0]["request_options"] == {"max_retries": 0, "timeout_in_seconds": 3}
    sdk.error = ApiError("credit exhausted", 402)
    with pytest.raises(ApiError):
        chat.completions(messages=[{"role": "user", "content": "hi"}])
    assert reported == [sdk.error]


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
        "list price",
    ):
        assert forbidden not in source
    assert "max_prompt_bytes" in source and "TextEncoder" in source


def test_local_dev_reroutes_the_answer_function() -> None:
    config = (ROOT / "web" / "next.config.ts").read_text(encoding="utf-8")
    assert '"sarvam_answer"' in config


def test_production_installs_the_hosted_extras_from_pypi() -> None:
    lines = (ROOT / "web" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pinned = next(line for line in lines if line.startswith("llmslim"))
    assert pinned.startswith("llmslim[") and "sarvam" in pinned and "mongodb" in pinned
    assert pinned.endswith("==0.11.0")
