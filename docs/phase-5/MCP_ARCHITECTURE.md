# MCP architecture

```text
trusted configured MCP server
        │ official SDK client (HTTP / argv stdio)
        ▼
MCPToolCatalogSource → CatalogCache → ToolCatalogSnapshot → CatalogContextPlan → host adapter
                                                        │                         │
                                                        └─ hydrate full raw schema ┴─ host executor only
```

LLMSlim performs no `tools/call` operation. Model-facing plans are not authorization decisions. The host/agent framework owns user approval, argument validation, and execution.

