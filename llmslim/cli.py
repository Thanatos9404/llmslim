"""Command-line interface for llmslim.

Usage:
    llmslim input.txt -r 0.5 -o compressed.txt --stats
    llmslim input.txt --detect --mode quality
    llmslim input.txt --analyze
    cat prompt.txt | llmslim --ratio 0.4 --cost gpt-5
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Sequence

from .analysis import analyze as run_analysis
from .core import compress
from .cost import estimate_cost_savings, list_supported_models
from .modes import list_modes
from .planning import PolicyPreset, plan_context
from .runtime import ContextRuntime
from .tokens import count_tokens
from .tools import canonical_json, fingerprint_tool_schema, from_mcp_tool, inspect_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmslim",
        description="Compress text/prompts to reduce LLM token usage by 40-70%.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to an input text file. Reads from stdin if omitted.",
    )
    parser.add_argument(
        "-r",
        "--ratio",
        type=float,
        default=0.5,
        help="Target fraction of tokens to keep, e.g. 0.5 = 50%% reduction (default: 0.5).",
    )
    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        default=None,
        help=f"Optimisation mode. Options: 'auto', {', '.join(list_modes())}",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Auto-detect input content type and populate detailed telemetry.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run content analysis only and print the profile (does not perform compression).",
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        default=None,
        help="Optional query for relevance-aware compression (RAG use case).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write compressed text to this file instead of stdout.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print compression statistics to stderr.",
    )
    parser.add_argument(
        "--cost",
        type=str,
        default=None,
        metavar="MODEL",
        help=f"Print a cost-savings estimate for MODEL. Options: {', '.join(list_supported_models())}",
    )
    parser.add_argument(
        "-s",
        "--strategy",
        type=str,
        default="extractive",
        choices=["extractive", "rewrite", "hybrid"],
        help="Optimization strategy: 'extractive' (default), 'rewrite', or 'hybrid'.",
    )
    parser.add_argument(
        "-b",
        "--backend",
        type=str,
        default="tfidf",
        help="Embedding backend for semantic ranking: 'tfidf' (fast, default) or 'semantic'/'sentence-transformers'.",
    )
    parser.add_argument(
        "--requests-per-day",
        type=int,
        default=1000,
        help="Request volume used for --cost estimates (default: 1000).",
    )
    return parser


def build_tools_parser() -> argparse.ArgumentParser:
    """Build the offline tool-catalog inspection parser.

    This intentionally accepts a local JSON file only. MCP endpoints and
    credentials belong in explicit host application configuration rather than
    command-line history.
    """
    parser = argparse.ArgumentParser(
        prog="llmslim tools",
        description="Inspect or measure a local MCP-compatible tool catalog JSON file.",
    )
    subparsers = parser.add_subparsers(dest="tools_command", required=True)
    for name, help_text in (
        ("inspect", "Inspect tool identities, schema bounds, and fingerprints."),
        ("measure", "Measure the complete authoritative tool catalog context cost."),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "file", help="JSON array of MCP tools, or an object containing a tools array."
        )
        command.add_argument("--json", action="store_true", help="Emit stable JSON for automation.")
    return parser


def build_plan_parser() -> argparse.ArgumentParser:
    """Build the local, provider-free adaptive context planning parser."""

    parser = argparse.ArgumentParser(
        prog="llmslim plan",
        description="Plan messages, RAG, memory, and tool schemas against a model budget.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Context JSON object. Reads stdin when omitted or when FILE is '-'.",
    )
    parser.add_argument("--model", default="generic-128k", help="Planner model profile ID.")
    parser.add_argument(
        "--max-input-tokens",
        type=int,
        default=None,
        help="Explicit model-input ceiling. Required for unknown model IDs.",
    )
    parser.add_argument(
        "--reserve-output-tokens",
        type=int,
        default=4096,
        help="Context-window tokens reserved for generation (default: 4096).",
    )
    parser.add_argument(
        "--safety-margin-tokens",
        type=int,
        default=256,
        help="Additional estimated-token safety margin (default: 256).",
    )
    parser.add_argument(
        "--policy",
        choices=[policy.value for policy in PolicyPreset],
        default=PolicyPreset.BALANCED.value,
    )
    parser.add_argument("--query", default=None, help="Override the JSON relevance query.")
    parser.add_argument("--json", action="store_true", help="Emit the complete stable JSON plan.")
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="Omit context bodies from JSON output for safer diagnostics.",
    )
    parser.add_argument("-o", "--output", help="Write output to this file instead of stdout.")
    parser.add_argument(
        "--fail-on-infeasible",
        action="store_true",
        help="Return exit code 3 when mandatory context exceeds the budget.",
    )
    return parser


def build_context_parser() -> argparse.ArgumentParser:
    """Build the provider-free Context Inspector command parser."""
    parser = argparse.ArgumentParser(
        prog="llmslim context",
        description="Inspect and plan one local agent context envelope.",
    )
    parser.add_argument("command", choices=("inspect", "plan", "trace", "graph"))
    parser.add_argument("file", help="Context JSON object or '-' for standard input.")
    parser.add_argument("--model", default="generic-128k")
    parser.add_argument("--max-input-tokens", type=int, default=None)
    parser.add_argument("--quality-floor", type=float, default=0.80)
    parser.add_argument(
        "--objective", choices=("balanced", "quality", "cost", "latency", "minimize_tokens"),
        default="balanced",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--include-content", action="store_true", help="Include prompt bodies in local output.")
    parser.add_argument("--fail-on-infeasible", action="store_true")
    return parser


def _load_tool_catalog(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError("could not read a JSON tool catalog: %s" % exc) from exc
    if isinstance(value, dict):
        value = value.get("tools")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(
            "catalog must be a JSON array of tools or an object containing a tools array"
        )
    return value


def _tool_catalog_report(path: str) -> Dict[str, Any]:
    raw_tools = _load_tool_catalog(path)
    tools = tuple(from_mcp_tool(raw, namespace="cli") for raw in raw_tools)
    if len({tool.tool_id for tool in tools}) != len(tools):
        raise ValueError("catalog contains duplicate stable tool identities")
    details = []
    for tool in tools:
        schema = tool.input_schema or {}
        inspection = inspect_schema(schema) if schema else None
        details.append(
            {
                "tool_id": tool.tool_id,
                "name": tool.name,
                "fingerprint": fingerprint_tool_schema(tool),
                "input_schema_depth": inspection.depth if inspection is not None else 0,
                "input_schema_nodes": inspection.nodes if inspection is not None else 0,
                "external_references": list(inspection.external_references) if inspection else [],
            }
        )
    return {
        "tool_count": len(tools),
        "catalog_fingerprint": fingerprint_tool_schema({"tools": [tool.raw for tool in tools]}),
        "catalog_tokens": count_tokens(canonical_json([tool.raw for tool in tools])),
        "tools": details,
    }


def _run_tools_command(argv: Sequence[str]) -> int:
    parser = build_tools_parser()
    args = parser.parse_args(argv)
    try:
        report = _tool_catalog_report(args.file)
    except ValueError as exc:
        parser.error(str(exc))
        return 2  # argparse exits; keeps the return type explicit for callers.
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    print("Tool catalog: %s tools" % report["tool_count"])
    print("Fingerprint: %s" % report["catalog_fingerprint"])
    print("Context tokens: %s" % report["catalog_tokens"])
    if args.tools_command == "inspect":
        for tool in report["tools"]:
            print("- %(tool_id)s (%(input_schema_nodes)s schema nodes)" % tool)
    return 0


def _load_context_payload(path: str | None) -> Dict[str, Any]:
    try:
        if path and path != "-":
            with open(path, encoding="utf-8") as handle:
                raw = handle.read(20_000_001)
        else:
            raw = sys.stdin.read(20_000_001)
    except OSError as exc:
        raise ValueError("could not read context JSON: %s" % exc) from exc
    if len(raw) > 20_000_000:
        raise ValueError("context JSON exceeds the 20 MB CLI safety limit")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("context input must be valid JSON: %s" % exc) from exc
    if not isinstance(payload, dict):
        raise ValueError("context input must be a JSON object")
    for key in ("messages", "documents", "tools", "memories", "tool_results"):
        value = payload.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"context field '{key}' must be an array")
    if payload.get("query") is not None and not isinstance(payload["query"], str):
        raise ValueError("context field 'query' must be a string")
    return payload


def _run_context_command(argv: Sequence[str]) -> int:
    parser = build_context_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_context_payload(args.file)
        runtime = ContextRuntime(
            model=args.model,
            max_input_tokens=args.max_input_tokens,
            quality_floor=args.quality_floor,
            objective=args.objective,
        )
        prepared = runtime.prepare_sync(
            session_id=payload.get("session_id"),
            user_input=payload.get("query", ""),
            messages=payload.get("messages", []),
            documents=payload.get("documents", []),
            memories=payload.get("memories", []),
            tool_results=payload.get("tool_results", []),
            tools=payload.get("tools", []),
        )
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
        return 2
    if args.command == "inspect":
        output = prepared.envelope.to_dict(include_content=args.include_content)
    elif args.command == "plan":
        output = prepared.plan.to_dict(include_content=args.include_content)
        output["quality"] = prepared.quality.to_dict()
    elif args.command == "trace":
        output = prepared.trace.to_dict()
    else:
        output = prepared.graph.to_dict()
    if args.json:
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
    if args.fail_on_infeasible and not prepared.feasible:
        return 3
    return 0


def _human_plan_report(plan: Any) -> str:
    metrics = plan.metrics
    lines = [
        f"Plan status: {plan.status.value.upper()}",
        f"Model: {plan.model_profile.model_id}",
        f"Policy: {metrics.policy}",
        f"Estimated tokens: {metrics.original_tokens} -> {metrics.planned_tokens}",
        f"Budget utilization: {metrics.planned_tokens}/{metrics.budget_tokens} ({metrics.utilization:.1%})",
    ]
    if metrics.estimated_input_cost_before is not None:
        lines.append(
            "Estimated input cost: "
            f"{metrics.cost_currency} {metrics.estimated_input_cost_before:.6f} -> "
            f"{metrics.cost_currency} {metrics.estimated_input_cost_after:.6f}"
        )
    lines.extend(("", "Decisions:"))
    for decision in plan.decisions:
        lines.append(
            f"- {decision.item.item_id}: {decision.selected.method.value.upper()} "
            f"({decision.item.token_count} -> {decision.selected.token_cost} tokens) — "
            f"{decision.reason}"
        )
    if plan.warnings:
        lines.extend(("", "Warnings:"))
        lines.extend(f"- {warning}" for warning in plan.warnings)
    return "\n".join(lines)


def _run_plan_command(argv: Sequence[str]) -> int:
    parser = build_plan_parser()
    args = parser.parse_args(argv)
    try:
        payload = _load_context_payload(args.file)
        plan = plan_context(
            messages=payload.get("messages", []),
            documents=payload.get("documents", []),
            tools=payload.get("tools", []),
            memories=payload.get("memories", []),
            query=args.query if args.query is not None else payload.get("query", ""),
            model=args.model,
            max_input_tokens=args.max_input_tokens,
            reserve_output_tokens=args.reserve_output_tokens,
            safety_margin_tokens=args.safety_margin_tokens,
            policy=args.policy,
        )
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
        return 2
    output = (
        json.dumps(
            plan.to_dict(include_content=not args.no_content),
            ensure_ascii=False,
            sort_keys=True,
        )
        if args.json
        else _human_plan_report(plan)
    )
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output + "\n")
    else:
        print(output)
    if args.fail_on_infeasible and not plan.feasible:
        return 3
    return 0


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "context":
        return _run_context_command(arguments[1:])
    if arguments and arguments[0] == "tools":
        return _run_tools_command(arguments[1:])
    if arguments and arguments[0] == "plan":
        return _run_plan_command(arguments[1:])
    parser = build_parser()
    args = parser.parse_args(arguments)

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if args.analyze:
        profile = run_analysis(text)
        print("--- Content Analysis Profile ---")
        print(f"Content Type     : {profile.content_type.value}")
        print(f"Confidence       : {profile.confidence:.0%}")
        print(f"Secondary Types  : {', '.join(s.value for s in profile.secondary_types) or 'None'}")
        print(f"Has Structure    : {profile.has_structure}")
        print(f"Estimated Tokens : {profile.estimated_tokens}")
        print(f"Language Hint    : {profile.language_hint or 'None'}")
        print(f"Structure Depth  : {profile.structure_depth}")
        print(f"Instruction Dens.: {profile.instruction_density:.2f}")
        print(f"Entity Density   : {profile.entity_density:.2f}")
        return 0

    result = compress(
        text,
        target_ratio=args.ratio,
        query=args.query,
        mode=args.mode,
        detect_content=args.detect,
        strategy=args.strategy,
        embedding_backend=args.backend,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result.compressed_text)
    else:
        print(result.compressed_text)

    if args.stats:
        print("\n--- Compression Stats ---", file=sys.stderr)
        if result.mode is not None or result.content_type is not None:
            print(result.detailed_summary(), file=sys.stderr)
        else:
            print(result.summary(), file=sys.stderr)

    if args.cost:
        print("\n--- Cost Savings Estimate ---", file=sys.stderr)
        estimate = estimate_cost_savings(
            result.original_tokens,
            result.compressed_tokens,
            model=args.cost,
            requests_per_day=args.requests_per_day,
        )
        print(estimate.summary(), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
