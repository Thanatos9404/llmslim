"""Neo4j temporal memory store tests against a recording fake async driver (no network)."""

from __future__ import annotations

import asyncio
import hashlib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union

import pytest

import llmslim.integrations.neo4j as store_module
from llmslim import AdaptiveContextPlanner, ContextItem, ContextKind, ContextRole
from llmslim.context import ContextSource, ContextStore
from llmslim.integrations._guard import (
    RateLimitExceeded,
    UsageCapExceeded,
    UsageGuard,
    UsageLimits,
)
from llmslim.integrations.neo4j import (
    DEFAULT_USAGE_LIMITS,
    MEMORY_LABEL,
    SUPERSEDES_RELATIONSHIP,
    MemoryDraft,
    MemoryRecord,
    Neo4jAuthenticationError,
    Neo4jConstraintError,
    Neo4jContextStore,
    Neo4jIntegrationError,
    Neo4jMemoryNotFoundError,
    Neo4jSupersessionError,
    Neo4jTransientError,
    Neo4jUnavailableError,
)

UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 3, 1, tzinfo=UTC)
TENANT = "tenant-a"
SUBJECT = "user:42/language"

Rows = List[Dict[str, Any]]
Response = Union[Rows, BaseException]

DATA_STATEMENTS = {
    store_module._GET,
    store_module._FIND_CURRENT_DUPLICATE,
    store_module._CREATE,
    store_module._RECALL,
    store_module._RECALL_SUBJECT,
    store_module._CYCLE_CHECK,
    store_module._LINK,
    store_module._FORGET_SOFT,
    store_module._FORGET_HARD,
    store_module._HISTORY_OLDER,
    store_module._HISTORY_NEWER,
    store_module._CONFLICTS,
    store_module._CONFLICTS_SUBJECT,
}
ALL_STATEMENTS = DATA_STATEMENTS | set(store_module._SCHEMA_STATEMENTS)


# --- fake driver --------------------------------------------------------------------------


@dataclass
class Call:
    query: str
    parameters: Dict[str, Any]
    session: Dict[str, Any]
    timeout: Optional[float]


@dataclass
class FakeDriver:
    """Records every statement and returns scripted rows (FIFO) or a responder's rows."""

    script: List[Response] = field(default_factory=list)
    responder: Optional[Callable[[str, Dict[str, Any]], Response]] = None
    session_error: Optional[BaseException] = None
    begin_error: Optional[BaseException] = None
    commit_error: Optional[BaseException] = None
    calls: List[Call] = field(default_factory=list)
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0
    closed: int = 0

    def session(self, **config: Any) -> "FakeSession":
        self.sessions.append(dict(config))
        if self.session_error is not None:
            raise self.session_error
        return FakeSession(self, dict(config))

    async def close(self) -> None:
        self.closed += 1

    def respond(self, query: str, parameters: Dict[str, Any]) -> Response:
        if self.responder is not None:
            return self.responder(query, parameters)
        return self.script.pop(0) if self.script else []

    def queries(self) -> List[str]:
        return [call.query for call in self.calls]


class FakeSession:
    def __init__(self, driver: FakeDriver, config: Dict[str, Any]) -> None:
        self.driver = driver
        self.config = config

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def begin_transaction(self, timeout: Optional[float] = None) -> "FakeTransaction":
        if self.driver.begin_error is not None:
            raise self.driver.begin_error
        return FakeTransaction(self.driver, self.config, timeout)


class FakeResult:
    def __init__(self, rows: Rows) -> None:
        self.rows = rows

    async def data(self) -> Rows:
        return [dict(row) for row in self.rows]


class FakeTransaction:
    def __init__(self, driver: FakeDriver, config: Dict[str, Any], timeout: Optional[float]):
        self.driver = driver
        self.config = config
        self.timeout = timeout
        self.done = False

    async def __aenter__(self) -> "FakeTransaction":
        return self

    async def __aexit__(self, exc_type: Any, *_: Any) -> None:
        if not self.done:
            self.done = True
            self.driver.rollbacks += 1

    async def run(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> FakeResult:
        params = dict(parameters or {})
        self.driver.calls.append(Call(query, params, self.config, self.timeout))
        response = self.driver.respond(query, params)
        if isinstance(response, BaseException):
            raise response
        return FakeResult(response)

    async def commit(self) -> None:
        if self.driver.commit_error is not None:
            raise self.driver.commit_error
        self.done = True
        self.driver.commits += 1


# --- helpers ------------------------------------------------------------------------------


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def node(
    memory_id: str,
    content: str = "The user prefers Hindi.",
    *,
    subject: str = SUBJECT,
    tenant: str = TENANT,
    namespace: str = "default",
    valid_from: Any = T0,
    valid_until: Any = None,
    created_at: Any = T0,
    forgotten_at: Any = None,
    metadata_json: str = "{}",
) -> Dict[str, Any]:
    return {
        "tenant_id": tenant,
        "namespace": namespace,
        "memory_id": memory_id,
        "subject": subject,
        "content": content,
        "content_sha256": sha(content),
        "kind": "fact",
        "source": "user-approved",
        "created_at": created_at,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "forgotten_at": forgotten_at,
        "metadata_json": metadata_json,
    }


def row(
    memory: Dict[str, Any],
    supersedes: Sequence[str] = (),
    superseded_by: Sequence[str] = (),
) -> Dict[str, Any]:
    return {"memory": memory, "supersedes": list(supersedes), "superseded_by": list(superseded_by)}


def make_store(driver: FakeDriver, **kwargs: Any) -> Neo4jContextStore:
    kwargs.setdefault("tenant_id", TENANT)
    kwargs.setdefault("guard", UsageGuard.unlimited(name="neo4j"))
    kwargs.setdefault("clock", lambda: NOW)
    return Neo4jContextStore(driver, **kwargs)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# --- construction, credentials and lifecycle ----------------------------------------------


def test_constructor_validates_inputs_without_echoing_secrets() -> None:
    driver = FakeDriver()
    with pytest.raises(ValueError, match="not both"):
        Neo4jContextStore(driver, uri="neo4j+s://x.example", tenant_id=TENANT)
    with pytest.raises(ValueError, match="from_env"):
        Neo4jContextStore(tenant_id=TENANT)
    for tenant in ("", "  ", "a\nb", "x" * 201, 7):
        with pytest.raises(ValueError, match="tenant_id"):
            Neo4jContextStore(driver, tenant_id=tenant)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="namespace"):
        Neo4jContextStore(driver, tenant_id=TENANT, namespace="bad\x00ns")
    with pytest.raises(ValueError, match="database"):
        Neo4jContextStore(driver, tenant_id=TENANT, database="bad name; DROP")
    for value in (0, True, store_module.MAX_CONTENT_CHARS_CEILING + 1, 1.5):
        with pytest.raises(ValueError, match="max_content_chars"):
            Neo4jContextStore(driver, tenant_id=TENANT, max_content_chars=value)  # type: ignore[arg-type]
    for value in (0, -1, float("nan"), True, "5"):
        with pytest.raises(ValueError, match="transaction_timeout_seconds"):
            Neo4jContextStore(driver, tenant_id=TENANT, transaction_timeout_seconds=value)  # type: ignore[arg-type]
    secret_uri = "http://neo4j:hunter2@example.test"
    with pytest.raises(ValueError) as captured:
        Neo4jContextStore(uri=secret_uri, auth=("neo4j", "hunter2"), tenant_id=TENANT)
    assert "hunter2" not in str(captured.value)
    with pytest.raises(ValueError, match="auth is required"):
        Neo4jContextStore(uri="neo4j+s://x.example", tenant_id=TENANT)
    for auth in (("neo4j",), ("neo4j", ""), ("neo4j", 5)):
        with pytest.raises(ValueError, match="username, password"):
            Neo4jContextStore(uri="neo4j+s://x.example", auth=auth, tenant_id=TENANT)
    assert driver.sessions == []


def _fake_neo4j_module(monkeypatch: Any) -> List[Dict[str, Any]]:
    created: List[Dict[str, Any]] = []

    def factory(uri: str, **kwargs: Any) -> FakeDriver:
        created.append({"uri": uri, **kwargs})
        return FakeDriver()

    monkeypatch.setitem(
        sys.modules, "neo4j", SimpleNamespace(AsyncGraphDatabase=SimpleNamespace(driver=factory))
    )
    return created


def test_owned_driver_is_created_lazily_and_closed_once(monkeypatch: Any) -> None:
    created = _fake_neo4j_module(monkeypatch)
    store = Neo4jContextStore(
        uri="neo4j+s://abc.databases.neo4j.io",
        auth=["neo4j", "hunter2"],
        tenant_id=TENANT,
        database="neo4j",
        guard=UsageGuard.unlimited(),
        connection_timeout_seconds=3,
    )
    assert created == [
        {
            "uri": "neo4j+s://abc.databases.neo4j.io",
            "auth": ("neo4j", "hunter2"),
            "connection_timeout": 3.0,
            "connection_acquisition_timeout": 3.0,
            "user_agent": "llmslim",
        }
    ]
    driver = store._driver
    assert driver.sessions == []  # construction never opens a session
    text = repr(store)
    assert "hunter2" not in text and "databases.neo4j.io" not in text and "redacted" in text
    run(store.aclose())
    run(store.close())
    assert driver.closed == 1

    async def scoped() -> FakeDriver:
        async with Neo4jContextStore(
            uri="bolt://localhost:7687", auth=("neo4j", "pw"), tenant_id=TENANT
        ) as owned:
            return owned._driver

    assert run(scoped()).closed == 1


def test_auth_objects_pass_through_and_default_clock_is_utc(monkeypatch: Any) -> None:
    created = _fake_neo4j_module(monkeypatch)
    token = SimpleNamespace(scheme="bearer")
    Neo4jContextStore(uri="neo4j://localhost", auth=token, tenant_id=TENANT)
    assert created[0]["auth"] is token
    driver = FakeDriver()
    store = Neo4jContextStore(driver, tenant_id=TENANT, guard=UsageGuard.unlimited())
    before = datetime.now(UTC)
    run(store.recall())
    as_of = driver.calls[0].parameters["as_of"]
    assert as_of.tzinfo == UTC and before <= as_of <= datetime.now(UTC)


def test_injected_driver_is_never_closed_by_the_store() -> None:
    driver = FakeDriver()

    async def scoped() -> None:
        async with make_store(driver) as store:
            await store.aclose()

    run(scoped())
    assert driver.closed == 0


def test_real_driver_construction_does_not_connect() -> None:
    pytest.importorskip("neo4j")

    async def construct_and_close() -> str:
        store = Neo4jContextStore(
            uri="neo4j+s://unreachable.invalid", auth=("neo4j", "hunter2"), tenant_id=TENANT
        )
        name = type(store._driver).__name__
        await store.aclose()
        return name

    assert run(construct_and_close()) == "AsyncNeo4jDriver"


def test_from_env_reads_only_named_variables(monkeypatch: Any) -> None:
    created = _fake_neo4j_module(monkeypatch)
    with pytest.raises(ValueError, match="NEO4J_PASSWORD is not set") as captured:
        Neo4jContextStore.from_env(
            tenant_id=TENANT, env={"NEO4J_URI": "neo4j+s://x.example", "NEO4J_USERNAME": "neo4j"}
        )
    assert "x.example" not in str(captured.value)
    env = {
        "NEO4J_URI": "neo4j+s://x.example",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "hunter2",
        "NEO4J_DATABASE": " memories ",
        "LLMSLIM_NEO4J_REQUESTS_PER_MINUTE": "5",
        "LLMSLIM_NEO4J_MAX_REQUESTS": "none",
    }
    store = Neo4jContextStore.from_env(tenant_id=TENANT, env=env, namespace="agent-7")
    assert created[-1]["auth"] == ("neo4j", "hunter2")
    assert store.database == "memories" and store.namespace == "agent-7"
    assert store.guard.limits.requests_per_minute == 5
    assert store.guard.limits.max_requests is None
    assert store.guard.limits.unit == "queries"
    explicit = UsageGuard.unlimited()
    assert Neo4jContextStore.from_env(tenant_id=TENANT, env=env, guard=explicit).guard is explicit
    overridden = Neo4jContextStore.from_env(tenant_id=TENANT, env=env, database="other")
    assert overridden.database == "other"
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert Neo4jContextStore.from_env(tenant_id=TENANT).database == "memories"


def test_default_guard_uses_neo4j_limits_and_env_overrides(monkeypatch: Any) -> None:
    for suffix in ("REQUESTS_PER_MINUTE", "MAX_REQUESTS", "MAX_UNITS"):
        monkeypatch.delenv("LLMSLIM_NEO4J_" + suffix, raising=False)
    store = Neo4jContextStore(FakeDriver(), tenant_id=TENANT)
    assert store.guard.limits == DEFAULT_USAGE_LIMITS
    assert (DEFAULT_USAGE_LIMITS.requests_per_minute, DEFAULT_USAGE_LIMITS.max_requests) == (
        600,
        100_000,
    )
    monkeypatch.setenv("LLMSLIM_NEO4J_MAX_REQUESTS", "7")
    assert Neo4jContextStore(FakeDriver(), tenant_id=TENANT).guard.limits.max_requests == 7


# --- schema -------------------------------------------------------------------------------


def test_ensure_schema_is_idempotent_and_parameter_free() -> None:
    driver = FakeDriver()
    store = make_store(driver, database="neo4j", transaction_timeout_seconds=4)
    run(store.ensure_schema())
    run(store.ensure_schema())
    queries = driver.queries()
    assert queries[:4] == queries[4:] == list(store_module._SCHEMA_STATEMENTS)
    assert all("IF NOT EXISTS" in query for query in queries)
    assert all(call.parameters == {} for call in driver.calls)
    assert all(
        call.session == {"default_access_mode": "WRITE", "database": "neo4j"}
        for call in driver.calls
    )
    assert all(call.timeout == 4.0 for call in driver.calls)
    constraint = queries[0]
    assert "REQUIRE (m.tenant_id, m.namespace, m.memory_id) IS UNIQUE" in constraint
    assert any("m.subject" in query for query in queries)
    assert any("m.valid_from" in query for query in queries)
    assert any("m.valid_until" in query for query in queries)
    assert driver.commits == 8 and len(driver.sessions) == 8  # one transaction per statement


# --- remember -----------------------------------------------------------------------------


def test_remember_creates_one_scoped_memory_with_hash_and_scrubbed_metadata() -> None:
    created = node("mem-1", metadata_json='{"password":"<redacted>","topic":"lang"}')
    driver = FakeDriver(script=[[], [], [row(created)]])
    store = make_store(driver)
    record = run(
        store.remember(
            f"  {SUBJECT} ",
            "  The user prefers Hindi.\n",
            memory_id="mem-1",
            source="user-approved",
            metadata={"password": "never-store", "topic": "lang"},
        )
    )
    get, duplicate, create = driver.calls
    assert get.query == store_module._GET and get.parameters["memory_id"] == "mem-1"
    assert duplicate.query == store_module._FIND_CURRENT_DUPLICATE
    assert duplicate.parameters == {
        "tenant_id": TENANT,
        "namespace": "default",
        "subject": SUBJECT,
        "content_sha256": sha("The user prefers Hindi."),
        "valid_from": NOW,
    }
    assert create.query == store_module._CREATE
    params = create.parameters
    assert params["content"] == "The user prefers Hindi."
    assert params["created_at"] == NOW and params["valid_from"] == NOW
    assert params["valid_until"] is None
    assert "never-store" not in params["metadata_json"]
    assert '"password":"<redacted>"' in params["metadata_json"]
    assert create.session["default_access_mode"] == "WRITE"
    assert driver.commits == 1 and driver.rollbacks == 0
    assert isinstance(record, MemoryRecord)
    assert record.memory_id == "mem-1" and record.metadata["topic"] == "lang"
    assert record.to_dict()["valid_from"] == T0.isoformat()


def test_remember_generates_ids_and_accepts_bounded_validity() -> None:
    driver = FakeDriver(script=[[], [row(node("generated"))]])
    store = make_store(driver)
    run(
        store.remember(
            SUBJECT,
            "Fact",
            valid_from=datetime(2026, 2, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
            valid_until=NOW + timedelta(days=1),
        )
    )
    duplicate, create = driver.calls  # no ID lookup without an explicit memory_id
    assert create.parameters["memory_id"].startswith("mem_")
    assert create.parameters["valid_from"] == datetime(2026, 2, 1, tzinfo=UTC)
    assert create.parameters["valid_from"].tzinfo == UTC
    assert create.parameters["valid_until"] == NOW + timedelta(days=1)


def test_remember_is_idempotent_on_content_hash_per_subject() -> None:
    existing = node("mem-old")
    driver = FakeDriver(script=[[row(existing)]])
    record = run(make_store(driver).remember(SUBJECT, "The user prefers Hindi."))
    assert record.memory_id == "mem-old"
    assert driver.queries() == [store_module._FIND_CURRENT_DUPLICATE]
    assert driver.commits == 1


def test_remember_with_existing_id_is_idempotent_or_refused() -> None:
    same = FakeDriver(script=[[row(node("mem-1"))]])
    assert run(make_store(same).remember(SUBJECT, "The user prefers Hindi.", memory_id="mem-1"))
    assert same.queries() == [store_module._GET]

    different = FakeDriver(script=[[row(node("mem-1", "Something else"))]])
    with pytest.raises(Neo4jConstraintError, match="supersede"):
        run(make_store(different).remember(SUBJECT, "The user prefers Hindi.", memory_id="mem-1"))
    assert different.rollbacks == 1 and different.commits == 0


def test_create_must_return_the_memory() -> None:
    driver = FakeDriver(script=[[], []])
    with pytest.raises(Neo4jIntegrationError, match="did not return"):
        run(make_store(driver).remember(SUBJECT, "Fact"))


# --- datetimes and bounds -----------------------------------------------------------------


def test_naive_datetimes_are_rejected_before_any_query() -> None:
    driver = FakeDriver()
    store = make_store(driver)
    naive = datetime(2026, 1, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        run(store.remember(SUBJECT, "Fact", valid_from=naive))
    with pytest.raises(ValueError, match="timezone-aware"):
        run(store.remember(SUBJECT, "Fact", valid_until=naive))
    with pytest.raises(ValueError, match="timezone-aware"):
        run(store.recall(as_of=naive))
    with pytest.raises(ValueError, match="timezone-aware"):
        run(store.conflicts(as_of=naive))
    with pytest.raises(ValueError, match="timezone-aware"):
        run(store.supersede("a", "b", reason="r", at=naive))
    with pytest.raises(ValueError, match="timezone-aware"):
        run(store.forget("a", at=naive))
    with pytest.raises(ValueError, match="timezone-aware"):
        run(store.remember(SUBJECT, "Fact", valid_from="2026-01-01T00:00:00Z"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="clock"):
        run(make_store(driver, clock=lambda: naive).recall())
    record = MemoryRecord("m", SUBJECT, "c", sha("c"), "fact", "caller", T0, T0)
    with pytest.raises(ValueError, match="timezone-aware"):
        record.is_valid_at(naive)
    assert driver.calls == []


def test_bounds_are_validated_with_clear_errors() -> None:
    driver = FakeDriver()
    store = make_store(driver, max_content_chars=20)
    cases: List[Any] = [
        (store.remember(SUBJECT, "x" * 21), "max_content_chars"),
        (store.remember(SUBJECT, "   "), "must not be empty"),
        (store.remember(SUBJECT, 5), "must be a string"),  # type: ignore[arg-type]
        (store.remember(SUBJECT, "a\x00b"), "control characters"),
        (store.remember("", "Fact"), "subject"),
        (store.remember("s" * 201, "Fact"), "subject"),
        (store.remember(None, "Fact"), "subject"),  # type: ignore[arg-type]
        (store.remember(SUBJECT, "Fact", kind="Bad Kind"), "kind"),
        (store.remember(SUBJECT, "Fact", source=""), "source"),
        (store.remember(SUBJECT, "Fact", memory_id="i" * 201), "memory_id"),
        (store.remember(SUBJECT, "Fact", metadata={"blob": "x" * 9000}), "8192 bytes"),
        (store.remember(SUBJECT, "Fact", metadata=["not", "a", "mapping"]), "mapping"),  # type: ignore[arg-type]
        (store.remember(SUBJECT, "Fact", valid_from=NOW, valid_until=NOW), "later than"),
        (store.recall(query="q" * 501), "query"),
        (store.recall(query="   "), "query"),
        (store.recall(limit=0), "recall limit"),
        (store.recall(limit=101), "recall limit"),
        (store.recall(limit=True), "recall limit"),  # type: ignore[arg-type]
        (store.history("m", max_depth=0), "max_depth"),
        (store.history("m", max_depth=51), "max_depth"),
        (store.conflicts(limit=101), "conflict limit"),
        (store.supersede("a", "b", reason=""), "reason"),
        (store.supersede("a", "b", reason="r" * 501), "reason"),
        (store.supersede("a", "b", reason=5), "reason must be a string"),  # type: ignore[arg-type]
        (store.supersede("", "b", reason="r"), "old_id"),
        (store.forget("x\ny"), "memory_id"),
        (store.get(""), "memory_id"),
        (store.recall(namespace=""), "namespace"),
    ]
    circular: Dict[str, Any] = {}
    circular["self"] = circular
    cases.append((store.remember(SUBJECT, "Fact", metadata=circular), "nesting exceeds"))
    cases.append(
        (store.remember(SUBJECT, "Fact", metadata={"n": float("nan")}), "JSON-serializable")
    )
    for coro, message in cases:
        with pytest.raises(ValueError, match=message):
            run(coro)
    with pytest.raises(TypeError, match="MemoryDraft"):
        run(store.supersede("a", 42, reason="r"))  # type: ignore[arg-type]
    assert driver.calls == []


# --- supersession -------------------------------------------------------------------------


def test_supersede_with_draft_closes_old_and_links_atomically() -> None:
    at = datetime(2026, 2, 1, tzinfo=UTC)
    old = node("mem-old")
    new = node("mem-new", "The user now prefers English.", valid_from=at, created_at=NOW)
    driver = FakeDriver(script=[[row(old)], [], [row(new)], [{"linked": 1}]])
    record = run(
        make_store(driver).supersede(
            "mem-old",
            MemoryDraft("The user now prefers English.", memory_id="mem-new", metadata={"k": 1}),
            reason="user changed the setting",
            at=at,
        )
    )
    get, duplicate, create, link = driver.calls
    assert get.parameters["memory_id"] == "mem-old"
    assert duplicate.parameters["subject"] == SUBJECT  # inherited from the old memory
    assert duplicate.parameters["valid_from"] == at
    assert create.parameters["valid_from"] == at and create.parameters["created_at"] == NOW
    assert create.parameters["valid_until"] is None
    assert link.query == store_module._LINK
    assert link.parameters == {
        "tenant_id": TENANT,
        "namespace": "default",
        "old_id": "mem-old",
        "new_id": "mem-new",
        "at": at,
        "reason": "user changed the setting",
    }
    assert (
        "SET prior.valid_until" in link.query
        and "MERGE (successor)-[link:SUPERSEDES]->(prior)" in link.query
    )
    assert record.memory_id == "mem-new" and record.supersedes == ("mem-old",)
    assert driver.commits == 1 and driver.rollbacks == 0


def test_supersede_links_an_existing_memory_after_cycle_check() -> None:
    old = node("A", "Office is in Pune.")
    new = node("B", "Office is in Bengaluru.", valid_from=T0 + timedelta(days=3))
    driver = FakeDriver(script=[[row(old)], [row(new)], [{"cycle": False}], [{"linked": 1}]])
    record = run(make_store(driver).supersede("A", "B", reason="moved"))
    assert driver.queries() == [
        store_module._GET,
        store_module._GET,
        store_module._CYCLE_CHECK,
        store_module._LINK,
    ]
    assert driver.calls[2].parameters == {
        "tenant_id": TENANT,
        "namespace": "default",
        "old_id": "A",
        "new_id": "B",
    }
    assert driver.calls[3].parameters["at"] == NOW
    assert record.supersedes == ("A",)


def test_supersede_with_draft_matching_a_current_fact_links_it_instead_of_copying() -> None:
    old = node("A", "Office is in Pune.")
    current = node("C", "Office is in Bengaluru.")
    driver = FakeDriver(script=[[row(old)], [row(current)], [{"cycle": False}], [{"linked": 1}]])
    record = run(
        make_store(driver).supersede("A", MemoryDraft("Office is in Bengaluru."), reason="r")
    )
    assert store_module._CREATE not in driver.queries()
    assert record.memory_id == "C" and record.supersedes == ("A",)


def test_supersede_refusals_roll_back_and_never_link() -> None:
    store_factory = make_store
    # Self-supersession is refused before any query.
    driver = FakeDriver()
    with pytest.raises(Neo4jSupersessionError, match="itself"):
        run(store_factory(driver).supersede("A", " A ", reason="r"))
    assert driver.calls == []

    refusals: List[Any] = [
        # missing old
        ([[]], "A", "B", {}, Neo4jMemoryNotFoundError, "to supersede was not found"),
        # missing replacement
        ([[row(node("A"))], []], "A", "B", {}, Neo4jMemoryNotFoundError, "replacement"),
        # cycle: A already supersedes B, so B superseding A would loop
        (
            [
                [row(node("A"), supersedes=["B"])],
                [row(node("B", "x"), superseded_by=["A"])],
                [{"cycle": True}],
            ],
            "A",
            "B",
            {"allow_superseded": True},
            Neo4jSupersessionError,
            "cycle",
        ),
        # already superseded old memory
        (
            [[row(node("A"), superseded_by=["Z"])]],
            "A",
            "B",
            {},
            Neo4jSupersessionError,
            "already superseded",
        ),
        # replacement superseded
        (
            [[row(node("A"))], [row(node("B", "x"), superseded_by=["Z"])], [{"cycle": False}]],
            "A",
            "B",
            {},
            Neo4jSupersessionError,
            "itself superseded",
        ),
        # replacement already ended
        (
            [[row(node("A"))], [row(node("B", "x", valid_until=NOW))], [{"cycle": False}]],
            "A",
            "B",
            {},
            Neo4jSupersessionError,
            "no longer valid",
        ),
        # supersession instant before the old memory began
        (
            [[row(node("A", valid_from=NOW + timedelta(days=1)))]],
            "A",
            "B",
            {},
            Neo4jSupersessionError,
            "precedes",
        ),
        # identical replacement content
        (
            [[row(node("A"))]],
            "A",
            MemoryDraft("The user prefers Hindi."),
            {},
            Neo4jSupersessionError,
            "identical",
        ),
        # duplicate lookup returned the old memory itself
        (
            [[row(node("A"))], [row(node("A"))]],
            "A",
            MemoryDraft("Different", subject="other"),
            {},
            Neo4jSupersessionError,
            "itself",
        ),
        # the link returned no usable count
        (
            [[row(node("A"))], [row(node("B", "x"))], [{"cycle": False}], [{"linked": None}]],
            "A",
            "B",
            {},
            Neo4jMemoryNotFoundError,
            "changed",
        ),
        # the link matched nothing (concurrent delete)
        (
            [[row(node("A"))], [row(node("B", "x"))], [{"cycle": False}], [{"linked": 0}]],
            "A",
            "B",
            {},
            Neo4jMemoryNotFoundError,
            "changed",
        ),
    ]
    for script, old_id, new_memory, options, error, message in refusals:
        driver = FakeDriver(script=list(script))
        with pytest.raises(error, match=message):
            run(store_factory(driver).supersede(old_id, new_memory, reason="r", **options))
        assert driver.commits == 0 and driver.rollbacks == 1
        if error is not Neo4jMemoryNotFoundError or message != "changed":
            assert store_module._LINK not in driver.queries()


def test_allow_superseded_permits_an_additional_successor() -> None:
    script: List[Response] = [
        [row(node("A"), superseded_by=["Z"])],
        [row(node("B", "x"), superseded_by=["Y"])],
        [{"cycle": False}],
        [{"linked": 1}],
    ]
    driver = FakeDriver(script=script)
    record = run(make_store(driver).supersede("A", "B", reason="merge", allow_superseded=True))
    assert record.supersedes == ("A",) and driver.commits == 1


def test_cross_tenant_ids_are_not_found_and_scope_is_enforced() -> None:
    graph = {("tenant-b", "default", "B-1"): node("B-1", tenant="tenant-b")}

    def responder(query: str, params: Dict[str, Any]) -> Response:
        assert params["tenant_id"] == TENANT  # every lookup is scoped to the store's tenant
        if query == store_module._GET:
            found = graph.get((params["tenant_id"], params["namespace"], params["memory_id"]))
            return [row(found)] if found else []
        return []

    driver = FakeDriver(responder=responder)
    store = make_store(driver)
    with pytest.raises(Neo4jMemoryNotFoundError):
        run(store.supersede("B-1", MemoryDraft("new"), reason="r"))
    assert run(store.get("B-1")) is None
    with pytest.raises(Neo4jMemoryNotFoundError):
        run(store.history("B-1"))

    # A query that leaked another tenant's node is refused, never returned.
    leaky = FakeDriver(script=[[row(node("B-1", tenant="tenant-b"))]])
    with pytest.raises(Neo4jIntegrationError, match="outside this store's scope"):
        run(make_store(leaky).recall())
    other_namespace = FakeDriver(script=[[row(node("N-1", namespace="other"))]])
    with pytest.raises(Neo4jIntegrationError, match="outside"):
        run(make_store(other_namespace).get("N-1"))


def test_namespace_override_changes_partition_but_never_tenant() -> None:
    driver = FakeDriver(script=[[row(node("N-1", namespace="agent-2"))]])
    store = make_store(driver)
    item = run(store.get("N-1", "agent-2"))
    assert item is not None
    assert driver.calls[0].parameters["namespace"] == "agent-2"
    assert driver.calls[0].parameters["tenant_id"] == TENANT


# --- recall -------------------------------------------------------------------------------


def test_recall_as_of_boundaries_are_half_open() -> None:
    as_of = datetime(2026, 2, 1, tzinfo=UTC)
    rows = [
        row(node("starts-at", "Starts exactly now.", valid_from=as_of)),
        row(node("ends-at", "Ended exactly now.", valid_from=T0, valid_until=as_of)),
        row(node("spans", "Spans the instant.", valid_from=T0, valid_until=NOW)),
        row(node("future", "Not yet valid.", valid_from=as_of + timedelta(seconds=1))),
    ]
    driver = FakeDriver(script=[rows])
    store = make_store(driver)
    local = as_of.astimezone(timezone(timedelta(hours=5, minutes=30)))
    items = run(store.recall(as_of=local))
    assert [item.item_id for item in items] == ["starts-at", "spans"]
    call = driver.calls[0]
    assert call.query == store_module._RECALL
    assert call.parameters["as_of"] == as_of and call.parameters["as_of"].tzinfo == UTC
    assert "m.valid_from <= $as_of" in call.query
    assert "m.valid_until IS NULL OR m.valid_until > $as_of" in call.query
    assert call.session["default_access_mode"] == "READ"
    assert call.parameters["terms"] == [] and call.parameters["candidate_limit"] == 10
    starts = items[0]
    assert starts.kind is ContextKind.MEMORY and starts.role is ContextRole.RAG
    assert starts.source == "neo4j:memory" and starts.required is False
    assert starts.recency == 1.0
    assert starts.metadata["valid_from"] == as_of.isoformat()
    assert starts.metadata["valid_until"] is None
    assert items[1].metadata["valid_until"] == NOW.isoformat()
    assert 0.0 < items[1].recency < 1.0

    record = MemoryRecord("m", SUBJECT, "c", sha("c"), "fact", "caller", T0, as_of, valid_until=NOW)
    assert record.is_valid_at(as_of) and not record.is_valid_at(NOW)
    assert not record.is_valid_at(as_of - timedelta(microseconds=1))


def test_recall_defaults_to_now_and_reports_supersession_and_conflicts() -> None:
    rows = [
        row(
            node("lang-new", "The user prefers English.", valid_from=T0 + timedelta(days=30)),
            supersedes=["lang-old"],
        ),
        row(node("lang-other", "The user prefers Tamil.", valid_from=T0 + timedelta(days=20))),
        row(
            node(
                "tz",
                "The user is in IST.",
                subject="user:42/timezone",
                metadata_json='{"conf":0.9}',
            )
        ),
    ]
    driver = FakeDriver(script=[rows])
    items = run(make_store(driver, recency_half_life_days=30).recall())
    assert driver.calls[0].parameters["as_of"] == NOW
    by_id = {item.item_id: item for item in items}
    assert [item.item_id for item in items] == ["lang-new", "lang-other", "tz"]
    assert [item.original_order for item in items] == [0, 1, 2]
    assert by_id["lang-new"].metadata["supersedes"] == ["lang-old"]
    assert by_id["lang-new"].metadata["conflicts_with"] == ["lang-other"]
    assert by_id["lang-other"].metadata["conflicts_with"] == ["lang-new"]
    assert "conflicts_with" not in by_id["tz"].metadata
    assert by_id["tz"].metadata["attributes"] == {"conf": 0.9}
    assert by_id["tz"].recency == pytest.approx(0.5 ** (59 / 30), abs=1e-6)
    # Stored attributes are nested, so they can never set planner-level metadata keys.
    assert set(by_id["tz"].metadata) >= {"memory_id", "subject", "memory_kind", "memory_source"}


def test_recall_with_subject_and_query_ranks_lexically() -> None:
    rows = [
        row(node("a", "Prefers dark mode in the editor.", valid_from=T0 + timedelta(days=5))),
        row(node("b", "Preferred language is Hindi for replies.", valid_from=T0)),
    ]
    driver = FakeDriver(script=[rows])
    items = run(make_store(driver).recall(SUBJECT, query="Preferred LANGUAGE?", limit=1))
    call = driver.calls[0]
    assert call.query == store_module._RECALL_SUBJECT
    assert call.parameters["subject"] == SUBJECT
    assert call.parameters["terms"] == ["language", "preferred"]
    assert call.parameters["candidate_limit"] == 4
    assert [item.item_id for item in items] == ["b"]

    single = FakeDriver()
    run(make_store(single).recall(query="a"))
    assert single.calls[0].parameters["terms"] == ["a"]
    many = FakeDriver()
    run(make_store(many).recall(query=" ".join(f"term{i}" for i in range(40))))
    assert len(many.calls[0].parameters["terms"]) == store_module.MAX_QUERY_TERMS


def test_recall_filters_wrong_subject_rows_on_the_client() -> None:
    driver = FakeDriver(script=[[row(node("x", subject="other"))]])
    assert run(make_store(driver).recall(SUBJECT)) == ()


def test_store_satisfies_context_protocols_and_plans_end_to_end() -> None:
    driver = FakeDriver(
        script=[[row(node("lang", "The user prefers concise status updates in Hindi."))]]
    )
    store = make_store(driver)
    assert isinstance(store, ContextSource) and isinstance(store, ContextStore)
    plan = run(
        AdaptiveContextPlanner().aplan(
            context_sources=[store],
            query="How should I format this status update?",
            model="generic-128k",
            max_input_tokens=1024,
        )
    )
    assert "concise status updates" in plan.final_context
    assert driver.calls[0].parameters["terms"]

    blank = FakeDriver()
    assert run(make_store(blank).search("   ")) == ()
    assert blank.calls[0].parameters["terms"] == []


def test_save_get_and_delete_follow_the_context_store_protocol() -> None:
    saved = node("item-1", "Saved fact.", subject="account:9", namespace="agent-1")
    driver = FakeDriver(script=[[], [], [row(saved)]])
    store = make_store(driver)
    item = ContextItem(
        "item-1",
        "Saved fact.",
        kind=ContextKind.MEMORY,
        source="approved",
        metadata={"subject": "account:9", "owner": "u7"},
    )
    assert run(store.save(item, "agent-1")) is None
    create = driver.calls[-1]
    assert create.parameters["subject"] == "account:9"
    assert create.parameters["namespace"] == "agent-1"
    assert create.parameters["memory_id"] == "item-1"
    assert create.parameters["metadata_json"] == '{"owner":"u7"}'

    general = FakeDriver(script=[[], [], [row(node("i2", "x", subject="general"))]])
    run(make_store(general).save(ContextItem("i2", "x")))
    assert general.calls[-1].parameters["subject"] == "general"

    getter = FakeDriver(
        script=[
            [
                row(
                    node(
                        "item-1",
                        valid_until=T0 + timedelta(days=1),
                        forgotten_at=T0 + timedelta(days=1),
                    )
                )
            ],
            [],
        ]
    )
    fetched = run(make_store(getter).get("item-1"))
    assert fetched is not None and fetched.metadata["forgotten_at"] is not None
    assert run(make_store(getter).get("missing")) is None

    deleter = FakeDriver(script=[[{"deleted": 1}], [{"deleted": 0}]])
    assert run(make_store(deleter).delete("item-1")) is True
    assert run(make_store(deleter).delete("item-1")) is False
    assert deleter.queries() == [store_module._FORGET_HARD] * 2


# --- history, conflicts, forget -----------------------------------------------------------


def _history_link(old_id: str, new_id: str, days: int) -> Dict[str, Any]:
    return {
        "old_id": old_id,
        "new_id": new_id,
        "at": T0 + timedelta(days=days),
        "reason": f"r{days}",
    }


def test_history_returns_bounded_chain_both_ways() -> None:
    a = node("A", "v1", valid_from=T0, valid_until=T0 + timedelta(days=1))
    b = node("B", "v2", valid_from=T0 + timedelta(days=1), valid_until=T0 + timedelta(days=2))
    c = node("C", "v3", valid_from=T0 + timedelta(days=2), valid_until=T0 + timedelta(days=3))
    d = node("D", "v4", valid_from=T0 + timedelta(days=3))
    script: List[Response] = [
        [row(c, supersedes=["B"], superseded_by=["D"])],
        [
            {"direction": "older", "nodes": [c, b], "links": [_history_link("B", "C", 2)]},
            {
                "direction": "older",
                "nodes": [c, b, a],
                "links": [_history_link("B", "C", 2), _history_link("A", "B", 1)],
            },
        ],
        [{"direction": "newer", "nodes": [c, d], "links": [_history_link("C", "D", 3)]}],
    ]
    driver = FakeDriver(script=list(script))
    history = run(make_store(driver).history("C", max_depth=2))
    assert [record.memory_id for record in history.records] == ["A", "B", "C", "D"]
    assert [(link.old_id, link.new_id) for link in history.links] == [
        ("A", "B"),
        ("B", "C"),
        ("C", "D"),
    ]
    by_id = {record.memory_id: record for record in history.records}
    assert by_id["B"].supersedes == ("A",) and by_id["B"].superseded_by == ("C",)
    assert history.truncated is False
    older, newer = driver.calls[1], driver.calls[2]
    assert older.query == store_module._HISTORY_OLDER and newer.query == store_module._HISTORY_NEWER
    assert older.parameters["max_depth"] == 2 and older.parameters["direction"] == "older"
    assert "*1..51]" in older.query and "length(path) <= $max_depth + 1" in older.query

    shallow = FakeDriver(script=list(script))
    clipped = run(make_store(shallow).history("C", max_depth=1))
    assert [record.memory_id for record in clipped.records] == ["B", "C", "D"]
    assert clipped.truncated is True

    with pytest.raises(Neo4jMemoryNotFoundError):
        run(make_store(FakeDriver(script=[[]])).history("missing"))
    bad = FakeDriver(script=[[row(c)], [{"direction": "older", "nodes": "oops", "links": []}], []])
    with pytest.raises(Neo4jIntegrationError, match="history path"):
        run(make_store(bad).history("C"))
    bad_link = FakeDriver(
        script=[[row(c)], [{"direction": "older", "nodes": [c], "links": ["x"]}], []]
    )
    with pytest.raises(Neo4jIntegrationError, match="supersession link"):
        run(make_store(bad_link).history("C"))
    missing_key = FakeDriver(
        script=[[row(c)], [{"direction": "older", "nodes": [c], "links": [{"old_id": "B"}]}], []]
    )
    with pytest.raises(Neo4jIntegrationError, match="KeyError"):
        run(make_store(missing_key).history("C"))


def test_history_marks_truncation_at_the_path_cap(monkeypatch: Any) -> None:
    monkeypatch.setattr(store_module, "_MAX_HISTORY_PATHS", 1)
    c = node("C")
    driver = FakeDriver(script=[[row(c)], [{"direction": "older", "nodes": [c], "links": []}], []])
    assert run(make_store(driver).history("C")).truncated is True


def test_conflicts_surface_overlapping_facts_on_a_subject() -> None:
    first = node("A", "Office is in Pune.", valid_until=NOW + timedelta(days=5))
    second = node("B", "Office is in Bengaluru.", valid_from=T0 + timedelta(days=10))
    same_text = node("C", "Office is in Pune.")
    expired = node("D", "Office is in Delhi.", valid_until=NOW)
    driver = FakeDriver(
        script=[
            [
                {"first": first, "second": second},
                {"first": first, "second": same_text},
                {"first": first, "second": expired},
                {"first": first, "second": node("E", "x", subject="other")},
            ]
        ]
    )
    found = run(make_store(driver).conflicts(SUBJECT, limit=5))
    call = driver.calls[0]
    assert call.query == store_module._CONFLICTS_SUBJECT
    assert call.parameters == {
        "tenant_id": TENANT,
        "namespace": "default",
        "as_of": NOW,
        "limit": 5,
        "subject": SUBJECT,
    }
    assert "a.content_sha256 <> b.content_sha256" in call.query
    assert "NOT EXISTS { MATCH (a)-[:SUPERSEDES]-(b) }" in call.query
    assert len(found) == 1
    conflict = found[0]
    assert (conflict.first.memory_id, conflict.second.memory_id) == ("A", "B")
    assert conflict.subject == SUBJECT
    assert conflict.overlap_from == T0 + timedelta(days=10)
    assert conflict.overlap_until == NOW + timedelta(days=5)

    open_ended = FakeDriver(script=[[{"first": node("A", "x"), "second": node("B", "y")}]])
    unbounded = run(make_store(open_ended).conflicts(as_of=NOW))
    assert open_ended.calls[0].query == store_module._CONFLICTS
    assert unbounded[0].overlap_until is None


def test_forget_soft_and_hard() -> None:
    driver = FakeDriver(script=[[{"changed": True}], [{"changed": False}], [], [{"deleted": 1}]])
    store = make_store(driver)
    assert run(store.forget("A")) is True
    assert run(store.forget("A", at=NOW + timedelta(hours=1))) is False
    assert run(store.forget("missing")) is False
    assert run(store.forget("A", hard=True)) is True
    soft = driver.calls[0]
    assert soft.query == store_module._FORGET_SOFT
    assert soft.parameters == {
        "tenant_id": TENANT,
        "namespace": "default",
        "memory_id": "A",
        "at": NOW,
    }
    assert "m.forgotten_at" in soft.query
    assert driver.calls[1].parameters["at"] == NOW + timedelta(hours=1)
    assert driver.calls[3].query == store_module._FORGET_HARD
    assert "DETACH DELETE m" in driver.calls[3].query


# --- isolation, injection, guard and errors -----------------------------------------------


def test_every_statement_is_static_scoped_and_free_of_caller_text() -> None:
    sentinel = "ZQXSENTINEL"
    tenant = sentinel + "-tenant"
    namespace = sentinel + "-ns"

    graph: Dict[str, Dict[str, Any]] = {
        f"{sentinel}-other": node(
            f"{sentinel}-other", f"{sentinel} other", tenant=tenant, namespace=namespace
        )
    }

    def responder(query: str, params: Dict[str, Any]) -> Response:
        if query == store_module._GET:
            found = graph.get(params["memory_id"])
            return [row(found)] if found else []
        if query == store_module._CREATE:
            created = node(
                params["memory_id"],
                params["content"],
                tenant=tenant,
                namespace=namespace,
                subject=params["subject"],
            )
            graph[params["memory_id"]] = created
            return [row(created)]
        if query == store_module._LINK:
            return [{"linked": 1}]
        if query == store_module._CYCLE_CHECK:
            return [{"cycle": False}]
        return []

    driver = FakeDriver(responder=responder)
    store = make_store(driver, tenant_id=tenant, namespace=namespace)

    async def exercise() -> None:
        await store.ensure_schema()
        await store.remember(
            f"{sentinel}-s",
            f"{sentinel} content') DETACH DELETE n //",
            memory_id=f"{sentinel}-id",
            source=f"{sentinel}-src",
            kind="fact",
            metadata={sentinel: sentinel},
        )
        await store.supersede(
            f"{sentinel}-id",
            MemoryDraft(f"{sentinel} new", memory_id=f"{sentinel}-new"),
            reason=f"{sentinel} reason",
        )
        await store.supersede(
            f"{sentinel}-id", f"{sentinel}-other", reason="r", allow_superseded=True
        )
        await store.recall(f"{sentinel}-s", query=f"{sentinel} query")
        await store.recall(query=f"{sentinel} query")
        await store.history(f"{sentinel}-id")
        await store.conflicts(f"{sentinel}-s")
        await store.conflicts()
        await store.forget(f"{sentinel}-id")
        await store.forget(f"{sentinel}-id", hard=True)
        await store.get(f"{sentinel}-id")
        await store.search(f"{sentinel}")
        await store.save(ContextItem(f"{sentinel}-item", f"{sentinel} item"))
        await store.delete(f"{sentinel}-item")

    run(exercise())
    assert len(driver.calls) > 20
    used = set(driver.queries())
    assert used <= ALL_STATEMENTS
    assert DATA_STATEMENTS <= used  # every data statement was exercised
    for call in driver.calls:
        assert sentinel not in call.query
        if call.query in DATA_STATEMENTS:
            assert call.parameters["tenant_id"] == tenant
            assert call.parameters["namespace"] == namespace
            assert "$tenant_id" in call.query and "$namespace" in call.query
    for statement in ALL_STATEMENTS:
        assert MEMORY_LABEL in statement
    assert all(
        SUPERSEDES_RELATIONSHIP in statement
        for statement in (store_module._LINK, store_module._CYCLE_CHECK)
    )


def test_guard_refuses_before_the_driver_is_called_and_counts_statements() -> None:
    driver = FakeDriver(script=[[], [row(node("m"))]])
    guard = UsageGuard(UsageLimits(requests_per_minute=None, max_requests=1, unit="queries"))
    store = make_store(driver, guard=guard)
    run(store.remember(SUBJECT, "The user prefers Hindi."))
    assert guard.snapshot()["units"] == 2  # duplicate check + create
    sessions = len(driver.sessions)
    with pytest.raises(UsageCapExceeded):
        run(store.recall())
    assert len(driver.sessions) == sessions and len(driver.calls) == 2

    ticks = iter([0.0, 1.0])
    rate_guard = UsageGuard(
        UsageLimits(requests_per_minute=1, max_requests=None), clock=lambda: next(ticks)
    )
    rate_driver = FakeDriver()
    rate_store = make_store(rate_driver, guard=rate_guard)
    run(rate_store.recall())
    with pytest.raises(RateLimitExceeded):
        run(rate_store.forget("A"))
    assert len(rate_driver.sessions) == 1

    unit_guard = UsageGuard(UsageLimits(requests_per_minute=None, max_requests=None, max_units=4))
    unit_driver = FakeDriver()
    with pytest.raises(UsageCapExceeded):
        run(make_store(unit_driver, guard=unit_guard).supersede("A", "B", reason="r"))
    assert unit_driver.sessions == []


def _neo4j_errors() -> List[Any]:
    exceptions = pytest.importorskip("neo4j.exceptions")
    return [
        (exceptions.AuthError, Neo4jAuthenticationError, "authentication"),
        (exceptions.TokenExpired, Neo4jAuthenticationError, "authentication"),
        (exceptions.Forbidden, Neo4jAuthenticationError, "authorization"),
        (exceptions.ServiceUnavailable, Neo4jUnavailableError, "unavailable"),
        (exceptions.SessionExpired, Neo4jUnavailableError, "unavailable"),
        (exceptions.DatabaseUnavailable, Neo4jUnavailableError, "unavailable"),
        (exceptions.IncompleteCommit, Neo4jUnavailableError, "may or may not"),
        (exceptions.ConstraintError, Neo4jConstraintError, "constraint"),
        (exceptions.TransientError, Neo4jTransientError, "not retried"),
        (exceptions.CypherSyntaxError, Neo4jIntegrationError, "CypherSyntaxError"),
    ]


def test_driver_exceptions_are_mapped_and_sanitized() -> None:
    secret = "neo4j+s://neo4j:hunter2@abc.databases.neo4j.io The user prefers Hindi."
    for raw, mapped, message in _neo4j_errors():
        for where in ("run", "session", "begin", "commit"):
            driver = FakeDriver()
            failure = raw(secret)
            if where == "run":
                driver.script = [failure]
            elif where == "session":
                driver.session_error = failure
            elif where == "begin":
                driver.begin_error = failure
            else:
                driver.commit_error = failure
            with pytest.raises(mapped, match=message) as captured:
                run(make_store(driver).forget("A"))
            assert type(captured.value) is mapped
            assert "hunter2" not in str(captured.value) and "Hindi" not in str(captured.value)
            assert captured.value.__cause__ is None and captured.value.__suppress_context__
            if where in ("run", "commit"):
                assert driver.commits == 0 and driver.rollbacks == 1
            assert len(driver.calls) <= 1  # a failed write is never retried


def test_unknown_driver_errors_and_name_based_mapping() -> None:
    class AuthError(Exception):
        pass

    class ConnectionAcquisitionTimeoutError(Exception):
        pass

    for raw, mapped in (
        (RuntimeError("hunter2"), Neo4jIntegrationError),
        (AuthError("hunter2"), Neo4jAuthenticationError),
        (ConnectionAcquisitionTimeoutError("hunter2"), Neo4jUnavailableError),
    ):
        driver = FakeDriver(script=[raw])
        with pytest.raises(mapped) as captured:
            run(make_store(driver).recall())
        assert type(captured.value) is mapped
        assert "hunter2" not in str(captured.value)


def test_malformed_records_raise_sanitized_errors() -> None:
    cases: List[Any] = [
        [{"memory": "not-a-map"}],
        [row({**node("m"), "valid_from": datetime(2026, 1, 1)})],
        [row({**node("m"), "created_at": None})],
        [row({key: value for key, value in node("m").items() if key != "content"})],
        [row({**node("m"), "valid_until": "not a date"})],
    ]
    for rows in cases:
        with pytest.raises(Neo4jIntegrationError, match="malformed"):
            run(make_store(FakeDriver(script=[rows])).recall())


def test_stored_temporal_values_from_the_driver_are_normalized() -> None:
    class DriverDateTime:
        def __init__(self, value: datetime) -> None:
            self.value = value

        def to_native(self) -> datetime:
            return self.value

    stored = node(
        "m",
        valid_from=DriverDateTime(T0),
        created_at="2026-01-01T00:00:00Z",
        valid_until=DriverDateTime(
            datetime(2026, 6, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        ),
        metadata_json='["not-a-dict"]',
    )
    driver = FakeDriver(script=[[row(stored)]])
    item = run(make_store(driver).recall())[0]
    assert item.metadata["valid_from"] == T0.isoformat()
    assert item.metadata["created_at"] == T0.isoformat()
    assert item.metadata["valid_until"] == datetime(2026, 6, 1, tzinfo=UTC).isoformat()
    assert item.metadata["attributes"] == {}


def test_memory_records_and_drafts_are_frozen_audit_values() -> None:
    record = MemoryRecord(
        "m", SUBJECT, "c", sha("c"), "fact", "caller", T0, T0, metadata={"a": [1]}, supersedes=["x"]
    )
    assert record.supersedes == ("x",)
    with pytest.raises(TypeError):
        record.metadata["a"] = 2  # type: ignore[index]
    exported = record.to_dict()
    exported["metadata"]["a"].append(2)
    assert record.metadata["a"] == [1]
    assert exported["valid_until"] is None and exported["supersedes"] == ["x"]
    draft = MemoryDraft("c", metadata={"k": "v"})
    with pytest.raises(TypeError):
        draft.metadata["k"] = "w"  # type: ignore[index]
    assert isinstance(store_module.Neo4jContextStore.source_id, str)
    assert isinstance(repr(make_store(FakeDriver())), str)


def test_mapping_type_alias_is_respected_for_metadata() -> None:
    proxy: Mapping[str, Any] = MemoryDraft(
        "c", metadata={"api_key": "sk-123", "x": (1, 2)}
    ).metadata
    encoded = store_module._metadata_json(proxy)
    assert "sk-123" not in encoded and '"x":[1,2]' in encoded
    assert store_module._metadata_json(None) == "{}"
