# Agent / tool schema-tax research track

This is a measurement track, not a shipped LLMSlim feature.  A community member
reported an approximately 875-token schema payload resent on every turn; that is
a motivating anecdote, not an LLMSlim result.  Phase 2 constructs and measures
its own transparent synthetic catalogs.

Tool schemas are contracts.  Phase 2 contract comparison protects tool name,
parameter names and types, required set, enum values, nested shape, constraints,
and meaningful defaults.  Descriptions are deliberately reported separately:
they may affect tool selection or argument generation and are not assumed safe
to discard.  No semantic schema compression, tool gating, lazy loading, or MCP
middleware is exposed by LLMSlim.

## Future directions

| Direction | Savings | Contract safety | Selection risk | Complexity | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Lossless schema minification | Low–medium | High if verified | None | Low | Useful foundation |
| Selective tool loading | High | High after routing | Medium | Medium | Strong candidate |
| Semantic top-k retrieval | High | High after selection | High | Medium | Evaluate against labelled recall |
| Lazy schema hydration | High | High | Medium | High | Consider for agent runtimes |
| Tool-family routing | Medium–high | High | Medium | Medium | Complement retrieval |
| Session-aware caching | High | Protocol-dependent | Low | High | Framework-specific |
| Hybrid | Highest potential | Depends on layers | Medium–high | High | Long-term option |

**Phase 4 recommendation:** start with lossless contract-verified minification
plus an offline relevance evaluation; only then prototype selective loading or
top-k retrieval behind an opt-in, benchmarked integration.  That order is
portable across Python, future TypeScript/WASM, and MCP because the contract
checker stays independent of runtime transport.
