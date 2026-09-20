"""Validation and parity tests for the Studio v0.6 planner endpoint."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from llmslim import plan_context

API_PATH = Path(__file__).resolve().parents[1] / "web" / "api" / "plan.py"
SPEC = importlib.util.spec_from_file_location("studio_plan_api", API_PATH)
assert SPEC is not None and SPEC.loader is not None
studio_plan_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(studio_plan_api)


def payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "messages": [
            {"role": "system", "content": "Keep verified dates."},
            {"role": "user", "content": "When does Acme renew?"},
        ],
        "documents": [{"content": "Acme renews on 30 November 2026."}],
        "memories": [{"content": "The user prefers concise answers."}],
        "tools": [
            {
                "name": "lookup_customer",
                "description": "Read a customer record.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ],
        "query": "Acme renewal",
        "model": "sarvam-105b",
        "max_input_tokens": 2048,
        "reserve_output_tokens": 256,
        "safety_margin_tokens": 64,
        "policy": "balanced",
    }
    value.update(overrides)
    return value


def test_studio_plan_matches_public_api() -> None:
    request = payload()
    response = studio_plan_api.execute_plan(request)
    direct = plan_context(**request)
    assert response["status"] == direct.status.value
    assert response["final_context"] == direct.final_context
    assert response["metrics"]["planned_tokens"] == direct.metrics.planned_tokens
    assert response["validation"]["passed"] is True


@pytest.mark.parametrize(
    "request_payload,code",
    [
        (payload(model="unknown"), "invalid_model"),
        (payload(policy="magic"), "invalid_policy"),
        (payload(max_input_tokens=100), "invalid_max_input_tokens"),
        (payload(messages="not-an-array"), "invalid_messages"),
        (payload(tools=["not-a-schema"]), "invalid_tools"),
        (payload(secret="must-not-be-accepted"), "unsupported_field"),
    ],
)
def test_studio_plan_rejects_invalid_requests(
    request_payload: dict[str, object], code: str
) -> None:
    with pytest.raises(studio_plan_api.RequestProblem) as error:
        studio_plan_api.execute_plan(request_payload)
    assert error.value.code == code


def test_studio_plan_input_is_bounded() -> None:
    with pytest.raises(studio_plan_api.RequestProblem) as error:
        studio_plan_api.execute_plan(payload(documents=["x" * 100_000]))
    assert error.value.code == "input_too_large"
