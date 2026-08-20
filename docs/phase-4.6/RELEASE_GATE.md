# Phase 4.6 release gate

## Decision: CONDITIONAL PASS; retrieval remains RESEARCH_ONLY

- Frozen Phase 4.5 corpus/split: **PASS** (hash guard).
- Optional dependency, offline local-only loading, schema authority, metadata/
  annotation exclusion, deterministic RRF, and full-catalog fail-open: **PASS**.
- Dense and hybrid implementation/fixed-k/dynamic evaluation: **PASS**.
- No-tool: **PASS** on frozen and robustness cases.
- Semantic selectivity frontier: **FAIL**. Neither dense nor RRF reduces
  fail-open or produces positive median token savings versus BM25.
- Multilingual robustness: **PARTIAL**. The selected model accepts the four
  tested languages, but the small suite lacks the breadth for a product claim.
- ToolRet: **PARTIAL**, attempted from official pinned datasets but not completed
  within the measured CPU/memory budget; no external score is claimed.

Stable Phase 4 schema APIs remain suitable for the v0.4.0 package decision;
the retrieval result does not block a release by itself. Recommendation:
**RELEASE v0.4.0 only with tool-schema APIs stable and retrieval explicitly
opt-in RESEARCH_ONLY**. Do not change version, tag, publish, push, or deploy.
