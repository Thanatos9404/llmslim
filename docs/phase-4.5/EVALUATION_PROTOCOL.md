# Evaluation protocol

The primary artifact is `benchmarks/results/phase4-5-latest.json`, produced by:

```bash
py -3.12 -m benchmarks.phase4_5 --output benchmarks/results/phase4-5-latest.json
```

The corpus is fixed static text before the retrieval result is read: 100 MCP-shaped tools and 500 repository-authored queries. A SHA-256 case-id modulo-five split with seed `phase4_5_split_v1` assigns 20% to development and the rest to test. Only development labels choose candidate `k` and fail-open thresholds. The test split is never used to select a policy.

Predeclared comparisons are TF-IDF and BM25 (`k1=1.2`, `b=0.75`); dense and hybrid require a pinned local model before they may be measured. Predeclared top-k policies are full, 1, 3, 5, and 10; the dynamic policy may fail open to the full catalog. Primary metrics are required-tool recall, all-required-tool recall, precision, MRR, NDCG, no-tool accuracy, coverage, fail-open rate, and token avoidance. Bootstrap intervals use 1,000 deterministic resamples with seed 20260819.

Release threshold: a selective policy can be considered only if its *development* all-required recall and no-tool accuracy are each at least 0.95, its test lower 95% bound is at least 0.95, and robustness checks pass. Otherwise it remains `RESEARCH_ONLY` and full authoritative schemas stay available.
