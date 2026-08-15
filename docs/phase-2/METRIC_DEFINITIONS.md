# Metric definitions

- **Token reduction (MEASURED):** `(original_tokens - compressed_tokens) / original_tokens`.
- **Actual compression ratio (MEASURED):** `compressed_tokens / original_tokens`.
- **Target-ratio error (MEASURED):** `abs(actual_ratio - requested_ratio)`.
- **Instruction/entity/number/negation retention (MEASURED):** fraction of
  independently labelled normalized strings present in compressed output. Empty
  label sets are `N/A`, never converted into a perfect score.
- **Semantic similarity (MEASURED proxy):** Unicode lexical Jaccard similarity.
  It is not a claim of embedding or human semantic equivalence.
- **Structural integrity (MEASURED):** JSON/XML parser success; YAML parser
  success when PyYAML is available; Markdown header/fence preservation; Python
  compilation for code. Unavailable optional parsers are reported as `N/A`.
- **Latency (MEASURED):** wall-clock end-to-end local compression after warmup.
  Median, p95, mean, standard deviation, and iteration count are retained.
- **Throughput (MEASURED):** original tokens divided by median elapsed seconds.
- **Determinism (MEASURED):** byte equality across repeated local outputs.
- **Schema session totals (DERIVED):** measured full-catalog tokens multiplied
  by a stated number of turns assuming the catalog is resent every turn.

Provider-dependent rewrite/hybrid, tool-selection Recall@K/Precision@K/MRR, and
dollar savings are `NOT_APPLICABLE` in the default local suite.
