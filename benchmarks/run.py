"""Run the reproducible Phase 2 benchmark suite offline.

Usage: python -m benchmarks.run [--mode fast|full] [--iterations N] [--output PATH]
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from benchmarks.evaluation.core import (
    DEFAULT_DATASET,
    RESULT_SCHEMA_VERSION,
    aggregate_records,
    environment_metadata,
    evaluate_sample,
    evaluate_security,
    load_dataset,
    validate_result,
    write_json,
)
from benchmarks.phase4 import run_phase4_benchmark
from benchmarks.phase4_5 import run_phase4_5_benchmark
from benchmarks.schema_tax.core import run_schema_tax
from llmslim import __version__

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results" / "latest.json"


def _summary(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = (
        "token_reduction",
        "actual_compression_ratio",
        "target_ratio_error",
        "instruction_retention",
        "entity_retention",
        "number_retention",
        "negation_retention",
        "semantic_similarity",
    )
    micro = {metric: aggregate_records(records, metric) for metric in metrics}
    micro["latency_ms"] = aggregate_records(
        [{"latency_ms": row["latency_ms"]["median"]} for row in records], "latency_ms"
    )
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["category"]].append(record)
    macro = {
        metric: aggregate_records(
            [{"value": aggregate_records(rows, metric)["mean"]} for rows in grouped.values()],
            "value",
        )
        for metric in metrics
    }
    structural = [
        record["structural_integrity"]
        for record in records
        if record["structural_integrity"]["applicable"]
    ]
    return {
        "micro": micro,
        "macro": macro,
        "failure_rate": sum(record["failure"] is not None for record in records) / len(records)
        if records
        else 0.0,
        "determinism_rate": sum(record["deterministic"] for record in records) / len(records)
        if records
        else None,
        "structural_integrity": {
            "applicable_count": len(structural),
            "valid_count": sum(item["valid"] is True for item in structural),
            "unavailable_count": sum(not item["available"] for item in structural),
        },
        "aggregation_note": "micro weights samples equally; macro weights benchmark categories equally",
    }


def _dataset_audit(
    samples: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    tokens = {record["id"]: record["original_tokens"] for record in records}
    return {
        "name": "phase2_core",
        "path": str(DEFAULT_DATASET.relative_to(ROOT)),
        "provenance": "repository-owned synthetic, independently labelled",
        "sample_count": len(samples),
        "categories": dict(sorted(Counter(sample["category"] for sample in samples).items())),
        "languages": dict(sorted(Counter(sample["language"] for sample in samples).items())),
        "tokens_by_category": dict(
            sorted(
                (
                    category,
                    sum(
                        tokens[sample["id"]] for sample in samples if sample["category"] == category
                    ),
                )
                for category in {item["category"] for item in samples}
            )
        ),
        "length_distribution": {
            "short_under_100_tokens": sum(value < 100 for value in tokens.values()),
            "medium_100_to_299_tokens": sum(100 <= value < 300 for value in tokens.values()),
            "long_300_plus_tokens": sum(value >= 300 for value in tokens.values()),
        },
        "strategy_applicability": {
            "extractive": len(samples),
            "rewrite": "OPTIONAL_PROVIDER_NOT_RUN",
            "hybrid": "OPTIONAL_PROVIDER_NOT_RUN",
        },
    }


def build_result(
    mode: str = "fast",
    iterations: int | None = None,
    seed: int = 20260815,
    dataset_path: Path = DEFAULT_DATASET,
    phase4_6: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if mode not in {"fast", "full"}:
        raise ValueError("mode must be fast or full")
    random.seed(seed)
    samples = load_dataset(dataset_path)
    count = iterations if iterations is not None else (3 if mode == "fast" else 7)
    records = [evaluate_sample(sample, iterations=count, warmup=1) for sample in samples]
    security = evaluate_security()
    schema_tax = run_schema_tax()
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "classification": "MEASURED",
        "llmslim_version": __version__,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mode": mode,
        "environment": environment_metadata(seed),
        "dataset": _dataset_audit(samples, records),
        "strategies": {
            "extractive": {
                "classification": "MEASURED",
                "records": records,
                "summary": _summary(records),
            },
            "rewrite": {
                "classification": "NOT_APPLICABLE",
                "reason": "provider-dependent strategy is optional and not run by offline suite",
            },
            "hybrid": {
                "classification": "NOT_APPLICABLE",
                "reason": "provider-dependent strategy is optional and not run by offline suite",
            },
        },
        "security": security,
        "schema_tax": schema_tax,
        "phase4": run_phase4_benchmark(),
        "phase4_5": run_phase4_5_benchmark(),
        "phase4_6": dict(phase4_6)
        if phase4_6 is not None
        else {
            "classification": "NOT_RUN_OPTIONAL",
            "reason": "Phase 4.6 requires an explicitly cached optional local model; default benchmark and pytest do not load it.",
        },
        "summary": _summary(records),
    }
    validate_result(result)
    return result


def render_report(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    schema_rows = result["schema_tax"]["catalogs"]
    lines = [
        "# LLMSlim Phase 2 benchmark report",
        "",
        "## Executive summary",
        "",
        f"- Classification: {result['classification']}",
        f"- Mode: {result['mode']}",
        f"- Samples: {result['dataset']['sample_count']} across {len(result['dataset']['categories'])} categories",
        f"- Security provenance-boundary violations: {result['security']['provenance_boundary_violations']}",
        f"- Schema catalogs: {result['schema_tax']['catalog_count']} ({result['schema_tax']['tool_schema_count']} tool schemas)",
        "",
        "## Environment",
        "",
        "```json",
        json.dumps(result["environment"], indent=2, sort_keys=True),
        "```",
        "",
        "## Dataset composition",
        "",
        f"- Categories: {json.dumps(result['dataset']['categories'], ensure_ascii=False, sort_keys=True)}",
        f"- Languages: {json.dumps(result['dataset']['languages'], ensure_ascii=False, sort_keys=True)}",
        f"- Length distribution: {json.dumps(result['dataset']['length_distribution'], sort_keys=True)}",
        "",
        "## Strategy results",
        "",
        "Only deterministic local extractive results are measured. Rewrite and hybrid are provider-dependent and not run by the offline suite.",
        "",
        "| Metric | Micro mean | Macro mean |",
        "| --- | ---: | ---: |",
    ]
    for metric in (
        "token_reduction",
        "actual_compression_ratio",
        "target_ratio_error",
        "instruction_retention",
        "entity_retention",
        "number_retention",
        "negation_retention",
        "semantic_similarity",
    ):
        lines.append(
            f"| {metric} | {_format(summary['micro'][metric]['mean'])} | {_format(summary['macro'][metric]['mean'])} |"
        )
    lines.extend(
        [
            "",
            "## Quality, performance, and determinism",
            "",
            f"- Structural validity: {summary['structural_integrity']['valid_count']}/{summary['structural_integrity']['applicable_count']} applicable samples (unavailable parser: {summary['structural_integrity']['unavailable_count']}).",
            f"- Median end-to-end latency: {_format(summary['micro']['latency_ms']['median'])} ms; p95: {_format(summary['micro']['latency_ms']['p95'])} ms.",
            f"- Determinism: {_format(summary['determinism_rate'])}.",
            "",
            "## Security results",
            "",
            f"- Protected-priority elevation violations: {result['security']['protected_priority_elevation_violations']}",
            f"- `must_keep` violations: {result['security']['must_keep_violations']}",
            f"- Provenance-boundary violations: {result['security']['provenance_boundary_violations']}",
            "",
            "## Multilingual results",
            "",
            f"Language distribution: {json.dumps(result['dataset']['languages'], ensure_ascii=False, sort_keys=True)}. Token counts use `{result['environment']['token_counter']}` and should not be compared across tokenizer backends as equivalent measurements.",
            "",
            "## Tool schema tax",
            "",
            "All schema payloads below are MEASURED using the recorded tokenizer. Multi-turn totals are DERIVED under the stated full-catalog-resend assumption.",
            "",
            "| Complexity | Tools | Schema tokens | Tokens/tool | 1-turn tax | 16-turn derived | 32-turn derived |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in schema_rows:
        lines.append(
            f"| {row['complexity']} | {row['tool_count']} | {row['total_schema_tokens']} | {_format(row['mean_tokens_per_tool'])} | {row['full_catalog_tokens_per_turn']} | {row['cumulative_schema_tokens']['16']['tokens']} | {row['cumulative_schema_tokens']['32']['tokens']} |"
        )
    phase4 = result["phase4"]
    optimization = phase4["schema_optimization"]
    relevance = phase4["relevance"]
    lines.extend(
        [
            "",
            "## Phase 4 tool-context results",
            "",
            "All numbers in this section are local measurements. The Phase 2 schema-tax baseline already uses compact canonical JSON, so lossless canonical serialization can legitimately save zero tokens from that baseline.",
            "",
            f"- Schema catalogs: {optimization['catalog_count']}; generated schemas: {optimization['tool_schema_count']}.",
            f"- Lossless optimization: {optimization['original_tokens']} → {optimization['optimized_tokens']} tokens ({optimization['reduction_ratio']:.2%}).",
            f"- Relevance Recall@1/@3/@5: {relevance['metrics']['recall_at_1']:.2%} / {relevance['metrics']['recall_at_3']:.2%} / {relevance['metrics']['recall_at_5']:.2%}; MRR: {relevance['metrics']['mrr']:.4g}.",
            f"- Selective exposure: {phase4['selective_exposure']['status']}.",
            "",
            "| top-k | Required-tool recall | Mean tokens avoided |",
            "| ---: | ---: | ---: |",
        ]
    )
    for row in phase4["selective_exposure"]["rows"]:
        lines.append(
            f"| {row['top_k']} | {row['required_tool_recall']:.2%} | {row['mean_tokens_avoided']:.2f} |"
        )
    phase45 = result["phase4_5"]
    bm25 = phase45["strategies"]["bm25_v1_k1_1.2_b_0.75"]["test_policies"]["dynamic"]["metrics"]
    lines.extend(
        [
            "",
            "## Phase 4.5 retrieval bakeoff",
            "",
            "Phase 4.5 is a repository-owned, static 100-tool / 500-query regression corpus. It is not a production-traffic claim. Its dynamic policy is conservative and currently RESEARCH_ONLY because development fixed-top-k all-required recall did not meet the release threshold.",
            "",
            f"- BM25 all-required-tool recall: {bm25['all_required_tool_recall']['mean']:.2%} (95% bootstrap CI {bm25['all_required_tool_recall']['ci95_low']:.2%}–{bm25['all_required_tool_recall']['ci95_high']:.2%}).",
            f"- BM25 fail-open rate: {bm25['fail_open_rate']:.2%}; coverage: {bm25['coverage']:.2%}.",
            "- TF-IDF remains an independently measured baseline; no automatic default swap is made.",
        ]
    )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- This is a synthetic, repository-owned benchmark corpus, not a universal workload claim.",
            "- Lexical TF-IDF relevance is an offline proxy; no embedding model is downloaded.",
            "- Selective exposure and lazy hydration are experimental, explicit APIs; the executor contract remains the complete raw schema.",
            "- Full catalog resend is a modelled protocol assumption, not a claim about every agent framework.",
            "",
            "## Reproduction command",
            "",
            "```bash",
            "python -m benchmarks.run --mode fast",
            "python -m benchmarks.run --mode full",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _format(value: Any) -> str:
    return "N/A" if value is None else f"{value:.4g}" if isinstance(value, float) else str(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LLMSlim Phase 2 offline benchmark suite")
    parser.add_argument("--mode", choices=("fast", "full"), default="fast")
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-archive", action="store_true")
    parser.add_argument(
        "--phase4-6",
        action="store_true",
        help="Run the explicit optional pinned local semantic benchmark",
    )
    args = parser.parse_args(argv)
    phase4_6 = None
    if args.phase4_6:
        from benchmarks.phase4_6 import run_phase4_6_benchmark

        phase4_6 = run_phase4_6_benchmark()
    result = build_result(args.mode, args.iterations, args.seed, phase4_6=phase4_6)
    write_json(result, args.output, archive=not args.no_archive)
    report_path = ROOT / "benchmarks" / "reports" / "latest.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(result), encoding="utf-8")
    summary_path = ROOT / "benchmarks" / "results" / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "classification": result["classification"],
                "dataset": result["dataset"],
                "summary": result["summary"],
                "security": result["security"]["status"],
                "schema_tax": {
                    "catalog_count": result["schema_tax"]["catalog_count"],
                    "tool_schema_count": result["schema_tax"]["tool_schema_count"],
                },
                "phase4": result["phase4"],
                "phase4_5": result["phase4_5"],
                "phase4_6": result["phase4_6"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
