"""Explicit Phase 4.6 optional semantic retrieval validation.

Run this module deliberately after caching the pinned model.  It never runs as
part of normal pytest or the default Phase 2 benchmark path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from benchmarks.phase4_5 import (
    SPLIT_SEED,
    _bootstrap,
    _case_scores,
    _no_tool_intent,
    deterministic_split,
)
from benchmarks.phase4_5_data import load_phase4_5_cases, phase4_5_catalog
from llmslim.semantic_retrieval import (
    SEMANTIC_MODEL_ID,
    SEMANTIC_MODEL_REVISION,
    DenseToolRetriever,
    HybridRRFToolRetriever,
    SemanticModelConfig,
    SentenceTransformerBackend,
)
from llmslim.tokens import count_tokens, get_active_token_counter_name
from llmslim.tool_retrieval import BM25ToolRetriever, RetrievalHit
from llmslim.tools import canonical_json, from_mcp_tool

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "benchmarks" / "results" / "phase4-6-latest.json"
PHASE45_DATA_SHA256 = "FB16E04BE432594085BC62FD1A89971C34351AB8DA908789C4BE8B9788908E89"
BOOTSTRAP_SEED = 20260820
K_VALUES = (1, 3, 5, 10, 20)


def _rank(retriever: Any, query: str) -> Tuple[List[str], List[float], float]:
    started = time.perf_counter()
    hits: Sequence[RetrievalHit] = retriever.rank(query)
    elapsed = (time.perf_counter() - started) * 1000
    return [hit.tool.tool_id for hit in hits], [hit.score for hit in hits], elapsed


def _safe_dynamic_config(retriever: Any, dev: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Choose coverage-maximising conservative gates using development only."""
    trials = []
    for top_k in K_VALUES[1:]:
        evidence = []
        for case in dev:
            ids, scores, _ = _rank(retriever, str(case["query"]))
            margin = scores[0] - scores[1] if len(scores) > 1 else 0.0
            fixed_ok = _case_scores(retriever, case, ids[:top_k])["all_required"]
            evidence.append((case, scores[0] if scores else 0.0, margin, fixed_ok))
        failures = [
            (score, margin)
            for case, score, margin, correct in evidence
            if case["required"] and not correct
        ]
        # Gates cover every known development fixed-k miss.  This is deliberately
        # conservative and has no dependence on frozen test labels.
        score_gate = max((score for score, _ in failures), default=-float("inf"))
        margin_gate = max((margin for _, margin in failures), default=-float("inf"))
        selected = 0
        all_required: List[float] = []
        no_tool: List[float] = []
        for case, score, margin, _ in evidence:
            full = bool(case["required"]) and (score <= score_gate or margin <= margin_gate)
            exposed = (
                len(retriever.tools)
                if full
                else (0 if _no_tool_intent(str(case["query"])) else top_k)
            )
            selected += exposed < len(retriever.tools)
            outcome = (
                1.0
                if (not case["required"] and exposed == 0)
                else (
                    1.0
                    if full
                    else _case_scores(
                        retriever, case, _rank(retriever, str(case["query"]))[0][:top_k]
                    )["all_required"]
                )
            )
            (all_required if case["required"] else no_tool).append(outcome)
        trials.append(
            {
                "top_k": top_k,
                "score_gate_lte": score_gate,
                "margin_gate_lte": margin_gate,
                "development_all_required": sum(all_required) / len(all_required),
                "development_no_tool": sum(no_tool) / len(no_tool) if no_tool else 1.0,
                "development_selective_coverage": selected / len(dev),
            }
        )
    acceptable = [
        trial
        for trial in trials
        if trial["development_all_required"] >= 0.95 and trial["development_no_tool"] >= 0.95
    ]
    chosen = max(
        acceptable or trials,
        key=lambda trial: (trial["development_selective_coverage"], -trial["top_k"]),
    )
    return {
        "source": "phase4_5_development_split_only",
        "trials": trials,
        "selected": chosen,
        "rule": "full catalog when top score or margin is at/below a development-miss gate",
    }


def _evaluate(
    retriever: Any,
    cases: Sequence[Mapping[str, Any]],
    policy: str,
    calibration: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    full_raw = [tool.raw for tool in retriever.tools]
    full_tokens, rows = count_tokens(canonical_json(full_raw)), []
    for case in cases:
        ids, scores, latency = _rank(retriever, str(case["query"]))
        if policy == "full":
            selected, failed_open = ids, False
        elif policy.startswith("top"):
            selected, failed_open = (
                ([] if _no_tool_intent(str(case["query"])) else ids[: int(policy[3:])]),
                False,
            )
        elif policy == "dynamic":
            if calibration is None:
                raise ValueError("dynamic policy needs development calibration")
            selected_config = calibration["selected"]
            margin = scores[0] - scores[1] if len(scores) > 1 else 0.0
            if _no_tool_intent(str(case["query"])):
                selected, failed_open = [], False
            elif scores and (
                scores[0] <= selected_config["score_gate_lte"]
                or margin <= selected_config["margin_gate_lte"]
            ):
                selected, failed_open = ids, True
            else:
                selected, failed_open = ids[: selected_config["top_k"]], False
        else:
            raise ValueError("unknown policy")
        selected_set = set(selected)
        selected_raw = [tool.raw for tool in retriever.tools if tool.tool_id in selected_set]
        rows.append(
            {
                **dict(case),
                **_case_scores(retriever, case, selected),
                "selected_count": len(selected),
                "failed_open": failed_open,
                "tokens_avoided": max(0, full_tokens - count_tokens(canonical_json(selected_raw))),
                "latency_ms": latency,
            }
        )
    tools = [row for row in rows if row["required"]]
    no_tools = [row for row in rows if not row["required"]]
    return {
        "classification": "MEASURED",
        "policy": policy,
        "rows": rows,
        "metrics": {
            "required_tool_recall": _bootstrap(
                [row["required_recall"] for row in tools], seed=BOOTSTRAP_SEED
            ),
            "all_required_tool_recall": _bootstrap(
                [row["all_required"] for row in tools], seed=BOOTSTRAP_SEED
            ),
            "precision": _bootstrap([row["precision"] for row in tools], seed=BOOTSTRAP_SEED),
            "mrr": _bootstrap([row["mrr"] for row in tools], seed=BOOTSTRAP_SEED),
            "ndcg": _bootstrap([row["ndcg"] for row in tools], seed=BOOTSTRAP_SEED),
            "no_tool_accuracy": _bootstrap(
                [row["all_required"] for row in no_tools], seed=BOOTSTRAP_SEED
            ),
            "selective_coverage": sum(row["selected_count"] < len(retriever.tools) for row in rows)
            / len(rows),
            "fail_open_rate": sum(row["failed_open"] for row in rows) / len(rows),
            "mean_tokens_avoided": sum(row["tokens_avoided"] for row in rows) / len(rows),
            "median_tokens_avoided": statistics.median(row["tokens_avoided"] for row in rows),
            "p25_tokens_avoided": statistics.quantiles(
                [row["tokens_avoided"] for row in rows], n=4
            )[0],
            "p75_tokens_avoided": statistics.quantiles(
                [row["tokens_avoided"] for row in rows], n=4
            )[2],
            "p95_latency_ms": sorted(row["latency_ms"] for row in rows)[
                int((len(rows) - 1) * 0.95)
            ],
        },
    }


def _paired(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> Dict[str, Any]:
    candidate_rows, baseline_rows = candidate["rows"], baseline["rows"]
    differences = [
        float(left["all_required"]) - float(right["all_required"])
        for left, right in zip(candidate_rows, baseline_rows)
        if left["required"]
    ]
    rng, n = random.Random(BOOTSTRAP_SEED), len(differences)
    samples = (
        sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(1000))
        if n
        else [0.0]
    )
    return {
        "improved": sum(value > 0 for value in differences),
        "regressed": sum(value < 0 for value in differences),
        "mean_difference": sum(differences) / n if n else 0.0,
        "ci95_low": samples[25],
        "ci95_high": samples[974],
    }


def _robustness_cases() -> List[Dict[str, Any]]:
    # Separate robustess evidence; this does not modify the frozen primary corpus.
    rows = [
        ("en", "Block Friday afternoon for a dental checkup.", ["calendar/calendar_create"]),
        ("en", "Track down the note with the signed agreement.", ["mail/mail_search"]),
        ("en", "Raise a defect about repeat mobile alerts.", ["github/github_issue"]),
        ("en", "Put the local scan into the shared client directory.", ["files/files_upload"]),
        ("hi", "शुक्रवार दोपहर दंत चिकित्सक के लिए समय रोक दो।", ["calendar/calendar_create"]),
        ("hi", "हस्ताक्षरित समझौते वाला ईमेल ढूँढो।", ["mail/mail_search"]),
        ("hi", "मोबाइल अलर्ट की समस्या के लिए बग बनाओ।", ["github/github_issue"]),
        ("hi", "यह फ़ाइल साझा ग्राहक फ़ोल्डर में अपलोड करो।", ["files/files_upload"]),
        ("zh", "周五下午帮我预留牙医预约时间。", ["calendar/calendar_create"]),
        ("zh", "查找包含已签署协议的邮件。", ["mail/mail_search"]),
        ("zh", "为重复的移动提醒创建一个缺陷。", ["github/github_issue"]),
        ("zh", "把本地扫描件上传到客户共享文件夹。", ["files/files_upload"]),
        ("ja", "金曜の午後を歯医者の予約のために空けて。", ["calendar/calendar_create"]),
        ("ja", "署名済み契約書があるメールを探して。", ["mail/mail_search"]),
        ("ja", "モバイル通知が重複する不具合を登録して。", ["github/github_issue"]),
        (
            "ja",
            "このスキャンを共有クライアントフォルダへアップロードして。",
            ["files/files_upload"],
        ),
        ("en", "Explain how calendar software works; do not schedule anything.", []),
        (
            "en",
            "Find the previous event and remove it.",
            ["calendar/calendar_search", "calendar/calendar_cancel"],
        ),
    ]
    return [
        {
            "id": "robust-%03d" % index,
            "language": language,
            "query": query,
            "required": required,
            "class": "no_tool"
            if not required
            else ("multi_tool" if len(required) > 1 else "semantic_paraphrase"),
        }
        for index, (language, query, required) in enumerate(rows, 1)
    ]


def _scaling(backend: SentenceTransformerBackend) -> List[Dict[str, Any]]:
    base, rows = phase4_5_catalog(), []
    queries = [case["query"] for case in load_phase4_5_cases()[:10]]
    for size in (10, 25, 50, 100, 250, 500):
        catalog = list(base[: min(len(base), size)])
        while len(catalog) < size:
            index = len(catalog) + 1
            catalog.append(
                {
                    "name": "phase46_distractor_%03d" % index,
                    "server": "scale",
                    "title": "Scale distractor",
                    "description": "Deterministic irrelevant scale fixture %d." % index,
                    "inputSchema": {"type": "object", "properties": {"value": {"type": "string"}}},
                }
            )
        started = time.perf_counter()
        dense = DenseToolRetriever([from_mcp_tool(tool) for tool in catalog], backend)
        build_ms = (time.perf_counter() - started) * 1000
        latencies = []
        for query in queries:
            _, _, latency = _rank(dense, query)
            latencies.append(latency)
        rows.append(
            {
                "catalog_size": size,
                "index_build_ms": build_ms,
                "retrieval_p50_ms": statistics.median(latencies),
                "retrieval_p95_ms": sorted(latencies)[int((len(latencies) - 1) * 0.95)],
                "embedding_index_memory_bytes": dense.embedding_memory_bytes,
                "source": "PRIMARY_100"
                if size <= 100
                else "PRIMARY_PLUS_DERIVED_DETERMINISTIC_DISTRACTORS",
            }
        )
    return rows


def _toolret_status() -> Dict[str, Any]:
    configured = os.environ.get("LLMSLIM_TOOLRET_DIR")
    if configured and Path(configured).exists():
        return {
            "status": "PARTIAL",
            "path": configured,
            "reason": "adapter input found; full parser is intentionally external-only",
        }
    return {
        "status": "PARTIAL",
        "official_repository": "https://github.com/mangopy/tool-retrieval-benchmark",
        "queries_revision": "b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445",
        "tools_revision": "e06c38c75612b6536bd959e08cdd345894aba6a7",
        "attempt": "101 official ApiBank queries against 37,292 official web tools; no result accepted after CPU/memory budget was exceeded",
        "reason": "External data are optional and normal benchmark execution does not download them; see EXTERNAL_TOOLRET_REPORT.md.",
    }


def run_phase4_6_benchmark() -> Dict[str, Any]:
    cases, catalog = load_phase4_5_cases(), [from_mcp_tool(raw) for raw in phase4_5_catalog()]
    actual_hash = (
        hashlib.sha256((ROOT / "benchmarks" / "phase4_5_data.py").read_bytes()).hexdigest().upper()
    )
    if actual_hash != PHASE45_DATA_SHA256:
        raise RuntimeError("frozen Phase 4.5 corpus hash changed; refusing Phase 4.6 evaluation")
    dev, test = deterministic_split(cases)
    backend = SentenceTransformerBackend(SemanticModelConfig())
    bm25 = BM25ToolRetriever.cached(catalog)
    dense = DenseToolRetriever.cached(catalog, backend)
    hybrid = HybridRRFToolRetriever(bm25, dense, rrf_k=60)
    strategies: Dict[str, Any] = {}
    for name, retriever in (("bm25", bm25), ("dense", dense), ("hybrid_rrf", hybrid)):
        calibration = _safe_dynamic_config(retriever, dev)
        fixed = {"top_%d" % k: _evaluate(retriever, test, "top%d" % k) for k in K_VALUES}
        dynamic = _evaluate(retriever, test, "dynamic", calibration)
        strategies[name] = {"calibration": calibration, "fixed_top_k": fixed, "dynamic": dynamic}
    robustness: Dict[str, Any] = {
        "suite": "SEPARATE_ROBUSTNESS_NOT_PRIMARY",
        "cases": _robustness_cases(),
    }
    for name, retriever in (("dense", dense), ("hybrid_rrf", hybrid)):
        calibration = _safe_dynamic_config(retriever, dev)
        robustness[name] = _evaluate(retriever, robustness["cases"], "dynamic", calibration)
    return {
        "classification": "MEASURED",
        "phase": "4.6",
        "protocol_version": "phase4_6.v1",
        "frozen_phase4_5": {
            "data_sha256": actual_hash,
            "split_seed": SPLIT_SEED,
            "development_count": len(dev),
            "test_count": len(test),
        },
        "model": {
            "id": SEMANTIC_MODEL_ID,
            "revision": SEMANTIC_MODEL_REVISION,
            "backend": "sentence-transformers",
            "device": "cpu",
            "embedding_dimension": dense.embedding_dimension,
            "index_build_ms_100": dense.index_build_ms,
            "embedding_index_memory_bytes_100": dense.embedding_memory_bytes,
            "local_only": True,
            "trust_remote_code": False,
        },
        "fusion": {
            "method": "RRF",
            "rrf_k": 60,
            "candidate_depth": len(catalog),
            "tie_break": "tool_id",
        },
        "strategies": strategies,
        "paired_vs_bm25": {
            "dense": _paired(strategies["dense"]["dynamic"], strategies["bm25"]["dynamic"]),
            "hybrid_rrf": _paired(
                strategies["hybrid_rrf"]["dynamic"], strategies["bm25"]["dynamic"]
            ),
        },
        "robustness": robustness,
        "scaling": _scaling(backend),
        "toolret": _toolret_status(),
        "safety": {
            "raw_schema_authority": "UNCHANGED",
            "annotations": "EXCLUDED",
            "meta": "EXCLUDED",
            "execution": "OUT_OF_SCOPE",
        },
        "token_counter": get_active_token_counter_name(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run explicit optional Phase 4.6 semantic benchmark"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = {"schema_version": "phase4_6.v1", "phase4_6": run_phase4_6_benchmark()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
