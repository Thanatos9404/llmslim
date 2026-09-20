# LLMSlim v0.6.0 — Adaptive context planning

**Release date:** 2026-09-20

LLMSlim now plans heterogeneous application context against explicit model
budgets while retaining its established compression APIs. See
`docs/releases/v0.6.0.md` for full notes and
`docs/releases/v0.6.0-MIGRATION.md` for adoption guidance.

Studio includes an offline planner and an optional Sarvam-hosted mode. Hosted
mode is disabled by default and requires a server-only provider key, durable
MongoDB quota ledger, pseudonymous network/session rate limits, token and
concurrency ceilings, atomic daily/monthly spend reservations, strict payload
limits, aggregate-only telemetry, and an emergency environment kill switch.
BYOK is deliberately absent from the public UI. Python 3.9 is the new declared
minimum, matching the tested CI matrix.

---

# LLMSlim v0.4.0 — Tool-aware context, without rewriting the contract

**Release date:** 2026-08-20

## What changed

LLMSlim now has stable infrastructure for representing, inspecting,
canonicalizing, fingerprinting, verifying, and measuring supported tool
contracts without modifying the authoritative execution schema. The release
also includes experimental retrieval research, kept separate from stable APIs.

## Stable tool-schema infrastructure

- `ToolSchema` provider normalization for supported MCP, OpenAI function,
  Anthropic, and generic tool definitions.
- Deterministic canonical JSON and complete-contract SHA-256 fingerprints.
- Exact-equivalence verification and safe catalog optimization.
- Raw-schema preservation: the caller/executor remains authoritative.

## Experimental tool retrieval

**RESEARCH ONLY — NOT ENABLED AUTOMATICALLY.**

TF-IDF, BM25, optional `intfloat/multilingual-e5-small` dense retrieval,
BM25+dense RRF, selective exposure, and lazy hydration are model-context
planning experiments. They do not authorize or execute a tool. Low-confidence
policies fail open to the full catalog.

Install the optional local semantic support with:

```bash
pip install "llmslim[semantic]"
```

The normal `pip install llmslim` path stays lightweight. The semantic model is
pinned to revision `0e60b8d9d2166d80387f86e3b48ec9ced55f4d15`, is loaded from
an explicit local cache only, and is not included in package artifacts.

## Benchmark findings

Phase 4 measured 375 schemas across 18 catalogs. Lossless serialization
reduced the compact canonical baseline by 0 tokens (0.00%); the baseline was
already compact, so this is a valid result rather than a hidden failure.

Phase 4.5/4.6 retrieval results are research evidence, not marketing claims.
On the frozen corpus, BM25 had 98.25% all-required recall with 25.89%
selective coverage; dense and hybrid reached 98.54% recall but failed open
more often and avoided fewer tokens. Median tokens avoided was zero for every
strategy. The safety–selectivity frontier did not improve.

External ToolRet validation was attempted but not completed within the declared
CPU/resource budget. No ToolRet score is claimed.

## Security boundaries

Authoritative schemas remain authoritative. Ranking is not authorization;
tool annotations and `_meta` are untrusted for retrieval representation where
excluded, remote references are not fetched automatically, and LLMSlim does
not cryptographically authenticate caller or provider provenance. It remains
defense in depth, not complete prompt-injection prevention.

## Upgrade

Default `compress()` behavior is unchanged. Tool-contract APIs are available
from `llmslim.tools`; retrieval modules are explicitly experimental. Review
[docs/tool-apis.md](docs/tool-apis.md) and [SECURITY.md](SECURITY.md) before
integrating tool workflows.
