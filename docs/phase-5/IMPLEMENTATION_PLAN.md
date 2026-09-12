# Phase 5 implementation plan

## Architecture and release criteria

1. `ToolCatalogSource` separates authoritative catalog ingestion from tool execution.
2. `MCPToolCatalogSource` uses the official async SDK over Streamable HTTP or explicit argv stdio; `StaticToolCatalogSource` supports offline hosts.
3. `CatalogCache` uses monotonic time, single-flight locks, source identity, and principal partitions. Public reuse follows an explicit server hint only.
4. Snapshots retain original `ToolSchema` contracts and fingerprints. Cursor loops and catalog/schema bounds fail closed.
5. FULL and MEASURE_ONLY plans are stable. SELECTIVE is opt-in research only and retains conservative fail-open selection.
6. Hydration rejects changed catalogs or tool fingerprints. The host retains argument validation, authorization, and execution.
7. A generic bridge and an optional OpenAI Agents SDK `FunctionTool` bridge are data/host-callback adapters, never an agent loop.

## Success gates

| Gate | Required result |
| --- | --- |
| Local MCP fixture/integration correctness | 100% pass |
| Cache TTL, scope, and private isolation | 100% pass |
| Stale plan and authoritative hydration | 100% pass |
| Provenance boundary regressions | 0 violations |
| Tests | 0 failures |
| Coverage | at least 90% |
| Ruff and MyPy | pass |

Remaining work before a release decision: execute the full clean-install, SDK transport, package, benchmark, and regression matrix; wire change notifications only after an SDK-supported invalidation path is tested.

