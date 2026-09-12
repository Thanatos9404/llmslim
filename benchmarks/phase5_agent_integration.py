"""Offline Phase 5 catalog-plan integration measurement.

This benchmark measures LLMSlim's deterministic catalog/planning path. It does
not call a model or infer live-agent task success from a deterministic host.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from benchmarks.phase4 import relevance_cases, relevance_catalog
from llmslim import __version__
from llmslim.mcp import PlanMode, StaticToolCatalogSource, plan_catalog_context
from llmslim.tools import from_mcp_tool

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results" / "phase5-latest.json"


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, int((len(ordered) - 1) * percentile))]


def _tasks() -> List[Dict[str, Any]]:
    """Return 60 deterministic availability tasks across Phase 4 tool families."""
    base = relevance_cases()
    tasks = []
    for round_number in range(5):
        for case in base:
            item = dict(case)
            item["id"] = "%s-%02d" % (case["id"], round_number + 1)
            tasks.append(item)
    return tasks


def run_phase5_agent_integration_benchmark() -> Dict[str, Any]:
    """Measure full and explicitly experimental plans without tool execution."""
    tools = tuple(from_mcp_tool(raw) for raw in relevance_catalog())
    snapshot = asyncio.run(StaticToolCatalogSource(tools, source_id="phase5-offline").list_tools())
    tasks = _tasks()
    full_latencies: List[float] = []
    selective_latencies: List[float] = []
    full_available = 0
    selective_available = 0
    full_tokens: List[int] = []
    selective_tokens: List[int] = []
    for task in tasks:
        started = time.perf_counter()
        full = plan_catalog_context(snapshot, mode=PlanMode.FULL)
        full_latencies.append((time.perf_counter() - started) * 1_000.0)
        expected = set(task["required"])
        full_available += expected.issubset(set(full.selected_tool_ids))
        full_tokens.append(full.metrics.presented_tokens)

        started = time.perf_counter()
        selective = plan_catalog_context(
            snapshot,
            mode=PlanMode.SELECTIVE,
            query=task["query"],
            experimental=True,
        )
        selective_latencies.append((time.perf_counter() - started) * 1_000.0)
        selective_available += expected.issubset(set(selective.selected_tool_ids))
        selective_tokens.append(selective.metrics.presented_tokens)
    catalog_tokens = snapshot.token_count
    return {
        "classification": "MEASURED_OFFLINE_INTEGRATION",
        "llmslim_version": __version__,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "token_counter": "llmslim.tokens.count_tokens",
        },
        "catalog": {
            "source_mode": "static_repository_owned_fixture",
            "tool_count": snapshot.tool_count,
            "catalog_fingerprint": snapshot.catalog_fingerprint,
            "catalog_tokens": catalog_tokens,
        },
        "tasks": {
            "count": len(tasks),
            "kind": "deterministic integration availability; not live-model task success",
            "full_required_tool_availability": full_available / len(tasks),
            "selective_required_tool_availability": selective_available / len(tasks),
            "host_tool_call_correctness": "NOT_MEASURED_IN_BENCHMARK",
            "live_model_status": "NOT_RUN",
        },
        "plans": {
            "full": {
                "exposure": "FULL_AUTHORITATIVE_CATALOG",
                "presented_tokens": statistics.mean(full_tokens),
                "tokens_avoided": 0,
                "planning_latency_ms": {
                    "median": statistics.median(full_latencies),
                    "p95": _percentile(full_latencies, 0.95),
                },
            },
            "selective": {
                "exposure": "EXPERIMENTAL_OPT_IN_RESEARCH_ONLY",
                "presented_tokens": statistics.mean(selective_tokens),
                "tokens_avoided": catalog_tokens - statistics.mean(selective_tokens),
                "planning_latency_ms": {
                    "median": statistics.median(selective_latencies),
                    "p95": _percentile(selective_latencies, 0.95),
                },
            },
        },
        "cache": {
            "status": "NOT_APPLICABLE_STATIC_SOURCE",
            "note": "Transport cache hit-rate and network latency are measured by MCP transport E2E tests, not this static benchmark.",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run offline Phase 5 catalog-plan integration measurement"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = run_phase5_agent_integration_benchmark()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
