"""Adaptive planner CLI tests."""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import patch

import pytest

from llmslim.cli import build_plan_parser, main


def _payload() -> dict:
    return {
        "messages": [
            {"role": "system", "content": "Always preserve the account identifier."},
            {"role": "user", "content": "What changed for Acme?"},
        ],
        "documents": [
            {
                "id": "crm-1",
                "content": "Acme account ACME-42 moved to negotiation. " * 20,
                "source": "fixture",
            }
        ],
        "memories": [],
        "tools": [],
        "query": "Acme account status",
    }


def test_plan_parser_defaults() -> None:
    args = build_plan_parser().parse_args([])
    assert args.model == "generic-128k"
    assert args.policy == "balanced"
    assert args.reserve_output_tokens == 4096
    assert args.safety_margin_tokens == 256


def test_plan_cli_emits_stable_json(tmp_path: Any) -> None:
    source = tmp_path / "context.json"
    source.write_text(json.dumps(_payload()), encoding="utf-8")
    with patch("sys.stdout", new_callable=io.StringIO) as output:
        exit_code = main(
            [
                "plan",
                str(source),
                "--max-input-tokens",
                "500",
                "--reserve-output-tokens",
                "0",
                "--safety-margin-tokens",
                "0",
                "--json",
            ]
        )
    result = json.loads(output.getvalue())
    assert exit_code == 0
    assert result["status"] == "feasible"
    assert result["metrics"]["policy"] == "balanced"
    assert len(result["decisions"]) == 3


def test_plan_cli_no_content_supports_safe_diagnostics() -> None:
    with patch("sys.stdin", io.StringIO(json.dumps(_payload()))):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            exit_code = main(
                [
                    "plan",
                    "-",
                    "--max-input-tokens",
                    "500",
                    "--reserve-output-tokens",
                    "0",
                    "--safety-margin-tokens",
                    "0",
                    "--json",
                    "--no-content",
                ]
            )
    result = json.loads(output.getvalue())
    assert exit_code == 0
    assert "final_context" not in result
    assert "content" not in result["decisions"][0]["item"]


def test_plan_cli_human_report_and_infeasible_exit(tmp_path: Any) -> None:
    source = tmp_path / "context.json"
    source.write_text(
        json.dumps({"messages": [{"role": "system", "content": "Required instruction. " * 100}]}),
        encoding="utf-8",
    )
    with patch("sys.stdout", new_callable=io.StringIO) as output:
        exit_code = main(
            [
                "plan",
                str(source),
                "--max-input-tokens",
                "10",
                "--reserve-output-tokens",
                "0",
                "--safety-margin-tokens",
                "0",
                "--fail-on-infeasible",
            ]
        )
    assert exit_code == 3
    assert "Plan status: INFEASIBLE" in output.getvalue()
    assert "RAW" in output.getvalue()


def test_plan_cli_rejects_invalid_shapes_without_traceback() -> None:
    with patch("sys.stdin", io.StringIO('{"messages": "not-an-array"}')):
        with pytest.raises(SystemExit) as captured:
            main(["plan", "-"])
    assert captured.value.code == 2
