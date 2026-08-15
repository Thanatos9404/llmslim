"""Tests for Phase 2 benchmark infrastructure, kept independent from compressor heuristics."""

from __future__ import annotations

import json

import pytest

from benchmarks.evaluation.core import (
    RESULT_SCHEMA_VERSION,
    aggregate_records,
    compare_results,
    labelled_retention,
    load_dataset,
    ratio_metrics,
    structural_integrity,
    validate_result,
)
from benchmarks.run import build_result, render_report
from benchmarks.schema_tax.core import (
    CATALOG_SCALES,
    compare_contracts,
    generate_catalog,
    measure_catalog,
    relevance_cases,
)


def test_ratio_metrics_and_zero_token_edge_case():
    metrics = ratio_metrics(100, 40, 0.5)
    assert metrics["token_reduction"] == pytest.approx(0.6)
    assert metrics["actual_compression_ratio"] == pytest.approx(0.4)
    assert metrics["target_ratio_error"] == pytest.approx(0.1)
    assert ratio_metrics(0, 0, 0.5)["actual_compression_ratio"] is None


def test_independent_label_retention_and_empty_labels():
    assert labelled_retention("Keep Alpha and 42", ["alpha", "42"]) == 1.0
    assert labelled_retention("Keep Alpha", []) is None


def test_dataset_is_well_formed_and_multilingual():
    samples = load_dataset()
    assert len(samples) >= 22
    assert {"en", "hi", "zh", "ja"} <= {sample["language"] for sample in samples}
    assert len({sample["category"] for sample in samples}) >= 20


def test_dataset_rejects_malformed_data(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"id": "x"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_dataset(path)


def test_parser_based_structural_integrity():
    assert structural_integrity('{"ok": true}', '{"ok": true}', "json")["valid"] is True
    assert structural_integrity('<a/>', '<a>', "xml")["valid"] is False
    assert structural_integrity("# H\n\n```py\nx=1\n```", "# H\n\n```py\nx=1\n```", "markdown")["valid"] is True


def test_aggregation_has_macro_safe_empty_values():
    assert aggregate_records([], "score")["count"] == 0
    assert aggregate_records([{"score": 0.2}, {"score": 0.4}], "score")["median"] == pytest.approx(0.3)


def test_schema_tax_measurement_and_turn_derivation():
    measured = measure_catalog(generate_catalog(4, "COMPLEX"), "COMPLEX")
    assert measured["classification"] == "MEASURED"
    assert measured["cumulative_schema_tokens"]["16"]["classification"] == "DERIVED"
    assert measured["cumulative_schema_tokens"]["16"]["tokens"] == measured["total_schema_tokens"] * 16
    assert measured["description_token_share"] > 0


def test_schema_contract_detects_semantic_changes_but_tracks_description():
    original = generate_catalog(1, "MEDIUM")[0]
    description_only = json.loads(json.dumps(original))
    description_only["function"]["description"] = "Different behaviour hint"
    assert compare_contracts(original, description_only)["contract_equal"] is True
    assert compare_contracts(original, description_only)["description_equal"] is False
    changed = json.loads(json.dumps(original))
    changed["function"]["parameters"]["properties"]["limit"]["maximum"] = 10
    assert compare_contracts(original, changed)["contract_equal"] is False


def test_catalog_scales_and_relevance_ground_truth():
    assert all(len(generate_catalog(scale, "SIMPLE")) == scale for scale in CATALOG_SCALES)
    assert any(not item["relevant_tool_ids"] for item in relevance_cases())


def test_result_schema_report_and_strict_security_regression():
    result = build_result(mode="fast", iterations=1)
    validate_result(result)
    assert result["schema_version"] == RESULT_SCHEMA_VERSION
    assert "Tool schema tax" in render_report(result)
    previous = json.loads(json.dumps(result))
    result["security"]["provenance_boundary_violations"] = 1
    assert compare_results(result, previous)[0] == {"category": "SECURITY_REGRESSION", "status": "FAIL"}
