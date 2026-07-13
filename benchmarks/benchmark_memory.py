"""Memory usage benchmark module for llmslim v0.2."""

from __future__ import annotations

import json
import os
import tracemalloc
from dataclasses import dataclass
from typing import List

from llmslim import compress
from llmslim.tokens import count_tokens


@dataclass
class MemoryMetrics:
    sample_id: str
    category: str
    original_tokens: int
    compressed_tokens: int
    peak_memory_kb: float
    memory_kb_per_1k_tokens: float


def measure_memory_usage(sample_id: str, text: str, category: str) -> MemoryMetrics:
    original_tokens = count_tokens(text)

    tracemalloc.start()
    result = compress(text, target_ratio=0.5)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_kb = peak / 1024.0
    kb_per_1k = (peak_kb / (original_tokens / 1000.0)) if original_tokens > 0 else 0.0

    return MemoryMetrics(
        sample_id=sample_id,
        category=category,
        original_tokens=original_tokens,
        compressed_tokens=result.compressed_tokens,
        peak_memory_kb=round(peak_kb, 2),
        memory_kb_per_1k_tokens=round(kb_per_1k, 2)
    )


def run_memory_benchmarks(dataset_dir: str = "datasets") -> List[MemoryMetrics]:
    results: List[MemoryMetrics] = []
    if not os.path.exists(dataset_dir):
        dataset_dir = os.path.join("benchmarks", "datasets")

    for filename in sorted(os.listdir(dataset_dir)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(dataset_dir, filename)
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            sample_id = item.get("id", "unknown")
            text = item.get("text") or item.get("document") or ""
            if not text and "messages" in item:
                text = " ".join(m.get("content", "") for m in item["messages"])

            if text.strip():
                metrics = measure_memory_usage(
                    sample_id=sample_id,
                    text=text,
                    category=filename.replace(".json", "")
                )
                results.append(metrics)

    return results


if __name__ == "__main__":
    results = run_memory_benchmarks()
    print(f"Evaluated memory on {len(results)} samples.")
    if results:
        avg_peak = sum(r.peak_memory_kb for r in results) / len(results)
        print(f"Average Peak Memory  : {avg_peak:.2f} KB")
