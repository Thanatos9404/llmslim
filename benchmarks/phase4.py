"""Offline Phase 4 tool-contract, relevance, and exposure benchmarks."""

from __future__ import annotations

import copy
import statistics
import time
from typing import Any, Dict, List, Mapping, Sequence

from benchmarks.schema_tax.core import CATALOG_SCALES, canonical_json, generate_catalog
from llmslim.tokens import count_tokens, get_active_token_counter_name
from llmslim.tools import (
    from_mcp_tool,
    optimize_tool_catalog,
    plan_tool_context,
    rank_tools,
    select_tools,
)

RELEVANCE_GO_NO_GO_RECALL_AT_5 = 0.95
RELEVANCE_GO_NO_GO_NO_TOOL_ACCURACY = 1.0


def _tool(
    name: str, description: str, server: str, properties: Mapping[str, Mapping[str, Any]]
) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "server": server,
        "inputSchema": {
            "type": "object",
            "properties": dict(properties),
            "additionalProperties": False,
        },
        "_meta": {"fixture_provenance": "repository-owned synthetic Phase 4 relevance fixture"},
    }


def relevance_catalog() -> List[Dict[str, Any]]:
    """Repository-owned, realistic MCP-shaped tools; no proprietary catalog is copied."""
    return [
        _tool(
            "calendar.search_events",
            "Find calendar events, meetings, attendees, and dates.",
            "calendar",
            {"query": {"type": "string", "description": "Meeting or attendee search."}},
        ),
        _tool(
            "calendar.create_event",
            "Create a calendar event or schedule a meeting.",
            "calendar",
            {"title": {"type": "string"}, "start": {"type": "string", "format": "date-time"}},
        ),
        _tool(
            "calendar.cancel_event",
            "Cancel an existing calendar event or meeting.",
            "calendar",
            {"event_id": {"type": "string"}},
        ),
        _tool(
            "github.search_code",
            "Search source code in GitHub repositories.",
            "github",
            {"query": {"type": "string", "description": "Code symbol or text."}},
        ),
        _tool(
            "github.create_issue",
            "Create a GitHub issue for a bug, task, or feature request.",
            "github",
            {"title": {"type": "string"}, "body": {"type": "string"}},
        ),
        _tool(
            "github.list_issues",
            "List open or closed GitHub repository issues.",
            "github",
            {"state": {"type": "string", "enum": ["open", "closed"]}},
        ),
        _tool(
            "gmail.search_messages",
            "Search Gmail messages, invoices, and email threads.",
            "gmail",
            {"query": {"type": "string"}},
        ),
        _tool(
            "gmail.send_message",
            "Send an email message through Gmail.",
            "gmail",
            {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
        ),
        _tool(
            "slack.send_message",
            "Send a Slack message to a channel or colleague.",
            "slack",
            {"channel": {"type": "string"}, "text": {"type": "string"}},
        ),
        _tool(
            "weather.get_forecast",
            "Get a weather forecast for a city and date.",
            "weather",
            {"location": {"type": "string"}, "date": {"type": "string", "format": "date"}},
        ),
    ]


def relevance_cases() -> List[Dict[str, Any]]:
    return [
        {
            "id": "calendar_next",
            "query": "Find my next calendar meeting.",
            "required": ["calendar/calendar.search_events"],
        },
        {
            "id": "calendar_create",
            "query": "Schedule a project planning meeting tomorrow.",
            "required": ["calendar/calendar.create_event"],
        },
        {
            "id": "calendar_cancel",
            "query": "Cancel the design review event.",
            "required": ["calendar/calendar.cancel_event"],
        },
        {
            "id": "code_search",
            "query": "Search the repository source for the auth middleware.",
            "required": ["github/github.search_code"],
        },
        {
            "id": "issue_create",
            "query": "Create a bug issue for the login error.",
            "required": ["github/github.create_issue"],
        },
        {
            "id": "issue_list",
            "query": "Show the open issues in this repository.",
            "required": ["github/github.list_issues"],
        },
        {
            "id": "email_search",
            "query": "Find the invoice email from last month.",
            "required": ["gmail/gmail.search_messages"],
        },
        {
            "id": "email_send",
            "query": "Send the release notes by email to the team.",
            "required": ["gmail/gmail.send_message"],
        },
        {
            "id": "weather",
            "query": "What is the weather forecast in Delhi tomorrow?",
            "required": ["weather/weather.get_forecast"],
        },
        {
            "id": "issue_and_notify",
            "query": "Create a bug issue and notify the team in Slack.",
            "required": ["github/github.create_issue", "slack/slack.send_message"],
        },
        {
            "id": "calendar_ambiguous",
            "query": "Manage my calendar meeting.",
            "required": ["calendar/calendar.search_events", "calendar/calendar.create_event"],
        },
        {"id": "no_tool", "query": "Explain what a JSON Schema is.", "required": []},
    ]


def _aggregate(values: Sequence[float]) -> Dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p95": None}
    ordered = sorted(values)
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "median": statistics.median(values),
        "p95": ordered[max(0, int((len(ordered) - 1) * 0.95))],
    }


def run_schema_optimization_benchmark(repetitions: int = 5) -> Dict[str, Any]:
    """Reuse all Phase 2 catalog scales and complexity classes exactly."""
    catalogs: List[Dict[str, Any]] = []
    latency: List[float] = []
    for complexity in ("SIMPLE", "MEDIUM", "COMPLEX"):
        for scale in CATALOG_SCALES:
            raw = generate_catalog(scale, complexity)
            for _ in range(1):
                optimize_tool_catalog(raw)
            timings = []
            for _ in range(repetitions):
                started = time.perf_counter()
                result = optimize_tool_catalog(raw)
                timings.append((time.perf_counter() - started) * 1000)
            source_tokens = count_tokens(canonical_json(raw))
            optimized_tokens = count_tokens(canonical_json([tool.raw for tool in result.optimized]))
            serializer_source = sum(item.original_tokens for item in result.per_tool)
            serializer_optimized = sum(item.optimized_tokens for item in result.per_tool)
            catalogs.append(
                {
                    "classification": "MEASURED",
                    "complexity": complexity,
                    "tool_count": scale,
                    "phase2_compact_source_tokens": source_tokens,
                    "optimized_tokens": optimized_tokens,
                    "tokens_saved": source_tokens - optimized_tokens,
                    "reduction_ratio": (source_tokens - optimized_tokens) / source_tokens
                    if source_tokens
                    else 0.0,
                    "default_json_serialization_tokens": serializer_source,
                    "compact_json_serialization_tokens": serializer_optimized,
                    "serialization_tokens_saved": serializer_source - serializer_optimized,
                    "contract_statuses": sorted(
                        {item.equivalence.status.value for item in result.per_tool}
                    ),
                    "latency_ms": _aggregate(timings),
                    "operators": [item.operators_applied for item in result.per_tool],
                }
            )
            latency.extend(timings)
    performance: List[Dict[str, Any]] = [
        {
            "complexity": row["complexity"],
            "tool_count": row["tool_count"],
            "latency_ms": row["latency_ms"],
        }
        for row in catalogs
    ]
    for complexity in ("SIMPLE", "MEDIUM", "COMPLEX"):
        raw = _catalog_at_128(complexity)
        timings = []
        for _ in range(1):
            optimize_tool_catalog(raw)
        for _ in range(repetitions):
            started = time.perf_counter()
            optimize_tool_catalog(raw)
            timings.append((time.perf_counter() - started) * 1000)
        performance.append(
            {"complexity": complexity, "tool_count": 128, "latency_ms": _aggregate(timings)}
        )
        latency.extend(timings)
    total_source = sum(item["phase2_compact_source_tokens"] for item in catalogs)
    total_optimized = sum(item["optimized_tokens"] for item in catalogs)
    return {
        "classification": "MEASURED",
        "scope": "Phase 2 generated catalogs with canonical compact JSON baseline",
        "catalogs": catalogs,
        "catalog_count": len(catalogs),
        "tool_schema_count": sum(item["tool_count"] for item in catalogs),
        "original_tokens": total_source,
        "optimized_tokens": total_optimized,
        "tokens_saved": total_source - total_optimized,
        "reduction_ratio": (total_source - total_optimized) / total_source if total_source else 0.0,
        "latency_ms": _aggregate(latency),
        "performance_by_scale": performance,
        "ablation": {
            "canonical_json_serialization": "MEASURED",
            "other_operators": "NOT_IMPLEMENTED_CONTRACT_UNPROVEN",
        },
    }


def _catalog_at_128(complexity: str) -> List[Dict[str, Any]]:
    """Extend a Phase 2 generated catalog for a performance-only 128-tool run."""
    first = generate_catalog(64, complexity)
    second = copy.deepcopy(first)
    for index, tool in enumerate(second, start=65):
        tool["function"]["name"] = "%s_tool_%02d" % (complexity.lower(), index)
    return first + second


def run_relevance_benchmark() -> Dict[str, Any]:
    tools = [from_mcp_tool(raw) for raw in relevance_catalog()]
    cases: List[Dict[str, Any]] = []
    recall_at: Dict[int, List[float]] = {1: [], 3: [], 5: []}
    precision_at: Dict[int, List[float]] = {1: [], 3: [], 5: []}
    reciprocal_ranks: List[float] = []
    for case in relevance_cases():
        ranked = rank_tools(case["query"], tools)
        expected = set(case["required"])
        selection = select_tools(case["query"], tools, top_k=5, mode="conservative")
        row = {
            "id": case["id"],
            "required": sorted(expected),
            "ranked_tool_ids": [item.tool.tool_id for item in ranked],
            "no_tool_detected": selection.no_tool_detected,
        }
        for k in (1, 3, 5):
            top = [item.tool.tool_id for item in ranked[:k]]
            if expected:
                recall = len(expected.intersection(top)) / len(expected)
                precision = len(expected.intersection(top)) / len(top)
                first = min(
                    (index + 1 for index, tool_id in enumerate(top) if tool_id in expected),
                    default=None,
                )
                reciprocal = 1.0 / first if first else 0.0
            else:
                recall = 1.0 if selection.no_tool_detected else 0.0
                precision = 1.0 if selection.no_tool_detected else 0.0
                reciprocal = precision
            recall_at[k].append(recall)
            precision_at[k].append(precision)
            if k == 5:
                reciprocal_ranks.append(reciprocal)
            row["recall_at_%d" % k] = recall
            row["precision_at_%d" % k] = precision
        cases.append(row)
    metrics = {"recall_at_%d" % k: sum(values) / len(values) for k, values in recall_at.items()}
    metrics.update(
        {"precision_at_%d" % k: sum(values) / len(values) for k, values in precision_at.items()}
    )
    metrics["mrr"] = sum(reciprocal_ranks) / len(reciprocal_ranks)
    no_tool_cases = [row for row in cases if not row["required"]]
    no_tool_accuracy = (
        sum(row["no_tool_detected"] for row in no_tool_cases) / len(no_tool_cases)
        if no_tool_cases
        else 1.0
    )
    return {
        "classification": "MEASURED",
        "provenance": "repository-owned synthetic realistic MCP-style fixtures",
        "catalog_size": len(tools),
        "cases": cases,
        "metrics": metrics,
        "no_tool_accuracy": no_tool_accuracy,
        "go_no_go_thresholds": {
            "recall_at_5": RELEVANCE_GO_NO_GO_RECALL_AT_5,
            "no_tool_accuracy": RELEVANCE_GO_NO_GO_NO_TOOL_ACCURACY,
        },
    }


def run_selective_exposure_benchmark() -> Dict[str, Any]:
    tools = [from_mcp_tool(raw) for raw in relevance_catalog()]
    rows: List[Dict[str, Any]] = []
    for top_k in (16, 8, 5, 3):
        recalls, avoided = [], []
        for case in relevance_cases():
            plan = plan_tool_context(case["query"], tools, top_k=top_k, mode="conservative")
            expected = set(case["required"])
            selected = set(plan.selected_tool_ids)
            recalls.append(
                1.0
                if not expected and not selected
                else (len(expected.intersection(selected)) / len(expected) if expected else 0.0)
            )
            avoided.append(plan.tokens_avoided)
        rows.append(
            {
                "top_k": top_k,
                "required_tool_recall": sum(recalls) / len(recalls),
                "mean_tokens_avoided": sum(avoided) / len(avoided),
                "token_counter_used": get_active_token_counter_name(),
            }
        )
    top5 = next(row for row in rows if row["top_k"] == 5)
    relevance = run_relevance_benchmark()
    shippable = (
        float(top5["required_tool_recall"]) >= RELEVANCE_GO_NO_GO_RECALL_AT_5
        and float(relevance["no_tool_accuracy"]) >= RELEVANCE_GO_NO_GO_NO_TOOL_ACCURACY
    )
    return {
        "classification": "MEASURED",
        "rows": rows,
        "status": "SHIPPABLE_EXPERIMENTAL" if shippable else "RESEARCH_ONLY",
        "thresholds_predeclared": relevance["go_no_go_thresholds"],
    }


def run_phase4_benchmark() -> Dict[str, Any]:
    schema = run_schema_optimization_benchmark()
    relevance = run_relevance_benchmark()
    exposure = run_selective_exposure_benchmark()
    return {
        "classification": "MEASURED",
        "schema_optimization": schema,
        "relevance": relevance,
        "selective_exposure": exposure,
        "lazy_hydration": {
            "status": "EXPERIMENTAL_MODEL_ONLY",
            "note": "The in-memory registry hydrates complete authoritative copies; it does not call executors.",
        },
    }
