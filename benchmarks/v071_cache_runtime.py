"""Offline multi-turn cache benchmark; never calls a model provider.

Observed values are local planner time and serialized request bytes. Prefix
reuse is a structural estimate, not an actual provider hit or billed saving.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from llmslim import (
    CacheManager,
    CachePolicy,
    ContextRuntime,
    ModelProfile,
    openai_responses_request,
    request_bytes,
)
from llmslim.cache import CacheStatus
from llmslim.tokens import count_tokens

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "benchmarks" / "results" / "v0.7.1-cache-runtime.json"
REPORT = ROOT / "docs" / "releases" / "v0.7.1-BENCHMARK.md"


def _scenario(name: str, turns: int) -> dict[str, Any]:
    return {
        "name": name,
        "turns": turns,
        "large_system": name == "stable_20k",
        "large_tools": name == "large_tool_catalog",
        "tool_change": name == "tool_added_midway",
        "policy_change": name == "policy_changed_midway",
        "dynamic_rag": name == "rag_changes_each_turn",
        "static_rag": name == "static_rag",
        "compaction": name == "periodic_compaction",
    }


def _cases(quick: bool) -> list[dict[str, Any]]:
    lengths = [10] if quick else [10, 50, 100]
    cases = [_scenario(f"conversation_{length}", length) for length in lengths]
    cases.extend(
        _scenario(name, 10)
        for name in (
            "stable_20k",
            "large_tool_catalog",
            "tool_added_midway",
            "policy_changed_midway",
            "rag_changes_each_turn",
            "static_rag",
            "periodic_compaction",
        )
    )
    return cases


def _lcp_tokens(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> int:
    common = []
    for old, new in zip(previous, current):
        if old != new:
            break
        common.append(old)
    return count_tokens(json.dumps(common, ensure_ascii=False, sort_keys=True)) if common else 0


def _record(name: str) -> dict[str, Any]:
    return {
        "baseline": name,
        "turns": 0,
        "input_integrity_turns": 0,
        "total_logical_input_tokens": 0,
        "transmitted_input_bytes": 0,
        "structural_reusable_prefix_tokens": 0,
        "estimated_cache_read_tokens": 0,
        "estimated_cache_write_tokens": None,
        "provider_reported_cache_read_tokens": None,
        "provider_reported_cache_write_tokens": None,
        "uncached_processed_tokens": None,
        "provider_cache_hit_rate": None,
        "time_to_first_token_ms": None,
        "full_latency_ms": None,
        "provider_cost": None,
        "planner_overhead_ms": 0.0,
        "cache_invalidations": 0,
        "budget_feasible_turns": 0,
        "compression_ratio": None,
    }


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    name, turns = case["name"], case["turns"]
    system = (
        "VERIFIED-CANARY stable operating policy. " * 2220
        if case["large_system"]
        else "VERIFIED-CANARY stable operating policy. " * 35
    )
    tools = (
        [
            {
                "name": f"tool_{index:03d}",
                "description": "Read authorized data",
                "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}}},
            }
            for index in range(60)
        ]
        if case["large_tools"]
        else []
    )
    profile = ModelProfile(model_id="gpt-5.6", provider="openai", context_window=128000)
    shared = {
        "model": "gpt-5.6",
        "model_profile": profile,
        "reserve_output_tokens": 0,
        "safety_margin_tokens": 0,
    }
    tight_budget = (
        100000 if case["large_system"] or case["large_tools"] else 8000 if turns == 100 else 4096
    )
    current = ContextRuntime(**shared, max_input_tokens=100000)
    compression = ContextRuntime(
        **shared, max_input_tokens=tight_budget, objective="minimize_tokens"
    )
    aware = ContextRuntime(
        **shared,
        max_input_tokens=tight_budget,
        cache_policy=CachePolicy(mode="auto", provider="openai", tenant_id="benchmark"),
        cache_manager=CacheManager(),
    )
    stateful = ContextRuntime(
        **shared,
        max_input_tokens=tight_budget,
        cache_policy=CachePolicy(
            mode="auto",
            provider="openai",
            tenant_id="benchmark-stateful",
            conversation_mode="provider_stateful",
        ),
        cache_manager=CacheManager(),
    )
    rows = {
        baseline: _record(baseline)
        for baseline in (
            "v07_current",
            "compression_only",
            "provider_automatic_without_planning",
            "cache_aware",
            "provider_stateful_modeled",
            "self_hosted_prefix_modeled",
        )
    }
    raw_messages: list[dict[str, Any]] = []
    previous_raw: list[dict[str, Any]] = []
    previous_aware: list[dict[str, Any]] = []
    original_token_total = 0
    for turn in range(turns):
        if case["compaction"] and turn and turn % 5 == 0:
            raw_messages = raw_messages[-4:]
        if case["tool_change"] and turn == turns // 2:
            tools = tools + [{"name": "new_tool", "inputSchema": {"type": "object"}}]
        if case["policy_change"] and turn == turns // 2:
            aware.objective = "cost"
            stateful.objective = "cost"
        question = f"Turn {turn}: explain the verified policy for task {turn}."
        raw_messages.append({"role": "user", "content": question})
        messages = [{"role": "system", "content": system}] + list(raw_messages)
        if case["dynamic_rag"]:
            docs = [{"id": "dynamic", "content": f"Current evidence revision {turn}."}]
        elif case["static_rag"]:
            docs = [
                {
                    "id": "static",
                    "content": "Stable reference " * 500,
                    "metadata": {
                        "cache_stability": "stable",
                        "cache_authorized": True,
                        "cache_order_safe": True,
                    },
                }
            ]
        else:
            docs = []
        args = {
            "session_id": "benchmark-session",
            "messages": messages,
            "user_input": question,
            "documents": docs,
            "tools": tools,
        }
        prepared = {}
        times = {}
        for key, rt in (
            ("v07_current", current),
            ("compression_only", compression),
            ("cache_aware", aware),
            ("provider_stateful_modeled", stateful),
        ):
            started = time.perf_counter()
            prepared[key] = rt.prepare_sync(**args)
            times[key] = (time.perf_counter() - started) * 1000
        raw_request = {
            "model": prepared["v07_current"].model_input.model,
            "messages": [dict(m) for m in prepared["v07_current"].model_input.messages],
            "tools": [dict(t) for t in prepared["v07_current"].model_input.tools],
        }
        raw_tokens = prepared["v07_current"].cache_plan.logical_context_tokens
        original_token_total += raw_tokens
        for key in ("v07_current", "compression_only", "cache_aware", "provider_stateful_modeled"):
            result = prepared[key]
            row = rows[key]
            request = (
                openai_responses_request(result, stateful.cache_policy)
                if key == "provider_stateful_modeled" and result.feasible
                else {
                    "model": result.model_input.model,
                    "messages": [dict(m) for m in result.model_input.messages],
                    "tools": [dict(t) for t in result.model_input.tools],
                }
            )
            row["turns"] += 1
            row["budget_feasible_turns"] += int(result.feasible)
            row["input_integrity_turns"] += int(
                result.feasible and "VERIFIED-CANARY" in str(request)
            )
            row["total_logical_input_tokens"] += result.cache_plan.logical_context_tokens
            row["transmitted_input_bytes"] += request_bytes(request)
            row["planner_overhead_ms"] += times[key]
            row["estimated_cache_read_tokens"] += result.cache_plan.estimated_cache_read_tokens
            row["cache_invalidations"] += int(result.cache_plan.status is CacheStatus.INVALIDATED)
        state_result = prepared["provider_stateful_modeled"]
        if state_result.feasible:
            stateful.cache_manager.record_provider_reference(
                stateful.cache_policy,
                "benchmark-session",
                stateful.model,
                state_result.cache_plan.prefix_fingerprint,
                previous_response_id=f"offline-response-{turn}",
            )
        automatic = rows["provider_automatic_without_planning"]
        automatic["turns"] += 1
        automatic["input_integrity_turns"] += int(
            prepared["v07_current"].feasible and "VERIFIED-CANARY" in str(raw_request)
        )
        automatic["total_logical_input_tokens"] += prepared[
            "v07_current"
        ].cache_plan.logical_context_tokens
        automatic["transmitted_input_bytes"] += request_bytes(raw_request)
        automatic["structural_reusable_prefix_tokens"] += _lcp_tokens(
            previous_raw, raw_request["messages"]
        )
        hosted = rows["self_hosted_prefix_modeled"]
        hosted["turns"] += 1
        hosted["input_integrity_turns"] += int(prepared["cache_aware"].feasible)
        hosted["total_logical_input_tokens"] += prepared[
            "cache_aware"
        ].cache_plan.logical_context_tokens
        hosted["transmitted_input_bytes"] += request_bytes(
            {
                "model": "gpt-5.6",
                "messages": [dict(m) for m in prepared["cache_aware"].model_input.messages],
                "tools": [dict(t) for t in prepared["cache_aware"].model_input.tools],
            }
        )
        current_aware = [dict(m) for m in prepared["cache_aware"].model_input.messages]
        hosted["structural_reusable_prefix_tokens"] += _lcp_tokens(previous_aware, current_aware)
        previous_raw = raw_request["messages"]
        previous_aware = current_aware
    for row in rows.values():
        row["planner_overhead_ms"] = round(row["planner_overhead_ms"], 3)
        row["compression_ratio"] = round(
            1 - row["total_logical_input_tokens"] / max(1, original_token_total), 6
        )
    return {"scenario": name, "turns": turns, "baselines": list(rows.values())}


def run(*, quick: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    cases = [run_case(case) for case in _cases(quick)]
    return {
        "schema_version": "1.0",
        "classification": "OFFLINE_STRUCTURAL_ESTIMATE",
        "paid_provider_calls": 0,
        "actual_provider_hits_measured": False,
        "actual_ttft_measured": False,
        "actual_cost_measured": False,
        "scenarios": cases,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "notes": [
            "Input integrity checks presence of the required canary, not answer quality.",
            "Reusable prefix tokens are structural estimates, not provider cache hits.",
            "Stateful network bytes assume an accepted previous_response_id; no API call validates it.",
            "Self-hosted prefix reuse is modeled; no vLLM or GPU was used.",
            "TTFT, provider latency, cache writes, hit rate, and billed cost require a live provider run.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    result = run(quick=args.quick)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# LLMSlim cache-aware runtime benchmark",
        "",
        "Offline structural estimate. No model or paid provider API was called.",
        "",
        "| Scenario | Turns | v0.7 transmitted bytes | Cache-aware transmitted bytes | Stateful modeled bytes | Cache-aware estimated read tokens | Invalidations |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in result["scenarios"]:
        rows = {row["baseline"]: row for row in case["baselines"]}
        lines.append(
            f"| {case['scenario']} | {case['turns']} | "
            f"{rows['v07_current']['transmitted_input_bytes']} | "
            f"{rows['cache_aware']['transmitted_input_bytes']} | "
            f"{rows['provider_stateful_modeled']['transmitted_input_bytes']} | "
            f"{rows['cache_aware']['estimated_cache_read_tokens']} | "
            f"{rows['cache_aware']['cache_invalidations']} |"
        )
    lines.extend(
        [
            "",
            "TTFT, full provider latency, actual cache hits and writes, answer correctness,",
            "and billed cost were not measured; the JSON leaves them null.",
            "",
            "Data: `benchmarks/results/v0.7.1-cache-runtime.json`.",
        ]
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output} and {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
