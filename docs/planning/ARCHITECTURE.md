# Adaptive Context Planner architecture

LLMSlim v0.6 is a local-first context optimization layer. Fixed-ratio
`compress()` remains supported, but `plan_context()` can jointly allocate a
finite input budget across chat, RAG, memory, tool results and tool schemas.

## Boundaries

1. Callers and optional `ContextSource` adapters produce provenance-bearing
   `ContextItem` values.
2. The planner normalizes copied inputs and computes deterministic, explainable
   scores. It does not authenticate sources.
3. Each item receives safe candidate representations: raw, validated
   extractive compression, optional provider rewrite/hybrid, and drop only when
   policy and provenance permit it.
4. A multiple-choice budget allocator selects one representation per logical
   item while preserving order and hard constraints.
5. Validation checks the budget, required/trusted retention, ordering,
   candidate validation and authoritative tool fingerprints. An unsafe
   compressed choice falls back conservatively.

External I/O is isolated behind `ContextSource`, `ContextStore`, and rewrite
provider interfaces. The synchronous planner remains deterministic and needs
no cloud dependency. `AdaptiveContextPlanner.aplan()` only adds concurrent,
bounded source retrieval before calling the same planner.

## Optional hosted inference boundary

`llmslim.hosted` is an application-control layer, not part of offline planning.
Studio's `/api/sarvam` route validates and rate-checks a request, creates a
normal `ContextPlan`, reserves conservative token/spend quota, acquires an
expiring concurrency lease, and only then calls `SarvamProvider.chat()`.

`MongoDBHostedQuotaStore` uses a dedicated operational collection. Atomic
conditional updates implement sliding network/session windows, daily identity
tokens, daily/monthly project cost, and concurrency slots. Request identities
and repeated-request fingerprints are HMAC-pseudonymous; raw prompts, IPs,
cookies, and credentials never enter the collection. This ledger is separate
from `MongoDBContextStore` and does not make MongoDB mandatory for local users.

Paid inference is unavailable unless the explicit kill switch, provider key,
durable store, and identity HMAC secret are all configured. Any pre-call store
failure is fail-closed. Provider-reported usage reconciles the reservation;
when post-call reconciliation is unavailable, conservative estimated accounting
remains charged so an answer can be returned without encouraging a retry.

## Trust and ownership

`ContextRole` is the single trust vocabulary. System and developer content are
trusted; retrieved documents, database records, tool output and prior assistant
text do not become trusted because of wording or metadata. LLMSlim ranks and
formats context; the host retains authorization, tool execution, model calls,
persistence and data-retention policy.

MCP integration produces a data-only `MCPAdaptiveContextPlan`. Stable FULL and
MEASURE_ONLY behavior remains the production default. SELECTIVE is explicit,
experimental, fingerprint-checked, and hydrates only from the authoritative
snapshot. The planner never executes a tool.

## Data and telemetry

`ContextPlan` is an immutable audit record containing decisions, metrics,
warnings, fallbacks and validation. Use `to_dict(include_content=False)` for a
content-free trace; MongoDB trace persistence does this by default. Metrics are
local only. Token and cost values are labeled estimates; provider usage is
recorded separately by integrations.
