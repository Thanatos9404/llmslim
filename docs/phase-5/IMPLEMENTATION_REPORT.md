# Implementation report

Implemented: asynchronous MCP and static catalog sources; official-SDK Streamable HTTP and argv-only stdio transport factories; bounded pagination; monotonic single-flight source cache; private/public isolation; immutable snapshots; full/measure/selective plans; full-schema hydration with stale detection; caller-local events/metrics; offline catalog CLI inspection; an optional host-callback OpenAI Agents SDK bridge; and a 60-task benchmark artifact that separates deterministic integration availability from live-model success.

Intentionally excluded: an agent loop, automatic authorization, automatic tool calls, prompt-derived endpoints, hosted credentials in Studio, SSE-first support, telemetry, release/publishing changes, and promotion of retrieval out of research-only status.
