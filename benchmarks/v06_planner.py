"""Frozen offline benchmark for the LLMSlim v0.6 Adaptive Context Planner.

Compares raw context, naive prefix truncation, the existing fixed-ratio
compressor, and adaptive planning. All quality checks are task-grounded string
constraints; no LLM judge or network service is used.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple

from llmslim import __version__, compress, plan_context
from llmslim.mcp import (
    CatalogChangedError,
    PlanMode,
    StaticToolCatalogSource,
    ToolCatalogSnapshot,
    hydrate_plan,
)
from llmslim.planning.candidates import render_context_item
from llmslim.planning.mcp import plan_mcp_context
from llmslim.tokens import count_tokens, get_active_token_counter_name
from llmslim.tools import canonical_json, from_mcp_tool

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks" / "datasets" / "v06_context_planning.json"
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results" / "v0.6-planner-latest.json"
DEFAULT_REPORT = ROOT / "docs" / "planning" / "BENCHMARK_REPORT.md"

BASELINES = ("raw_full_context", "naive_prefix_truncation", "fixed_ratio", "adaptive_planner")


def load_cases(path: Path = DATASET) -> Tuple[Mapping[str, Any], ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or not isinstance(payload.get("cases"), list):
        raise ValueError("invalid v0.6 benchmark dataset")
    ids = [case.get("id") for case in payload["cases"]]
    if any(not isinstance(case_id, str) or not case_id for case_id in ids):
        raise ValueError("each benchmark case requires a non-empty ID")
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark case IDs must be unique")
    return tuple(payload["cases"])


def _tool_catalog(count: int, boundary_tool: bool = False) -> List[Dict[str, Any]]:
    tools = []
    for index in range(count):
        if index == 0:
            name = "tool_000_lookup_customer"
        elif index == 1:
            name = "tool_001_schedule_followup"
        elif boundary_tool and index == count - 1:
            name = f"tool_{index:03d}_boundary_target"
        else:
            name = f"tool_{index:03d}_operation"
        tools.append(
            {
                "name": name,
                "description": (
                    f"Authorized host capability {name}. Ranking this schema never grants "
                    "authorization and LLMSlim never invokes it."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Caller-approved query"},
                        "tenant_id": {"type": "string"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            }
        )
    return tools


def expand_case(case: Mapping[str, Any]) -> Dict[str, Any]:
    expanded = dict(case)
    if case.get("history_turns"):
        turns = int(case["history_turns"])
        messages: List[Dict[str, str]] = [
            {
                "role": "system",
                "content": "Preserve exact customer facts. Never invent a project detail.",
            },
            {"role": "user", "content": str(case["early_fact"])},
            {"role": "assistant", "content": "I recorded that verified fact."},
        ]
        for index in range(max(0, turns - 4)):
            role = "user" if index % 2 == 0 else "assistant"
            messages.append(
                {
                    "role": role,
                    "content": (
                        f"Routine turn {index:03d}: planning notes about meetings, formatting, "
                        "status reviews, and ordinary operational updates without new facts."
                    ),
                }
            )
        messages.append({"role": "user", "content": str(case["query"])})
        expanded["messages"] = messages
    expanded.setdefault("messages", [])
    expanded.setdefault("documents", [])
    expanded.setdefault("memories", [])
    expanded["tools"] = _tool_catalog(
        int(case.get("tool_count", 0)), bool(case.get("boundary_tool", False))
    )
    return expanded


def _raw_context(case: Mapping[str, Any]) -> str:
    sections: List[str] = []
    for message in case["messages"]:
        sections.append(f"[message:{message.get('role', 'general')}]\n{message.get('content', '')}")
    for index, document in enumerate(case["documents"]):
        content = document.get("content", "") if isinstance(document, Mapping) else document
        sections.append(f"[document:{index}]\n{content}")
    for index, memory in enumerate(case["memories"]):
        content = memory.get("content", "") if isinstance(memory, Mapping) else memory
        sections.append(f"[memory:{index}]\n{content}")
    for index, tool in enumerate(case["tools"]):
        sections.append(f"[tool:{index}]\n{canonical_json(tool)}")
    if case.get("query") and not case["messages"]:
        sections.append(f"[query]\n{case['query']}")
    return "\n\n".join(sections)


def _truncate_to_tokens(text: str, budget: int) -> str:
    if count_tokens(text) <= budget:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if count_tokens(text[:middle]) <= budget:
            low = middle
        else:
            high = middle - 1
    return text[:low]


def _contains_all(text: str, values: Sequence[str]) -> float:
    if not values:
        return 1.0
    folded = text.casefold()
    return sum(str(value).casefold() in folded for value in values) / len(values)


def _measure_output(
    name: str,
    text: str,
    *,
    elapsed_ms: float,
    budget: int,
    original_tokens: int,
    case: Mapping[str, Any],
    feasible: bool | None = None,
) -> Dict[str, Any]:
    final_tokens = count_tokens(text)
    fact_retention = _contains_all(text, case.get("expected_facts", []))
    instruction_retention = _contains_all(text, case.get("required_instructions", []))
    tool_availability = _contains_all(text, case.get("expected_tools", []))
    return {
        "baseline": name,
        "final_tokens": final_tokens,
        "budget_tokens": budget,
        "budget_success": final_tokens <= budget if feasible is None else bool(feasible),
        "budget_utilization": final_tokens / budget if budget else 0.0,
        "context_reduction": 1.0 - final_tokens / max(1, original_tokens),
        "hard_constraint_retention": min(instruction_retention, tool_availability),
        "trusted_instruction_retention": instruction_retention,
        "factual_retention": fact_retention,
        "entity_retention": fact_retention,
        "tool_availability": tool_availability,
        "latency_ms": elapsed_ms,
    }


def evaluate_case(case: Mapping[str, Any]) -> Dict[str, Any]:
    expanded = expand_case(case)
    budget = int(expanded["budget"])
    planner_started = time.perf_counter()
    plan = plan_context(
        messages=expanded["messages"],
        documents=expanded["documents"],
        memories=expanded["memories"],
        tools=expanded["tools"],
        query=str(expanded.get("query", "")),
        model="sarvam-105b",
        max_input_tokens=budget,
        reserve_output_tokens=0,
        safety_margin_tokens=0,
    )
    planner_elapsed_ms = (time.perf_counter() - planner_started) * 1000.0
    # Compare every baseline against the exact same provenance-delimited wire
    # representation. Counting a content-only raw form against the planner's
    # safe envelope would incorrectly report the security boundary as growth.
    raw = "".join(
        render_context_item(decision.item, decision.item.content)
        for decision in plan.decisions
    ).rstrip()
    raw_tokens = count_tokens(raw)
    records: List[Dict[str, Any]] = []

    records.append(
        _measure_output(
            "raw_full_context",
            raw,
            elapsed_ms=0.0,
            budget=budget,
            original_tokens=raw_tokens,
            case=expanded,
        )
    )

    started = time.perf_counter()
    naive = _truncate_to_tokens(raw, budget)
    records.append(
        _measure_output(
            "naive_prefix_truncation",
            naive,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            budget=budget,
            original_tokens=raw_tokens,
            case=expanded,
        )
    )

    ratio = min(1.0, max(0.05, budget / max(1, raw_tokens)))
    started = time.perf_counter()
    fixed = compress(raw, target_ratio=ratio, min_tokens_for_compression=0).compressed_text
    records.append(
        _measure_output(
            "fixed_ratio",
            fixed,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            budget=budget,
            original_tokens=raw_tokens,
            case=expanded,
        )
    )

    adaptive = _measure_output(
        "adaptive_planner",
        plan.final_context,
        elapsed_ms=planner_elapsed_ms,
        budget=budget,
        original_tokens=raw_tokens,
        case=expanded,
        feasible=plan.feasible,
    )
    adaptive.update(
        {
            "validation_passed": plan.validation.passed,
            "decisions": Counter(decision.selected.method.value for decision in plan.decisions),
            "estimated_input_cost_before_inr": plan.metrics.estimated_input_cost_before,
            "estimated_input_cost_after_inr": plan.metrics.estimated_input_cost_after,
            "warnings": list(plan.warnings),
        }
    )
    records.append(adaptive)
    return {
        "id": expanded["id"],
        "category": expanded["category"],
        "language": expanded["language"],
        "original_tokens": raw_tokens,
        "budget_tokens": budget,
        "records": records,
    }


def _aggregate(cases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    grouped: MutableMapping[str, List[Mapping[str, Any]]] = defaultdict(list)
    for case in cases:
        for record in case["records"]:
            grouped[str(record["baseline"])].append(record)
    metrics = (
        "budget_success",
        "hard_constraint_retention",
        "trusted_instruction_retention",
        "factual_retention",
        "entity_retention",
        "tool_availability",
        "context_reduction",
        "budget_utilization",
        "latency_ms",
    )
    result: Dict[str, Any] = {}
    for baseline in BASELINES:
        records = grouped[baseline]
        result[baseline] = {
            metric: statistics.fmean(float(record[metric]) for record in records)
            for metric in metrics
        }
        result[baseline]["case_count"] = len(records)
    return result


def _mcp_evaluation() -> Dict[str, Any]:
    catalog = tuple(from_mcp_tool(tool, namespace="benchmark") for tool in _tool_catalog(25))
    snapshot = asyncio.run(StaticToolCatalogSource(catalog, "benchmark").list_tools())
    modes: Dict[str, Any] = {}
    for mode in (PlanMode.FULL, PlanMode.MEASURE_ONLY, PlanMode.SELECTIVE):
        result = plan_mcp_context(
            snapshot,
            mode=mode,
            query="lookup customer",
            top_k=5,
            experimental=mode is PlanMode.SELECTIVE,
            max_input_tokens=10_000,
            reserve_output_tokens=0,
            safety_margin_tokens=0,
        )
        modes[mode.value] = {
            "experimental": result.catalog_plan.experimental,
            "selected_tools": len(result.catalog_plan.selected_tool_ids),
            "catalog_tokens": result.catalog_plan.metrics.catalog_tokens,
            "presented_tokens": result.catalog_plan.metrics.presented_tokens,
            "required_tool_present": any(
                "lookup_customer" in tool_id for tool_id in result.catalog_plan.selected_tool_ids
            ),
        }
    stale = ToolCatalogSnapshot(
        source_id=snapshot.source_id,
        tools=snapshot.tools[:-1],
        catalog_fingerprint="changed",
        retrieved_at=snapshot.retrieved_at,
        expires_at=snapshot.expires_at,
        cache_scope=snapshot.cache_scope,
        pages=snapshot.pages,
        cache_status="test",
    )
    full_plan = plan_mcp_context(
        snapshot,
        mode=PlanMode.FULL,
        max_input_tokens=10_000,
        reserve_output_tokens=0,
        safety_margin_tokens=0,
    ).catalog_plan
    stale_rejected = False
    try:
        hydrate_plan(stale, full_plan)
    except CatalogChangedError:
        stale_rejected = True
    return {"modes": modes, "stale_plan_rejected": stale_rejected, "tool_execution_count": 0}


def build_result(dataset_path: Path = DATASET) -> Dict[str, Any]:
    cases = [evaluate_case(case) for case in load_cases(dataset_path)]
    return {
        "schema_version": "1.0",
        "classification": "MEASURED_OFFLINE",
        "llmslim_version": __version__,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset": {
            "path": str(dataset_path.relative_to(ROOT)),
            "sha256": __import__("hashlib").sha256(dataset_path.read_bytes()).hexdigest(),
            "case_count": len(cases),
            "categories": dict(sorted(Counter(case["category"] for case in cases).items())),
            "languages": dict(sorted(Counter(case["language"] for case in cases).items())),
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "token_counter": get_active_token_counter_name(),
            "network_calls": 0,
            "provider_calls": 0,
        },
        "summary": _aggregate(cases),
        "mcp": _mcp_evaluation(),
        "cases": cases,
        "live_sarvam": {
            "classification": "NOT_RUN_BY_OFFLINE_BENCHMARK",
            "required_opt_in": "LLMSLIM_RUN_LIVE_SARVAM=1",
        },
    }


def render_report(result: Mapping[str, Any]) -> str:
    lines = [
        "# LLMSlim v0.6 Adaptive Context Planner benchmark",
        "",
        f"Classification: **{result['classification']}**. No provider or network calls were made.",
        "",
        f"Corpus: {result['dataset']['case_count']} frozen cases; SHA-256 `{result['dataset']['sha256']}`.",
        f"Categories: `{json.dumps(result['dataset']['categories'], sort_keys=True)}`.",
        f"Languages: `{json.dumps(result['dataset']['languages'], ensure_ascii=False, sort_keys=True)}`.",
        "",
        "## Four-baseline comparison",
        "",
        "| Baseline | Budget success | Hard constraints | Facts retained | Tool availability | Reduction | Mean latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for baseline in BASELINES:
        row = result["summary"][baseline]
        lines.append(
            f"| {baseline} | {row['budget_success']:.1%} | "
            f"{row['hard_constraint_retention']:.1%} | {row['factual_retention']:.1%} | "
            f"{row['tool_availability']:.1%} | {row['context_reduction']:.1%} | "
            f"{row['latency_ms']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## MCP safety observations",
            "",
            f"- Stale catalog plan rejected: `{result['mcp']['stale_plan_rejected']}`.",
            f"- Tool executions performed by benchmark/planner: `{result['mcp']['tool_execution_count']}`.",
            f"- SELECTIVE remains experimental: `{result['mcp']['modes']['selective']['experimental']}`.",
            "",
            "## Interpretation and limitations",
            "",
            "- Metrics are measured on repository-owned synthetic cases, not production traffic.",
            "- Fact/entity checks are exact task-grounded constraints; they do not establish universal semantic quality.",
            "- Token counts are tokenizer estimates and are not provider-reported usage.",
            "- Latency is environment-specific. Raw context has no transformation work and is expected to be fastest.",
            "- Cases are not constructed so the adaptive planner must win; the JSON artifact retains per-case failures.",
            "- Live Sarvam quality, latency, and billed usage are intentionally separate and require explicit credentials/opt-in.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "python -m benchmarks.v06_planner",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    result = build_result(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(result), encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
