"""Security and quota tests for the optional hosted Sarvam Studio path."""

from __future__ import annotations

import importlib.util
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Optional

import pytest

from llmslim.hosted import (
    ConcurrencyLease,
    HostedQuotaStoreError,
    HostedSarvamConfig,
    HostedSarvamError,
    HostedSarvamService,
    MongoDBHostedQuotaStore,
    RequestIdentity,
    ReservationDecision,
    UsageReservation,
    build_request_identity,
    estimate_sarvam_cost_micros,
)
from llmslim.integrations.sarvam import SarvamProvider, SarvamUsage

API_PATH = Path(__file__).resolve().parents[1] / "web" / "api" / "sarvam.py"
SPEC = importlib.util.spec_from_file_location("studio_sarvam_api", API_PATH)
assert SPEC is not None and SPEC.loader is not None
studio_sarvam_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(studio_sarvam_api)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
IDENTITY = RequestIdentity("i" * 64, "s" * 64, "c" * 64, "session-token", False)


def config(**overrides: Any) -> HostedSarvamConfig:
    values = {
        "enabled": True,
        "max_input_tokens": 2_048,
        "max_output_tokens": 128,
        "daily_budget_inr": Decimal("10"),
        "monthly_budget_inr": Decimal("100"),
        "max_request_cost_inr": Decimal("1"),
    }
    values.update(overrides)
    return HostedSarvamConfig(**values)


def payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "Use only verified context."},
            {"role": "user", "content": "When does Acme renew?"},
        ],
        "documents": [{"content": "Acme renews on 30 November 2026."}],
        "memories": [],
        "tools": [],
        "query": "Answer with the renewal date.",
        "model": "sarvam-105b",
        "max_input_tokens": 1_024,
        "max_output_tokens": 64,
        "policy": "balanced",
    }
    value.update(overrides)
    return value


class FakeQuotaStore:
    def __init__(self) -> None:
        self.rate_allowed = True
        self.acquire_allowed = True
        self.reserve_reason: Optional[str] = None
        self.fail_store = False
        self.fail_settle = False
        self.calls: list[tuple[str, Any]] = []
        self.settled: list[tuple[UsageReservation, Optional[int], Optional[int]]] = []
        self.released: list[ConcurrencyLease] = []
        self._lock = threading.Lock()
        self._active = 0

    def consume_rate(self, **kwargs: Any) -> bool:
        self.calls.append(("rate", kwargs))
        return self.rate_allowed

    def acquire_concurrency(self, **kwargs: Any) -> Optional[ConcurrencyLease]:
        self.calls.append(("acquire", kwargs))
        if not self.acquire_allowed:
            return None
        with self._lock:
            if self._active:
                return None
            self._active += 1
        return ConcurrencyLease("lease", 0, 0, kwargs["client_hash"])

    def release_concurrency(self, lease: ConcurrencyLease) -> None:
        if self.fail_store:
            raise HostedQuotaStoreError("secret database error")
        with self._lock:
            self._active = max(0, self._active - 1)
        self.released.append(lease)

    def reserve_usage(self, **kwargs: Any) -> ReservationDecision:
        self.calls.append(("reserve", kwargs))
        if self.fail_store:
            raise HostedQuotaStoreError("mongodb://user:password@example.test")
        if self.reserve_reason:
            return ReservationDecision(None, self.reserve_reason)
        return ReservationDecision(
            UsageReservation(
                kwargs["request_id"],
                kwargs["identity_hash"],
                "2026-09-19",
                "2026-09",
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
        if self.fail_settle:
            raise HostedQuotaStoreError("settlement backend secret")
        self.settled.append((reservation, actual_input_tokens, actual_cost_micros))

    def record_event(self, event: str, **kwargs: Any) -> None:
        if self.fail_store:
            raise HostedQuotaStoreError("secret store exception")
        self.calls.append(("event", (event, kwargs)))


class FakeProvider:
    def __init__(
        self,
        usage: Optional[SarvamUsage] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self.last_usage = usage
        self.error = error
        self.messages: Any = None
        self.max_tokens: Optional[int] = None

    def chat(self, messages: Any, *, max_tokens: Optional[int] = None) -> str:
        self.messages = messages
        self.max_tokens = max_tokens
        if self.error:
            raise self.error
        return "Acme renews on 30 November 2026."


def service(
    store: FakeQuotaStore,
    provider: Optional[FakeProvider] = None,
    **config_overrides: Any,
) -> HostedSarvamService:
    selected = provider or FakeProvider(SarvamUsage(120, 20, 140))
    return HostedSarvamService(
        config(**config_overrides),
        store,
        provider_factory=lambda _model, _maximum, _timeout: selected,  # type: ignore[arg-type,return-value]
        clock=lambda: NOW,
    )


def test_config_defaults_disabled_and_requires_valid_server_limits() -> None:
    assert HostedSarvamConfig.from_env({}).enabled is False
    enabled = HostedSarvamConfig.from_env(
        {
            "LLMSLIM_HOSTED_SARVAM_ENABLED": "true",
            "LLMSLIM_SARVAM_DAILY_BUDGET_INR": "5",
            "LLMSLIM_SARVAM_MONTHLY_BUDGET_INR": "50",
        }
    )
    assert enabled.enabled is True
    assert enabled.daily_budget_inr == Decimal("5")
    with pytest.raises(HostedSarvamError, match="unavailable"):
        HostedSarvamConfig.from_env({"LLMSLIM_HOSTED_SARVAM_ENABLED": "maybe"})
    with pytest.raises(HostedSarvamError):
        HostedSarvamConfig.from_env(
            {
                "LLMSLIM_SARVAM_DAILY_BUDGET_INR": "20",
                "LLMSLIM_SARVAM_MONTHLY_BUDGET_INR": "10",
            }
        )


def test_identity_is_stable_pseudonymous_and_rotated_sessions_share_network_hash() -> None:
    secret = "a" * 32
    first = build_request_identity(
        forwarded_for="203.0.113.4, 10.0.0.1",
        session_id="A" * 24,
        hmac_secret=secret,
    )
    second = build_request_identity(
        forwarded_for="203.0.113.4",
        session_id="B" * 24,
        hmac_secret=secret,
    )
    assert first.ip_hash == second.ip_hash
    assert first.session_hash != second.session_hash
    assert "203.0.113.4" not in repr(first)
    assert first.is_new_session is False
    generated = build_request_identity(
        forwarded_for="not-an-ip", session_id="forged", hmac_secret=secret
    )
    assert generated.is_new_session is True
    assert len(generated.session_id) >= 20
    with pytest.raises(HostedSarvamError):
        build_request_identity(forwarded_for="127.0.0.1", session_id=None, hmac_secret="short")


def test_kill_switch_rejects_before_any_quota_or_provider_work() -> None:
    store = FakeQuotaStore()
    hosted = HostedSarvamService(config(enabled=False), store, clock=lambda: NOW)
    with pytest.raises(HostedSarvamError) as captured:
        hosted.check_initial_limits(IDENTITY)
    assert captured.value.code == "hosted_disabled"
    assert store.calls == []


def test_layered_network_and_session_limits_are_server_authoritative() -> None:
    store = FakeQuotaStore()
    hosted = service(store)
    hosted.check_initial_limits(IDENTITY)
    rate_calls = [call for call in store.calls if call[0] == "rate"]
    assert len(rate_calls) == 8
    assert {call[1]["scope"] for call in rate_calls} == {
        "network:burst",
        "network:minute",
        "network:hour",
        "network:day",
        "session:burst",
        "session:minute",
        "session:hour",
        "session:day",
    }
    store.rate_allowed = False
    with pytest.raises(HostedSarvamError) as captured:
        hosted.check_initial_limits(IDENTITY)
    assert captured.value.status == 429
    assert captured.value.retry_after is not None


def test_successful_flow_plans_reserves_calls_settles_and_returns_real_usage() -> None:
    store = FakeQuotaStore()
    provider = FakeProvider(SarvamUsage(120, 20, 140))
    result = service(store, provider).execute(payload(), IDENTITY)
    assert result["plan"]["validation"]["passed"] is True
    assert result["answer"].startswith("Acme renews")
    assert result["usage"]["estimated"]["classification"] == "ESTIMATED"
    reported = result["usage"]["provider_reported"]
    assert reported["classification"] == "PROVIDER_REPORTED"
    assert reported["total_tokens"] == 140
    assert provider.max_tokens == 64
    serialized_messages = json.dumps(provider.messages)
    assert "PLANNED CONTEXT" in serialized_messages
    assert "Never claim to have executed a tool" in serialized_messages
    assert store.settled[0][1] == 120
    assert store.released


@pytest.mark.parametrize(
    "override,code,status",
    [
        ({"max_input_tokens": 99}, "invalid_max_input_tokens", 422),
        ({"max_output_tokens": 10_000}, "invalid_max_output_tokens", 422),
        ({"query": ""}, "invalid_query", 422),
        ({"model": "generic-128k"}, "invalid_model", 422),
        ({"tools": ["not-a-schema"]}, "invalid_tools", 422),
        ({"client_quota_remaining": 999_999}, "unsupported_field", 400),
    ],
)
def test_payload_and_forged_quota_fields_are_rejected(
    override: Mapping[str, Any], code: str, status: int
) -> None:
    with pytest.raises(HostedSarvamError) as captured:
        service(FakeQuotaStore()).execute(payload(**override), IDENTITY)
    assert captured.value.code == code
    assert captured.value.status == status


def test_payload_counts_total_size_and_tool_size_are_bounded() -> None:
    with pytest.raises(HostedSarvamError) as count_error:
        service(FakeQuotaStore(), max_documents=1).execute(payload(documents=["a", "b"]), IDENTITY)
    assert count_error.value.status == 413
    with pytest.raises(HostedSarvamError) as size_error:
        service(FakeQuotaStore(), max_total_chars=1_000).execute(
            payload(documents=["x" * 2_000]), IDENTITY
        )
    assert size_error.value.code == "input_too_large"
    with pytest.raises(HostedSarvamError) as tool_error:
        service(FakeQuotaStore(), max_tool_chars=10).execute(
            payload(tools=[{"name": "large", "description": "x" * 100}]), IDENTITY
        )
    assert tool_error.value.code == "tool_payload_too_large"


def test_concurrency_and_daily_or_global_quotas_fail_closed() -> None:
    concurrent = FakeQuotaStore()
    concurrent.acquire_allowed = False
    with pytest.raises(HostedSarvamError) as busy:
        service(concurrent).execute(payload(), IDENTITY)
    assert busy.value.code == "concurrency_limited"

    identity_quota = FakeQuotaStore()
    identity_quota.reserve_reason = "identity_token_quota"
    with pytest.raises(HostedSarvamError) as daily:
        service(identity_quota).execute(payload(), IDENTITY)
    assert daily.value.status == 429
    assert identity_quota.released

    global_quota = FakeQuotaStore()
    global_quota.reserve_reason = "global_spend_quota"
    with pytest.raises(HostedSarvamError) as exhausted:
        service(global_quota).execute(payload(), IDENTITY)
    assert exhausted.value.status == 503
    assert exhausted.value.code == "hosted_budget_exhausted"


def test_per_request_cost_and_repeated_high_cost_limits_block_before_provider() -> None:
    tiny = FakeQuotaStore()
    with pytest.raises(HostedSarvamError) as cost:
        service(tiny, max_request_cost_inr=Decimal("0.000001")).execute(payload(), IDENTITY)
    assert cost.value.code == "request_cost_limit"
    assert not any(call[0] == "acquire" for call in tiny.calls)

    probe = FakeQuotaStore()
    service(probe).execute(payload(max_output_tokens=128), IDENTITY)
    reserve_call = next(call[1] for call in probe.calls if call[0] == "reserve")
    request_limit = Decimal(reserve_call["estimated_cost_micros"] * 3 // 2) / Decimal(1_000_000)

    repeated = FakeQuotaStore()
    repeated.rate_allowed = False
    with pytest.raises(HostedSarvamError) as repeat:
        service(repeated, max_request_cost_inr=request_limit).execute(
            payload(max_output_tokens=128), IDENTITY
        )
    assert repeat.value.code == "repeated_high_cost_request"


def test_provider_and_store_failures_are_sanitized_and_release_leases() -> None:
    provider_store = FakeQuotaStore()
    secret = "sk_project_secret_never_return"
    failing_provider = FakeProvider(error=RuntimeError(secret))
    with pytest.raises(HostedSarvamError) as provider_error:
        service(provider_store, failing_provider).execute(payload(), IDENTITY)
    assert provider_error.value.code == "provider_unavailable"
    assert secret not in str(provider_error.value)
    assert provider_store.settled[0][1:] == (None, None)
    assert provider_store.released

    unavailable_store = FakeQuotaStore()
    unavailable_store.fail_store = True
    with pytest.raises(HostedSarvamError) as store_error:
        service(unavailable_store).execute(payload(), IDENTITY)
    assert store_error.value.code == "quota_store_unavailable"
    assert "mongodb" not in str(store_error.value).lower()

    settlement_store = FakeQuotaStore()
    settlement_store.fail_settle = True
    completed = service(settlement_store).execute(payload(), IDENTITY)
    assert completed["answer"]
    assert completed["usage"]["accounting_basis"] == "ESTIMATED_FAIL_CLOSED"
    assert completed["usage"]["provider_reported"]["cost_inr"] is not None


def test_cost_math_uses_current_input_and_output_rates() -> None:
    assert estimate_sarvam_cost_micros("sarvam-105b", 1_000_000, 1_000_000) == 102_480_000


def test_sarvam_provider_chat_validates_messages_and_never_exposes_key() -> None:
    class Chat:
        def completions(self, **kwargs: Any) -> Any:
            self.kwargs = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="नमस्ते"))],
                usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2, total_tokens=6),
            )

    chat = Chat()
    provider = SarvamProvider(api_key="never-visible", client=SimpleNamespace(chat=chat))
    assert provider.chat([{"role": "user", "content": "Hello"}], max_tokens=8) == "नमस्ते"
    assert provider.last_usage == SarvamUsage(4, 2, 6)
    assert "never-visible" not in repr(provider)
    with pytest.raises(ValueError):
        provider.chat([])
    with pytest.raises(ValueError):
        provider.chat([{"role": "owner", "content": "unsafe"}])


def test_route_parsing_and_identity_never_serialize_server_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLMSLIM_RATE_LIMIT_HMAC_SECRET", "h" * 32)
    monkeypatch.setenv("SARVAM_API_KEY", "sk_never_serialize_this_value")
    identity = studio_sarvam_api._identity(
        {
            "x-vercel-forwarded-for": "198.51.100.7",
            "cookie": f"{studio_sarvam_api.SESSION_COOKIE}={'S' * 24}",
        }
    )
    assert "198.51.100.7" not in repr(identity)
    parsed = studio_sarvam_api.parse_json_body(b'{"query":"safe"}', "application/json")
    assert parsed == {"query": "safe"}
    public = json.dumps({"data": {"identity": identity.combined_hash}})
    assert "sk_never_serialize_this_value" not in public
    with pytest.raises(HostedSarvamError):
        studio_sarvam_api.parse_json_body(b"not-json", "application/json")


def test_route_reports_hosted_ready_only_when_every_server_secret_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready_config = config()
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("LLMSLIM_RATE_LIMIT_HMAC_SECRET", raising=False)
    assert studio_sarvam_api._hosted_ready(ready_config) is False
    monkeypatch.setenv("SARVAM_API_KEY", "server-only-key")
    monkeypatch.setenv("MONGODB_URI", "mongodb://example.invalid")
    monkeypatch.setenv("LLMSLIM_RATE_LIMIT_HMAC_SECRET", "h" * 32)
    assert studio_sarvam_api._hosted_ready(ready_config) is True
    assert studio_sarvam_api._hosted_ready(config(enabled=False)) is False


def test_frontend_contains_no_provider_secret_or_public_key_variable() -> None:
    frontend = (
        Path(__file__).resolve().parents[1]
        / "web"
        / "src"
        / "components"
        / "studio"
        / "AdaptivePlannerStudio.tsx"
    ).read_text(encoding="utf-8")
    assert "SARVAM_API_KEY" not in frontend
    assert "NEXT_PUBLIC_" not in frontend
    assert "localStorage" not in frontend


class CapturingCollection:
    def __init__(self) -> None:
        self.find_calls: list[tuple[Mapping[str, Any], Any, Mapping[str, Any]]] = []

    def create_index(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def find_one_and_update(
        self, query: Mapping[str, Any], update: Any, **kwargs: Any
    ) -> Mapping[str, Any]:
        self.find_calls.append((query, update, kwargs))
        owner = None
        if isinstance(update, Mapping):
            owner = update.get("$set", {}).get("owner")
        return {"owner": owner, "events": [NOW]}

    def update_one(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def delete_one(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class CapturingDatabase:
    def __init__(self, collection: Any) -> None:
        self.collection = collection

    def __getitem__(self, _name: str) -> Any:
        return self.collection


class CapturingClient:
    def __init__(self, collection: Any) -> None:
        self.collection = collection

    def __getitem__(self, _name: str) -> CapturingDatabase:
        return CapturingDatabase(self.collection)


def test_mongodb_store_uses_sliding_window_pipeline_and_redacted_repr() -> None:
    collection = CapturingCollection()
    store = MongoDBHostedQuotaStore(client=CapturingClient(collection))
    assert store.consume_rate(
        subject="hashed-subject",
        scope="minute",
        window_seconds=60,
        limit=4,
        now=NOW,
    )
    query, update, options = collection.find_calls[0]
    assert "$expr" in query
    assert isinstance(update, list)
    assert "$filter" in json.dumps(update, default=str)
    assert "hashed-subject" in str(query["_id"])
    assert options["upsert"] is False
    assert "uri=<redacted>" in repr(store)


def test_mongodb_spend_and_token_reservations_use_conditional_atomic_updates() -> None:
    collection = CapturingCollection()
    store = MongoDBHostedQuotaStore(client=CapturingClient(collection))
    decision = store.reserve_usage(
        request_id="request",
        identity_hash="identity",
        estimated_input_tokens=100,
        estimated_cost_micros=500,
        input_tokens_per_day=1_000,
        daily_budget_micros=5_000,
        monthly_budget_micros=50_000,
        now=NOW,
    )
    assert decision.reservation is not None
    token_query, _, token_options = collection.find_calls[0]
    spend_query, _, spend_options = collection.find_calls[1]
    assert "$expr" in token_query
    assert "$and" in spend_query["$expr"]
    assert token_options["upsert"] is False
    assert spend_options["upsert"] is False


class AtomicSlotCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def create_index(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def update_one(
        self, query: Mapping[str, Any], update: Mapping[str, Any], **_kwargs: Any
    ) -> None:
        with self.lock:
            self.documents.setdefault(str(query["_id"]), dict(update.get("$setOnInsert", {})))

    def find_one_and_update(
        self, query: Mapping[str, Any], update: Mapping[str, Any], **_kwargs: Any
    ) -> Optional[Mapping[str, Any]]:
        document_id = str(query["_id"])
        owner = update.get("$set", {}).get("owner")
        with self.lock:
            current = self.documents.get(document_id)
            if current and current.get("owner") != owner and current.get("expires_at") > NOW:
                return None
            value = dict(current or {})
            value.update(update.get("$set", {}))
            self.documents[document_id] = value
            return dict(value)

    def delete_one(self, query: Mapping[str, Any]) -> None:
        with self.lock:
            current = self.documents.get(str(query["_id"]))
            if current and current.get("owner") == query.get("owner"):
                self.documents.pop(str(query["_id"]), None)


def test_atomic_concurrency_slots_allow_only_one_simultaneous_client_request() -> None:
    collection = AtomicSlotCollection()
    store = MongoDBHostedQuotaStore(client=CapturingClient(collection))
    barrier = threading.Barrier(2)

    def acquire() -> Optional[ConcurrencyLease]:
        barrier.wait()
        return store.acquire_concurrency(
            client_hash="same-client",
            global_limit=2,
            client_limit=1,
            lease_seconds=45,
            now=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _value: acquire(), range(2)))
    assert sum(result is not None for result in results) == 1
