"""Measure agent tool schema payloads without changing their contracts."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from typing import Any, Dict, List, Mapping, Sequence

from llmslim.tokens import count_tokens, get_active_token_counter_name

CATALOG_SCALES = (1, 4, 8, 16, 32, 64)
SESSION_TURNS = (1, 4, 8, 16, 32)


def _tool_schema(index: int, complexity: str) -> Dict[str, Any]:
    name = f"{complexity.lower()}_tool_{index:02d}"
    properties: Dict[str, Any] = {
        "query": {"type": "string", "description": "User supplied search or lookup expression."}
    }
    required = ["query"]
    if complexity in {"MEDIUM", "COMPLEX"}:
        properties.update(
            {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Maximum number of matching records to return.",
                },
                "format": {
                    "type": "string",
                    "enum": ["summary", "detailed", "json"],
                    "description": "Requested response representation.",
                },
            }
        )
    if complexity == "COMPLEX":
        properties.update(
            {
                "filters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "region": {"type": "string", "enum": ["us", "eu", "apac"]},
                        "from_date": {"type": "string", "format": "date"},
                        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                    },
                    "description": "Optional region, date, and tag constraints.",
                },
                "include_archived": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include archived records when explicitly requested.",
                },
            }
        )
        required.append("format")
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Retrieve {complexity.lower()} operational records for a scoped agent task.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": required,
            },
        },
    }


def generate_catalog(scale: int, complexity: str) -> List[Dict[str, Any]]:
    if scale not in CATALOG_SCALES or complexity not in {"SIMPLE", "MEDIUM", "COMPLEX"}:
        raise ValueError("unsupported catalog scale or complexity")
    return [_tool_schema(index, complexity) for index in range(1, scale + 1)]


def canonical_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def _strip_descriptions(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_descriptions(item) for key, item in value.items() if key != "description"
        }
    if isinstance(value, list):
        return [_strip_descriptions(item) for item in value]
    return value


def _descriptions(value: Any) -> List[str]:
    if isinstance(value, dict):
        found = [
            item for key, item in value.items() if key == "description" and isinstance(item, str)
        ]
        return found + [
            description for item in value.values() for description in _descriptions(item)
        ]
    if isinstance(value, list):
        return [description for item in value for description in _descriptions(item)]
    return []


def schema_contract(tool: Mapping[str, Any]) -> Dict[str, Any]:
    """Return fields whose mutation can change tool invocation semantics."""
    function = tool.get("function", tool)
    parameters = function.get("parameters", {})
    return {"name": function.get("name"), "parameters": _contract_node(parameters)}


def _contract_node(node: Any) -> Any:
    if not isinstance(node, Mapping):
        return node
    keep = {
        key: node[key]
        for key in (
            "type",
            "enum",
            "required",
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "pattern",
            "format",
            "default",
            "additionalProperties",
            "minItems",
            "maxItems",
        )
        if key in node
    }
    if "properties" in node:
        keep["properties"] = {
            key: _contract_node(value) for key, value in node["properties"].items()
        }
    if "items" in node:
        keep["items"] = _contract_node(node["items"])
    return keep


def compare_contracts(before: Mapping[str, Any], after: Mapping[str, Any]) -> Dict[str, Any]:
    before_contract, after_contract = schema_contract(before), schema_contract(after)
    return {
        "contract_equal": before_contract == after_contract,
        "description_equal": _descriptions(before) == _descriptions(after),
        "before": before_contract,
        "after": after_contract,
    }


def measure_catalog(catalog: Sequence[Mapping[str, Any]], complexity: str) -> Dict[str, Any]:
    serialized = canonical_json(catalog)
    tool_counts = [count_tokens(canonical_json(tool)) for tool in catalog]
    structural_counts = [
        count_tokens(canonical_json(_strip_descriptions(tool))) for tool in catalog
    ]
    description_counts = [count_tokens(" ".join(_descriptions(tool))) for tool in catalog]
    signatures = [
        canonical_json(_strip_descriptions(tool["function"]["parameters"])) for tool in catalog
    ]
    counts = Counter(signatures)
    repeated = sum(
        (count - 1) * count_tokens(signature) for signature, count in counts.items() if count > 1
    )
    total = count_tokens(serialized)
    return {
        "classification": "MEASURED",
        "complexity": complexity,
        "tool_count": len(catalog),
        "total_schema_tokens": total,
        "mean_tokens_per_tool": statistics.mean(tool_counts),
        "median_tokens_per_tool": statistics.median(tool_counts),
        "p95_tokens_per_tool": _p95(tool_counts),
        "description_tokens": sum(description_counts),
        "structural_schema_tokens": sum(structural_counts),
        "repeated_schema_tokens": repeated,
        "description_token_share": sum(description_counts) / total if total else 0.0,
        "structural_schema_token_share": sum(structural_counts) / total if total else 0.0,
        "full_catalog_tokens_per_turn": total,
        "cumulative_schema_tokens": {
            str(turns): {
                "classification": "DERIVED",
                "tokens": total * turns,
                "assumption": "full catalog resent each turn",
            }
            for turns in SESSION_TURNS
        },
        "unused_tool_scenarios": _unused_tool_scenarios(catalog, total),
        "token_counter_used": get_active_token_counter_name(),
    }


def _unused_tool_scenarios(
    catalog: Sequence[Mapping[str, Any]], total: int
) -> List[Dict[str, Any]]:
    relevant_one = count_tokens(canonical_json(list(catalog[:1]))) if catalog else 0
    relevant_two = count_tokens(canonical_json(list(catalog[:2]))) if catalog else 0
    return [
        {
            "scenario": "no_tool_called",
            "classification": "DERIVED",
            "avoidable_schema_tokens": total,
        },
        {
            "scenario": "one_tool_called",
            "classification": "DERIVED",
            "avoidable_schema_tokens": max(0, total - relevant_one),
        },
        {
            "scenario": "small_subset_relevant",
            "classification": "DERIVED",
            "avoidable_schema_tokens": max(0, total - relevant_two),
        },
        {
            "scenario": "many_tools_one_relevant",
            "classification": "DERIVED",
            "avoidable_schema_tokens": max(0, total - relevant_one),
        },
    ]


def _p95(values: Sequence[float]) -> float:
    return sorted(values)[max(0, int((len(values) - 1) * 0.95))] if values else 0.0


def run_schema_tax() -> Dict[str, Any]:
    catalogs = [
        measure_catalog(generate_catalog(scale, complexity), complexity)
        for complexity in ("SIMPLE", "MEDIUM", "COMPLEX")
        for scale in CATALOG_SCALES
    ]
    return {
        "scope": "BENCHMARK_ONLY_NO_PRODUCTION_SCHEMA_COMPRESSION",
        "catalogs": catalogs,
        "catalog_count": len(catalogs),
        "tool_schema_count": sum(item["tool_count"] for item in catalogs),
        "relevance_cases": relevance_cases(),
        "selection_metrics": "NOT_APPLICABLE_NO_SELECTION_ALGORITHM",
    }


def relevance_cases() -> List[Dict[str, Any]]:
    return [
        {
            "id": "calendar_next",
            "intent": "Find my next calendar meeting.",
            "relevant_tool_ids": ["calendar.search_events"],
        },
        {
            "id": "issue_and_notify",
            "intent": "Create a bug issue and notify the team.",
            "relevant_tool_ids": ["github.create_issue", "slack.send_message"],
        },
        {
            "id": "weather",
            "intent": "What is the weather tomorrow in Delhi?",
            "relevant_tool_ids": ["weather.get_forecast"],
        },
        {"id": "no_tool", "intent": "Explain what a JSON Schema is.", "relevant_tool_ids": []},
        {
            "id": "email_search",
            "intent": "Find the invoice email from last month.",
            "relevant_tool_ids": ["gmail.search_messages"],
        },
        {
            "id": "repository_status",
            "intent": "Show open issues in this repository.",
            "relevant_tool_ids": ["github.list_issues"],
        },
    ]
