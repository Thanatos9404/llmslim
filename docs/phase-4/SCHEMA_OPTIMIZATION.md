# Schema optimization

Stable API: `llmslim.tools.optimize_tool_schema()` and
`optimize_tool_catalog()`.

The only production operator is `canonical_json_serialization` at safety level
`LOSSLESS_SERIALIZATION`. Its precondition is a bounded JSON-shaped tool
definition. It deep-copies and recursively orders object keys, preserving all
arrays and scalar values. Its verification requires `EXACT` complete-contract
equivalence. It is pure and idempotent; a verification failure rolls the
candidate back and is recorded as a warning.

This deliberately excludes description paraphrasing, redundant-keyword
elimination, `$ref` rewriting, enum/default changes, metadata stripping, and
JSON-to-text schema compilation. Those may reduce prompt tokens but do not have
a general contract-equivalence proof and are not shipped as production
optimization.

Token accounting records two values: source/default JSON serialization and
canonical compact serialization. The Phase 2 schema-tax baseline already uses
compact canonical JSON; therefore its measured Phase 4 lossless reduction is
expected to be zero, not hidden behind a misleading reserialization baseline.
