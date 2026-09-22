"""Security and behavior tests for the request-scoped Studio BYOK route."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Optional

import pytest

from llmslim.integrations.sarvam import SarvamUsage

API_PATH = Path(__file__).resolve().parents[1] / "web" / "api" / "sarvam_byok.py"
SPEC = importlib.util.spec_from_file_location("studio_sarvam_byok_api", API_PATH)
assert SPEC is not None and SPEC.loader is not None
studio_sarvam_byok_api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(studio_sarvam_byok_api)


def payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "Use only verified context."},
            {"role": "user", "content": "When does Acme renew?"},
        ],
        "documents": [{"content": "Acme renews on 30 November 2026."}],
        "memories": [],
        "tools": [],
        "query": "Answer with the renewal date.",
        "model": "sarvam-105b",
        "max_input_tokens": 1_024,
        "max_output_tokens": 64,
        "policy": "balanced",
    }
    value.update(overrides)
    return value


class FakeProvider:
    def __init__(self) -> None:
        self.last_usage: Optional[SarvamUsage] = SarvamUsage(120, 20, 140)
        self.messages: Any = None
        self.max_tokens: Optional[int] = None

    def chat(self, messages: Any, *, max_tokens: Optional[int] = None) -> str:
        self.messages = messages
        self.max_tokens = max_tokens
        return "Acme renews on 30 November 2026."


def test_byok_request_plans_calls_provider_and_never_returns_key() -> None:
    provider = FakeProvider()
    secret = "sarvam-test-key-that-must-never-leak"
    result = studio_sarvam_byok_api.execute_byok(
        payload(),
        secret,
        provider_factory=lambda _key, _model, _maximum: provider,
    )
    assert result["plan"]["validation"]["passed"] is True
    assert result["answer"] == "Acme renews on 30 November 2026."
    assert result["usage"]["billing_scope"] == "USER_KEY"
    assert result["usage"]["provider_reported"]["total_tokens"] == 140
    assert provider.max_tokens == 64
    assert secret not in repr(result)
    assert secret not in repr(provider.messages)


@pytest.mark.parametrize("key", [None, "short", "contains whitespace key"])
def test_byok_rejects_missing_or_malformed_keys(key: Optional[str]) -> None:
    with pytest.raises(studio_sarvam_byok_api.ByokProblem) as error:
        studio_sarvam_byok_api.validate_api_key(key)
    assert error.value.code in {"api_key_required", "invalid_api_key"}


def test_byok_rejects_credentials_in_json_and_bounds_provider_tokens() -> None:
    secret = "sarvam-test-key-that-must-never-leak"
    with pytest.raises(studio_sarvam_byok_api.ByokProblem) as body_error:
        studio_sarvam_byok_api.execute_byok(payload(api_key=secret), secret)
    assert body_error.value.code == "credential_in_body"

    with pytest.raises(studio_sarvam_byok_api.ByokProblem) as token_error:
        studio_sarvam_byok_api.execute_byok(payload(max_output_tokens=513), secret)
    assert token_error.value.code == "invalid_max_output_tokens"
