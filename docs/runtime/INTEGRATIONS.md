# Runtime integrations

## Generic Python agent

`await runtime.prepare(...)` returns `PreparedContext`. Pass
`generic_request(prepared)` to a host-owned model caller only when
`prepared.feasible` is true. See
[the two-turn example](../../examples/agent_context_runtime.py).

## Sessions

`async with runtime.session("session-id") as session:` opts into process-local,
bounded history. `session.prepare(user_input, ...)` stores the user turn after
a feasible plan. The host should call `session.record("assistant", answer)`
after its model completes. No database or cloud is required. Direct
`runtime.prepare(session_id=...)` is stateless.

## Sarvam

`sarvam_messages(prepared)` produces the message list consumed by the
existing `SarvamProvider.chat` method. The host creates the provider and owns
its key, quotas, and call. Preparing context never calls Sarvam. Model profile
prices are dated estimates; provider usage is a separate reported value.

## OpenAI-compatible and OpenAI Agents SDK

`openai_compatible_request(prepared)` returns detached messages and raw tool
schemas without making a call. For text-only OpenAI Agents conversations,
install `llmslim[agents]` and use
`RunConfig(call_model_input_filter=make_openai_agents_input_filter(runtime))`.
The SDK calls the hook immediately before each model call, including calls
after it merges its session history. The hook preserves SDK instructions and
returns `ModelInputData`; tool execution remains with the SDK/host. Complex
SDK items fail closed until a contract-safe adapter is available. See the
[runnable example](../../examples/openai_agents_context_runtime.py) and the
[current SDK hook documentation](https://openai.github.io/openai-agents-python/running_agents/#call-model-input-filter).

## MongoDB and Zoho

Pass an explicitly configured `MongoDBContextSource`,
`ZohoCRMContextSource`, or `ZohoWorkDriveContextSource` in
`context_sources=(source,)` to `await runtime.prepare(...)`. The runtime
retrieves bounded candidates and demotes their provenance to untrusted RAG.
MongoDB storage remains explicit through `MongoDBContextStore.save`; the
runtime never calls it automatically. Zoho OAuth and read-only field
allowlists remain with the existing source classes. See the existing
[MongoDB](../integrations/MONGODB.md) and
[Zoho](../integrations/ZOHO.md) guides.

## CLI and Studio

`llmslim context inspect|plan|trace|graph context.json --json` gives local
machine-readable diagnostics. `inspect` and `trace` omit prompt content by
default; `plan --include-content` explicitly includes it. Studio's Context
Inspector uses the same runtime through a bounded offline Python endpoint.
It makes no model call.
