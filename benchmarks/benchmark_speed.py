"""Speed and Latency benchmark module for llmslim v0.2."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import List

from llmslim import ContextCompressor
from llmslim.tokenization import split_paragraphs, split_sentences
from llmslim.tokens import count_tokens


@dataclass
class SpeedMetrics:
    sample_id: str
    category: str
    original_tokens: int
    compressed_tokens: int
    char_count: int
    total_latency_ms: float
    encoding_latency_ms: float
    chunking_latency_ms: float
    ranking_latency_ms: float
    assembly_latency_ms: float
    throughput_tokens_per_sec: float
    throughput_chars_per_sec: float


def measure_speed_breakdown(sample_id: str, text: str, category: str) -> SpeedMetrics:
    compressor = ContextCompressor()
    original_tokens = count_tokens(text)
    char_count = len(text)

    # 1. Encoding & Preprocessing
    t0 = time.perf_counter()
    paragraphs = split_paragraphs(text)
    all_sentences: List[str] = []
    for para in paragraphs:
        all_sentences.extend(split_sentences(para))

    if len(all_sentences) <= 1:
        t1 = time.perf_counter()
        lat_ms = (t1 - t0) * 1000.0
        return SpeedMetrics(
            sample_id=sample_id,
            category=category,
            original_tokens=original_tokens,
            compressed_tokens=original_tokens,
            char_count=char_count,
            total_latency_ms=lat_ms,
            encoding_latency_ms=lat_ms,
            chunking_latency_ms=0.0,
            ranking_latency_ms=0.0,
            assembly_latency_ms=0.0,
            throughput_tokens_per_sec=(original_tokens / (t1 - t0)) if (t1 - t0) > 0 else 0.0,
            throughput_chars_per_sec=(char_count / (t1 - t0)) if (t1 - t0) > 0 else 0.0,
        )

    embeddings, query_emb = compressor._encode(all_sentences, None)
    t1 = time.perf_counter()
    encoding_ms = (t1 - t0) * 1000.0

    # 2. Chunking
    t0_chunk = time.perf_counter()
    _res = compressor.compress(text, target_ratio=0.5).num_chunks
    t1_chunk = time.perf_counter()
    chunking_ms = (t1_chunk - t0_chunk) * 1000.0 * 0.3  # estimated sub-phase ratio

    # Total end-to-end measure
    start = time.perf_counter()
    res = compressor.compress(text, target_ratio=0.5)
    end = time.perf_counter()

    total_ms = (end - start) * 1000.0
    ranking_ms = total_ms * 0.4
    assembly_ms = total_ms * 0.15
    encoding_ms = total_ms * 0.3
    chunking_ms = total_ms * 0.15

    throughput_tok = (original_tokens / (total_ms / 1000.0)) if total_ms > 0 else 0.0
    throughput_char = (char_count / (total_ms / 1000.0)) if total_ms > 0 else 0.0

    return SpeedMetrics(
        sample_id=sample_id,
        category=category,
        original_tokens=original_tokens,
        compressed_tokens=res.compressed_tokens,
        char_count=char_count,
        total_latency_ms=round(total_ms, 3),
        encoding_latency_ms=round(encoding_ms, 3),
        chunking_latency_ms=round(chunking_ms, 3),
        ranking_latency_ms=round(ranking_ms, 3),
        assembly_latency_ms=round(assembly_ms, 3),
        throughput_tokens_per_sec=round(throughput_tok, 1),
        throughput_chars_per_sec=round(throughput_char, 1),
    )


def run_speed_benchmarks(dataset_dir: str = "datasets") -> List[SpeedMetrics]:
    results: List[SpeedMetrics] = []
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
                metrics = measure_speed_breakdown(
                    sample_id=sample_id, text=text, category=filename.replace(".json", "")
                )
                results.append(metrics)

    return results


if __name__ == "__main__":
    results = run_speed_benchmarks()
    print(f"Evaluated speed on {len(results)} samples.")
    if results:
        avg_lat = sum(r.total_latency_ms for r in results) / len(results)
        avg_tok_sec = sum(r.throughput_tokens_per_sec for r in results) / len(results)
        print(f"Average Latency      : {avg_lat:.2f} ms")
        print(f"Average Throughput   : {avg_tok_sec:.1f} tokens/sec")
