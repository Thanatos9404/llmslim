---
name: Benchmark Regression Report
about: Report a drop in compression quality, entity retention, or instruction retention metrics.
title: "[BENCHMARK] "
labels: ["benchmarks", "quality-regression"]
assignees: ""
---

### Benchmark Drop Overview
Describe the quality or retention drop observed across test corpora or benchmark datasets.

### Benchmark Dataset / Corpus Affected
- Dataset (e.g. `datasets/arxiv_summarization.json`, custom dataset)
- Metric affected: (e.g. Entity Retention %, Instruction Preservation %, Similarity Score)

### Quantitative Metrics Comparison
| Metric | Previous Value | New Value | Change |
|---|---|---|---|
| Latency (ms) | | | |
| Compression Ratio (%) | | | |
| Instruction Retention (%) | | | |
| Entity Retention (%) | | | |

### Reproduction Command
```bash
python benchmarks/benchmark_quality.py
```
