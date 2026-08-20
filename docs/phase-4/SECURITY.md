# Phase 4 security boundaries

Tool definitions are untrusted data. Phase 4 never evaluates descriptions,
examples, defaults, patterns, schema values, metadata, or extensions as code.
It neither executes regexes nor fetches external `$ref` URLs. `inspect_schema`
records non-local references as warnings and optional JSON Schema syntax checks
never enable a remote resolver.

Bounds reject non-JSON values, non-finite numbers, excessive depth (64), more
than 10,000 nodes, and oversized strings. Duplicate stable tool identities are
rejected. Arrays are never reordered. Unknown fields, `_meta`, and `x-*`
extensions remain in the authoritative raw definition.

Tool annotations are not used for ranking or authorization because current MCP
guidance treats annotations from untrusted servers as unsafe decision inputs.
The context planner only changes explicit model exposure; execution must keep
using the caller's complete authoritative contracts and ordinary authorization,
input validation, output validation, and least-privilege controls.

Phase 4 does not change `compress()` or `ContextRole`; Phase 1 provenance
security tests remain part of the full regression suite.
