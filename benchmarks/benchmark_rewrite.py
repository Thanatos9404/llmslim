"""Benchmark rewrite and hybrid strategies against extractive baseline.

Measures:
- Token Reduction (%)
- Latency (ms)
- Semantic Similarity
- Instruction Retention (%)
- Entity Retention (%)
- Validation Failure Rate (%) [Critical Metric]
- Fallback Rate (%)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from llmslim import compress
from llmslim.rewrite import CallableProvider, RewriteRequest


@dataclass
class StrategyBenchmarkResult:
    strategy: str
    num_samples: int
    avg_reduction_percent: float
    avg_latency_ms: float
    avg_similarity: float
    avg_instruction_retention: float
    avg_entity_retention: float
    validation_failure_rate_percent: float
    fallback_rate_percent: float


BENCHMARK_DATASET = [
    (
        "System Prompt",
        "You are an expert software architect. You must respond in valid JSON format. "
        "Rule 1: Always validate inputs. Rule 2: Never expose secret keys or tokens. "
        "Rule 3: Ensure error messages are clear and actionable. "
        "The endpoint URL is https://api.example.com/v1/deploy.",
    ),
    (
        "RAG Context",
        "Document 1: Kubernetes HPA scales pods based on CPU utilization metrics. "
        "Minimum replicas: 2, Maximum replicas: 10. Target CPU: 80%. "
        "Document 2: Prometheus monitors cluster metrics every 15 seconds. "
        "Alerts are routed via Alertmanager to Slack channel #ops-alerts.",
    ),
    (
        "Chat History",
        "User: How do I configure SSL in Nginx?\n"
        "Assistant: You must specify ssl_certificate and ssl_certificate_key in server block.\n"
        "User: Thanks! What port should I listen on?\n"
        "Assistant: Listen on port 443 with ssl parameter enabled.",
    ),
]


def _mock_llm_rewriter(request: RewriteRequest) -> str:
    # Simulates an LLM rewrite that shortens prose while keeping key entities/instructions
    text = request.text
    if "System Prompt" in text or "software architect" in text:
        return (
            "You are a software architect. You must respond in JSON. "
            "Rule 1: Always validate inputs. Rule 2: Never expose keys. "
            "Rule 3: Ensure clear errors. Endpoint: https://api.example.com/v1/deploy."
        )
    if "Kubernetes" in text or "Prometheus" in text:
        return (
            "Kubernetes HPA scales pods (min 2, max 10) at 80% CPU. "
            "Prometheus monitors metrics every 15s, alerting #ops-alerts via Alertmanager."
        )
    return (
        "User asked for SSL in Nginx. "
        "Assistant: Must set ssl_certificate, ssl_certificate_key, listen port 443 ssl."
    )


def run_rewrite_benchmarks() -> List[StrategyBenchmarkResult]:
    """Run benchmark comparison across extractive, rewrite, and hybrid strategies."""
    provider = CallableProvider(_mock_llm_rewriter, name="benchmark_mock")
    strategies = ["extractive", "rewrite", "hybrid"]
    results: List[StrategyBenchmarkResult] = []

    for strat in strategies:
        reductions = []
        latencies = []
        similarities = []
        inst_retentions = []
        ent_retentions = []
        failures = 0
        fallbacks = 0

        for _label, text in BENCHMARK_DATASET:
            t0 = time.perf_counter()
            if strat == "extractive":
                res = compress(text, target_ratio=0.5, strategy="extractive")
            else:
                res = compress(text, target_ratio=0.5, strategy=strat, provider=provider)
            latency = (time.perf_counter() - t0) * 1000

            reductions.append(res.reduction_percent)
            latencies.append(latency)

            if res.rewrite_metadata:
                rm = res.rewrite_metadata
                similarities.append(rm.similarity_score)
                inst_retentions.append(rm.instruction_retention * 100)
                ent_retentions.append(rm.entity_retention * 100)
                if not rm.accepted:
                    failures += 1
                if rm.fallback_used:
                    fallbacks += 1
            else:
                # Extractive baseline fallback values
                similarities.append(1.0)
                inst_retentions.append(100.0)
                ent_retentions.append(100.0)

        n = len(BENCHMARK_DATASET)
        results.append(
            StrategyBenchmarkResult(
                strategy=strat,
                num_samples=n,
                avg_reduction_percent=round(sum(reductions) / n, 1),
                avg_latency_ms=round(sum(latencies) / n, 2),
                avg_similarity=round(sum(similarities) / n, 3),
                avg_instruction_retention=round(sum(inst_retentions) / n, 1),
                avg_entity_retention=round(sum(ent_retentions) / n, 1),
                validation_failure_rate_percent=round((failures / n) * 100, 1),
                fallback_rate_percent=round((fallbacks / n) * 100, 1),
            )
        )

    return results


if __name__ == "__main__":
    bench_results = run_rewrite_benchmarks()
    print("=== Strategy Benchmark Results ===")
    for r in bench_results:
        print(f"Strategy: {r.strategy.upper()}")
        print(f"  Token Reduction       : {r.avg_reduction_percent}%")
        print(f"  Avg Latency           : {r.avg_latency_ms} ms")
        print(f"  Semantic Similarity   : {r.avg_similarity}")
        print(f"  Instruction Retention : {r.avg_instruction_retention}%")
        print(f"  Entity Retention      : {r.avg_entity_retention}%")
        print(f"  Validation Fail Rate  : {r.validation_failure_rate_percent}%")
        print(f"  Fallback Rate         : {r.fallback_rate_percent}%\n")
