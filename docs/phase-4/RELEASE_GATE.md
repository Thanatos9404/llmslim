# Phase 4 release gate

| Gate | Result | Evidence |
| --- | --- | --- |
| RESEARCH | PASS | Official MCP, JSON Schema, OpenAI, Anthropic, and external-work research in `RESEARCH.md`. |
| SCHEMA MODEL | PASS | Provider-aware `ToolSchema`; raw unknown fields retained. |
| CANONICALIZATION | PASS | Deterministic key ordering, compact JSON, arrays preserved. |
| FINGERPRINTING | PASS | Full canonical raw SHA-256; extension-sensitive tests. |
| LOSSLESS OPTIMIZATION | PASS | One idempotent exact-verified serialization operator. |
| CONTRACT VERIFICATION | PASS | Production only accepts `EXACT`; no claimed general semantic proof. |
| MCP 2026 COMPATIBILITY | PASS | `inputSchema`, `outputSchema`, `_meta`, annotations, extensions, compositions, refs tested. |
| OPENAI TOOL COMPATIBILITY | PASS | Current/nested function adapter round trips tested. |
| ANTHROPIC TOOL COMPATIBILITY | PASS | `input_schema` adapter round trip tested. |
| SCHEMA TAX BENCHMARK | PASS | 18 Phase 2 catalogs / 375 schemas measured. |
| RELEVANCE ENGINE | PASS | Offline deterministic TF-IDF with measured Recall/Precision/MRR. |
| SELECTIVE EXPOSURE | PASS — EXPERIMENTAL | Meets declared curated-fixture threshold; never automatic. |
| LAZY HYDRATION | PASS — EXPERIMENTAL | Deep-copied in-memory authoritative registry only. |
| SECURITY | PASS | No remote `$ref`, code, regex, or schema execution; bounds and collision guards tested. |
| BACKWARD COMPATIBILITY | PASS | `compress()` unchanged; v0.2/v0.3 regressions pass. |
| TESTS | PASS | 453 passed / 0 failed. |
| COVERAGE | PASS | 91.04% branch coverage (minimum 90%). |
| LINT | PASS | `ruff check llmslim benchmarks tests`. |

## Final status: CONDITIONAL PASS

Stable contract-safe serialization and fingerprinting are ready for a public
minor API release. Selective exposure and lazy hydration remain experimental;
their curated-fixture result is not a production reliability guarantee.

## Release recommendation

**v0.4.0 if the owner elects to release.** New public functionality under the
intentional `llmslim.tools` namespace is a backward-compatible feature addition,
which is semantically a minor release. No version, tag, publication, or push
was performed here.
