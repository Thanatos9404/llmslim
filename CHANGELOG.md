# Changelog

All notable changes to `llmslim` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
