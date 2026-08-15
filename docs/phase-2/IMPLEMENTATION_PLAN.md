# Phase 2 implementation plan

## 1. Current architecture and weaknesses

The legacy `benchmarks/benchmark_*.py` scripts read eight small JSON datasets and
emit human-oriented output.  The Phase 0 audit established that the old quality
judge shares entity/instruction regular expressions with the compressor, stage
timings are partly synthesized, and regression/determinism values are partly
hard-coded.  Their results are not a canonical release artifact.

## 2. Proposed architecture

Phase 2 adds an isolated, offline `benchmarks.evaluation` package for datasets,
metrics, execution, result validation, regression comparison, and reporting;
`benchmarks.schema_tax` for tool-catalog accounting and contract invariants; and
`python -m benchmarks.run` as the single canonical entry point.  Legacy scripts
remain intact for compatibility but are not sources of Phase 2 claims.

## 3. Dataset design

`benchmarks/datasets/phase2_core.json` is a repository-owned synthetic corpus.
Each sample declares category, language, role, provenance, labelled
instructions/entities/numbers/negations, and structure expectations where
applicable.  It covers system, user, RAG, agent, tool, chat, documentation,
technical prose, source code, JSON/YAML/XML/Markdown, tables, numeric/entity/
constraint-dense and short/medium/long contexts, English/Hindi/Chinese/Japanese,
and adversarial security cases.  Tool catalogs and labelled relevance cases are
separate synthetic datasets in `benchmarks/schema_tax`.

## 4. Metric definitions

Token reduction is `(original - compressed) / original`; actual ratio is
`compressed / original`; target-ratio error is `abs(actual - requested)`.
Retention is exact normalized matching against independently authored dataset
labels, never the compressor's patterns.  Structural integrity is parser-based
where an applicable parser is available.  Semantic similarity is a clearly
labelled lexical Jaccard fallback; no model is downloaded.  Latency is repeated
end-to-end wall-clock timing with warmup, reported as mean, median, p95, and
sample count.  Determinism is byte equality over repeated local calls.

## 5. Schema-tax design

The schema track synthesizes realistic simple, medium, and complex function
contracts at catalog scales 1/4/8/16/32/64.  It measures serialized JSON token
payloads, per-tool distribution, description versus structural shares, and
full-catalog per-turn payload.  Multi-turn totals are explicitly `DERIVED` from
the measured per-turn payload.  No schema is compressed or exposed through
LLMSlim's production API.

## 6. Statistics and reproducibility

The local suite uses a recorded seed, deterministic synthetic data, one warmup,
and configurable iterations (FAST defaults to 3, FULL to 7).  It records Python,
platform, architecture, non-identifying processor string when available,
LLMSlim version, commit, dependency versions, and tokenizer backend.  Optional
provider strategies are excluded by default and recorded as not applicable.

## 7. Canonical results and consumers

The versioned JSON result is validated before writing to
`benchmarks/results/latest.json`; timestamped copies are retained under
`benchmarks/results/runs/`.  A deterministic report generator consumes only
that JSON and writes `benchmarks/reports/latest.md`.  A small generated
`summary.json` is available for future web consumption; existing website release
verification is left unchanged because it reports v0.3.1 release-gate facts,
not Phase 2 performance claims.

## 8. Security and regression strategy

The security track measures LLMSlim provenance invariants, not prompt-injection
prevention.  Any protected-priority elevation, untrusted `must_keep`, or trusted
instruction retention failure is reported; provenance-boundary violations have
zero tolerance.  Regression comparison accepts a previous canonical JSON and
uses explicit tolerances for noisy metrics while keeping security strict.

## 9. Tests, scope, and acceptance

Unit tests cover formulas, empty inputs, dataset validation, aggregation,
serialization, report generation, security counting, schema accounting,
turn derivation, contract comparison, multilingual metadata, determinism, and
regression thresholds.  The suite is offline and does not alter compression
behaviour, `cost.py`, schema contracts, Studio, package version, or provider
requirements.  Acceptance requires passing tests, >=90% existing package
coverage, Ruff, a valid result/report, and zero security boundary violations.
