"""MCP catalog ingestion and contract-safe context planning.

This module deliberately stops before execution.  It reads a catalog through
an explicitly configured MCP client, preserves each complete tool contract,
and gives a host enough information to expose or hydrate tools safely.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    AsyncContextManager,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from .tokens import count_tokens
from .tools import (
    ToolSchema,
    ToolSchemaError,
    canonical_json,
    fingerprint_tool_schema,
    from_mcp_tool,
    select_tools,
)


class MCPIntegrationError(RuntimeError):
    """Base class for safe, actionable MCP catalog integration failures."""


class OptionalDependencyError(MCPIntegrationError):
    """Raised when an optional MCP dependency has not been installed."""


class CatalogError(MCPIntegrationError):
    """Raised when a remote catalog is malformed or cannot be represented."""


class CatalogLimitError(CatalogError):
    """Raised when a catalog exceeds configured, defensive ingestion bounds."""


class CatalogChangedError(CatalogError):
    """Raised when a plan no longer matches the authoritative catalog."""


class ToolNotFoundError(CatalogError):
    """Raised when a selected stable tool identity is absent from a catalog."""


class CacheScope(str, Enum):
    """MCP cache scopes accepted by the 2026-07-28 protocol revision."""

    PUBLIC = "public"
    PRIVATE = "private"


class PlanMode(str, Enum):
    """Model-context exposure modes; only SELECTIVE is experimental."""

    FULL = "full"
    MEASURE_ONLY = "measure_only"
    SELECTIVE = "selective"


@dataclass(frozen=True)
class CatalogLimits:
    """Defensive bounds for one tools/list ingestion operation."""

    max_pages: int = 100
    max_tools: int = 1_000
    max_serialized_bytes: int = 10_000_000

    def __post_init__(self) -> None:
        if self.max_pages < 1 or self.max_tools < 1 or self.max_serialized_bytes < 1:
            raise ValueError("catalog limits must be positive")


@dataclass(frozen=True)
class CatalogPage:
    """One normalized tools/list response, including protocol cache hints."""

    tools: Tuple[Mapping[str, Any], ...]
    next_cursor: Optional[str] = None
    ttl_ms: int = 0
    cache_scope: CacheScope = CacheScope.PRIVATE

    def __post_init__(self) -> None:
        if self.ttl_ms < 0:
            raise CatalogError("tools/list ttlMs must be non-negative")


@dataclass(frozen=True)
class ToolCatalogSnapshot:
    """An immutable, authoritative MCP tool catalog snapshot.

    ``tools`` are copied ``ToolSchema`` values whose ``raw`` members remain the
    only source for hydration and execution-facing adapters.
    """

    source_id: str
    tools: Tuple[ToolSchema, ...]
    catalog_fingerprint: str
    retrieved_at: float
    expires_at: Optional[float]
    cache_scope: CacheScope
    pages: int
    protocol_version: Optional[str] = None
    cache_status: str = "miss"
    fetch_ms: float = 0.0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def token_count(self) -> int:
        return count_tokens(canonical_json([tool.raw for tool in self.tools]))


@dataclass(frozen=True)
class ToolContextMetrics:
    """Local-only measurements for a catalog plan; no telemetry is emitted."""

    catalog_tokens: int
    presented_tokens: int
    tokens_avoided: int
    cache_status: str
    fetch_ms: float
    planning_ms: float


@dataclass(frozen=True)
class CatalogContextPlan:
    """A model-facing plan that can be hydrated, but never executes tools."""

    source_id: str
    catalog_fingerprint: str
    mode: PlanMode
    selected_tool_ids: Tuple[str, ...]
    selected_fingerprints: Tuple[Tuple[str, str], ...]
    model_tools: Tuple[Dict[str, Any], ...]
    metrics: ToolContextMetrics
    experimental: bool = False
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogEvent:
    """A caller-local observable event for catalog cache and planning work."""

    name: str
    source_id: str
    cache_scope: CacheScope
    detail: str = ""


EventCallback = Callable[[CatalogEvent], None]


class ToolCatalogSource:
    """Async source abstraction for authoritative tool catalogs; never executes tools."""

    source_id: str

    async def list_tools(self, refresh: bool = False) -> ToolCatalogSnapshot:
        """Return an authoritative snapshot, optionally bypassing local cache."""
        raise NotImplementedError

    async def refresh(self) -> ToolCatalogSnapshot:
        """Fetch a new snapshot without executing any listed tools."""
        return await self.list_tools(refresh=True)


def _catalog_fingerprint(tools: Sequence[ToolSchema]) -> str:
    return hashlib.sha256(canonical_json([tool.raw for tool in tools]).encode("utf-8")).hexdigest()


class StaticToolCatalogSource(ToolCatalogSource):
    """A deterministic in-memory source useful for static and offline hosts."""

    def __init__(self, tools: Sequence[ToolSchema], source_id: str = "static") -> None:
        self.source_id = source_id
        self._tools = copy.deepcopy(tuple(tools))
        _ensure_unique_ids(self._tools)

    async def list_tools(self, refresh: bool = False) -> ToolCatalogSnapshot:
        del refresh
        now = time.monotonic()
        return ToolCatalogSnapshot(
            self.source_id,
            copy.deepcopy(self._tools),
            _catalog_fingerprint(self._tools),
            now,
            None,
            CacheScope.PRIVATE,
            1,
            cache_status="static",
        )


@dataclass
class _CacheEntry:
    snapshot: ToolCatalogSnapshot
    expires_at: Optional[float]


class CatalogCache:
    """In-process snapshot cache with conservative private-principal isolation."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: Dict[Tuple[str, str], _CacheEntry] = {}
        self._locks: Dict[Tuple[str, str], asyncio.Lock] = {}

    def key(
        self, source_id: str, scope: CacheScope, principal: str, instance_id: str
    ) -> Tuple[str, str]:
        # A server may allow public reuse only after it explicitly sent public.
        return (
            source_id,
            "public" if scope is CacheScope.PUBLIC else "private:" + (principal or instance_id),
        )

    def lock_for(self, key: Tuple[str, str]) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def now(self) -> float:
        """Return the injected monotonic time source used for cache expiry."""
        return self._clock()

    def get(self, key: Tuple[str, str]) -> Optional[ToolCatalogSnapshot]:
        entry = self._entries.get(key)
        if entry is None or entry.expires_at is None or entry.expires_at <= self._clock():
            return None
        return copy.deepcopy(entry.snapshot)

    def put(self, snapshot: ToolCatalogSnapshot, principal: str, instance_id: str) -> None:
        key = self.key(snapshot.source_id, snapshot.cache_scope, principal, instance_id)
        self._entries[key] = _CacheEntry(copy.deepcopy(snapshot), snapshot.expires_at)

    def invalidate(self, source_id: str) -> None:
        for key in tuple(self._entries):
            if key[0] == source_id:
                del self._entries[key]


class MCPToolCatalogSource(ToolCatalogSource):
    """Official-SDK-backed async MCP catalog source for stdio or Streamable HTTP.

    Construct only from explicit endpoint or argv configuration. This source
    never derives a server URL from a prompt and never exposes credentials in
    snapshots, source IDs, exceptions, or observable events.
    """

    def __init__(
        self,
        client_factory: Callable[[], AsyncContextManager[Any]],
        source_id: str,
        *,
        namespace: Optional[str] = None,
        cache_principal: str = "",
        cache: Optional[CatalogCache] = None,
        limits: CatalogLimits = CatalogLimits(),
        event_callback: Optional[EventCallback] = None,
    ) -> None:
        if not source_id:
            raise ValueError("source_id must be non-empty")
        self.source_id = source_id
        self._client_factory = client_factory
        self._namespace = namespace or source_id
        self._principal = cache_principal
        self._cache = cache or CatalogCache()
        self._limits = limits
        self._event_callback = event_callback
        self._instance_id = uuid.uuid4().hex

    @classmethod
    def from_stdio(
        cls,
        executable: str,
        argv: Sequence[str] = (),
        *,
        source_id: str = "mcp-stdio",
        cwd: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
        timeout_seconds: Optional[float] = 30.0,
        **kwargs: Any,
    ) -> "MCPToolCatalogSource":
        """Create a source using argv-only stdio spawning; no shell is involved."""
        if not executable or "\x00" in executable or any("\x00" in item for item in argv):
            raise ValueError(
                "stdio executable and argv must be explicit non-empty strings without NUL bytes"
            )

        @asynccontextmanager
        async def factory() -> Any:
            try:
                from mcp.client import Client
                from mcp.client.stdio import StdioServerParameters, stdio_client
            except ImportError as exc:  # pragma: no cover - exercised without the optional extra.
                raise OptionalDependencyError(
                    "install llmslim[mcp] for MCP catalog sources"
                ) from exc
            params = StdioServerParameters(
                command=executable, args=list(argv), cwd=cwd, env=dict(env or {})
            )
            async with Client(stdio_client(params), read_timeout_seconds=timeout_seconds) as client:
                yield client

        return cls(factory, source_id, **kwargs)

    @classmethod
    def from_streamable_http(
        cls,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        source_id: Optional[str] = None,
        timeout_seconds: float = 30.0,
        allow_http_localhost: bool = True,
        **kwargs: Any,
    ) -> "MCPToolCatalogSource":
        """Create an HTTPS source, allowing HTTP only for loopback development."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "MCP URLs may not contain credentials, query parameters, or fragments; use headers"
            )
        if parsed.scheme == "http" and not (
            allow_http_localhost and parsed.hostname in local_hosts
        ):
            raise ValueError(
                "MCP HTTP endpoints must use HTTPS except explicit localhost development"
            )
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MCP endpoint must be an absolute HTTP(S) URL")
        safe_source_id = source_id or (parsed.scheme + "://" + parsed.netloc + parsed.path)

        @asynccontextmanager
        async def factory() -> Any:
            try:
                import httpx2
                from mcp.client import Client
                from mcp.client.streamable_http import streamable_http_client
            except ImportError as exc:  # pragma: no cover
                raise OptionalDependencyError(
                    "install llmslim[mcp] for MCP catalog sources"
                ) from exc
            async with httpx2.AsyncClient(
                headers=dict(headers or {}), timeout=timeout_seconds, follow_redirects=False
            ) as http:
                async with Client(
                    streamable_http_client(url, http_client=http),
                    read_timeout_seconds=timeout_seconds,
                ) as client:
                    yield client

        return cls(factory, safe_source_id, **kwargs)

    async def list_tools(self, refresh: bool = False) -> ToolCatalogSnapshot:
        # Unknown scope starts private. A known public cache is checked first;
        # it can only exist after a server explicitly allowed it.
        private_key = self._cache.key(
            self.source_id, CacheScope.PRIVATE, self._principal, self._instance_id
        )
        public_key = self._cache.key(
            self.source_id, CacheScope.PUBLIC, self._principal, self._instance_id
        )
        if not refresh:
            for key in (private_key, public_key):
                hit = self._cache.get(key)
                if hit is not None:
                    self._emit("cache_hit", hit.cache_scope)
                    return _with_cache_status(hit, "hit")
        self._emit("cache_miss", CacheScope.PRIVATE)
        # A private-key lock is intentionally used even if the eventual response
        # is public; it prevents same-principal stampedes without unsafe sharing.
        async with self._cache.lock_for(private_key):
            if not refresh:
                hit = self._cache.get(private_key) or self._cache.get(public_key)
                if hit is not None:
                    self._emit("cache_hit", hit.cache_scope)
                    return _with_cache_status(hit, "hit")
            snapshot = await self._fetch_snapshot()
            # A fresh response supersedes this principal's old entry and any
            # public entry, even when the new response disallows caching.
            self._cache._entries.pop(private_key, None)
            self._cache._entries.pop(public_key, None)
            if snapshot.expires_at is not None:
                self._cache.put(snapshot, self._principal, self._instance_id)
            self._emit("refresh" if refresh else "catalog_fetch", snapshot.cache_scope)
            return snapshot

    def invalidate(self) -> None:
        """Explicitly discard cached catalog entries for this source."""
        self._cache.invalidate(self.source_id)

    async def _fetch_snapshot(self) -> ToolCatalogSnapshot:
        started = time.perf_counter()
        cursor: Optional[str] = None
        seen_cursors = set()
        pages = 0
        raw_tools: List[Mapping[str, Any]] = []
        ttl_values: List[int] = []
        scope = CacheScope.PRIVATE
        protocol_version: Optional[str] = None
        try:
            async with self._client_factory() as client:
                protocol_version = getattr(client, "protocol_version", None)
                while True:
                    if pages >= self._limits.max_pages:
                        raise CatalogLimitError("MCP tools/list exceeded max_pages")
                    response = await client.list_tools(cursor=cursor, cache_mode="bypass")
                    page = _page_from_sdk(response)
                    pages += 1
                    raw_tools.extend(page.tools)
                    if (
                        len(canonical_json(list(raw_tools)).encode("utf-8"))
                        > self._limits.max_serialized_bytes
                    ):
                        raise CatalogLimitError("MCP tools/list exceeded max_serialized_bytes")
                    if len(raw_tools) > self._limits.max_tools:
                        raise CatalogLimitError("MCP tools/list exceeded max_tools")
                    ttl_values.append(page.ttl_ms)
                    # A mixed listing is only safe to cache as privately scoped.
                    if page.cache_scope is CacheScope.PRIVATE:
                        scope = CacheScope.PRIVATE
                    elif pages == 1:
                        scope = CacheScope.PUBLIC
                    cursor = page.next_cursor
                    if cursor is None:
                        break
                    if cursor in seen_cursors:
                        raise CatalogError("MCP tools/list repeated a pagination cursor")
                    seen_cursors.add(cursor)
        except asyncio.CancelledError:
            raise
        except MCPIntegrationError:
            raise
        except Exception as exc:
            raise MCPIntegrationError(
                "MCP tools/list failed; verify the configured trusted endpoint"
            ) from exc
        serialized = canonical_json(list(raw_tools)).encode("utf-8")
        if len(serialized) > self._limits.max_serialized_bytes:
            raise CatalogLimitError("MCP tools/list exceeded max_serialized_bytes")
        try:
            tools = tuple(from_mcp_tool(raw, namespace=self._namespace) for raw in raw_tools)
            _ensure_unique_ids(tools)
        except (ToolSchemaError, TypeError, ValueError) as exc:
            raise CatalogError(
                "MCP tools/list included an invalid or duplicate tool definition"
            ) from exc
        now = self._cache.now()
        # The shortest page TTL governs a concatenated list. ttl=0 is immediately stale.
        ttl_ms = min(ttl_values) if ttl_values else 0
        expiry = now + ttl_ms / 1000.0 if ttl_ms > 0 else None
        return ToolCatalogSnapshot(
            self.source_id,
            tools,
            _catalog_fingerprint(tools),
            now,
            expiry,
            scope,
            pages,
            protocol_version=protocol_version,
            fetch_ms=(time.perf_counter() - started) * 1_000.0,
        )

    def _emit(self, name: str, scope: CacheScope) -> None:
        if self._event_callback is not None:
            self._event_callback(CatalogEvent(name, self.source_id, scope))


def _page_from_sdk(response: Any) -> CatalogPage:
    tools = []
    for tool in getattr(response, "tools", ()):
        if hasattr(tool, "model_dump"):
            tools.append(tool.model_dump(by_alias=True, exclude_none=True))
        elif isinstance(tool, Mapping):
            tools.append(copy.deepcopy(dict(tool)))
        else:
            raise CatalogError("MCP tools/list tool entries must be mappings")
    scope_value = getattr(response, "cache_scope", "private")
    try:
        scope = CacheScope(str(scope_value))
    except ValueError as exc:
        raise CatalogError("MCP tools/list cacheScope must be public or private") from exc
    return CatalogPage(
        tuple(tools),
        getattr(response, "next_cursor", None),
        int(getattr(response, "ttl_ms", 0)),
        scope,
    )


def _ensure_unique_ids(tools: Sequence[ToolSchema]) -> None:
    ids = [tool.tool_id for tool in tools]
    if len(ids) != len(set(ids)):
        raise CatalogError("tool catalog has duplicate stable tool identities")


def _with_cache_status(snapshot: ToolCatalogSnapshot, status: str) -> ToolCatalogSnapshot:
    return ToolCatalogSnapshot(
        snapshot.source_id,
        snapshot.tools,
        snapshot.catalog_fingerprint,
        snapshot.retrieved_at,
        snapshot.expires_at,
        snapshot.cache_scope,
        snapshot.pages,
        snapshot.protocol_version,
        status,
        snapshot.fetch_ms,
    )


def plan_catalog_context(
    snapshot: ToolCatalogSnapshot,
    *,
    mode: PlanMode = PlanMode.FULL,
    query: str = "",
    top_k: int = 5,
    experimental: bool = False,
) -> CatalogContextPlan:
    """Create a model context plan without changing host execution authority.

    FULL and MEASURE_ONLY expose the complete authoritative catalog. SELECTIVE
    requires ``experimental=True`` and reuses the existing research retrieval
    selection; low-confidence behavior remains the retriever's fail-open path.
    """
    started = time.perf_counter()
    tools = snapshot.tools
    warnings: List[str] = []
    if mode is PlanMode.SELECTIVE:
        if not experimental:
            raise ValueError(
                "selective planning is research-only; pass experimental=True explicitly"
            )
        selection = select_tools(query, tools, top_k=top_k, mode="conservative")
        selected = selection.selected
        warnings.extend(selection.warnings)
        warnings.append("EXPERIMENTAL: selective exposure is not authorization or execution")
    elif mode in {PlanMode.FULL, PlanMode.MEASURE_ONLY}:
        selected = tools
    else:
        raise ValueError("unsupported catalog plan mode")
    model_tools = tuple(tool.authoritative_copy() for tool in selected)
    catalog_tokens = snapshot.token_count
    presented_tokens = count_tokens(canonical_json(list(model_tools)))
    metrics = ToolContextMetrics(
        catalog_tokens,
        presented_tokens,
        max(0, catalog_tokens - presented_tokens),
        snapshot.cache_status,
        snapshot.fetch_ms,
        (time.perf_counter() - started) * 1_000.0,
    )
    return CatalogContextPlan(
        snapshot.source_id,
        snapshot.catalog_fingerprint,
        mode,
        tuple(tool.tool_id for tool in selected),
        tuple((tool.tool_id, fingerprint_tool_schema(tool)) for tool in selected),
        model_tools,
        metrics,
        experimental=mode is PlanMode.SELECTIVE,
        warnings=tuple(warnings),
    )


def hydrate_plan(
    snapshot: ToolCatalogSnapshot, plan: CatalogContextPlan
) -> Tuple[Dict[str, Any], ...]:
    """Return complete authoritative schemas, rejecting stale or altered plans."""
    if (
        snapshot.source_id != plan.source_id
        or snapshot.catalog_fingerprint != plan.catalog_fingerprint
    ):
        raise CatalogChangedError("catalog changed since the model-facing plan was created")
    by_id = {tool.tool_id: tool for tool in snapshot.tools}
    hydrated = []
    for tool_id, expected_fingerprint in plan.selected_fingerprints:
        tool = by_id.get(tool_id)
        if tool is None:
            raise ToolNotFoundError("selected tool is no longer present: " + tool_id)
        if fingerprint_tool_schema(tool) != expected_fingerprint:
            raise CatalogChangedError("selected tool contract changed: " + tool_id)
        hydrated.append(tool.authoritative_copy())
    return tuple(hydrated)


class HostToolAdapter:
    """Framework-neutral bridge exposing data only; it contains no call method."""

    def __init__(self, snapshot: ToolCatalogSnapshot, plan: CatalogContextPlan) -> None:
        self._snapshot = snapshot
        self._plan = plan

    @property
    def model_tools(self) -> Tuple[Dict[str, Any], ...]:
        """Return safe copied representations for a host's model surface."""
        return tuple(copy.deepcopy(tool) for tool in self._plan.model_tools)

    def hydrate(self) -> Tuple[Dict[str, Any], ...]:
        """Resolve complete source contracts; the host remains responsible for calls."""
        return hydrate_plan(self._snapshot, self._plan)

    def matches_plan(self, plan: CatalogContextPlan) -> bool:
        """Require the exact plan used to construct this bridge."""
        return self._plan == plan
