# Data quality report

The measured artifact records 100 tools and 500 queries. Normalized exact duplicates: **0**. Token-set Jaccard near-duplicate pairs at or above 0.90: **0**. The checks are deterministic and run in `benchmarks.phase4_5._quality_report`.

There are 400 single-tool, 40 multi-tool, and 60 no-tool cases. These are intentionally explicit; no generated prompt family is counted as benchmark evidence. Limitations remain: many requests are short and English-heavy, while several catalog-only distractor domains are not direct label targets. The release gate treats this as a regression corpus, not a broad production estimate.
