# LLMSlim v0.3.1 — Security Hardening and Core Correctness

**Release date:** 2026-08-13

## What changed

v0.3.1 adds provenance-aware priority locking, inline-code and CJK sentence-boundary handling, nonce-protected rewrite-template fences, token-counter telemetry, a corrected benchmark test collector, and removes obsolete selection helpers.

## Why it matters

Earlier priority handling could treat imperative-looking untrusted retrieved or tool text as protected context. v0.3.1 adds `ContextRole` provenance to the scoring path so that compression decisions account for who authored the content.

## Security

LLMSlim mitigates compression-induced instruction elevation by preventing untrusted RAG/tool/assistant content from gaining protected priority through imperative or safety-critical wording.

- `RAG`, `TOOL`, and `ASSISTANT` are capped at Tier 2 and cannot become `must_keep`.
- `SYSTEM` and `DEVELOPER` remain trusted caller-provided roles.
- `USER` is semi-trusted; `GENERAL` preserves the legacy default path.
- Payload text containing a rewrite-fence-like token is embedded unchanged between nonce-tagged template fences.

This is not complete prompt-injection prevention. LLMSlim trusts caller-provided provenance labels and applications still need defense in depth.

## Correctness

- Inline backtick code spans no longer introduce false sentence boundaries.
- CJK `。`, `！`, and `？` punctuation is recognized by both fallback and NLTK post-processing paths.
- `CompressionResult.token_counter_used` reports `tiktoken` or `heuristic`.
- The heuristic fallback emits one warning per process.
- The benchmark runner reports actual pytest outcomes.
- Unused DP/greedy selection helpers were removed.

## Verification

- 432 tests passed; 0 failed.
- 92.57% branch coverage.
- Ruff passed.
- `python benchmark.py` reported 432 passed / 0 failed and reliability 100/100.

## Migration notes

No change is needed for default `compress(text)` callers.

Two intentional pipeline changes apply:

1. `compress_documents()` now defaults to `ContextRole.RAG`.
2. `compress_chat_messages()` propagates each message role; system messages stay uncompressed by default.

If a caller has authenticated provenance and needs a different treatment, pass an explicit `context_role`.

## Availability

v0.3.1 is a Python release. npm, Rust, and WASM runtimes are not shipped.
