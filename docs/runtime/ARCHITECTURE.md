# Agent Context Runtime architecture

LLMSlim prepares model-visible context on each agent turn. The host owns the
agent loop, authentication, model call, tool authorization/execution, and
credentials. The runtime performs no cloud I/O unless the host explicitly
passes a context source, and it never persists a prompt automatically.

```text
Host messages / RAG / memory / tool results / authoritative schemas
    -> ContextEnvelope (copied, typed ContextItems)
    -> ContextPolicy (source, age, cap, redaction)
    -> ContextGraph (deterministic evidenced edges)
    -> Planner 2.0 (raw first, bounded candidate frontier under pressure)
    -> QualityReport + ContextPlan (or explicit infeasible status)
    -> ModelInput + local ContextTrace
    -> host-selected provider adapter -> host model call
```

`ContextEnvelope.from_inputs` reuses the v0.6 `ContextItem`, `ContextKind`, and
`ContextRole` model. It copies metadata, rejects credential-named metadata and
unsafe IDs, and limits one envelope to 512 items. Runtime planning currently
limits an envelope to 256 items. `ContextEnvelope.to_dict()` omits prompt
content and hashes item IDs by default.

`ContextGraph` has at most 512 nodes and 4096 edges. Caller-declared
`depends_on`, `derived_from`, `reply_to`, and `memory_source_id` metadata must
name actual item IDs. Explicit tool-call IDs and matching tool-result IDs
produce call/result dependencies. Equal declared entity IDs produce diagnostic
`SAME_ENTITY` edges. Only dependency edge types affect closure; a graph edge
never changes trust or authorization. Cycles are safe and closure is bounded.

Planner 2.0 starts from raw items. When raw context fits, it skips expensive
candidate generation. Under budget pressure it reuses the v0.6 extractive
candidate generator, considers at most eight candidates per item, and takes
the next reduction with the lowest utility loss per token saved (or the
objective's explicit variant). It rejects candidates that fail their named
validation metrics, the caller quality floor, numerical fact retention, or
known dependency closure. System and developer instructions and authoritative
tool schemas stay raw. A single evidence item for a query is not dropped.
If no safe sequence fits, the plan is `INFEASIBLE`; no content is truncated.

`QualityReport` exposes trusted-instruction, required-fact, numerical-fact,
entity, semantic, conversation, structural, dependency, tool-contract, and
query-relevance checks separately. Query overlap is diagnostic because lexical
matching is weak on some multilingual content. These
local checks cannot prove downstream answer quality. `ContextTrace` records
hashed item IDs, methods, counts, timing, costs, and safe reason categories;
it does not contain prompt bodies, raw item IDs, or session IDs. Token counts
remain estimates until a provider reports actual usage. Pricing is read from
the existing dated model profiles and is not embedded in the planner.

`ContextRuntime.prepare_sync()` is deterministic for fixed input aside from
timings and creation timestamps. `prepare()` retrieves explicitly configured
sources asynchronously, demotes all returned items to untrusted RAG evidence,
then uses the same local planner. Direct `prepare(..., session_id=...)` does
not persist messages. `runtime.session(id)` explicitly opts into bounded
in-memory history; it records the current user turn only after a feasible
plan. The host records assistant responses with `session.record(...)`.
`clear_session(id)` removes the runtime's reference to that history.

The original `plan_context()` continues to use the untouched v0.6 planner.
Its 28-case benchmark is frozen separately from the v0.7 corpus.
