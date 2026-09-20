"""Mocked v0.6 source/store/provider integration and security tests."""

from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import pytest

from llmslim import (
    AdaptiveContextPlanner,
    ContextItem,
    ContextKind,
    ContextRole,
    InMemoryContextSource,
    InMemoryContextStore,
    collect_context_sources,
)
from llmslim.context import ContextSourceError
from llmslim.integrations.mongodb import (
    MongoDBContextSource,
    MongoDBContextStore,
    MongoDBIntegrationError,
)
from llmslim.integrations.sarvam import (
    SarvamAuthenticationError,
    SarvamMalformedResponseError,
    SarvamProvider,
)
from llmslim.integrations.zoho import (
    ZohoAuthenticationError,
    ZohoCRMContextSource,
    ZohoWorkDriveContextSource,
)
from llmslim.rewrite import RewriteRequest


class _FakeSarvamCompletions:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[Mapping[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class _FakeSarvamClient:
    def __init__(self, completions: _FakeSarvamCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def _rewrite_request() -> RewriteRequest:
    return RewriteRequest(
        text="Original long prompt",
        target_ratio=0.5,
        system_prompt="Preserve facts.",
        user_prompt="Compress this prompt.",
    )


def test_sarvam_provider_uses_official_sdk_shape_and_reports_usage() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Short prompt"))],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=3, total_tokens=23),
    )
    completions = _FakeSarvamCompletions(response)
    provider = SarvamProvider(client=_FakeSarvamClient(completions), max_tokens=99)

    assert provider.rewrite(_rewrite_request()) == "Short prompt"
    assert completions.calls[0]["model"] == "sarvam-105b"
    assert completions.calls[0]["messages"][0]["role"] == "system"
    assert provider.last_usage is not None
    assert provider.last_usage.total_tokens == 23
    assert provider.last_usage.classification == "PROVIDER_REPORTED"
    assert "redacted" in repr(provider)


def test_sarvam_provider_sanitizes_auth_and_malformed_responses(monkeypatch: Any) -> None:
    class UnauthorizedError(Exception):
        pass

    secret = "sv_live_never_echo"
    failing = SarvamProvider(
        client=_FakeSarvamClient(_FakeSarvamCompletions(error=UnauthorizedError(secret)))
    )
    with pytest.raises(SarvamAuthenticationError) as captured:
        failing.rewrite(_rewrite_request())
    assert secret not in str(captured.value)
    assert secret not in repr(failing)

    empty = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=""))], usage=None
    )
    provider = SarvamProvider(client=_FakeSarvamClient(_FakeSarvamCompletions(empty)))
    with pytest.raises(SarvamMalformedResponseError):
        provider.rewrite(_rewrite_request())

    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="SARVAM_API_KEY"):
        SarvamProvider.from_env()


class _FakeResponse:
    def __init__(self, status: int, payload: Mapping[str, Any]) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Mapping[str, Any]:
        return self._payload


class _FakeHttpClient:
    def __init__(self, responses: Sequence[_FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, Mapping[str, Any]]] = []
        self.closed = False

    async def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    async def aclose(self) -> None:
        self.closed = True


def test_zoho_crm_search_applies_allowlist_and_untrusted_provenance() -> None:
    client = _FakeHttpClient(
        [
            _FakeResponse(
                200,
                {
                    "data": [
                        {
                            "id": "deal-1",
                            "Deal_Name": "Acme Renewal",
                            "Stage": "Negotiation",
                            "Secret_Internal_Field": "must not leave adapter",
                        }
                    ]
                },
            )
        ]
    )
    source = ZohoCRMContextSource(
        access_token="oauth-secret",
        modules=("Deals",),
        field_allowlists={"Deals": ("Deal_Name", "Stage")},
        client=client,
    )
    items = asyncio.run(source.search("Acme", limit=3))

    assert len(items) == 1
    assert items[0].role is ContextRole.RAG
    assert items[0].source == "zoho:crm"
    assert "Secret_Internal_Field" not in items[0].content
    assert client.calls[0][1] == "https://www.zohoapis.com/crm/v8/Deals/search"
    assert client.calls[0][2]["params"]["fields"] == "Deal_Name,Stage"
    assert "oauth-secret" not in repr(source)


def test_zoho_coql_is_constructed_from_allowlisted_identifiers_and_literals() -> None:
    client = _FakeHttpClient([_FakeResponse(200, {"data": []})])
    source = ZohoCRMContextSource(
        access_token="token",
        modules=("Deals",),
        field_allowlists={"Deals": ("Deal_Name", "Stage")},
        client=client,
    )
    asyncio.run(source.query_equal("Deals", {"Deal_Name": "O'Reilly"}, limit=5))
    body = client.calls[0][2]["json"]["select_query"]
    assert "O\\'Reilly" in body
    assert body.endswith("limit 0, 5")
    with pytest.raises(ValueError, match="allowlisted"):
        asyncio.run(source.query_equal("Deals", {"Unauthorized_Field": "x"}))


def test_zoho_workdrive_uses_explicit_loader_and_sanitizes_auth_errors() -> None:
    record = {
        "id": "file-1",
        "attributes": {"name": "notes.txt", "description": "metadata"},
    }

    async def loader(_: Mapping[str, Any]) -> str:
        return "Authorized file body"

    client = _FakeHttpClient([_FakeResponse(200, {"data": [record]})])
    source = ZohoWorkDriveContextSource(
        "team-1", access_token="token", client=client, content_loader=loader
    )
    item = asyncio.run(source.search("notes", limit=1))[0]
    assert item.content == "Authorized file body"
    assert item.metadata["content_loaded"] is True
    assert "filter[parentId]" not in client.calls[0][2]["params"]

    denied = ZohoWorkDriveContextSource(
        "team-1",
        access_token="never-echo",
        client=_FakeHttpClient([_FakeResponse(401, {"message": "never-echo"})]),
    )
    with pytest.raises(ZohoAuthenticationError) as captured:
        asyncio.run(denied.search("notes"))
    assert "never-echo" not in str(captured.value)


class _FakeCursor:
    def __init__(self, documents: Sequence[Mapping[str, Any]]) -> None:
        self.documents = list(documents)
        self.bound: int | None = None

    def limit(self, value: int) -> "_FakeCursor":
        self.bound = value
        return self

    async def to_list(self, length: int) -> list[Mapping[str, Any]]:
        bound = min(length, self.bound) if self.bound is not None else length
        return self.documents[:bound]


class _FakeCollection:
    def __init__(self) -> None:
        self.documents: dict[str, Mapping[str, Any]] = {}
        self.last_pipeline: Sequence[Mapping[str, Any]] | None = None
        self.failure: Exception | None = None

    async def replace_one(
        self, query: Mapping[str, Any], document: Mapping[str, Any], upsert: bool
    ) -> Any:
        del query, upsert
        if self.failure:
            raise self.failure
        self.documents[str(document["_id"])] = dict(document)
        return SimpleNamespace()

    async def find_one(self, query: Mapping[str, Any]) -> Mapping[str, Any] | None:
        if self.failure:
            raise self.failure
        return self.documents.get(str(query["_id"]))

    def find(self, query: Mapping[str, Any], **kwargs: Any) -> _FakeCursor:
        del kwargs
        pattern = re.compile(query["content"]["$regex"], re.IGNORECASE)
        documents = [
            document
            for document in self.documents.values()
            if document.get("namespace") == query["namespace"]
            and document.get("record_type") == "context_item"
            and pattern.search(str(document.get("content", "")))
        ]
        return _FakeCursor(documents)

    def aggregate(self, pipeline: Sequence[Mapping[str, Any]]) -> _FakeCursor:
        self.last_pipeline = pipeline
        return _FakeCursor(list(self.documents.values()))

    async def delete_one(self, query: Mapping[str, Any]) -> Any:
        existed = self.documents.pop(str(query["_id"]), None) is not None
        return SimpleNamespace(deleted_count=int(existed))


class _FakeDatabase:
    def __init__(self, collection: _FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, _: str) -> _FakeCollection:
        return self.collection


class _FakeMongoClient:
    def __init__(self, collection: _FakeCollection) -> None:
        self.collection = collection
        self.closed = False

    def __getitem__(self, _: str) -> _FakeDatabase:
        return _FakeDatabase(self.collection)

    async def close(self) -> None:
        self.closed = True


def test_mongodb_store_is_explicit_bounded_and_scrubs_sensitive_metadata() -> None:
    collection = _FakeCollection()
    store = MongoDBContextStore(client=_FakeMongoClient(collection))
    item = ContextItem(
        "memory-1",
        "Acme renewal is in negotiation",
        kind=ContextKind.MEMORY,
        role=ContextRole.USER,
        metadata={"access_token": "never-store", "owner": "user-7"},
    )
    asyncio.run(store.save(item, "tenant-a"))
    stored = collection.documents["tenant-a:memory-1"]
    assert stored["metadata"]["access_token"] == "<redacted>"
    assert "never-store" not in repr(store)
    assert asyncio.run(store.get("memory-1", "tenant-a")) is not None
    matches = asyncio.run(store.search("renewal", namespace="tenant-a"))
    assert [entry.item_id for entry in matches] == ["memory-1"]
    assert asyncio.run(store.delete("memory-1", "tenant-a")) is True
    assert asyncio.run(store.delete("memory-1", "tenant-a")) is False


def test_mongodb_source_downgrades_stored_trust_and_vector_provider_is_explicit() -> None:
    collection = _FakeCollection()
    store = MongoDBContextStore(client=_FakeMongoClient(collection))
    trusted = ContextItem(
        "stored",
        "customer preference",
        kind=ContextKind.SYSTEM,
        role=ContextRole.SYSTEM,
    )
    asyncio.run(store.save(trusted))
    source = MongoDBContextSource(store)
    retrieved = asyncio.run(source.search("customer"))[0]
    assert retrieved.role is ContextRole.RAG
    assert retrieved.kind is ContextKind.RAG_DOCUMENT
    assert retrieved.required is False

    async def embed(_: str) -> Sequence[float]:
        return (0.1, 0.2, 0.3)

    vector_source = MongoDBContextSource(
        store, embedding_provider=embed, vector_index="context_vectors"
    )
    asyncio.run(vector_source.search("customer", limit=1))
    assert collection.last_pipeline is not None
    stage = collection.last_pipeline[0]["$vectorSearch"]
    assert stage["queryVector"] == [0.1, 0.2, 0.3]
    assert stage["limit"] == 1


def test_mongodb_errors_never_echo_connection_material() -> None:
    class DriverFailure(Exception):
        pass

    secret = "mongodb+srv://user:password@example.test"
    collection = _FakeCollection()
    collection.failure = DriverFailure(secret)
    store = MongoDBContextStore(client=_FakeMongoClient(collection))
    with pytest.raises(MongoDBIntegrationError) as captured:
        asyncio.run(store.save(ContextItem("x", "safe")))
    assert secret not in str(captured.value)


def test_in_memory_store_source_collection_and_explicit_fail_open() -> None:
    item = ContextItem("one", "Acme account fact", kind=ContextKind.MEMORY)
    store = InMemoryContextStore()
    asyncio.run(store.save(item))
    assert asyncio.run(store.get("one")) == item
    assert asyncio.run(store.search("Acme"))[0] == item

    source = InMemoryContextSource((item,))
    result = asyncio.run(collect_context_sources((source,), "Acme"))
    assert result.items == (item,)

    class FailingSource:
        source_id = "failing"

        async def search(self, query: str, limit: int = 10) -> Sequence[ContextItem]:
            del query, limit
            raise RuntimeError("credential-shaped-message")

    with pytest.raises(ContextSourceError) as captured:
        asyncio.run(collect_context_sources((FailingSource(),), "query"))
    assert "credential-shaped-message" not in str(captured.value)

    partial = asyncio.run(
        collect_context_sources((source, FailingSource()), "Acme", fail_open=True)
    )
    assert partial.items == (item,)
    assert partial.failures[0].error_type == "RuntimeError"


def test_aplan_records_explicit_source_fail_open_without_corrupting_plan() -> None:
    class FailingSource:
        source_id = "offline-crm"

        async def search(self, query: str, limit: int = 10) -> Sequence[ContextItem]:
            del query, limit
            raise TimeoutError("customer payload")

    plan = asyncio.run(
        AdaptiveContextPlanner().aplan(
            context_sources=(FailingSource(),),
            fail_open_sources=True,
            query="What changed?",
            max_input_tokens=500,
            reserve_output_tokens=0,
            safety_margin_tokens=0,
        )
    )
    assert plan.feasible
    assert any("offline-crm" in warning and "TimeoutError" in warning for warning in plan.warnings)
    assert all("customer payload" not in warning for warning in plan.warnings)
