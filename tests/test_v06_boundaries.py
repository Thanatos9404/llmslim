"""Boundary, fallback, and error-path coverage for v0.6 public surfaces."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import pytest

from llmslim import (
    CandidateMethod,
    ContextBudget,
    ContextItem,
    ContextKind,
    ContextRole,
    InMemoryContextSource,
    InMemoryContextStore,
    ModelProfile,
    PlannerPolicy,
    plan_context,
)
from llmslim.context import collect_context_sources
from llmslim.integrations.mongodb import (
    MongoDBContextSource,
    MongoDBContextStore,
    MongoDBIntegrationError,
)
from llmslim.integrations.sarvam import (
    SarvamMalformedResponseError,
    SarvamProvider,
    SarvamProviderError,
    SarvamRateLimitError,
    SarvamTimeoutError,
)
from llmslim.integrations.zoho import (
    ZohoAuthenticationError,
    ZohoCRMContextSource,
    ZohoIntegrationError,
    ZohoRateLimitError,
    ZohoWorkDriveContextSource,
)
from llmslim.planning.budget import allocate_candidates
from llmslim.planning.candidates import CandidateSet, generate_candidates
from llmslim.planning.models import ContextBundle, ContextCandidate
from llmslim.planning.policy import PolicyPreset, resolve_policy
from llmslim.planning.profiles import ModelProfileRegistry
from llmslim.planning.scoring import ScoreBreakdown
from llmslim.rewrite import CallableProvider, RewriteRequest


class _Completions:
    def __init__(self, *, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error = response, error

    def __call__(self, **_: Any) -> Any:
        if self.error:
            raise self.error
        return self.response


def _sarvam_client(completions: _Completions) -> Any:
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


@pytest.mark.parametrize(
    "error,error_type",
    [
        (type("TooManyRequestsError", (Exception,), {})("secret"), SarvamRateLimitError),
        (type("RequestTimeout", (Exception,), {})("secret"), SarvamTimeoutError),
        (RuntimeError("secret"), SarvamProviderError),
    ],
)
def test_sarvam_error_classes_are_sanitized(error: Exception, error_type: type[Exception]) -> None:
    provider = SarvamProvider(client=_sarvam_client(_Completions(error=error)))
    with pytest.raises(error_type) as captured:
        provider.rewrite(RewriteRequest("text", user_prompt="prompt"))
    assert "secret" not in str(captured.value)
    assert provider.last_usage is None


def test_sarvam_validates_construction_and_response_shapes(monkeypatch: Any) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        SarvamProvider(client=object(), model="unknown")
    with pytest.raises(ValueError, match="positive"):
        SarvamProvider(client=object(), timeout_seconds=0)
    with pytest.raises(ValueError, match="requires api_key"):
        SarvamProvider()

    malformed = SarvamProvider(client=_sarvam_client(_Completions(response=object())))
    with pytest.raises(SarvamMalformedResponseError):
        malformed.rewrite(RewriteRequest("text"))

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="short"))], usage=None
    )
    provider = SarvamProvider(client=_sarvam_client(_Completions(response=response)))
    assert provider.rewrite(RewriteRequest("text")) == "short"
    assert provider.last_usage is None
    assert provider.is_available()

    monkeypatch.setenv("TEST_SARVAM_KEY", "server-only")
    from_env = SarvamProvider.from_env(
        "TEST_SARVAM_KEY", client=_sarvam_client(_Completions(response=response))
    )
    assert "server-only" not in repr(from_env)


class _Response:
    def __init__(self, status: int, payload: Any = None, malformed: bool = False) -> None:
        self.status_code, self.payload, self.malformed = status, payload, malformed

    def json(self) -> Any:
        if self.malformed:
            raise ValueError("secret response")
        return self.payload


class _HTTP:
    def __init__(self, responses: Sequence[Any] = (), failure: Exception | None = None) -> None:
        self.responses, self.failure, self.closed = list(responses), failure, False

    async def request(self, *_: Any, **__: Any) -> Any:
        if self.failure:
            raise self.failure
        return self.responses.pop(0)

    async def aclose(self) -> None:
        self.closed = True


def _crm(client: Any, **kwargs: Any) -> ZohoCRMContextSource:
    return ZohoCRMContextSource(
        access_token="token",
        modules=("Deals",),
        field_allowlists={"Deals": ("Deal_Name", "Stage")},
        client=client,
        **kwargs,
    )


def test_zoho_constructor_token_and_protocol_boundaries() -> None:
    for kwargs in ({}, {"access_token": "x", "token_provider": lambda: "x"}):
        with pytest.raises(ValueError, match="exactly one"):
            ZohoCRMContextSource(modules=(), field_allowlists={}, client=_HTTP(), **kwargs)
    with pytest.raises(ValueError, match="data center"):
        ZohoCRMContextSource(access_token="x", data_center="moon", client=_HTTP())
    with pytest.raises(ValueError, match="positive"):
        ZohoCRMContextSource(access_token="x", timeout_seconds=0, client=_HTTP())
    with pytest.raises(ValueError, match="max_records"):
        _crm(_HTTP(), max_records=0)
    with pytest.raises(ValueError, match="field allowlist"):
        ZohoCRMContextSource(
            access_token="x",
            modules=("Deals",),
            field_allowlists={"Accounts": ("Account_Name",)},
            client=_HTTP(),
        )
    with pytest.raises(ValueError, match="unsupported"):
        ZohoCRMContextSource(access_token="x", modules=("Bad-Module",), client=_HTTP())

    async def async_token() -> str:
        return "async-token"

    source = ZohoCRMContextSource(
        token_provider=async_token,
        modules=("Deals",),
        field_allowlists={"Deals": ("Deal_Name",)},
        client=_HTTP([_Response(204)]),
    )
    assert asyncio.run(source.search("Acme")) == ()

    empty = ZohoCRMContextSource(
        token_provider=lambda: "",
        modules=("Deals",),
        field_allowlists={"Deals": ("Deal_Name",)},
        client=_HTTP(),
    )
    with pytest.raises(ZohoAuthenticationError):
        asyncio.run(empty.search("Acme"))


@pytest.mark.parametrize(
    "client,error_type",
    [
        (_HTTP([_Response(429, {})]), ZohoRateLimitError),
        (_HTTP([_Response(500, {})]), ZohoIntegrationError),
        (_HTTP([_Response(200, malformed=True)]), ZohoIntegrationError),
        (_HTTP([_Response(200, [])]), ZohoIntegrationError),
        (_HTTP(failure=TimeoutError("secret")), ZohoIntegrationError),
    ],
)
def test_zoho_http_failures_are_typed_and_sanitized(
    client: _HTTP, error_type: type[Exception]
) -> None:
    with pytest.raises(error_type) as captured:
        asyncio.run(_crm(client).search("Acme"))
    assert "secret" not in str(captured.value)


def test_zoho_record_fetch_redaction_and_validation() -> None:
    redactor = lambda value: {"Deal_Name": value.get("Deal_Name", "")}  # noqa: E731
    source = _crm(
        _HTTP(
            [
                _Response(200, {"data": [{"id": "1", "Deal_Name": "Acme", "Stage": "Won"}]}),
                _Response(200, {"data": []}),
            ]
        ),
        redactor=redactor,
    )
    item = asyncio.run(source.fetch_record("Deals", "1"))
    assert item is not None and "Won" not in item.content
    assert asyncio.run(source.fetch_record("Deals", "missing")) is None
    with pytest.raises(ValueError):
        asyncio.run(source.fetch_record("Accounts", "1"))
    with pytest.raises(ValueError):
        asyncio.run(source.fetch_record("Deals", "bad/id"))
    with pytest.raises(ValueError):
        asyncio.run(source.search(""))
    with pytest.raises(ValueError):
        asyncio.run(source.search("x", limit=201))


def test_workdrive_metadata_paths_and_validation() -> None:
    record = {"id": "f1", "attributes": "malformed"}
    source = ZohoWorkDriveContextSource(
        "team",
        parent_id="folder",
        access_token="token",
        client=_HTTP([_Response(200, {"data": ["skip", record]})]),
        redactor=lambda value: value,
    )
    items = asyncio.run(source.search("policy"))
    assert len(items) == 1 and items[0].metadata["content_loaded"] is False
    with pytest.raises(ValueError):
        ZohoWorkDriveContextSource("bad/team", access_token="x", client=_HTTP())
    with pytest.raises(ValueError):
        ZohoWorkDriveContextSource("team", parent_id="bad/id", access_token="x", client=_HTTP())
    with pytest.raises(ValueError):
        ZohoWorkDriveContextSource("team", max_records=0, access_token="x", client=_HTTP())
    with pytest.raises(ValueError):
        asyncio.run(source.search(""))


class _Cursor:
    def __init__(self, documents: Sequence[Mapping[str, Any]]) -> None:
        self.documents = list(documents)

    def limit(self, _: int) -> "_Cursor":
        return self

    async def to_list(self, length: int) -> list[Mapping[str, Any]]:
        return self.documents[:length]


class _Collection:
    def __init__(self) -> None:
        self.documents: dict[str, Mapping[str, Any]] = {}
        self.failure: Exception | None = None
        self.pipeline: Any = None

    async def replace_one(self, _: Any, document: Mapping[str, Any], upsert: bool) -> Any:
        del upsert
        if self.failure:
            raise self.failure
        self.documents[str(document["_id"])] = document
        return object()

    async def find_one(self, query: Mapping[str, Any]) -> Any:
        if self.failure:
            raise self.failure
        return self.documents.get(str(query["_id"]))

    def find(self, *_: Any, **__: Any) -> _Cursor:
        if self.failure:
            raise self.failure
        return _Cursor(list(self.documents.values()))

    async def aggregate(self, pipeline: Any) -> _Cursor:
        if self.failure:
            raise self.failure
        self.pipeline = pipeline
        return _Cursor([value for value in self.documents.values() if "item_id" in value])

    async def delete_one(self, query: Mapping[str, Any]) -> Any:
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            deleted_count=int(self.documents.pop(str(query["_id"]), None) is not None)
        )


class _Database:
    def __init__(self, collection: _Collection) -> None:
        self.collection = collection

    def __getitem__(self, _: str) -> _Collection:
        return self.collection


class _MongoClient:
    def __init__(self, collection: _Collection) -> None:
        self.collection, self.closed = collection, False

    def __getitem__(self, _: str) -> _Database:
        return _Database(self.collection)

    async def close(self) -> None:
        self.closed = True


def test_mongodb_constructor_and_input_validation(monkeypatch: Any) -> None:
    collection = _Collection()
    client = _MongoClient(collection)
    with pytest.raises(ValueError, match="exactly one"):
        MongoDBContextStore()
    with pytest.raises(ValueError, match="exactly one"):
        MongoDBContextStore(uri="mongodb://x", client=client)
    for kwargs in (
        {"database": "system.bad"},
        {"collection": "bad/name"},
        {"atlas_search_index": "bad name"},
    ):
        with pytest.raises(ValueError):
            MongoDBContextStore(client=client, **kwargs)
    with pytest.raises(ValueError, match="timeouts"):
        MongoDBContextStore(client=client, connect_timeout_ms=0)
    with pytest.raises(ValueError, match="max_content"):
        MongoDBContextStore(client=client, max_content_bytes=0)
    monkeypatch.delenv("TEST_MONGO_URI", raising=False)
    with pytest.raises(ValueError, match="TEST_MONGO_URI"):
        MongoDBContextStore.from_env("TEST_MONGO_URI")

    store = MongoDBContextStore(client=client, max_content_bytes=3)
    with pytest.raises(ValueError, match="max_content"):
        asyncio.run(store.save(ContextItem("large", "four")))
    for namespace in ("", "bad\x00namespace", "x" * 201):
        with pytest.raises(ValueError):
            asyncio.run(store.get("id", namespace))
    for item_id in ("", "bad\x00id", "x" * 501):
        with pytest.raises(ValueError):
            asyncio.run(store.get(item_id))
    for query in ("", "x" * 501):
        with pytest.raises(ValueError):
            asyncio.run(store.search(query))
    with pytest.raises(ValueError):
        asyncio.run(store.search("x", limit=101))


def test_mongodb_atlas_trace_vector_and_trust_paths() -> None:
    collection = _Collection()
    client = _MongoClient(collection)
    store = MongoDBContextStore(client=client, atlas_search_index="context_search")
    item = ContextItem("memory", "Acme fact", kind=ContextKind.MEMORY, role=ContextRole.SYSTEM)
    asyncio.run(store.save(item))
    found = asyncio.run(store.search("Acme", limit=1))
    assert found[0].item_id == "memory" and collection.pipeline[0]["$search"]

    asyncio.run(store.save_record("feedback", "evaluation", {"nested": [{"api_key": "secret"}]}))
    assert (
        collection.documents["default:feedback"]["payload"]["nested"][0]["api_key"] == "<redacted>"
    )
    plan = plan_context(
        documents=["private prompt"],
        max_input_tokens=500,
        reserve_output_tokens=0,
        safety_margin_tokens=0,
    )
    asyncio.run(store.save_plan_trace("trace", plan))
    assert "final_context" not in collection.documents["default:trace"]["payload"]

    with pytest.raises(ValueError):
        asyncio.run(store.search_vector([], index_name="idx"))
    with pytest.raises(ValueError):
        asyncio.run(store.search_vector([0.1], index_name="idx", limit=5, num_candidates=4))
    asyncio.run(store.search_vector([0.1, 2], index_name="idx", filters={"owner": "a"}))
    assert collection.pipeline[0]["$vectorSearch"]["filter"]["owner"] == "a"

    preserved = MongoDBContextSource(store, preserve_caller_trust=True)
    assert asyncio.run(preserved.search("Acme"))[0].role is ContextRole.SYSTEM
    memory = MongoDBContextSource(store)
    assert asyncio.run(memory.search("Acme"))[0].kind is ContextKind.MEMORY
    assert "redacted" in repr(memory)
    with pytest.raises(ValueError, match="configured together"):
        MongoDBContextSource(store, vector_index="idx")


def test_mongodb_driver_failures_and_malformed_documents() -> None:
    collection = _Collection()
    store = MongoDBContextStore(client=_MongoClient(collection))
    collection.failure = RuntimeError("mongodb://secret")
    for call in (
        lambda: store.get("id"),
        lambda: store.search("query"),
        lambda: store.search_vector([0.1], index_name="idx"),
        lambda: store.delete("id"),
        lambda: store.save_record("id", "trace", {}),
    ):
        with pytest.raises(MongoDBIntegrationError) as captured:
            asyncio.run(call())
        assert "mongodb://secret" not in str(captured.value)
    collection.failure = None
    collection.documents["default:broken"] = {
        "_id": "default:broken",
        "item_id": "broken",
        "kind": "unknown",
    }
    with pytest.raises(MongoDBIntegrationError, match="malformed"):
        asyncio.run(store.get("broken"))


def test_context_and_model_validation_boundaries() -> None:
    with pytest.raises(ValueError):
        ContextItem("", "text")
    with pytest.raises(TypeError):
        ContextItem("id", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ContextItem("id", "text", token_count=-1)
    with pytest.raises(ValueError):
        ContextItem("id", "text", relevance=2)
    with pytest.raises(ValueError):
        ContextItem("id", "text", recency=-1)
    with pytest.raises(ValueError, match="unique"):
        ContextBundle((ContextItem("same", "a"), ContextItem("same", "b")))
    for kwargs in (
        {"max_input_tokens": 0},
        {"max_input_tokens": 10, "reserve_output_tokens": -1},
        {"max_input_tokens": 10, "target_utilization": 0},
        {"max_input_tokens": 10, "model_context_window": 0},
    ):
        with pytest.raises(ValueError):
            ContextBudget(**kwargs)
    with pytest.raises(ValueError):
        ModelProfile("", "x", 1)
    with pytest.raises(ValueError):
        ModelProfile("x", "x", 0)
    with pytest.raises(ValueError):
        ModelProfile("x", "x", 1, input_cost_per_million=-1)
    assert ModelProfile("x", "x", 100, input_cost_per_million=10).estimate_input_cost(1000) == 0.01
    assert ModelProfile("x", "x", 100).estimate_input_cost(1000) is None
    with pytest.raises(ValueError):
        ModelProfile("x", "x", 100).estimate_input_cost(-1)


def test_policy_profile_planner_and_allocator_boundaries() -> None:
    for kwargs in (
        {"name": ""},
        {"compression_ratios": ()},
        {"compression_ratios": (1.0,)},
        {"preserve_latest_turns": -1},
        {"target_utilization": 0},
    ):
        with pytest.raises(ValueError):
            PlannerPolicy(**kwargs)
    assert resolve_policy(None).name == "balanced"
    assert resolve_policy(PolicyPreset.COST_FIRST).name == "cost_first"
    with pytest.raises(ValueError, match="unknown"):
        resolve_policy("unknown")

    registry = ModelProfileRegistry()
    custom = ModelProfile("custom", "test", 1000)
    registry.register(custom)
    assert registry.get("custom") == custom
    assert custom in registry.list()
    with pytest.raises(ValueError, match="unknown"):
        registry.require("missing")

    with pytest.raises(ValueError):
        allocate_candidates((), -1)
    assert allocate_candidates((), 0).feasible
    score = ScoreBreakdown(0, 0, 0, 0, 0, 0, 0, 0)
    impossible = CandidateSet(
        ContextItem("i", "i"),
        (ContextCandidate("i", CandidateMethod.RAW, "i", 10, 1, 0, "x", 1),),
        score,
        0,
    )
    assert not allocate_candidates((impossible,), 1).feasible

    with pytest.raises(ValueError, match="disagree"):
        plan_context(budget=100, max_input_tokens=99)
    with pytest.raises(ValueError, match="no input"):
        plan_context(max_input_tokens=100, reserve_output_tokens=0, safety_margin_tokens=100)
    with pytest.raises(ValueError, match="unknown model"):
        plan_context(model="unknown")
    with pytest.raises(TypeError):
        plan_context(messages=["bad"])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        plan_context(documents=[object()])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        plan_context(tools=[object()])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="unique"):
        plan_context(
            documents=[{"id": "same", "content": "a"}, {"id": "same", "content": "b"}],
            max_input_tokens=1000,
        )


def test_provider_candidates_and_sanitized_provider_failure() -> None:
    text = "Alpha project retains verified date 2026-11-30. " * 12
    provider = CallableProvider(lambda request: request.text[: len(request.text) // 2])
    group = generate_candidates(
        ContextItem("doc", text, kind=ContextKind.RAG_DOCUMENT, role=ContextRole.RAG),
        query="Alpha date",
        policy=PlannerPolicy(minimum_entity_retention=0.1, minimum_instruction_retention=0.1),
        provider=provider,
    )
    assert any(
        candidate.method in {CandidateMethod.REWRITE_COMPRESSED, CandidateMethod.HYBRID_COMPRESSED}
        for candidate in group.candidates
    )

    secret_provider = CallableProvider(
        lambda _: (_ for _ in ()).throw(RuntimeError("api-key-secret"))
    )
    failed = generate_candidates(
        ContextItem("doc2", text, kind=ContextKind.RAG_DOCUMENT, role=ContextRole.RAG),
        query="Alpha",
        policy=PlannerPolicy(),
        provider=secret_provider,
    )
    assert any("no validated token reduction" in warning for warning in failed.warnings)
    assert all("api-key-secret" not in warning for warning in failed.warnings)


def test_in_memory_limits_delete_and_source_validation() -> None:
    item = ContextItem("x", "fact")
    source = InMemoryContextSource((item,))
    store = InMemoryContextStore()
    for limit in (0, 101):
        with pytest.raises(ValueError):
            asyncio.run(source.search("x", limit))
        with pytest.raises(ValueError):
            asyncio.run(store.search("x", limit))
        with pytest.raises(ValueError):
            asyncio.run(collect_context_sources((source,), "x", limit_per_source=limit))
    with pytest.raises(ValueError):
        asyncio.run(store.save(item, ""))
    assert asyncio.run(store.delete("missing")) is False
