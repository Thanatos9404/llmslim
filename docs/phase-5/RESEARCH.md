# Phase 5 research

Research snapshot: 2026-08-21.

## Specification requirements

- MCP revision **2026-07-28** has a stateless core. Clients use `server/discover` when needed; the old initialize/session flow remains a compatibility path in the official SDK.
- `tools/list` is paginated with `nextCursor`. A client must treat cursors as opaque and bound traversal.
- Cacheable list responses carry `ttlMs` and `cacheScope`. `ttlMs=0` is immediately stale; `private` must not cross an authorization context; only an explicitly `public` response can be reused across principals.
- Tool input schemas are JSON Schema 2020-12. Tool metadata and annotations are untrusted descriptive data, not authority or executable configuration.
- Streamable HTTP and stdio are supported. SSE is legacy-only and intentionally not implemented by LLMSlim.
- MCP’s security guidance keeps authorization and user consent in the host. Listing, ranking, and planning tools must not grant execution authority.

## SDK and provider behavior

- The official Python SDK is `mcp` **2.x**; Phase 5 uses the defended range `mcp>=2.0,<3`. It provides `Client`, `streamable_http_client`, and `stdio_client`, including modern protocol negotiation and its own transport implementation.
- The official SDK exposes a cacheable `Client.list_tools()` API. LLMSlim bypasses that internal response cache while it builds an auditable, complete snapshot, then applies its own source/principal cache boundary.
- The OpenAI Agents SDK supports Streamable HTTP and stdio MCP servers, hosted MCP, tool filtering, pagination, caching, and tracing. Its hosted MCP mode executes remotely in OpenAI infrastructure, so it is not the integration path for LLMSlim’s host-owned bridge.

## LLMSlim decisions

- MCP and Agents SDK dependencies are extras: `llmslim[mcp]` and `llmslim[agents]` (Python 3.10+); base `compress()` stays dependency-light and offline on every supported base Python version.
- `MCPToolCatalogSource` only ingests `tools/list`; it has no tool-call method. Stdio accepts an executable and argument vector, never a shell command string.
- Model plans default to **FULL** and preserve complete raw schemas. **MEASURE_ONLY** exposes the same full catalog while returning metrics. **SELECTIVE** remains explicit, experimental, and uses existing conservative fail-open selection.
- Hydration checks source, catalog, and per-tool fingerprints before returning copied authoritative raw schemas.
- The generic and OpenAI adapters only expose schemas and route an explicit host callback. They do not authorize or execute independently.

## Experimental ideas, not stable claims

- `subscriptions/listen` tool-change invalidation is not yet wired: explicit refresh and TTL correctness are the supported invalidation paths.
- Selective exposure remains research-only. Phase 4.5/4.6 did not prove it safe enough for default use.

Primary sources: [MCP 2026-07-28 release](https://blog.modelcontextprotocol.io/posts/2026-07-28/), [MCP caching](https://modelcontextprotocol.io/specification/draft/server/utilities/caching), [official Python SDK](https://github.com/modelcontextprotocol/python-sdk), and [OpenAI Agents SDK MCP guide](https://openai.github.io/openai-agents-python/mcp/).
