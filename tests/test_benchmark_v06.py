"""Integrity checks for the frozen v0.6 planner benchmark."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.benchmark_memory import run_memory_benchmarks
from benchmarks.benchmark_quality import run_quality_benchmarks
from benchmarks.benchmark_speed import run_speed_benchmarks
from benchmarks.live_sarvam_v06 import run_live
from benchmarks.v06_planner import DATASET, build_result, load_cases, render_report


def test_frozen_corpus_has_required_coverage() -> None:
    cases = load_cases()
    categories = {case["category"] for case in cases}
    languages = {case["language"] for case in cases}
    assert {"chat", "rag", "tools", "mixed", "multilingual", "external"} <= categories
    assert {"English", "Hindi", "Hinglish", "Bengali", "Tamil", "Telugu"} <= languages
    assert len(cases) >= 28


def test_checked_in_result_is_sanitized_and_matches_dataset() -> None:
    result_path = Path(__file__).parents[1] / "benchmarks/results/v0.6-planner-latest.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["classification"] == "MEASURED_OFFLINE"
    assert result["environment"]["network_calls"] == 0
    assert result["environment"]["provider_calls"] == 0
    assert result["dataset"]["case_count"] == len(load_cases())
    assert result["mcp"]["stale_plan_rejected"] is True
    assert result["mcp"]["tool_execution_count"] == 0
    serialized = json.dumps(result).casefold()
    assert "api_subscription_key" not in serialized
    assert "mongodb+srv://" not in serialized


def test_benchmark_is_reproducible_except_environmental_fields() -> None:
    result = build_result(DATASET)
    assert set(result["summary"]) == {
        "raw_full_context",
        "naive_prefix_truncation",
        "fixed_ratio",
        "adaptive_planner",
    }
    assert result["summary"]["adaptive_planner"]["hard_constraint_retention"] == 1.0
    assert "MEASURED_OFFLINE" in render_report(result)


def test_live_sarvam_benchmark_refuses_without_both_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLMSLIM_RUN_LIVE_SARVAM", raising=False)
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="acknowledge live credit usage"):
        run_live()

    monkeypatch.setenv("LLMSLIM_RUN_LIVE_SARVAM", "1")
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        run_live()


def test_legacy_quality_runner_skips_non_sample_json(tmp_path: Path) -> None:
    (tmp_path / "planner-corpus.json").write_text(
        json.dumps({"schema_version": "1", "cases": []}), encoding="utf-8"
    )
    (tmp_path / "invalid-list.json").write_text(json.dumps(["not-a-sample"]), encoding="utf-8")

    assert run_quality_benchmarks(str(tmp_path)) == []
    assert run_speed_benchmarks(str(tmp_path)) == []
    assert run_memory_benchmarks(str(tmp_path)) == []
