"""Offline Phase 5 MCP catalog, cache, plan, and authority-boundary tests."""

from __future__ import annotations

import asyncio
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from llmslim.mcp import (
    CacheScope,
    CatalogCache,
    CatalogChangedError,
    CatalogError,
    CatalogLimitError,
    CatalogLimits,
    HostToolAdapter,
    MCPToolCatalogSource,
    PlanMode,
    ToolCatalogSnapshot,
    hydrate_plan,
    plan_catalog_context,
)
from llmslim.tools import from_mcp_tool


def _tool(name: str = "search"):
    return {
        "name": name,
        "description": "Search deterministic local fixtures.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }


class _Client:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0
        self.protocol_version = "2026-07-28"

    async def list_tools(self, cursor=None, cache_mode=None):
        assert cache_mode == "bypass"
        self.calls += 1
        return self.pages[cursor]


class _DelayedClient(_Client):
    async def list_tools(self, cursor=None, cache_mode=None):
        await asyncio.sleep(0.05)
        return await super().list_tools(cursor=cursor, cache_mode=cache_mode)


def _factory(client):
    @asynccontextmanager
    async def make_client():
        yield client

    return make_client


def _response(tools, next_cursor=None, ttl_ms=1000, cache_scope="private"):
    return SimpleNamespace(
        tools=tools, next_cursor=next_cursor, ttl_ms=ttl_ms, cache_scope=cache_scope
    )


def test_pagination_snapshot_and_warm_cache_are_deterministic():
    client = _Client(
        {None: _response([_tool("first")], "page-2"), "page-2": _response([_tool("second")])}
    )
    events = []
    source = MCPToolCatalogSource(_factory(client), "fixture", event_callback=events.append)
    first = asyncio.run(source.list_tools())
    second = asyncio.run(source.list_tools())
    assert first.pages == 2
    assert first.tool_count == 2
    assert first.protocol_version == "2026-07-28"
    assert client.calls == 2
    assert second.cache_status == "hit"
    assert [event.name for event in events] == ["cache_miss", "catalog_fetch", "cache_hit"]


def test_ttl_zero_is_immediately_stale_and_refresh_bypasses_cache():
    client = _Client({None: _response([_tool()], ttl_ms=0)})
    source = MCPToolCatalogSource(_factory(client), "ttl-zero")
    asyncio.run(source.list_tools())
    asyncio.run(source.list_tools())
    asyncio.run(source.refresh())
    assert client.calls == 3


def test_positive_ttl_expiry_explicit_invalidation_and_single_flight_refresh():
    clock = [0.0]
    cache = CatalogCache(clock=lambda: clock[0])
    client = _Client({None: _response([_tool()], ttl_ms=100)})
    source = MCPToolCatalogSource(_factory(client), "expiring", cache=cache)
    asyncio.run(source.list_tools())
    clock[0] = 0.05
    assert asyncio.run(source.list_tools()).cache_status == "hit"
    clock[0] = 0.11
    asyncio.run(source.list_tools())
    assert client.calls == 2
    source.invalidate()
    asyncio.run(source.list_tools())
    assert client.calls == 3

    delayed = _DelayedClient({None: _response([_tool()], ttl_ms=100)})
    concurrent = MCPToolCatalogSource(_factory(delayed), "concurrent")

    async def fetch_concurrently():
        return await asyncio.gather(*[concurrent.list_tools() for _ in range(20)])

    snapshots = asyncio.run(fetch_concurrently())
    assert delayed.calls == 1
    assert {snapshot.catalog_fingerprint for snapshot in snapshots} == {
        snapshots[0].catalog_fingerprint
    }


def test_async_catalog_fetch_propagates_cancellation():
    delayed = _DelayedClient({None: _response([_tool()], ttl_ms=100)})
    source = MCPToolCatalogSource(_factory(delayed), "cancel")

    async def cancel_fetch():
        task = asyncio.create_task(source.list_tools())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_fetch())


def test_public_cache_reuses_and_private_cache_isolates_principals():
    shared = CatalogCache()
    public_client = _Client({None: _response([_tool("public")], cache_scope="public")})
    one = MCPToolCatalogSource(
        _factory(public_client), "same", cache_principal="alice", cache=shared
    )
    two_client = _Client({None: _response([_tool("unexpected")], cache_scope="public")})
    two = MCPToolCatalogSource(_factory(two_client), "same", cache_principal="bob", cache=shared)
    asyncio.run(one.list_tools())
    assert asyncio.run(two.list_tools()).tools[0].name == "public"
    assert two_client.calls == 0

    private_one_client = _Client({None: _response([_tool("alice")], cache_scope="private")})
    private_two_client = _Client({None: _response([_tool("bob")], cache_scope="private")})
    private_one = MCPToolCatalogSource(
        _factory(private_one_client), "private", cache_principal="alice", cache=shared
    )
    private_two = MCPToolCatalogSource(
        _factory(private_two_client), "private", cache_principal="bob", cache=shared
    )
    assert asyncio.run(private_one.list_tools()).tools[0].name == "alice"
    assert asyncio.run(private_two.list_tools()).tools[0].name == "bob"
    assert private_two_client.calls == 1


def test_cursor_loop_bounds_and_bad_cache_scope_fail_closed():
    loop_client = _Client(
        {None: _response([_tool()], "same"), "same": _response([_tool("second")], "same")}
    )
    with pytest.raises(CatalogError, match="repeated"):
        asyncio.run(MCPToolCatalogSource(_factory(loop_client), "loop").list_tools())
    limited_client = _Client(
        {None: _response([_tool()], "next"), "next": _response([_tool("second")])}
    )
    with pytest.raises(CatalogLimitError, match="max_pages"):
        asyncio.run(
            MCPToolCatalogSource(
                _factory(limited_client), "limit", limits=CatalogLimits(max_pages=1)
            ).list_tools()
        )
    invalid_client = _Client({None: _response([_tool()], cache_scope="shared")})
    with pytest.raises(CatalogError, match="cacheScope"):
        asyncio.run(MCPToolCatalogSource(_factory(invalid_client), "scope").list_tools())


def test_url_and_stdio_configurations_reject_unsafe_input():
    with pytest.raises(ValueError, match="HTTPS"):
        MCPToolCatalogSource.from_streamable_http("http://example.com/mcp")
    with pytest.raises(ValueError, match="credential"):
        MCPToolCatalogSource.from_streamable_http("https://user:secret@example.com/mcp")
    with pytest.raises(ValueError, match="query parameters"):
        MCPToolCatalogSource.from_streamable_http("https://example.com/mcp?token=secret")
    with pytest.raises(ValueError, match="NUL"):
        MCPToolCatalogSource.from_stdio("tool\x00", [])


def test_full_measure_selective_hydration_and_stale_detection():
    tools = (
        from_mcp_tool(_tool("one"), namespace="fixture"),
        from_mcp_tool(_tool("two"), namespace="fixture"),
    )
    snapshot = ToolCatalogSnapshot("fixture", tools, "catalog-a", 1.0, None, CacheScope.PRIVATE, 1)
    full = plan_catalog_context(snapshot)
    measured = plan_catalog_context(snapshot, mode=PlanMode.MEASURE_ONLY)
    assert full.selected_tool_ids == tuple(tool.tool_id for tool in tools)
    assert measured.metrics.catalog_tokens == measured.metrics.presented_tokens
    assert full.metrics.tokens_avoided == 0
    with pytest.raises(ValueError, match="research-only"):
        plan_catalog_context(snapshot, mode=PlanMode.SELECTIVE, query="search")
    selective = plan_catalog_context(
        snapshot, mode=PlanMode.SELECTIVE, query="search", experimental=True
    )
    assert selective.experimental is True
    hydrated = hydrate_plan(snapshot, full)
    hydrated[0]["description"] = "mutated"
    assert hydrate_plan(snapshot, full)[0]["description"] != "mutated"
    changed = ToolCatalogSnapshot("fixture", tools, "catalog-b", 1.0, None, CacheScope.PRIVATE, 1)
    with pytest.raises(CatalogChangedError):
        hydrate_plan(changed, full)
    bridge = HostToolAdapter(snapshot, full)
    assert bridge.model_tools == full.model_tools
    assert bridge.hydrate() == hydrate_plan(snapshot, full)


def test_official_sdk_inprocess_mcp_end_to_end_catalog_plan_hydrate_and_host_call():
    """The MCP/LLMSlim path is real; only the harmless local tool is deterministic."""
    pytest.importorskip("mcp")
    from mcp.client import Client
    from mcp.server.mcpserver import MCPServer

    server = MCPServer("phase5-fixture")

    @server.tool()
    def add(left: int, right: int) -> int:
        return left + right

    @asynccontextmanager
    async def official_client():
        async with Client(server) as client:
            yield client

    source = MCPToolCatalogSource(official_client, "official-fixture", namespace="fixture")
    snapshot = asyncio.run(source.list_tools())
    plan = plan_catalog_context(snapshot)
    hydrated = hydrate_plan(snapshot, plan)
    assert hydrated[0]["name"] == "add"

    async def call() -> object:
        async with Client(server) as client:
            return await client.call_tool("add", {"left": 2, "right": 3})

    result = asyncio.run(call())
    assert result.is_error is False
    assert result.structured_content == {"result": 5}


def test_openai_agents_bridge_requires_explicit_host_execution_callback():
    pytest.importorskip("agents")
    from llmslim.integrations.openai_agents import to_openai_agents_tools

    tool = from_mcp_tool(_tool("lookup"), namespace="fixture")
    snapshot = ToolCatalogSnapshot("fixture", (tool,), "catalog", 1.0, None, CacheScope.PRIVATE, 1)
    plan = plan_catalog_context(snapshot)
    calls = []

    async def host_invoker(tool_id, arguments):
        calls.append((tool_id, arguments))
        return {"ok": True}

    agent_tool = to_openai_agents_tools(HostToolAdapter(snapshot, plan), plan, host_invoker)[0]
    assert asyncio.run(agent_tool.on_invoke_tool(None, '{"query":"hello"}')) == {"ok": True}
    assert calls == [(tool.tool_id, {"query": "hello"})]


def test_streamable_http_catalog_and_host_call_use_the_official_sdk():
    """Exercise the actual localhost Streamable HTTP transport, not a fake client."""
    pytest.importorskip("mcp")
    import uvicorn
    from mcp.client import Client
    from mcp.server.mcpserver import MCPServer

    async def run() -> None:
        server = MCPServer("phase5-http-fixture")

        @server.tool()
        def subtract(left: int, right: int) -> int:
            return left - right

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        uvicorn_server = uvicorn.Server(
            uvicorn.Config(
                server.streamable_http_app(stateless_http=True),
                host="127.0.0.1",
                port=port,
                log_level="critical",
                access_log=False,
            )
        )
        serve_task = asyncio.create_task(uvicorn_server.serve(sockets=[listener]))
        try:
            for _ in range(100):
                if uvicorn_server.started:
                    break
                await asyncio.sleep(0.01)
            assert uvicorn_server.started
            url = "http://127.0.0.1:%s/mcp" % port
            source = MCPToolCatalogSource.from_streamable_http(url, source_id="phase5-http")
            snapshot = await source.list_tools()
            plan = plan_catalog_context(snapshot)
            assert hydrate_plan(snapshot, plan)[0]["name"] == "subtract"
            async with Client(url) as client:
                result = await client.call_tool("subtract", {"left": 7, "right": 2})
            assert result.is_error is False
            assert result.structured_content == {"result": 5}
        finally:
            uvicorn_server.should_exit = True
            await serve_task
            listener.close()

    asyncio.run(run())


def test_stdio_catalog_and_host_call_use_literal_argv_only():
    """The source launches a repository-owned fixture with an executable plus argv."""
    pytest.importorskip("mcp")
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters, stdio_client

    fixture = Path(__file__).parent / "fixtures" / "phase5_stdio_server.py"

    async def run() -> None:
        source = MCPToolCatalogSource.from_stdio(
            sys.executable,
            [str(fixture)],
            source_id="phase5-stdio",
        )
        snapshot = await source.list_tools()
        plan = plan_catalog_context(snapshot)
        assert hydrate_plan(snapshot, plan)[0]["name"] == "multiply"
        params = StdioServerParameters(command=sys.executable, args=[str(fixture)])
        async with Client(stdio_client(params)) as client:
            result = await client.call_tool("multiply", {"left": 6, "right": 7})
        assert result.is_error is False
        assert result.structured_content == {"result": 42}

    asyncio.run(run())


def test_offline_tools_cli_inspects_authoritative_catalog_json(tmp_path, capsys):
    from llmslim.cli import main

    catalog = tmp_path / "tools.json"
    catalog.write_text(
        '{"tools": [{"name": "lookup", "inputSchema": {"type": "object"}}]}', encoding="utf-8"
    )
    assert main(["tools", "inspect", str(catalog), "--json"]) == 0
    report = capsys.readouterr().out
    assert '"tool_count": 1' in report
    assert '"tool_id": "cli/lookup"' in report


def test_phase5_benchmark_separates_integration_availability_from_live_model_success():
    from benchmarks.phase5_agent_integration import run_phase5_agent_integration_benchmark

    result = run_phase5_agent_integration_benchmark()
    assert result["tasks"]["count"] == 60
    assert result["tasks"]["full_required_tool_availability"] == 1.0
    assert result["tasks"]["live_model_status"] == "NOT_RUN"
    assert result["plans"]["full"]["presented_tokens"] == result["catalog"]["catalog_tokens"]
    assert result["plans"]["full"]["tokens_avoided"] == 0


def test_refresh_revokes_old_public_cache_even_when_new_ttl_is_zero():
    client = _Client({None: _response([_tool("old")], cache_scope="public")})
    source = MCPToolCatalogSource(_factory(client), "refresh-scope")
    asyncio.run(source.list_tools())
    client.pages[None] = _response([_tool("new")], ttl_ms=0)
    assert asyncio.run(source.refresh()).tools[0].name == "new"
    assert asyncio.run(source.list_tools()).tools[0].name == "new"
    assert client.calls == 3


def test_returned_snapshot_cannot_mutate_cached_contract():
    client = _Client({None: _response([_tool()])})
    source = MCPToolCatalogSource(_factory(client), "copy")
    first = asyncio.run(source.list_tools())
    first.tools[0].raw["name"] = "tampered"
    second = asyncio.run(source.list_tools())
    assert second.tools[0].raw["name"] == "search"
    second.tools[0].raw["name"] = "tampered-again"
    assert asyncio.run(source.list_tools()).tools[0].raw["name"] == "search"


def test_agents_bridge_rejects_same_length_plan_from_another_catalog():
    pytest.importorskip("agents")
    from dataclasses import replace

    from llmslim.integrations.openai_agents import to_openai_agents_tools

    tool = from_mcp_tool(_tool(), namespace="fixture")
    snapshot = ToolCatalogSnapshot("fixture", (tool,), "catalog", 1.0, None, CacheScope.PRIVATE, 1)
    plan = plan_catalog_context(snapshot)
    other = replace(plan, selected_tool_ids=("other/tool",))

    async def invoker(tool_id, arguments):
        raise AssertionError("must not execute")

    with pytest.raises(ValueError, match="same model tool surface"):
        to_openai_agents_tools(HostToolAdapter(snapshot, plan), other, invoker)


def test_catalog_byte_limit_stops_before_fetching_next_page():
    client = _Client({None: _response([_tool()], "next"), "next": _response([_tool("second")])})
    source = MCPToolCatalogSource(
        _factory(client), "bounded", limits=CatalogLimits(max_serialized_bytes=10)
    )
    with pytest.raises(CatalogLimitError, match="max_serialized_bytes"):
        asyncio.run(source.list_tools())
    assert client.calls == 1
