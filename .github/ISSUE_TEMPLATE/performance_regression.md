---
name: Performance Regression Report
about: Report a performance, latency, or memory degradation issue.
title: "[PERF] "
labels: ["performance", "regression"]
assignees: ""
---

### Performance Degradation Overview
Describe the latency or throughput slowdown observed.

### Environment & Hardware Details
- **llmslim Version**: (e.g. `0.2.0`)
- **Previous Working Version**: (e.g. `0.1.0`)
- **Python Version**:
- **CPU / Memory Specs**:

### Benchmark / Profiling Results
```text
# Paste memory/speed benchmark output or cProfile breakdown
```

### Steps to Reproduce
1. Run `python benchmarks/benchmark_speed.py`
2. Measure latency delta on corpus size...

### Expected Latency / Throughput
Expected overhead (e.g. < 5ms for 4k prompt).
