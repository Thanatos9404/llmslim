"""Neo4j temporal memory store tests against a recording fake async driver (no network)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import pytest

import llmslim.integrations.neo4j as store_module
from llmslim import AdaptiveContextPlanner, ContextItem, ContextKind, ContextRole
from llmslim.context import ContextSource, ContextStore, InMemoryContextSource
from llmslim.integrations._guard import (
    RateLimitExceeded,
    UsageCapExceeded,
    UsageGuard,
    UsageLimits,
)
from llmslim.integrations.mongodb import MongoDBContextStore
from llmslim.integrations.neo4j import (
    DEFAULT_USAGE_LIMITS,
    ITEM_ID_PREFIX,
    MEMORY_LABEL,
    SUPERSEDES_RELATIONSHIP,
    MemoryDraft,
    MemoryRecord,
    Neo4jAuthenticationError,
    Neo4jConstraintError,
    Neo4jContextStore,
    Neo4jIntegrationError,
    Neo4jIntervalError,
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
    store_module._ARCHIVE,
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
    subject: Optional[str] = SUBJECT,
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


def mid(item: ContextItem) -> str:
    """The bare memory ID behind a planner item ID."""

    return str(item.metadata["memory_id"])


def scope_hash(tenant: str = TENANT, namespace: str = "default") -> str:
    return hashlib.sha256(f"{tenant}\x00{namespace}".encode("utf-8")).hexdigest()[:12]


def item_id(memory_id: str, tenant: str = TENANT, namespace: str = "default") -> str:
    return f"{ITEM_ID_PREFIX}:{scope_hash(tenant, namespace)}:{memory_id}"


class Clock:
    """A settable clock for the store."""

    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now = self.now + timedelta(**delta)


class ConstraintError(Exception):
    """Named like the driver's error so the store maps it to Neo4jConstraintError."""


class FakeGraph:
    """In-memory emulation of the store's Cypher statements, for behavioural tests.

    It mirrors each statement's semantics in Python (scope, half-open validity, term
    scoring, renaming, links), so tests can check what the store does end to end.
    """

    def __init__(self) -> None:
        self.nodes: Dict[int, Dict[str, Any]] = {}
        self.links: Dict[Tuple[int, int], Dict[str, Any]] = {}  # (newer, older) -> {at, reason}
        self._next = 0

    def driver(self) -> FakeDriver:
        return FakeDriver(responder=self.respond)

    def ids(self) -> List[str]:
        return sorted(props["memory_id"] for props in self.nodes.values())

    def _scoped(self, params: Mapping[str, Any]) -> List[Tuple[int, Dict[str, Any]]]:
        scope = (params["tenant_id"], params["namespace"])
        return [
            (nid, props)
            for nid, props in self.nodes.items()
            if (props["tenant_id"], props["namespace"]) == scope
        ]

    def _find(self, params: Mapping[str, Any], memory_id: str) -> Optional[int]:
        for nid, props in self._scoped(params):
            if props["memory_id"] == memory_id:
                return nid
        return None

    def _row(self, nid: int) -> Dict[str, Any]:
        older = [self.nodes[o]["memory_id"] for (n, o) in self.links if n == nid]
        newer = [self.nodes[n]["memory_id"] for (n, o) in self.links if o == nid]
        return row(dict(self.nodes[nid]), older, newer)

    @staticmethod
    def _valid(props: Mapping[str, Any], instant: datetime) -> bool:
        end = props.get("valid_until")
        return bool(props["valid_from"] <= instant and (end is None or end > instant))

    def _paths(self, start: int, direction: str, max_links: int) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []

        def walk(path: List[int], links: List[Dict[str, Any]]) -> None:
            for (newer, older), props in self.links.items():
                if direction == "older" and newer == path[-1]:
                    step = older
                elif direction == "newer" and older == path[-1]:
                    step = newer
                else:
                    continue
                if step in path:
                    continue
                link = {
                    "old_id": self.nodes[older]["memory_id"],
                    "new_id": self.nodes[newer]["memory_id"],
                    **props,
                }
                found.append(
                    {
                        "direction": direction,
                        "nodes": [dict(self.nodes[n]) for n in path + [step]],
                        "links": links + [link],
                    }
                )
                if len(links) + 1 < max_links:
                    walk(path + [step], links + [link])

        walk([start], [])
        return found

    def respond(self, query: str, params: Dict[str, Any]) -> Response:
        scoped = self._scoped(params)
        if query == store_module._GET:
            nid = self._find(params, params["memory_id"])
            return [] if nid is None else [self._row(nid)]
        if query == store_module._CREATE:
            if self._find(params, params["memory_id"]) is not None:
                return ConstraintError("duplicate memory_id")
            self._next += 1
            self.nodes[self._next] = {k: v for k, v in params.items() if v is not None}
            return [self._row(self._next)]
        if query == store_module._ARCHIVE:
            nid = self._find(params, params["memory_id"])
            if nid is None or self.nodes[nid]["content_sha256"] != params["content_sha256"]:
                return [{"archived": 0}]
            self.nodes[nid].update(
                memory_id=params["archived_id"], archived_from=params["memory_id"]
            )
            return [{"archived": 1}]
        if query == store_module._LINK:
            old = self._find(params, params["old_id"])
            new = self._find(params, params["new_id"])
            if old is None or new is None:
                return []
            prior = self.nodes[old]
            if prior.get("valid_until") is None or prior["valid_until"] > params["at"]:
                prior["valid_until"] = params["at"]
            self.links.setdefault((new, old), {"at": params["at"], "reason": params["reason"]})
            return [{"linked": 1}]
        if query == store_module._CYCLE_CHECK:
            old = self._find(params, params["old_id"])
            assert old is not None
            reachable = {path["nodes"][-1]["memory_id"] for path in self._paths(old, "older", 99)}
            return [{"cycle": params["new_id"] in reachable}]
        if query == store_module._FIND_CURRENT_DUPLICATE:
            matches = sorted(
                (-props["valid_from"].timestamp(), props["memory_id"], nid)
                for nid, props in scoped
                if props.get("subject") == params["subject"]
                and props["content_sha256"] == params["content_sha256"]
                and self._valid(props, params["valid_from"])
            )
            return [self._row(matches[0][2])] if matches else []
        if query == store_module._FORGET_SOFT:
            nid = self._find(params, params["memory_id"])
            if nid is None:
                return []
            props = self.nodes[nid]
            started = props["valid_from"] <= params["at"]
            end = props.get("valid_until")
            changed = started and (end is None or end > params["at"])
            if changed:
                props.update(valid_until=params["at"], forgotten_at=params["at"])
            return [{"changed": changed, "started": started}]
        if query == store_module._FORGET_HARD:
            doomed = {
                nid
                for nid, props in scoped
                if params["memory_id"] in (props["memory_id"], props.get("archived_from"))
            }
            for nid in doomed:
                del self.nodes[nid]
            self.links = {
                pair: props for pair, props in self.links.items() if not set(pair) & doomed
            }
            return [{"deleted": len(doomed)}]
        if query in (store_module._RECALL, store_module._RECALL_SUBJECT):
            ranked = []
            for nid, props in scoped:
                if query == store_module._RECALL_SUBJECT and (
                    props.get("subject") != params["subject"]
                ):
                    continue
                if not self._valid(props, params["as_of"]):
                    continue
                haystack = props["content"].lower() + " " + (props.get("subject") or "").lower()
                score = sum(t["weight"] for t in params["terms"] if t["text"] in haystack)
                if params["terms"] and score <= 0:
                    continue
                ranked.append((-score, -props["valid_from"].timestamp(), props["memory_id"], nid))
            ranked.sort()
            return [self._row(entry[3]) for entry in ranked[: params["candidate_limit"]]]
        if query in (store_module._CONFLICTS, store_module._CONFLICTS_SUBJECT):
            anchors = sorted(
                (props["subject"], props["memory_id"], nid)
                for nid, props in scoped
                if props.get("subject") is not None
                and (query == store_module._CONFLICTS or props["subject"] == params["subject"])
                and self._valid(props, params["as_of"])
            )[: params["candidate_limit"]]
            groups: Dict[str, List[int]] = {}
            for subject, _, nid in anchors:
                groups.setdefault(subject, []).append(nid)
            pairs = []
            for subject, members in groups.items():
                for index, a in enumerate(members):
                    for b in members[index + 1 :]:
                        if self.nodes[a]["content_sha256"] == self.nodes[b]["content_sha256"]:
                            continue
                        if (a, b) in self.links or (b, a) in self.links:
                            continue
                        first, second = self.nodes[a]["memory_id"], self.nodes[b]["memory_id"]
                        pairs.append((subject, first, second, a, b))
            pairs.sort()
            return [
                {"first": dict(self.nodes[a]), "second": dict(self.nodes[b])}
                for *_, a, b in pairs[: params["limit"]]
            ]
        if query in (store_module._HISTORY_OLDER, store_module._HISTORY_NEWER):
            nid = self._find(params, params["memory_id"])
            assert nid is not None
            return self._paths(nid, params["direction"], params["max_depth"] + 1)
        raise AssertionError(f"FakeGraph does not emulate: {query[:60]}")


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
        None,
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
    assert queries[:5] == queries[5:] == list(store_module._SCHEMA_STATEMENTS)
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
    assert any("m.archived_from" in query for query in queries)
    assert driver.commits == 10 and len(driver.sessions) == 10  # one transaction per statement


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
        (store.get(""), "item_id"),
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
    assert [mid(item) for item in items] == ["starts-at", "spans"]
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
    by_id = {mid(item): item for item in items}
    assert [mid(item) for item in items] == ["lang-new", "lang-other", "tz"]
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
    assert call.parameters["terms"] == [
        {"text": "preferred", "weight": 9},
        {"text": "language", "weight": 8},
    ]
    assert call.parameters["candidate_limit"] == 4
    assert [mid(item) for item in items] == ["b"]

    single = FakeDriver()
    run(make_store(single).recall(query="a"))
    assert single.calls[0].parameters["terms"] == [{"text": "a", "weight": 1}]
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
    driver = FakeDriver(script=[[], [row(saved)]])
    store = make_store(driver)
    item = ContextItem(
        "item-1",
        "Saved fact.",
        kind=ContextKind.MEMORY,
        source="approved",
        metadata={"subject": "account:9", "owner": "u7"},
    )
    assert run(store.save(item, "agent-1")) is None
    assert driver.queries() == [store_module._GET, store_module._CREATE]
    create = driver.calls[-1]
    assert create.parameters["subject"] == "account:9"
    assert create.parameters["namespace"] == "agent-1"
    assert create.parameters["memory_id"] == "item-1"
    assert create.parameters["metadata_json"] == '{"owner":"u7"}'
    assert create.parameters["valid_from"] == NOW and create.parameters["valid_until"] is None

    # Without metadata["subject"] the memory is subject-less, never filed under a catch-all.
    subjectless = FakeDriver(script=[[], [row(node("i2", "x", subject=None))]])
    run(make_store(subjectless).save(ContextItem("i2", "x", metadata={"subject": "  "})))
    assert subjectless.calls[-1].parameters["subject"] is None
    with pytest.raises(TypeError, match="ContextItem"):
        run(make_store(FakeDriver()).save({"id": "x"}))  # type: ignore[arg-type]

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
    assert fetched.item_id == item_id("item-1") and mid(fetched) == "item-1"
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
        "candidate_limit": 1_000,
        "subject": SUBJECT,
    }
    assert "LIMIT $candidate_limit" in call.query
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
    assert "DETACH DELETE n" in driver.calls[3].query
    assert "archived_from: $memory_id" in driver.calls[3].query


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
        if query == store_module._ARCHIVE:
            archived = {**graph.pop(params["memory_id"]), "memory_id": params["archived_id"]}
            graph[params["archived_id"]] = archived
            return [{"archived": 1}]
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
        await store.save(ContextItem(f"{sentinel}-item", f"{sentinel} item v2"))
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


# --- Indic and mixed-script recall --------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # Matras and viramas stay inside the word. "की" (consonant + vowel sign) has two
        # letters, like Hinglish "ki", so it is a term.
        ("किताब की कीमत", [("किताब", 5), ("की", 2), ("कीमत", 4)]),
        ("नमस्ते दुनिया", [("नमस्ते", 5), ("दुनिया", 6)]),
        ("தமிழ் நாடு", [("தமிழ்", 4), ("நாடு", 4)]),
        ("আমার সোনার বাংলা", [("আমার", 4), ("সোনার", 5), ("বাংলা", 5)]),
        ("ଓଡ଼ିଆ ଭାଷା", [("ଓଡ଼ିଆ", 4), ("ଭାଷା", 4)]),
        (
            "Kitaab KI keemat 2 din mein",
            [("kitaab", 6), ("ki", 2), ("keemat", 6), ("din", 3), ("mein", 4)],
        ),
        ("मेरा phone नंबर 98765", [("मेरा", 4), ("phone", 5), ("नंबर", 4), ("98765", 5)]),
        ("5G plan ₹499 का", [("5g", 2), ("plan", 4), ("499", 3), ("का", 2)]),
        ("COVID-19 टीका २०२४", [("covid", 5), ("19", 2), ("टीका", 4), ("२०२४", 4)]),
        ("Preferred LANGUAGE?", [("preferred", 9), ("language", 8)]),
        ("user_name a", [("user", 4), ("name", 4)]),
        # One-letter words are dropped unless nothing else is left; then the whole query is
        # the term.
        ("a", [("a", 1)]),
        ("क", [("क", 1)]),
        ("C++", [("c++", 1)]),
    ],
)
def test_query_terms_keep_whole_words_in_every_script(
    query: str, expected: List[Tuple[str, int]]
) -> None:
    assert list(store_module._query_terms(query)) == expected


def test_query_terms_never_split_inside_a_syllable() -> None:
    # The fragments the old [^\W_]+ tokenizer produced for these queries.
    for query, fragment in (
        ("किताब की कीमत", "मत"),
        ("नमस्ते दुनिया", "नमस"),
        ("தமிழ் நாடு", "தம"),
    ):
        terms = [term for term, _ in store_module._query_terms(query)]
        assert fragment not in terms
        assert all(unicodedata.category(term[0])[0] != "M" for term in terms)
    # ZWJ/ZWNJ inside a word are part of its spelling; at the edges they are dropped.
    assert store_module._words("क्‍ष ‌नाम‌") == ["क्‍ष", "नाम"]
    assert store_module._letter_count("क्") == 1 and store_module._letter_count("की") == 2


def test_query_terms_keep_the_longest_terms_when_capped() -> None:
    query = " ".join(["ab"] + [f"word{index:02d}" for index in range(20)] + ["xy"])
    terms = store_module._query_terms(query)
    assert len(terms) == store_module.MAX_QUERY_TERMS
    assert "ab" not in dict(terms) and "xy" not in dict(terms)
    assert [term for term, _ in terms] == [f"word{index:02d}" for index in range(16)]


def test_indic_recall_finds_relevant_memories_and_skips_fragment_matches() -> None:
    graph = FakeGraph()
    clock = Clock(T0)
    driver = graph.driver()
    store = make_store(driver, clock=clock)

    def remember(memory_id: str, content: str) -> None:
        clock.advance(hours=1)
        run(store.remember("notes", content, memory_id=memory_id))

    remember("price", "इस किताब की कीमत 500 रुपये है")
    remember("cost", "किताब का दाम कम हुआ")
    remember("vote", "आज मतदान हुआ")  # shares only the old fragment "मत"
    remember("greet", "नमस्ते दुनिया, आज छुट्टी है")
    remember("namaskar", "नमस्कार मित्र")  # shares only the old fragment "नमस"
    remember("tn", "தமிழ் நாடு அரசு அறிவிப்பு")
    remember("tamanna", "தமன்னா புதிய படம்")  # shares only the old fragment "தம"
    remember("bn", "আমার সোনার বাংলা গান")
    remember("or", "ଓଡ଼ିଆ ଭାଷା ଦିବସ ପାଳନ")
    remember("hinglish", "Kitaab ki keemat 500 rupaye hai")
    remember("plan5g", "5G plan ₹499 का है")
    remember("plan4g", "4G plan ₹299 का है")
    for index in range(10):  # newer memories that share only the function word "की"
        remember(f"filler-{index}", f"रमेश की कार नंबर {index}")

    def ids(query: str, limit: int = 20) -> List[str]:
        return [mid(item) for item in run(store.recall(query=query, limit=limit))]

    hindi = ids("किताब की कीमत")
    assert hindi[:2] == ["price", "cost"] and "vote" not in hindi
    assert set(hindi[2:]) == {f"filler-{index}" for index in range(10)}
    sent = driver.calls[-1].parameters["terms"]
    assert [term["text"] for term in sent] == ["किताब", "की", "कीमत"]
    # Candidates are ranked by matched letters before the cap, so ten newer memories that
    # match only "की" cannot crowd out the two relevant ones.
    assert ids("किताब की कीमत", limit=2) == ["price", "cost"]
    assert driver.calls[-1].parameters["candidate_limit"] == 8
    assert ids("नमस्ते दुनिया") == ["greet"]
    assert ids("தமிழ் நாடு") == ["tn"]
    assert ids("সোনার বাংলা") == ["bn"]
    assert ids("ଓଡ଼ିଆ ଭାଷା") == ["or"]
    assert ids("kitaab KI keemat") == ["hinglish"]
    assert ids("₹499 वाला 5G plan") == ["plan5g", "plan4g"]


def test_stored_text_and_queries_are_nfc_normalized_consistently() -> None:
    graph = FakeGraph()
    store = make_store(graph.driver())
    # U+0958 (qa) and U+0B5C (rra) are composition exclusions: NFC spells them base + nukta.
    precomposed_hindi = "क़ीमत"
    decomposed_hindi = "क़ीमत"
    precomposed_odia = "ଓଡ଼ିଆ"
    decomposed_odia = "ଓଡ଼ିଆ"
    hindi = run(store.remember("shop:tea", f"चाय की {precomposed_hindi} 20 रुपये"))
    odia = run(store.remember("states:odisha", f"{precomposed_odia} ଭାଷା ଦିବସ"))
    assert hindi.content == f"चाय की {decomposed_hindi} 20 रुपये"
    assert odia.content == f"{decomposed_odia} ଭାଷା ଦିବସ"
    assert [mid(i) for i in run(store.recall(query=decomposed_hindi))] == [hindi.memory_id]
    assert [mid(i) for i in run(store.recall(query=precomposed_hindi))] == [hindi.memory_id]
    assert [mid(i) for i in run(store.recall(query=decomposed_odia))] == [odia.memory_id]
    # Subjects are normalized too, so an NFD subject is found by its NFC spelling.
    cafe = run(store.remember("café:menu", "Serves filter coffee."))
    assert cafe.subject == "café:menu"
    assert [mid(i) for i in run(store.recall("café:menu"))] == [cafe.memory_id]


# --- item IDs -----------------------------------------------------------------------------


def test_item_ids_are_namespaced_and_accepted_in_both_forms() -> None:
    graph = FakeGraph()
    store = make_store(graph.driver())
    run(store.remember(SUBJECT, "The user prefers Hindi.", memory_id="lang"))
    run(store.remember(SUBJECT, "The user prefers Tamil.", memory_id="lang", namespace="agent-2"))
    default_item = run(store.get("lang"))
    other_item = run(store.get("lang", "agent-2"))
    assert default_item.item_id == item_id("lang")
    assert other_item.item_id == item_id("lang", namespace="agent-2")
    assert default_item.item_id != other_item.item_id
    assert re.fullmatch(r"neo4j-memory:[0-9a-f]{12}:lang", default_item.item_id)
    assert TENANT not in default_item.item_id  # the tenant is hashed, never shown
    assert mid(default_item) == "lang"
    # The item ID and the bare ID name the same memory everywhere.
    assert run(store.get(default_item.item_id)).content == "The user prefers Hindi."
    assert run(store.history(default_item.item_id)).memory_id == "lang"
    assert run(store.recall())[0].item_id == default_item.item_id
    # The namespace argument picks the partition; the hash only keeps planner IDs unique.
    assert run(store.get(default_item.item_id, "agent-2")).content == "The user prefers Tamil."
    assert run(store.forget(default_item.item_id)) is True
    assert run(store.delete(other_item.item_id, "agent-2")) is True
    for bad in (
        "neo4j-memory:xyz:lang",
        "neo4j-memory:0123456789AB:lang",
        "neo4j-memory:0123456789ab:",
        "neo4j-memory:0123456789ab:neo4j-memory:0123456789ab:lang",
    ):
        with pytest.raises(ValueError, match="item_id"):
            run(store.get(bad))


def test_memory_ids_are_validated_strictly_so_rendering_cannot_break() -> None:
    driver = FakeDriver()
    store = make_store(driver)
    for bad in (
        'a"b',
        "a'b",
        "a<b",
        "a>b",
        "a&b",
        "a b",
        "a\tb",
        "a b",
        "a​b",
        "a‮b",
        "a`b",
        "a\\b",
        "a~b",
        "a~0123456789abcdef",
        "x" * 201,
    ):
        with pytest.raises(ValueError, match="memory_id"):
            run(store.remember(SUBJECT, "Fact", memory_id=bad))
        if "~0" not in bad:  # an archived version's ID is a valid lookup / save key
            with pytest.raises(ValueError, match="item_id"):
                run(store.save(ContextItem(bad, "Fact")))
            with pytest.raises(ValueError, match="item_id"):
                run(store.delete(bad))
    with pytest.raises(ValueError, match="'~'"):
        run(store.supersede("a", MemoryDraft("x", memory_id="b~0123456789abcdef"), reason="r"))
    assert driver.calls == []
    for good in (
        "mem-1",
        "user:42/lang",
        "doc_7.v2",
        "a@b+c#d=e",
        "किताब-१",
        "தமிழ்_1",
        "(x)[y]{z}",
    ):
        assert store_module._memory_ref(good, "memory_id", mode="new") == good
    # Archived versions can be looked up; save() maps them to the ID they were saved under.
    assert store_module._memory_ref("doc~0123456789abcdef", "memory_id") == "doc~0123456789abcdef"
    assert store_module._memory_ref("doc~0123456789abcdef", "item_id", mode="item") == "doc"


def test_rendered_memory_ids_keep_the_provenance_header_intact() -> None:
    graph = FakeGraph()
    store = make_store(graph.driver())
    run(store.remember(SUBJECT, "The user prefers concise answers.", memory_id="pref:{style}/v1"))
    plan = run(
        AdaptiveContextPlanner().aplan(
            context_sources=[store],
            query="concise answers",
            model="generic-128k",
            max_input_tokens=1024,
        )
    )
    headers = re.findall(r'<llmslim_context id="([^"]*)" kind="memory"', plan.final_context)
    assert headers == [item_id("pref:{style}/v1")]


def test_planning_mixes_neo4j_items_with_sources_that_share_raw_ids() -> None:
    graph = FakeGraph()
    store = make_store(graph.driver())
    second = make_store(graph.driver(), namespace="agent-2")
    local = ContextItem("release", "Local note: the release ships on Friday.")
    # save() reuses the other source's ID; two namespaces hold the same raw ID too.
    run(store.save(local))
    run(second.save(replace(local, content="Agent two: the release ships on Friday after QA.")))
    plan = run(
        AdaptiveContextPlanner().aplan(
            context_sources=[InMemoryContextSource([local]), store, second],
            query="When does the release ship?",
            model="generic-128k",
            max_input_tokens=2048,
        )
    )
    ids = [decision.item.item_id for decision in plan.decisions]
    assert {"release", item_id("release"), item_id("release", namespace="agent-2")} <= set(ids)
    assert len(ids) == len(set(ids))
    assert "Agent two: the release ships" in plan.final_context
    assert "Local note: the release ships" in plan.final_context


# --- ContextStore compatibility -----------------------------------------------------------


class _MongoCursor:
    def __init__(self, documents: List[Dict[str, Any]]) -> None:
        self.documents = documents

    def limit(self, count: int) -> "_MongoCursor":
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length: int) -> List[Dict[str, Any]]:
        return self.documents[:length]


class _MongoCollection:
    def __init__(self) -> None:
        self.documents: Dict[str, Dict[str, Any]] = {}

    async def replace_one(
        self, query: Mapping[str, Any], document: Mapping[str, Any], upsert: bool
    ) -> None:
        assert upsert and query["_id"] == document["_id"]
        self.documents[str(document["_id"])] = dict(document)

    async def find_one(self, query: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        return self.documents.get(str(query["_id"]))

    def find(self, query: Mapping[str, Any], **_: Any) -> _MongoCursor:
        pattern = re.compile(query["content"]["$regex"], re.IGNORECASE)
        return _MongoCursor(
            [
                document
                for document in self.documents.values()
                if document["namespace"] == query["namespace"]
                and pattern.search(document["content"])
            ]
        )

    async def delete_one(self, query: Mapping[str, Any]) -> Any:
        existed = self.documents.pop(str(query["_id"]), None) is not None
        return SimpleNamespace(deleted_count=int(existed))


def test_save_matches_mongodb_upsert_semantics() -> None:
    first = ContextItem("doc-1", "Acme renewal is in negotiation.", metadata={"owner": "u7"})
    second = replace(first, content="Acme renewal signed for two years.")
    clock = Clock(T0)

    async def scenario(store: Any) -> List[Any]:
        seen: List[Any] = []
        await store.save(first)
        seen.append((await store.get("doc-1")).content)
        await store.save(first)
        seen.append((await store.get("doc-1")).content)
        clock.advance(days=1)
        await store.save(second)
        seen.append((await store.get("doc-1")).content)
        found = await store.search("Acme renewal")
        seen.append([item.metadata.get("memory_id", item.item_id) for item in found])
        seen.append([item.content for item in found])
        seen.append(await store.delete("doc-1"))
        seen.append(await store.get("doc-1"))
        seen.append(await store.delete("doc-1"))
        return seen

    # client[database][collection] is all MongoDBContextStore needs from a client.
    mongo = MongoDBContextStore(client={"llmslim": {"context_items": _MongoCollection()}})
    graph = FakeGraph()
    neo4j = make_store(graph.driver(), clock=clock)
    assert run(scenario(neo4j)) == run(scenario(mongo))
    assert graph.nodes == {}  # delete() erased the archived version too


def test_save_supersedes_changed_content_and_keeps_every_version_auditable() -> None:
    graph = FakeGraph()
    clock = Clock(T0)
    driver = graph.driver()
    store = make_store(driver, clock=clock)
    first = ContextItem(
        "doc-1",
        "Acme renewal is in negotiation.",
        source="crm-sync",
        metadata={"subject": "customer:acme/renewal", "owner": "u7"},
    )
    run(store.save(first))
    saved = run(store.get("doc-1"))
    assert saved.item_id == item_id("doc-1") and saved.content == first.content
    assert saved.metadata["subject"] == "customer:acme/renewal"
    assert saved.metadata["attributes"] == {"owner": "u7"}
    assert saved.metadata["memory_source"] == "crm-sync"
    # Saving the same item again, or the item get() returned, writes nothing.
    before = len(driver.calls)
    run(store.save(first))
    run(store.save(saved))
    assert driver.queries()[before:] == [store_module._GET, store_module._GET]

    clock.advance(days=1)
    signed = "Acme renewal signed for two years."
    run(store.save(replace(first, content=signed)))
    assert driver.queries()[-4:] == [
        store_module._GET,
        store_module._ARCHIVE,
        store_module._CREATE,
        store_module._LINK,
    ]
    current = run(store.get("doc-1"))
    assert current.content == signed
    (archived_id,) = current.metadata["supersedes"]
    assert re.fullmatch(r"doc-1~[0-9a-f]{16}", archived_id)
    old = run(store.get(archived_id))
    assert old.content == first.content and old.metadata["replaced_by"] == ["doc-1"]
    assert old.metadata["valid_from"] == T0.isoformat()
    assert old.metadata["valid_until"] == (T0 + timedelta(days=1)).isoformat()
    assert [mid(item) for item in run(store.search("Acme renewal"))] == ["doc-1"]
    earlier = run(store.recall(query="Acme", as_of=T0 + timedelta(hours=1)))
    assert [mid(item) for item in earlier] == [archived_id]
    history = run(store.history("doc-1"))
    assert [record.content for record in history.records] == [first.content, signed]
    assert [(link.old_id, link.new_id, link.reason) for link in history.links] == [
        (archived_id, "doc-1", "replaced by ContextStore.save()")
    ]

    # Attribute-only changes are versioned too.
    clock.advance(days=1)
    run(store.save(replace(first, content=signed, metadata={**first.metadata, "owner": "u8"})))
    assert run(store.get("doc-1")).metadata["attributes"] == {"owner": "u8"}
    assert len(run(store.history("doc-1")).records) == 3
    # An archived version's item saves to the ID it was archived from.
    clock.advance(days=1)
    run(store.save(replace(old, content="Acme renewal reopened.")))
    reopened = run(store.get("doc-1"))
    assert reopened.content == "Acme renewal reopened."
    assert reopened.metadata["attributes"] == {"owner": "u7"}
    assert reopened.metadata["memory_source"] == "crm-sync"

    # delete() erases the item and every version archived under it.
    assert run(store.delete(current.item_id)) is True
    assert graph.nodes == {} and graph.links == {}
    assert run(store.get("doc-1")) is None and run(store.delete("doc-1")) is False


def test_save_stores_content_verbatim_apart_from_nfc() -> None:
    graph = FakeGraph()
    store = make_store(graph.driver(), max_content_chars=60)
    page = "  Page one\fPage two\n\tindented  "
    run(store.save(ContextItem("page", page)))
    assert run(store.get("page")).content == page  # not trimmed; form feed kept
    run(store.save(ContextItem("menu", "café menu")))
    assert run(store.get("menu")).content == "café menu"
    for content, message in (
        ("   ", "must not be empty"),
        ("x" * 61, "max_content_chars"),
        ("a\x00b", "control characters"),
        ("a\x1bb", "control characters"),
    ):
        with pytest.raises(ValueError, match=message):
            run(store.save(ContextItem("bad", content)))
    # remember() still trims, and accepts form feeds as well.
    assert run(store.remember(SUBJECT, "  Line one\fLine two  ")).content == "Line one\fLine two"


def test_save_revives_an_ended_memory_as_a_new_version() -> None:
    graph = FakeGraph()
    clock = Clock(T0)
    store = make_store(graph.driver(), clock=clock)
    item = ContextItem("pref", "Prefers email.", metadata={"subject": "user:7/channel"})
    run(store.save(item))
    clock.advance(days=1)
    assert run(store.forget("pref")) is True
    assert run(store.recall()) == ()
    clock.advance(days=1)
    run(store.save(item))  # same content, but no longer current: stored as a new version
    current = run(store.get("pref"))
    assert current.metadata["valid_until"] is None and "forgotten_at" not in current.metadata
    (archived,) = current.metadata["supersedes"]
    forgotten = run(store.get(archived))
    assert forgotten.metadata["forgotten_at"] == (T0 + timedelta(days=1)).isoformat()
    assert [mid(entry) for entry in run(store.recall())] == ["pref"]


def test_save_refuses_a_future_memory_and_detects_concurrent_writers() -> None:
    graph = FakeGraph()
    driver = graph.driver()
    store = make_store(driver)
    later = NOW + timedelta(days=7)
    run(store.remember(SUBJECT, "Starts next week.", memory_id="later", valid_from=later))
    with pytest.raises(Neo4jIntervalError, match="supersede"):
        run(store.save(ContextItem("later", "Changed.", metadata={"subject": SUBJECT})))
    assert graph.ids() == ["later"] and driver.rollbacks == 1

    # Another writer replaced the version between this transaction's read and its rename.
    raced = FakeDriver(script=[[row(node("doc", "v1", subject=None))], [{"archived": 0}]])
    with pytest.raises(Neo4jConstraintError, match="retry"):
        run(make_store(raced).save(ContextItem("doc", "v2")))
    assert raced.queries() == [store_module._GET, store_module._ARCHIVE]
    assert raced.commits == 0 and raced.rollbacks == 1
    vanished = FakeDriver(
        script=[
            [row(node("doc", "v1", subject=None))],
            [{"archived": 1}],
            [row(node("doc", "v2", subject=None))],
            [],
        ]
    )
    with pytest.raises(Neo4jMemoryNotFoundError, match="changed"):
        run(make_store(vanished).save(ContextItem("doc", "v2")))
    assert vanished.commits == 0
    # Two writers creating one ID at once: the identity constraint refuses the second.
    run(store.save(ContextItem("dup", "x")))

    def stale_read(query: str, params: Dict[str, Any]) -> Response:
        return [] if query == store_module._GET else graph.respond(query, params)

    with pytest.raises(Neo4jConstraintError, match="constraint"):
        run(make_store(FakeDriver(responder=stale_read)).save(ContextItem("dup", "y")))


def test_subjectless_items_never_conflict_and_conflicts_need_a_subject() -> None:
    graph = FakeGraph()
    store = make_store(graph.driver())
    for index, text in enumerate(
        ("Acme renewal is due in May.", "Globex prefers email.", "Initech uses SAP.")
    ):
        run(store.save(ContextItem(f"note-{index}", text)))
    items = run(store.recall())
    assert len(items) == 3
    assert all(item.metadata["subject"] is None for item in items)
    assert all("conflicts_with" not in item.metadata for item in items)
    assert run(store.conflicts()) == ()

    run(store.remember(SUBJECT, "The user prefers Hindi.", memory_id="hi"))
    run(store.remember(SUBJECT, "The user prefers Tamil.", memory_id="ta"))
    found = run(store.conflicts())
    assert [(c.first.memory_id, c.second.memory_id, c.subject) for c in found] == [
        ("hi", "ta", SUBJECT)
    ]
    recalled = {mid(item): item for item in run(store.recall())}
    assert recalled["hi"].metadata["conflicts_with"] == ["ta"]
    assert all("conflicts_with" not in recalled[f"note-{index}"].metadata for index in range(3))
    # Superseding one side resolves the pair.
    run(store.supersede("ta", "hi", reason="user confirmed Hindi"))
    assert run(store.conflicts(SUBJECT)) == ()

    # Rows the client cannot use are skipped; pairs are reported in ID order.
    rows = [
        {"first": node("A", "x", subject=None), "second": node("B", "y", subject=None)},
        {"first": node("D", "x"), "second": node("C", "y")},
    ]
    reordered = run(make_store(FakeDriver(script=[rows])).conflicts())
    assert [(c.first.memory_id, c.second.memory_id) for c in reordered] == [("C", "D")]


def test_conflict_query_is_bounded_and_index_friendly(monkeypatch: Any) -> None:
    for statement in (store_module._CONFLICTS, store_module._CONFLICTS_SUBJECT):
        assert "LIMIT $candidate_limit" in statement and "LIMIT $limit" in statement
        assert "collect(a) AS anchors" in statement  # pairs form only among the anchors
    assert "a.subject IS NOT NULL" in store_module._CONFLICTS
    assert "subject: $subject" in store_module._CONFLICTS_SUBJECT  # subject index seek

    monkeypatch.setattr(store_module, "_MAX_CONFLICT_CANDIDATES", 2)
    graph = FakeGraph()
    driver = graph.driver()
    store = make_store(driver)
    for memory_id, text in (("a", "x"), ("b", "y"), ("c", "z")):
        run(store.remember(SUBJECT, text, memory_id=memory_id))
    found = run(store.conflicts())
    assert driver.calls[-1].parameters["candidate_limit"] == 2
    assert [(c.first.memory_id, c.second.memory_id) for c in found] == [("a", "b")]


# --- metadata, forget and the guard -------------------------------------------------------


def test_metadata_scrub_redacts_secret_keys_and_secret_looking_values() -> None:
    redacted_keys = (
        "Token",
        "id-token",
        "PRIVATE_KEY",
        "privateKey",
        "Set-Cookie",
        "session_id",
        "Authorization",
        "credentials",
        "client_secret",
        "Password",
        "API-Key",
        "aws_access_key_id",
        "bearer",
        "x_auth",
        "db_pwd",
        "NEO4J_URI",
    )
    secret_values = {
        "header": "Bearer abcdefghijklmnopqrstuvwxyz012345",
        "basic": "Basic dXNlcjpwYXNzd29yZA==",
        "pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA",
        "openssh": "-----BEGIN OPENSSH PRIVATE KEY-----",
        "dsn": "postgres://admin:hunter2@db.example.test/app",
        "anthropic": "sk-ant-api03-abcdefghijklmnopqrstuvwx",
        "github": "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4",
        "slack": "xoxb-1234567890-abcdefghij",
        "aws": "AKIAIOSFODNN7EXAMPLE",
        "google": "AIza" + "Sy" + "A1b2C3d4" * 4 + "x",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N",
        "random": "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3z",
        "sentence": "note: use Bearer abcdefghijklmnop for the sandbox",
    }
    kept = {
        "token_count": 120,
        "max_tokens": 512,
        "prompt_tokens": 40,
        "tokenizer": "cl100k",
        "author": "Asha",
        "topic": "billing",
        "sha256": hashlib.sha256(b"x").hexdigest(),
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "slug": "quarterly-report-2024-final-version-approved",
        "url": "https://example.com/docs/page?id=7",
        "identifier": "ThisIsAVeryLongIdentifierName123",
        "count": 3,
        "flag": True,
        "nothing": None,
    }
    metadata: Dict[str, Any] = dict.fromkeys(redacted_keys, "value")
    metadata.update(secret_values)
    metadata.update(kept)
    metadata["nested"] = [{"refresh_token": "r", "note": "ok", "auth": ["Bearer abcdefghijkl"]}]
    metadata["values"] = ["fine", "Bearer abcdefghijklmnop", 7]
    scrubbed = json.loads(store_module._metadata_json(metadata))
    for key in redacted_keys + tuple(secret_values):
        assert scrubbed[key] == "<redacted>", key
    for key, value in kept.items():
        assert scrubbed[key] == value, key
    assert scrubbed["nested"] == [
        {"refresh_token": "<redacted>", "note": "ok", "auth": "<redacted>"}
    ]
    assert scrubbed["values"] == ["fine", "<redacted>", 7]
    # Non-JSON values are stringified before they are scanned.
    assert json.loads(store_module._metadata_json({"when": T0}))["when"] == str(T0)

    driver = FakeDriver(script=[[], [row(node("m"))]])
    secret_item = ContextItem("m", "Fact", metadata={"cookie": "c", "k": "sk-" + "a" * 20})
    run(make_store(driver).save(secret_item))
    stored = driver.calls[-1].parameters["metadata_json"]
    assert "sk-aaaa" not in stored and '"cookie":"<redacted>"' in stored


def test_forget_refuses_an_instant_before_valid_from() -> None:
    graph = FakeGraph()
    driver = graph.driver()
    store = make_store(driver)
    start = T0 + timedelta(days=10)
    run(store.remember(SUBJECT, "Fact", memory_id="m", valid_from=start))
    with pytest.raises(Neo4jIntervalError, match="precedes") as captured:
        run(store.forget("m", at=T0))
    assert isinstance(captured.value, ValueError)
    (props,) = graph.nodes.values()
    assert "valid_until" not in props and "forgotten_at" not in props
    assert driver.commits == 1 and driver.rollbacks == 1
    assert "m.valid_from <= $at AS started" in store_module._FORGET_SOFT
    # At valid_from itself the fact is retracted: an empty interval, never an inverted one.
    assert run(store.forget("m", at=start)) is True
    assert props["valid_until"] == props["valid_from"] == start
    assert run(store.forget("m", hard=True, at=T0)) is True and graph.nodes == {}


def test_default_guard_never_locks_a_long_running_process_out(monkeypatch: Any) -> None:
    for suffix in ("REQUESTS_PER_MINUTE", "MAX_REQUESTS", "MAX_UNITS"):
        monkeypatch.delenv("LLMSLIM_NEO4J_" + suffix, raising=False)
    store = Neo4jContextStore(FakeDriver(), tenant_id=TENANT, clock=lambda: NOW)
    assert store.guard.limits.max_requests is None
    seconds = iter(range(10**6))
    guard = UsageGuard(DEFAULT_USAGE_LIMITS, name="neo4j", clock=lambda: float(next(seconds)))
    for _ in range(100_001):  # the old lifetime cap was 100,000 requests
        guard.acquire(1.0)
    run(make_store(FakeDriver(), guard=guard).recall())
    assert guard.snapshot()["requests"] == 100_002
    # The per-minute rate still stops a runaway loop.
    burst = UsageGuard(DEFAULT_USAGE_LIMITS, name="neo4j", clock=lambda: 0.0)
    for _ in range(600):
        burst.acquire()
    with pytest.raises(RateLimitExceeded):
        burst.acquire()
    # An explicit cap from the environment still applies.
    monkeypatch.setenv("LLMSLIM_NEO4J_MAX_REQUESTS", "2")
    capped = Neo4jContextStore(FakeDriver(), tenant_id=TENANT, clock=lambda: NOW)
    run(capped.recall())
    run(capped.recall())
    with pytest.raises(UsageCapExceeded):
        run(capped.recall())


def test_subjectless_supersession_and_client_side_term_filter() -> None:
    graph = FakeGraph()
    driver = graph.driver()
    store = make_store(driver)
    run(store.save(ContextItem("office", "Office is in Pune.")))
    before = len(driver.calls)
    record = run(store.supersede("office", MemoryDraft("Office is in Bengaluru."), reason="moved"))
    assert record.subject is None and record.supersedes == ("office",)
    # Subject-less drafts are never deduplicated against other subject-less memories.
    assert driver.queries()[before:] == [
        store_module._GET,
        store_module._CREATE,
        store_module._LINK,
    ]
    # A row that matches none of the query terms is dropped on the client as well.
    stray = FakeDriver(script=[[row(node("x", "Unrelated text"))]])
    assert run(make_store(stray).recall(query="Bengaluru")) == ()
    with pytest.raises(ValueError, match="must be a string"):
        run(store.get(7))  # type: ignore[arg-type]
