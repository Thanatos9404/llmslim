# Changelog

All notable changes to `llmslim` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.7.0] - 2026-09-26

### Added
- Added `ContextEnvelope`, a deterministic `ContextGraph`, progressive
  quality-gated planning, local `ContextPolicy`, `ContextRuntime`, bounded
  in-memory sessions, and prompt-free local `ContextTrace`.
- Added execution-free generic, Sarvam, OpenAI-compatible, and text-only
  OpenAI Agents SDK input adapters. The existing APIs and planner remain
  available unchanged.
- Added a Studio Context Inspector, offline context CLI, a frozen 112-case
  five-baseline benchmark, and opt-in live Sarvam/OpenAI evaluation harness.
- Tagged and hash-pinned the 0.7.0 wheel for Studio server functions so they
  install the matching runtime without depending on a previous package release.

### Verification
- Local release candidate: 623 tests passed, three optional MCP skips,
  90.20% branch coverage, Ruff passed, a scoped MyPy check passed, and
  wheel/sdist built. Hosted deployment and live-provider evaluation remain
  release gates.

## [0.6.0] - 2026-09-20

### Added
- Added deterministic multiple-choice context allocation across trusted
  instructions, chat, RAG, memory, tool results, and authoritative tool
  schemas, with explainable decisions and explicit infeasibility.
- Added balanced, quality-first, cost-first, and latency-first policies,
  conservative post-plan validation, local metrics, estimated cost telemetry,
  and stable `plan_context()` / `AdaptiveContextPlanner` APIs.
- Added `llmslim plan`, unified `ContextSource` / `ContextStore` boundaries,
  runnable examples, migration guidance, and dedicated planning documentation.

### Changed
- Retained the existing `compress()` family while positioning compression as
  one representation mechanism inside complete-context planning.
- Raised the declared minimum Python version from 3.8 to 3.9 so packaging
  metadata matches the tested CI matrix and source/tooling baseline.

### Security
- Added a disabled-by-default hosted Sarvam control plane with HMAC-pseudonymous
  network/session identities, distributed sliding rate windows, repeated
  high-cost request detection, atomic token and spend reservations, expiring
  concurrency slots, strict payload ceilings, safe errors, aggregate-only
  telemetry, and an environment kill switch.
- Preserved provenance hard constraints, authoritative tool schemas, no tool
  execution, no automatic persistence, and no browser/provider key exposure.

### Integrations
- Added optional official-SDK Sarvam rewrite/chat support and dated INR model
  profiles for `sarvam-105b` and `sarvam-105b-conversations`.
- Added bounded read-only Zoho CRM/WorkDrive sources and explicit PyMongo async
  memory/Atlas retrieval. External content remains untrusted by default.
- Added a separate MongoDB operational ledger for hosted rate, token, spend,
  concurrency, and aggregate telemetry records; local LLMSlim needs no database.
- Added a data-only MCP bridge. FULL and MEASURE_ONLY remain stable;
  SELECTIVE remains explicit and experimental and never executes tools.

### Benchmarks
- Added a 28-case frozen multilingual offline planner benchmark across chat,
  RAG, tools, mixed context, mocked external sources, and 12 languages.
- Added a separately gated live Sarvam harness; normal tests never spend credits
  and no live result is claimed without a sanitized measured artifact.

### Web/Studio
- Added Offline Planner and quota-limited Hosted Sarvam modes, planner decision
  traces, final answers, and clearly separated `ESTIMATED` versus
  `PROVIDER_REPORTED` usage/cost telemetry.
- Added same-origin Vercel and Catalyst server routes. Hosted mode remains off
  until the key, durable quota store, HMAC secret, and budgets are configured.

### Packaging
- Added optional `sarvam`, `zoho`, and `mongodb` extras while preserving
  `semantic`, `mcp`, and `agents`; the combined `all` extra includes each.
- Kept MCP Streamable HTTP on the official MCP 2.x `httpx2` transport and
  declared that directly imported client in the MCP/Agents extras.

### Known limitations
- MCP SELECTIVE remains experimental and opt-in.
- Offline benchmark checks are task-grounded but are not a universal model
  quality claim. Live Sarvam metrics are absent unless the paid harness runs.
- Hosted inference depends on operator-configured MongoDB, provider/platform
  alerts, production secrets, and explicit activation; it is not unlimited.

## [0.5.0] - 2026-09-13

### MCP catalog integration
- Added optional `llmslim[mcp]` support for official-SDK Streamable HTTP and
  argv-only stdio catalog sources, bounded `tools/list` pagination, monotonic
  cache hints, immutable snapshots, and stale-plan-safe hydration.
- Added stable full-catalog and measure-only plans. Selective exposure remains
  explicit, opt-in, and **RESEARCH_ONLY**.
- Added a framework-neutral host bridge and an optional OpenAI Agents SDK
  bridge. Both preserve host authorization and execution ownership.

### Packaging and security
- Kept MCP and Agents SDK dependencies out of the base install; the extras
  require Python 3.10+.
- Rejected credential-bearing endpoint URLs and non-localhost HTTP; stdio
  sources take an executable plus literal argv and never invoke a shell.

---

### Fixed
- Refreshed catalogs revoke stale cache entries, and returned snapshots cannot mutate cached authority.
- Agents bridges reject mismatched plans and hydrate authoritative schemas before exposing tools.

### Website
- Redesigned responsive landing page, dark/light themes, restrained parallax, and official Sarvam co-branding.
- LLMSlim is accepted into the Sarvam Startup Program; existing indexing routes are preserved.

## [0.4.0] - 2026-08-20

### Tool contract infrastructure
- Added provider-aware `ToolSchema` representations and adapters for supported
  MCP, OpenAI function, Anthropic, and generic tool shapes.
- Added deterministic canonical JSON serialization, complete-contract SHA-256
  fingerprints, conservative exact-equivalence verification, schema
  inspection, and safe catalog optimization.
- Preserved authoritative raw schemas: stable infrastructure operates on copied
  representations and does not authorize, execute, or rewrite a contract.

### Experimental tool-context retrieval
- Added deterministic TF-IDF and BM25 retrievers, catalog-fingerprint caches,
  and conservative full-catalog fail-open behavior.
- Added optional local-only multilingual dense retrieval and BM25+dense RRF
  using `intfloat/multilingual-e5-small` at pinned revision
  `0e60b8d9d2166d80387f86e3b48ec9ced55f4d15`.
- Retrieval, selective exposure, context planning, and lazy hydration remain
  **RESEARCH_ONLY**; they are never enabled automatically.

### Benchmarks
- Added Phase 4 measurements for 375 schemas across 18 catalogs. Lossless
  serialization saved 0 tokens because the baseline was already compact
  canonical JSON.
- Added frozen-corpus Phase 4.5/4.6 retrieval evaluation. Dynamic retrieval
  retains high all-required recall by failing open often and has zero median
  tokens avoided, so it is not a production optimization claim.
- External ToolRet validation was attempted but not completed within the
  declared CPU/resource budget; no external metric is claimed.

### Security
- Retrieval representations exclude tool annotations and `_meta` where
  applicable; remote references are not fetched automatically.
- Ranking is not authorization and does not execute tools. Caller/provider
  provenance remains unauthenticated by LLMSlim.

### Packaging
- Added `jsonschema` for stable schema inspection and retained semantic
  dependencies behind the optional `llmslim[semantic]` extra.

## [0.3.1] - 2026-08-13

> Verified release: 432 tests passed, 0 failed; 92.57% branch coverage;
> Ruff passed; `benchmark.py` reported 432 passed / 0 failed.

### Security
- **Provenance-aware priority locking (P0-1, CVSS 9.1 mitigation).** Added a
  `ContextRole` trust boundary (`system`/`developer`/`user`/`assistant`/`tool`/
  `rag`/`general`). Untrusted content (`rag`/`tool`/`assistant`) can no longer
  reach the hard-locked Priority Tier 4 or become `must_keep` from imperative
  wording, safety patterns, **or** `preserve_patterns` — closing the indirect
  prompt-injection amplification path. Trusted `system`/`developer` content
  retains full protection. This *mitigates compression-induced instruction
  elevation*; it is **not** complete prompt-injection prevention (defense in
  depth still required).
- **Rewrite template fence-breakout protection (P1-1).** A literal
  `---END TEXT---` (etc.) inside user text can no longer terminate the template's
  content region. Uses a content-preserving nonce fence: user text is passed
  **byte-for-byte unchanged**; only the template's own delimiters are hardened.

### Added
- `ContextRole` enum (exported from `llmslim`) and a `context_role` parameter on
  `compress()` / `ContextCompressor` (string or enum accepted).
- `CompressionResult.token_counter_used` (`"tiktoken"` | `"heuristic"`) and
  `tokens.get_active_token_counter_name()` (P1-4).
- Inline backtick code-span protection in sentence splitting (P0-2).
- CJK ideographic sentence boundaries `。` / `！` / `？` (P1-2).

### Changed (intentional behavioural changes — NOT 100% backward compatible)
- **`compress_documents()` now defaults to `context_role=ContextRole.RAG`.**
  Imperative sentences in retrieved documents are no longer force-kept.
- **`compress_chat_messages()` now propagates each message's role** as
  provenance (`system`→SYSTEM, `developer`→DEVELOPER, `user`→USER,
  `assistant`→ASSISTANT, `tool`→TOOL; unknown→GENERAL). No silent collapse.
- `count_tokens()` emits a one-time `logging.warning` when falling back to the
  character heuristic (P1-4).

### Fixed
- **Benchmark runner (P0-3).** `benchmarks/benchmark.py` now reports the real
  pytest pass/fail counts via a result-collector plugin instead of hardcoded
  `(159, 0)` / `(154, 5)` tuples, eliminating the false 5-failure result.

### Removed
- Dead code (P1-3): unused `_select_for_chunk()`, `_knapsack_select()`, and
  `_greedy_select()` static methods in `core.py`.

### Backward compatibility
- The default `compress(text, ...)` call (role `GENERAL`) is byte-for-byte
  identical to v0.3.0.

---

## [0.3.0] - 2026-07-18


### Added
- **Hybrid Prompt Compression & Semantic Optimization**: Extended `compress()` with `strategy` parameter supporting `"extractive"` (default), `"rewrite"`, and `"hybrid"` strategies.
- **Provider Abstraction Layer**: Zero-dependency `BaseRewriteProvider` ABC and `CallableProvider` wrapping custom functions or LLM APIs without hardcoding external dependencies.
- **Future-Proof `RewriteRequest`**: Clean request object interface passing text, target ratio, content type hints, prompt constraints, and metadata to providers.
- **Multi-Stage Semantic Validation Pipeline**: 4 independent validators (`StructuralValidator`, `InstructionValidator`, `EntityValidator`, `BaseSimilarityValidator`) ensuring rewrites never compromise prompt fidelity.
- **Pluggable Similarity Validation**: `BaseSimilarityValidator` interface with default offline `TfidfSimilarityValidator` (replaceable by embedding models or custom metrics).
- **Versioned Prompt Templates**: Builder functions (`build_general_template`, `build_rag_template`, `build_chat_template`, `build_system_prompt_template`, `build_documentation_template`, `build_code_template`) and `TemplateResolver` for domain-specific prompt generation.
- **Grouped `RewriteMetadata`**: Clean telemetry grouping inside `CompressionResult` for strategy outcomes, validation scores, latency, and failure reasons.
- **Strategy Benchmarking**: Benchmark framework extension in `benchmarks/benchmark_rewrite.py` measuring token reduction, latency, instruction/entity retention, and Validation Failure Rate.
- **CLI Strategy Parameter**: CLI `-s` / `--strategy` flag supporting `extractive`, `rewrite`, and `hybrid` modes.

### Changed
- Refactored rewrite functionality into isolated `llmslim.rewrite` sub-package (`base`, `engine`, `templates`, `validation`).
- Top-level `__init__.py` clean exports for `BaseRewriteProvider`, `CallableProvider`, `RewriteRequest`, `RewriteEngine`, `RewriteMetadata`, `RewriteValidator`, and `ValidationResult`.

### Improved
- Single-responsibility architecture separating prompt construction (`TemplateResolver`), execution (`RewriteEngine`), and validation (`RewriteValidator`).
- Improved error handling in `RewriteEngine` to automatically catch provider exceptions and fall back to extractive compression.

### Performance
- Extractive mode performance remains untouched (< 5ms CPU overhead for standard prompts).
- Hybrid mode executes fast extractive pre-compression to reduce tokens before optional LLM provider invocation.

### Testing
- Comprehensive test suite expansion with 130+ new test assertions across `test_providers.py`, `test_templates.py`, `test_validation.py`, `test_rewrite.py`, and `test_v03_regression.py`.
- Maintained > 90% code coverage (92.42% measured across 22 source modules).

### Documentation
- Created `examples/rewrite_example.py` demonstrating extractive, rewrite, and hybrid strategy workflows.
- Created `examples/custom_provider_example.py` showing custom `BaseRewriteProvider` subclassing.
- Updated `README.md` quickstart, CLI options, and feature tables.

### Backward Compatibility
- 100% backward compatible with v0.2.0. Default `strategy="extractive"` remains offline, deterministic, and byte-identical. Existing code calling `compress(text, target_ratio=0.5)` continues working without changes.

### Migration
- No code changes required for upgrading from v0.2.0 to v0.3.0 when using default extractive compression.
- To enable semantic rewriting, pass `strategy="rewrite"` (or `"hybrid"`) and supply a `provider=` parameter (e.g. `CallableProvider(my_llm_func)`).

### Known Limitations
- Semantic rewrite strategy requires user-supplied `provider=` parameter since core `llmslim` carries zero external LLM SDK dependencies.
- Lexical TF-IDF similarity validator may require a custom `BaseSimilarityValidator` implementation when validating heavily paraphrased text.

---

## [0.2.0] - 2026-07-13

### Added
- **Instruction Retention Engine**: Automatically extracts and prioritizes explicit user instructions, System Prompts, Markdown headers, code block delimiters, and task constraints.
- **Named Entity Preservation**: Integrated regex and heuristic entity recognition for proper names, dates, financial metrics, technical identifiers, and URLs.
- **Semantic & Hybrid Chunking**: Sliding-window semantic boundary splitting with dynamic fallback to paragraph/sentence boundaries.
- **Multi-Model Embeddings Support**: Optional integration with `sentence-transformers` alongside TF-IDF / N-gram fallback ranking.
- **Model Cost Estimation**: `cost.py` utility for calculating token savings and USD cost reduction across OpenAI (GPT-4o, O1), Anthropic (Claude 3.5 Sonnet), and Google (Gemini 1.5 Pro) models.
- **CLI Interface**: Interactive and file-based CLI tool (`llmslim input.txt -o compressed.txt --ratio 0.5`).
- **Comprehensive Benchmarks**: Benchmark regression suite, quality evaluation on multi-domain prompt datasets, and memory profile tooling.

### Improved
- Extractive sentence ranking using TF-IDF + PageRank sentence centrality.
- Token calculation accuracy using fallback word-token estimation and optional `tiktoken` exact token counting.
- Speed performance: Reduced compression overhead to < 5ms for 4k-token prompts.

### Changed
- Standardized `CompressionResult` output dataclass with detailed telemetry (original tokens, compressed tokens, compression ratio, preserved instructions count, entity count, processing time).

### Breaking Changes
- None. Fully backward compatible with `v0.1.0`.

### Known Limitations
- High-ratio compression (> 80%) on technical code snippets may drop syntactically dependent variable declarations if instructions are not explicitly flagged.

---

## [0.1.0] - 2026-06-16

### Added
- Initial public release of `llmslim`.
- Basic prompt compression engine with static ratio parameters.
- Basic TF-IDF sentence scoring and thresholding.
- Python 3.8+ package structure.
