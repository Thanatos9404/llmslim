"""v0.7 Studio Context Inspector executes the local runtime and stays bounded."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

API_PATH = Path(__file__).resolve().parents[1] / "web" / "api" / "context.py"
SPEC = importlib.util.spec_from_file_location("studio_context_api", API_PATH)
assert SPEC is not None and SPEC.loader is not None
studio_context_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(studio_context_api)


def _payload(**overrides):
    value = {
        "messages": [{"role": "system", "content": "Use verified dates."}],
        "documents": [{"id": "acme", "content": "Acme renews November 9."}],
        "query": "When does Acme renew?",
        "model": "sarvam-105b",
        "max_input_tokens": 2048,
        "reserve_output_tokens": 256,
        "quality_floor": 0.80,
        "objective": "balanced",
    }
    value.update(overrides)
    return value


def test_context_inspector_returns_real_plan_trace_graph():
    response = studio_context_api.execute_context(_payload())
    assert response["plan"]["feasible"]
    assert response["trace"]["planner_version"] == "0.7.0"
    assert response["quality"]["passed"]
    assert response["graph"]["nodes"]
    assert "Acme renews November 9" in response["plan"]["final_context"]
    assert "Acme renews November 9" not in str(response["trace"])
    assert "Acme renews November 9" not in str(response["envelope"])


@pytest.mark.parametrize("change,code", [
    ({"secret": "x"}, "unsupported_field"),
    ({"model": "unknown"}, "invalid_model"),
    ({"objective": "magic"}, "invalid_objective"),
    ({"quality_floor": 1.1}, "invalid_quality_floor"),
    ({"messages": "bad"}, "invalid_messages"),
    ({"documents": ["x" * 100_000]}, "input_too_large"),
    ({"tools": ["bad"]}, "invalid_tools"),
])
def test_context_inspector_rejects_invalid_inputs(change, code):
    with pytest.raises(studio_context_api.RequestProblem) as error:
        studio_context_api.execute_context(_payload(**change))
    assert error.value.code == code


def test_context_inspector_sanitizes_credential_metadata():
    with pytest.raises(studio_context_api.RequestProblem) as error:
        studio_context_api.execute_context(_payload(
            documents=[{"content": "text", "metadata": {"api_key": "never-return-me"}}]
        ))
    assert error.value.code == "invalid_context"
    assert "never-return-me" not in error.value.message


def test_context_inspector_reports_missing_runtime(monkeypatch):
    monkeypatch.setattr(studio_context_api, "ContextRuntime", None)
    with pytest.raises(studio_context_api.RequestProblem) as error:
        studio_context_api.execute_context(_payload())
    assert error.value.status == 503
    assert error.value.code == "runtime_unavailable"
