# Benchmark methodology

Run the deterministic offline suite with `python -m benchmarks.run --mode fast`.
Use `--mode full` for seven timed iterations per sample; FAST uses three.  Every
sample receives one unrecorded warmup before end-to-end `compress()` timing.
Results report mean, median, p95, standard deviation, and count without
synthetic pipeline-stage attribution.

`benchmarks/results/latest.json` is the canonical versioned result.  It records
the UTC timestamp, commit, package version, Python/platform/architecture,
relevant dependency versions, seed, and active tokenizer.  The runner works
without internet, API keys, or a paid provider.  Rewrite/hybrid outcomes are
explicitly not applicable in that default run because they require a caller
provider and can be nondeterministic.

The core corpus is repository-owned synthetic material with independently
authored labels.  It is representative rather than statistically representative
of all production prompts.  Macro summaries weight categories equally; micro
summaries weight samples equally.  Token counts from the heuristic fallback and
`tiktoken` are distinct measurements and must not be compared as equivalent.

The security track measures provenance-boundary invariants only.  It does not
measure or claim complete prompt-injection prevention.
