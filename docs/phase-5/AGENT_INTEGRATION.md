# Agent integration

Use `HostToolAdapter` for provider-neutral model schemas and checked hydration. The optional `llmslim.integrations.openai_agents.to_openai_agents_tools()` converts a plan to Agents SDK `FunctionTool` objects, but requires the caller to pass an async host invoker. LLMSlim never supplies an MCP executor or agent loop.

Hosted MCP/tool-search features in OpenAI infrastructure solve a different problem: they defer or execute a provider-hosted surface. LLMSlim’s value here is local catalog measurement, contract fingerprints, and host-owned execution boundaries.

