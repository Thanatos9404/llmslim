# Phase 2 implementation report

## Executive summary

Phase 2 adds a tested, offline benchmark source of truth without changing
LLMSlim's production compression behaviour.  The full deterministic baseline
was executed on 2026-08-15 and written to `benchmarks/results/latest.json`.

## Architecture and commands

`benchmarks.evaluation` owns labelled metrics, local execution, security checks,
result validation, serialization, comparison, and report rendering.
`benchmarks.schema_tax` owns synthetic catalog generation, token accounting,
contract comparison, and relevance ground truth.  Run:

```bash
python -m benchmarks.run --mode fast
python -m benchmarks.run --mode full
```

FAST uses three measured iterations; FULL uses seven. Both perform one warmup,
need no network/API key, and record a seed. CI now runs the FAST suite in
addition to the existing legacy benchmark smoke test.

## Dataset and metrics

The baseline contains 24 independently labelled repository-owned synthetic
samples across 22 categories, including all four required languages.  It records
category/token/language/length distribution and strategy applicability.  Metrics
include compression/target-ratio accuracy, labelled instruction/entity/number/
negation retention, lexical similarity, parser/format structure checks,
end-to-end latency/throughput, determinism, failures, security invariants, and
schema-tax accounting. Macro and micro aggregation are separately labelled.

## Actual baseline results

The full run used Python 3.12.5 on Windows, LLMSlim 0.3.1, commit
`b4d7923f785c88b05e7b1b4dd161f1b268ed362e`, and `tiktoken` 0.13.0. Results are
environment-dependent and are not release marketing claims.

| MEASURED metric | Micro mean |
| --- | ---: |
| Token reduction | 13.14% |
| Target-ratio error | 0.3686 |
| Instruction retention | 93.75% |
| Entity retention | 85.09% |
| Number retention | 89.12% |
| Negation retention | 86.67% |
| Lexical similarity proxy | 89.18% |
| Determinism | 100% |

The low aggregate reduction is expected for a corpus dominated by short,
constraint-heavy inputs and is intentionally reported rather than tuned away.
Parser/format checks were valid for 4/5 applicable samples; the Markdown sample
did not retain the expected code-fence/header structure. This is documented as a
baseline limitation and not fixed as a Phase 2 core-compression change.

## Security and schema tax

The dedicated security suite measured zero protected-priority elevation,
`must_keep`, and provenance-boundary violations.  It does not claim prompt
injection prevention.

The schema-tax track measured 18 catalogs and 375 generated tool schemas across
SIMPLE/MEDIUM/COMPLEX and 1–64 tools.  For example, the measured MEDIUM 8-tool
catalog is 867 tokens; 13,872 tokens over 16 resent turns and 27,744 over 32
turns are clearly labelled DERIVED. No schema compression or selection feature
was shipped. Contract tests cover names, parameter shape/types, required set,
enums, constraints, defaults, and separate description changes.

## Artifacts, synchronization, and limitations

The canonical JSON is validated before writing.  Timestamped runs are retained
under `benchmarks/results/runs/`; `summary.json` is a stable small consumer
artifact and `benchmarks/reports/latest.md` is generated solely from canonical
JSON. README links methodology and correctly describes schema tax as research.
The website continues to display its v0.3.1 release gate rather than copying
Phase 2 performance numbers, so no web build change is necessary.

Results contain only non-identifying environment data. No dollar pricing,
provider baseline, significance claim, or external benchmark number is blended
into this result. The next recommended work is a contract-verified minification
and offline relevance-evaluation prototype, not semantic schema compression.

## Validation

- `pytest tests --cov=llmslim --cov-branch --cov-report=term-missing`: **442 passed**, **92.94%** coverage.
- `ruff check llmslim benchmarks tests`: **PASS**.
- `python benchmark.py`: **PASS**, 442 tests observed by legacy runner.
- `python -m benchmarks.run --mode full`: **PASS** with a valid canonical JSON and generated report.

No package version was changed. This is benchmark/docs/CI infrastructure only;
recommend **no PyPI release**.
