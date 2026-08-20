"""Phase 4.5 reproducible tool-retrieval bakeoff and release artifact writer."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple, Type

from benchmarks.phase4_5_data import load_phase4_5_cases, phase4_5_catalog
from llmslim.tokens import count_tokens, get_active_token_counter_name
from llmslim.tool_retrieval import (
    BM25ToolRetriever,
    LexicalToolRetriever,
    TfidfToolRetriever,
    normalize_text,
)
from llmslim.tools import canonical_json, from_mcp_tool

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results" / "phase4-5-latest.json"
SPLIT_SEED = "phase4_5_split_v1"
BOOTSTRAP_SEED = 20260819
K_VALUES = (1, 3, 5, 10)


def deterministic_split(
    cases: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Hash split after corpus creation; case text never participates in tuning."""
    dev: List[Dict[str, Any]] = []
    test: List[Dict[str, Any]] = []
    for case in cases:
        bucket = (
            int(hashlib.sha256((SPLIT_SEED + str(case["id"])).encode("utf-8")).hexdigest()[:8], 16)
            % 5
        )
        (dev if bucket == 0 else test).append(dict(case))
    return dev, test


def _no_tool_intent(query: str) -> bool:
    words = normalize_text(query)
    if not words:
        return True
    starters = {
        "explain",
        "define",
        "summarize",
        "describe",
        "why",
        "write",
        "translate",
        "compare",
        "discuss",
        "tell",
    }
    return words[0] in starters or (words[:2] == ("what", "is")) or (words[:2] == ("how", "does"))


def _ranked_ids(retriever: LexicalToolRetriever, query: str) -> Tuple[List[str], List[float]]:
    ranked = retriever.rank(query)
    return [hit.tool.tool_id for hit in ranked], [hit.score for hit in ranked]


def _all_required(required: Iterable[str], selected: Iterable[str]) -> float:
    expected = set(required)
    return 1.0 if not expected else float(expected.issubset(set(selected)))


def _case_scores(
    retriever: LexicalToolRetriever, case: Mapping[str, Any], selected: Sequence[str]
) -> Dict[str, float]:
    expected, actual = set(case["required"]), list(selected)
    result: Dict[str, float] = {"all_required": _all_required(expected, actual)}
    if not expected:
        result.update(
            {
                "required_recall": 1.0 if not actual else 0.0,
                "precision": 1.0 if not actual else 0.0,
                "mrr": 1.0 if not actual else 0.0,
                "ndcg": 1.0 if not actual else 0.0,
            }
        )
        return result
    hits = [tool_id for tool_id in actual if tool_id in expected]
    result["required_recall"] = len(set(hits)) / len(expected)
    result["precision"] = len(set(hits)) / len(actual) if actual else 0.0
    first = next((index + 1 for index, tool_id in enumerate(actual) if tool_id in expected), None)
    result["mrr"] = 1.0 / first if first else 0.0
    dcg = sum(
        1.0 / (index + 1).bit_length()
        for index, tool_id in enumerate(actual)
        if tool_id in expected
    )
    ideal = sum(1.0 / (index + 1).bit_length() for index in range(min(len(expected), len(actual))))
    result["ndcg"] = dcg / ideal if ideal else 0.0
    return result


def _static_policy(
    retriever: LexicalToolRetriever, case: Mapping[str, Any], top_k: int
) -> Tuple[List[str], bool]:
    if _no_tool_intent(str(case["query"])):
        return [], False
    ids, _ = _ranked_ids(retriever, str(case["query"]))
    return ids[:top_k], False


def calibrate_dev(
    retriever: LexicalToolRetriever, dev: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Select k and fail-open thresholds solely from development labels."""
    candidates = []
    for k in (3, 5, 10):
        rows = []
        for case in dev:
            selected, _ = _static_policy(retriever, case, k)
            rows.append(_case_scores(retriever, case, selected))
        required_rows = [row for case, row in zip(dev, rows) if case["required"]]
        no_tool_rows = [row for case, row in zip(dev, rows) if not case["required"]]
        candidates.append(
            {
                "top_k": k,
                "all_required_recall": sum(row["all_required"] for row in required_rows)
                / len(required_rows),
                "no_tool_accuracy": sum(row["all_required"] for row in no_tool_rows)
                / len(no_tool_rows)
                if no_tool_rows
                else 1.0,
            }
        )
    safe = [
        row
        for row in candidates
        if row["all_required_recall"] >= 0.95 and row["no_tool_accuracy"] >= 0.95
    ]
    chosen = safe[0] if safe else candidates[-1]
    weak_scores, weak_margins = [], []
    for case in dev:
        if not case["required"]:
            continue
        ids, scores = _ranked_ids(retriever, str(case["query"]))
        selected = ids[: int(chosen["top_k"])]
        if not _all_required(case["required"], selected):
            weak_scores.append(scores[0] if scores else 0.0)
            weak_margins.append((scores[0] - scores[1]) if len(scores) > 1 else 0.0)
    # No observed miss means use a conservative zero threshold: do not claim a
    # learned confidence cutoff beyond the development evidence.
    return {
        "source": "development_split_only",
        "top_k": chosen["top_k"],
        "candidate_grid": candidates,
        "fail_open_top_score_lte": max(weak_scores) if weak_scores else 0.0,
        "fail_open_margin_lte": max(weak_margins) if weak_margins else 0.0,
        "selection_rule": "smallest k meeting preregistered dev all-required and no-tool targets",
    }


def _dynamic_policy(
    retriever: LexicalToolRetriever, case: Mapping[str, Any], calibration: Mapping[str, Any]
) -> Tuple[List[str], bool]:
    if _no_tool_intent(str(case["query"])):
        return [], False
    ids, scores = _ranked_ids(retriever, str(case["query"]))
    top, margin = (
        (scores[0] if scores else 0.0),
        (scores[0] - scores[1] if len(scores) > 1 else 0.0),
    )
    if top <= float(calibration["fail_open_top_score_lte"]) or margin <= float(
        calibration["fail_open_margin_lte"]
    ):
        return ids, True
    return ids[: int(calibration["top_k"])], False


def _bootstrap(
    values: Sequence[float], seed: int = BOOTSTRAP_SEED, samples: int = 1000
) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "resamples": samples}
    randomizer, size = random.Random(seed), len(values)
    estimates = sorted(
        sum(values[randomizer.randrange(size)] for _ in range(size)) / size for _ in range(samples)
    )
    return {
        "mean": sum(values) / size,
        "ci95_low": estimates[int(samples * 0.025)],
        "ci95_high": estimates[int(samples * 0.975) - 1],
        "resamples": samples,
    }


def evaluate_policy(
    retriever: LexicalToolRetriever,
    cases: Sequence[Mapping[str, Any]],
    policy: str,
    calibration: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    rows, full_tokens = [], count_tokens(canonical_json([tool.raw for tool in retriever.tools]))
    for case in cases:
        if policy == "full":
            selected, failed_open = [tool.tool_id for tool in retriever.tools], False
        elif policy.startswith("top"):
            selected, failed_open = _static_policy(retriever, case, int(policy[3:]))
        elif policy == "dynamic":
            if calibration is None:
                raise ValueError("dynamic evaluation needs dev-only calibration")
            selected, failed_open = _dynamic_policy(retriever, case, calibration)
        else:
            raise ValueError("unknown policy: %s" % policy)
        measure = _case_scores(retriever, case, selected)
        selected_raw = [tool.raw for tool in retriever.tools if tool.tool_id in set(selected)]
        avoided = max(0, full_tokens - count_tokens(canonical_json(selected_raw)))
        rows.append(
            {
                **dict(case),
                **measure,
                "selected_count": len(selected),
                "failed_open": failed_open,
                "tokens_avoided": avoided,
            }
        )
    tool_rows = [row for row in rows if row["required"]]
    no_tool_rows = [row for row in rows if not row["required"]]
    aggregate = {
        "required_tool_recall": _bootstrap([row["required_recall"] for row in tool_rows]),
        "all_required_tool_recall": _bootstrap([row["all_required"] for row in tool_rows]),
        "precision": _bootstrap([row["precision"] for row in tool_rows]),
        "mrr": _bootstrap([row["mrr"] for row in tool_rows]),
        "ndcg": _bootstrap([row["ndcg"] for row in tool_rows]),
        "no_tool_accuracy": _bootstrap([row["all_required"] for row in no_tool_rows]),
        "mean_tokens_avoided": sum(row["tokens_avoided"] for row in rows) / len(rows),
        "median_tokens_avoided": statistics.median(row["tokens_avoided"] for row in rows),
        "fail_open_rate": sum(row["failed_open"] for row in rows) / len(rows),
        "coverage": sum(1 for row in rows if row["selected_count"] < len(retriever.tools))
        / len(rows),
    }
    return {
        "classification": "MEASURED",
        "policy": policy,
        "case_count": len(rows),
        "metrics": aggregate,
        "rows": rows,
    }


def _quality_report(cases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    normalized = [" ".join(normalize_text(str(case["query"]))) for case in cases]
    exact_duplicates = len(normalized) - len(set(normalized))
    near_pairs = 0
    for index, left in enumerate(normalized):
        left_terms = set(left.split())
        for right in normalized[index + 1 :]:
            right_terms = set(right.split())
            union = left_terms | right_terms
            if union and len(left_terms & right_terms) / len(union) >= 0.9:
                near_pairs += 1
    return {
        "classification": "MEASURED",
        "tool_count": len(phase4_5_catalog()),
        "query_count": len(cases),
        "exact_normalized_duplicates": exact_duplicates,
        "near_duplicate_pairs_jaccard_gte_0_90": near_pairs,
        "classes": dict(sorted(Counter(case["class"] for case in cases).items())),
        "categories": dict(sorted(Counter(case["category"] for case in cases).items())),
        "languages": dict(sorted(Counter(case["language"] for case in cases).items())),
        "query_provenance": "REPOSITORY_AUTHORED_STATIC_TEXT",
        "tool_provenance": "REPOSITORY_OWNED_MCP_SHAPED",
    }


def _scaling(
    retriever_type: Type[LexicalToolRetriever], cases: Sequence[Mapping[str, Any]]
) -> List[Dict[str, Any]]:
    base = phase4_5_catalog()
    rows = []
    for size in (10, 25, 50, 100, 250, 500):
        catalog = list(base[: min(size, len(base))])
        while len(catalog) < size:
            index = len(catalog) + 1
            catalog.append(
                {
                    "name": "scale_distractor_%03d" % index,
                    "server": "scale",
                    "title": "Scale distractor %d" % index,
                    "description": "Deterministic irrelevant catalog-scale distractor number %d."
                    % index,
                    "inputSchema": {"type": "object", "properties": {"value": {"type": "string"}}},
                }
            )
        retriever = retriever_type.cached([from_mcp_tool(raw) for raw in catalog])
        started = __import__("time").perf_counter()
        for case in cases[: min(100, len(cases))]:
            retriever.rank(str(case["query"]), limit=10)
        elapsed = (__import__("time").perf_counter() - started) * 1000
        rows.append(
            {
                "catalog_size": size,
                "query_count": min(100, len(cases)),
                "rank_latency_ms_total": elapsed,
                "source": "PRIMARY_100"
                if size <= 100
                else "PRIMARY_PLUS_DERIVED_DETERMINISTIC_DISTRACTORS",
            }
        )
    return rows


def run_phase4_5_benchmark() -> Dict[str, Any]:
    cases, catalog = load_phase4_5_cases(), [from_mcp_tool(raw) for raw in phase4_5_catalog()]
    dev, test = deterministic_split(cases)
    strategies: Dict[str, Any] = {}
    for retriever_type in (TfidfToolRetriever, BM25ToolRetriever):
        retriever = retriever_type.cached(catalog)
        calibration = calibrate_dev(retriever, dev)
        policies = {
            policy: evaluate_policy(
                retriever, test, policy, calibration if policy == "dynamic" else None
            )
            for policy in ("full", "top1", "top3", "top5", "top10", "dynamic")
        }
        strategies[retriever.strategy] = {
            "index": {
                "catalog_fingerprint": retriever.info.catalog_fingerprint,
                "metadata_policy": retriever.info.metadata_policy,
                "cache_hit": retriever.info.cache_hit,
            },
            "calibration": calibration,
            "test_policies": policies,
            "scaling": _scaling(retriever_type, test),
        }
    # Dense/hybrid are deliberately not silently substituted: no local model is
    # downloaded or trusted during this reproducible offline release gate.
    strategies["dense"] = {
        "classification": "NOT_IMPLEMENTED_REJECTED",
        "reason": "No pinned local encoder artifact; downloading a model would make the offline bakeoff non-reproducible and expand the trusted execution surface.",
    }
    strategies["hybrid"] = {
        "classification": "NOT_IMPLEMENTED_REJECTED",
        "reason": "Hybrid depends on the rejected dense candidate; lexical strategies remain independently measured.",
    }
    return {
        "classification": "MEASURED",
        "phase": "4.5",
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset": {
            "quality": _quality_report(cases),
            "split": {
                "method": "sha256 case-id modulo 5",
                "seed": SPLIT_SEED,
                "development_count": len(dev),
                "test_count": len(test),
                "development_ids": [case["id"] for case in dev],
                "test_ids": [case["id"] for case in test],
            },
        },
        "strategies": strategies,
        "safety": {
            "raw_schema_authority": "UNCHANGED",
            "fingerprint_separation": "UNCHANGED",
            "annotations_and_meta": "EXCLUDED_FROM_RETRIEVAL",
            "execution": "OUT_OF_SCOPE_MODEL_FACING_EXPERIMENT",
        },
        "token_counter": get_active_token_counter_name(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4.5 tool retrieval bakeoff")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = {"schema_version": "phase4_5.v1", "phase4_5": run_phase4_5_benchmark()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
