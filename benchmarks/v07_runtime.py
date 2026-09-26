"""Offline five-baseline evaluation for the LLMSlim Agent Context Runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from benchmarks.v06_planner import _contains_all, _truncate_to_tokens, expand_case
from llmslim import ContextRuntime, compress, plan_context
from llmslim.planning.candidates import render_context_item
from llmslim.tokens import count_tokens, get_active_token_counter_name

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks" / "datasets" / "v07_agent_context.json"
OUTPUT = ROOT / "benchmarks" / "results" / "v0.7-runtime-latest.json"
REPORT = ROOT / "docs" / "releases" / "v0.7.0-BENCHMARK.md"
BASELINES = ("raw", "prefix", "fixed_ratio", "v06_adaptive", "v07_runtime")


def load_cases(path: Path = DATASET) -> List[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or not isinstance(payload.get("cases"), list):
        raise ValueError("invalid v0.7 benchmark corpus")
    cases = payload["cases"]
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)) or any(not isinstance(key, str) or not key for key in ids):
        raise ValueError("benchmark cases require unique non-empty IDs")
    return cases


def _expanded(case: Mapping[str, Any]) -> Dict[str, Any]:
    if case.get("corpus_source") == "v06":
        return expand_case(case)
    return dict(case)


def _measure(
    name: str, text: str, case: Mapping[str, Any], raw_tokens: int, budget: int,
    latency_ms: float, feasible: bool | None = None,
) -> Dict[str, Any]:
    final_tokens = count_tokens(text)
    return {
        "baseline": name,
        "final_tokens": final_tokens,
        "budget_success": final_tokens <= budget if feasible is None else feasible,
        "hard_constraint_retention": _contains_all(text, case.get("required_instructions", [])),
        "required_fact_retention": _contains_all(text, case.get("expected_facts", [])),
        "entity_retention": _contains_all(text, case.get("expected_facts", [])),
        "tool_availability": _contains_all(text, case.get("expected_tools", [])),
        "token_reduction": 1.0 - final_tokens / max(1, raw_tokens),
        "latency_ms": latency_ms,
    }


def _runtime(case: Mapping[str, Any], budget: int):
    runtime = ContextRuntime(
        model="sarvam-105b", max_input_tokens=budget,
        reserve_output_tokens=0, safety_margin_tokens=0, quality_floor=0.80,
    )
    return runtime.prepare_sync(
        user_input=str(case.get("query", "")),
        messages=case.get("messages", []),
        documents=case.get("documents", []),
        memories=case.get("memories", []),
        tools=case.get("tools", []),
    )


def _safe(prepared: Any, case: Mapping[str, Any]) -> bool:
    text = prepared.plan.final_context
    return bool(
        prepared.feasible
        and prepared.quality.passed
        and _contains_all(text, case.get("required_instructions", [])) == 1.0
        and _contains_all(text, case.get("expected_facts", [])) == 1.0
        and _contains_all(text, case.get("expected_tools", [])) == 1.0
        and prepared.quality.metrics["dependency_integrity"] == 1.0
    )


def _maximum_safe_observed(
    case: Mapping[str, Any], raw_tokens: int, *, probes: int
) -> Dict[str, Any]:
    """Find the lowest safe tested budget with bounded binary refinement.

    This is an observed bound at the tested budget resolution, not a proof of
    a globally optimal reduction or downstream model answer quality.
    """
    low, high = 1, max(1, raw_tokens)
    best_tokens = raw_tokens
    tested = 0
    for _ in range(probes):
        if low >= high:
            break
        budget = (low + high) // 2
        prepared = _runtime(case, budget)
        tested += 1
        if _safe(prepared, case):
            best_tokens = min(best_tokens, prepared.plan.metrics.planned_tokens)
            high = budget
        else:
            low = budget + 1
    return {
        "observed_reduction": 1.0 - best_tokens / max(1, raw_tokens),
        "best_safe_tokens": best_tokens,
        "tested_budget_count": tested,
        "search_resolution_tokens": max(0, high - low),
    }


def evaluate_case(case: Mapping[str, Any], *, max_safe_probes: int = 5) -> Dict[str, Any]:
    expanded = _expanded(case)
    budget = int(expanded["budget"])
    inputs = {
        "messages": expanded.get("messages", []),
        "documents": expanded.get("documents", []),
        "memories": expanded.get("memories", []),
        "tools": expanded.get("tools", []),
        "query": str(expanded.get("query", "")),
        "model": "sarvam-105b",
        "max_input_tokens": budget,
        "reserve_output_tokens": 0,
        "safety_margin_tokens": 0,
    }
    started = time.perf_counter()
    v06 = plan_context(**inputs)
    v06_ms = (time.perf_counter() - started) * 1000.0
    raw = "".join(
        render_context_item(decision.item, decision.item.content)
        for decision in v06.decisions
    ).rstrip()
    raw_tokens = count_tokens(raw)
    records = [_measure("raw", raw, expanded, raw_tokens, budget, 0.0)]
    started = time.perf_counter()
    prefix = _truncate_to_tokens(raw, budget)
    records.append(_measure("prefix", prefix, expanded, raw_tokens, budget,
                            (time.perf_counter() - started) * 1000.0))
    started = time.perf_counter()
    ratio = min(1.0, max(0.05, budget / max(1, raw_tokens)))
    fixed = compress(raw, target_ratio=ratio, min_tokens_for_compression=0).compressed_text
    records.append(_measure("fixed_ratio", fixed, expanded, raw_tokens, budget,
                            (time.perf_counter() - started) * 1000.0))
    records.append(_measure("v06_adaptive", v06.final_context, expanded, raw_tokens,
                            budget, v06_ms, feasible=v06.feasible))
    started = time.perf_counter()
    v07 = _runtime(expanded, budget)
    v07_ms = (time.perf_counter() - started) * 1000.0
    record = _measure("v07_runtime", v07.plan.final_context, expanded, raw_tokens, budget,
                      v07_ms, feasible=v07.feasible)
    record.update({
        "quality_gate_passed": v07.quality.passed,
        "dependency_integrity": v07.quality.metrics["dependency_integrity"],
        "quality_floor_violation": not v07.quality.passed,
        "planner_latency_ms": v07.plan.metrics.planning_latency_ms,
        "transformation_latency_ms": v07.plan.metrics.transformation_latency_ms,
        "selected_methods": dict(Counter(d.selected.method.value for d in v07.plan.decisions)),
    })
    records.append(record)
    return {
        "id": expanded["id"],
        "category": expanded["category"],
        "language": expanded["language"],
        "budget_tokens": budget,
        "raw_tokens": raw_tokens,
        "records": records,
        "maximum_safe_context_reduction": _maximum_safe_observed(
            expanded, raw_tokens, probes=max_safe_probes
        ),
    }


def build_result(dataset: Path = DATASET, *, max_safe_probes: int = 5) -> Dict[str, Any]:
    cases = [evaluate_case(case, max_safe_probes=max_safe_probes) for case in load_cases(dataset)]
    groups: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for case in cases:
        for record in case["records"]:
            groups[record["baseline"]].append(record)
    fields = ("budget_success", "hard_constraint_retention", "required_fact_retention",
              "entity_retention", "tool_availability", "token_reduction", "latency_ms")
    summary = {
        baseline: {
            field: statistics.fmean(float(record[field]) for record in groups[baseline])
            for field in fields
        }
        for baseline in BASELINES
    }
    safe_values = [case["maximum_safe_context_reduction"]["observed_reduction"] for case in cases]
    return {
        "schema_version": "1.0",
        "classification": "MEASURED_OFFLINE",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "case_count": len(cases),
        "categories": dict(sorted(Counter(case["category"] for case in cases).items())),
        "languages": dict(sorted(Counter(case["language"] for case in cases).items())),
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "token_counter": get_active_token_counter_name(),
            "network_calls": 0, "provider_calls": 0,
        },
        "summary": summary,
        "v07_quality_floor_violations": sum(
            case["records"][-1]["quality_floor_violation"] for case in cases
        ),
        "maximum_safe_context_reduction_observed": {
            "mean": statistics.fmean(safe_values),
            "median": statistics.median(safe_values),
            "min": min(safe_values), "max": max(safe_values),
            "probes_per_case": max_safe_probes,
            "interpretation": "lowest safe representation observed at tested budgets; task-grounded exact checks and local quality gates only",
        },
        "cases": cases,
    }


def render_report(result: Mapping[str, Any]) -> str:
    lines = [
        "# LLMSlim v0.7 Agent Context Runtime benchmark", "",
        "Classification: **MEASURED_OFFLINE**. No provider or network calls.", "",
        f"Corpus: {result['case_count']} frozen cases; SHA-256 `{result['dataset_sha256']}`.",
        f"Categories: `{json.dumps(result['categories'], sort_keys=True)}`.", "",
        "| Baseline | Budget success | Hard constraints | Required facts | Tool availability | Reduction | Mean latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in BASELINES:
        row = result["summary"][name]
        lines.append(
            f"| {name} | {row['budget_success']:.1%} | {row['hard_constraint_retention']:.1%} | "
            f"{row['required_fact_retention']:.1%} | {row['tool_availability']:.1%} | "
            f"{row['token_reduction']:.1%} | {row['latency_ms']:.2f} |"
        )
    safe = result["maximum_safe_context_reduction_observed"]
    lines += ["", "## Maximum Safe Context Reduction", "",
              f"Observed mean `{safe['mean']:.1%}`, median `{safe['median']:.1%}`, range "
              f"`{safe['min']:.1%}–{safe['max']:.1%}` across {safe['probes_per_case']} "
              "budget probes per case. This is an observed lower bound at tested budgets, not "
              "a universal optimal percentage or real-model task-success result.", "",
              f"v0.7 quality-floor violations: `{result['v07_quality_floor_violations']}`.", "",
              "Tool-contract and dependency integrity for v0.7 are in per-case JSON; "
              "the four older baselines do not expose comparable graph artifacts.", "",
              "## Limits", "",
              "- Exact string checks may miss semantic errors or valid paraphrases.",
              "- Token counts are estimates, not provider-reported usage.",
              "- Latency depends on this machine and Python environment.",
              "- The v0.6 planner code and dataset were not modified.", "",
              "## Reproduction", "", "```bash", "python -m benchmarks.v07_runtime", "```"]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--max-safe-probes", type=int, default=5)
    args = parser.parse_args(argv)
    if not 0 <= args.max_safe_probes <= 20:
        parser.error("max-safe-probes must be between 0 and 20")
    result = build_result(args.dataset, max_safe_probes=args.max_safe_probes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(result), encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
