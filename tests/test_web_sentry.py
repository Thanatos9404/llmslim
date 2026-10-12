"""Tests for the website functions' optional server-side Sentry setup (web/api/_sentry.py)."""

from __future__ import annotations

import importlib
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

API_DIR = Path(__file__).resolve().parents[1] / "web" / "api"
if str(API_DIR) not in sys.path:
    sys.path.append(str(API_DIR))
# The same module object the functions use, so state and patches are shared.
sentry = importlib.import_module("_sentry")

SECRET = "sk_live_should_never_leave_the_server"


@pytest.fixture(autouse=True)
def _fresh_state() -> Any:
    sentry.reset_for_tests()
    yield
    sentry.reset_for_tests()


def event_with_everything() -> dict[str, Any]:
    return {
        "message": f"failed for 'Ship to Koregaon Park' at https://api.example.test/v1?key={SECRET}",
        "logentry": {
            "message": "bad input %s",
            "params": ["Koregaon Park"],
            "formatted": 'bad "Koregaon"',
        },
        "user": {"ip_address": "203.0.113.9", "id": "u1"},
        "extra": {"payload": "the whole prompt"},
        "breadcrumbs": {"values": [{"message": "POST /api/studio"}]},
        "server_name": "ip-10-0-0-1",
        "tags": {"function": "studio"},
        "request": {
            "method": "POST",
            "url": f"https://www.llmslim.app/api/sarvam_answer?token={SECRET}#frag",
            "query_string": f"token={SECRET}",
            "data": {"context": "the compressed context", "question": "where?"},
            "cookies": {"llmslim_hosted_session": "abc"},
            "env": {"REMOTE_ADDR": "203.0.113.9"},
            "headers": {
                "Authorization": f"Bearer {SECRET}",
                "X-Sarvam-API-Key": SECRET,
                "Cookie": "llmslim_hosted_session=abc",
                "X-Forwarded-For": "203.0.113.9",
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Content-Length": "120",
            },
        },
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": f'could not parse "{SECRET}" from https://evil.test/x',
                    "stacktrace": {
                        "frames": [
                            {"function": "run", "lineno": 3, "vars": {"text": "the prompt"}},
                            "not-a-frame",
                        ]
                    },
                },
                "not-an-entry",
            ]
        },
    }


def test_scrubber_drops_bodies_cookies_query_strings_and_credential_headers() -> None:
    event = sentry.scrub_event(event_with_everything(), None)
    flat = repr(event)
    for leaked in (
        SECRET,
        "Koregaon",
        "the whole prompt",
        "203.0.113.9",
        "compressed context",
        "abc",
        "frag",
    ):
        assert leaked not in flat
    assert event["request"] == {
        "method": "POST",
        "url": "https://www.llmslim.app/api/sarvam_answer",
        "headers": {"Content-Type": "application/json", "Content-Length": "120"},
    }
    for key in ("user", "extra", "breadcrumbs", "server_name"):
        assert key not in event
    assert event["tags"] == {"function": "studio"}
    exception = event["exception"]["values"][0]
    assert exception["type"] == "ValueError"
    assert exception["value"] == 'could not parse "[redacted]" from [url]'
    assert "vars" not in exception["stacktrace"]["frames"][0]
    assert exception["stacktrace"]["frames"][0]["function"] == "run"
    assert "params" not in event["logentry"]
    assert event["logentry"]["formatted"] == 'bad "[redacted]"'


def test_secret_environment_values_and_bare_tokens_are_redacted_everywhere() -> None:
    environ = {
        "SARVAM_API_KEY": "sarvam-key-1234",
        "MONGODB_URI": "mongodb+srv://ledger:pass@cluster.example",
        "LLMSLIM_RATE_LIMIT_HMAC_SECRET": "h" * 40,
        "SHORT_TOKEN": "abc",
        "PATH": "/usr/bin",
    }
    token = "abcdefghijklmnopqrstuvwxyz0123456789"
    event = {
        "exception": {
            "values": [
                {
                    "value": f"auth failed for sarvam-key-1234 with {token}",
                    "stacktrace": {
                        "frames": [
                            {
                                "context_line": "uri = 'mongodb+srv://ledger:pass@cluster.example'",
                                "pre_context": ["sarvam-key-1234", 3],
                            }
                        ]
                    },
                }
            ]
        },
        "tags": {"path": "/usr/bin", "secret": "h" * 40, "short": "abc"},
    }
    scrubbed = sentry.scrub_event(event, None, environ=environ)
    blob = repr(scrubbed)
    for leaked in ("sarvam-key-1234", "ledger:pass", "h" * 40, token):
        assert leaked not in blob
    assert (
        scrubbed["exception"]["values"][0]["value"] == "auth failed for [redacted] with [redacted]"
    )
    assert scrubbed["tags"] == {"path": "/usr/bin", "secret": "[redacted]", "short": "abc"}
    assert scrubbed["exception"]["values"][0]["stacktrace"]["frames"][0]["pre_context"][1] == 3


def test_scrubber_tolerates_partial_or_odd_events() -> None:
    assert sentry.scrub_event({}, None) == {}
    odd = sentry.scrub_event(
        {"request": {"headers": "not-a-mapping", "url": 5, "method": 7}, "exception": "x"}, None
    )
    assert odd["request"] == {}
    assert sentry.scrub_event({"request": {"url": "http://[::1"}}, None)["request"] == {}
    assert sentry.scrub_text(None) is None
    assert len(sentry.scrub_text("word " * 100)) == 200


def test_options_are_errors_only_with_no_personal_data() -> None:
    options = sentry.options("https://public@o1.ingest.sentry.io/1", {"VERCEL_ENV": "production"})
    assert options["traces_sample_rate"] == 0
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert options["max_request_body_size"] == "never"
    assert options["max_breadcrumbs"] == 0
    assert options["default_integrations"] is False
    assert options["auto_enabling_integrations"] is False
    assert options["integrations"] == []
    assert options["before_send"] is sentry.scrub_event
    assert options["before_breadcrumb"]({"message": "x"}, None) is None
    assert options["environment"] == "production"
    assert sentry.options("dsn", {})["environment"] == "development"


def install_fake_sdk(
    monkeypatch: pytest.MonkeyPatch, *, fail: bool = False
) -> types.SimpleNamespace:
    calls = types.SimpleNamespace(init=[], captured=[], flushed=[])
    module = types.ModuleType("sentry_sdk")

    def init(**kwargs: Any) -> None:
        if fail:
            raise RuntimeError("bad dsn")
        calls.init.append(kwargs)

    def capture_exception(error: BaseException, **kwargs: Any) -> None:
        calls.captured.append((error, kwargs))

    def flush(timeout: float) -> None:
        calls.flushed.append(timeout)

    module.init = init  # type: ignore[attr-defined]
    module.capture_exception = capture_exception  # type: ignore[attr-defined]
    module.flush = flush  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", module)
    return calls


def test_nothing_is_loaded_or_sent_without_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_fake_sdk(monkeypatch)
    assert sentry.init({}) is False
    assert sentry.init({"SENTRY_DSN": "https://late@o1.ingest.sentry.io/1"}) is False  # once only
    sentry.capture(RuntimeError("x"), function="studio")
    assert calls.init == [] and calls.captured == []


def test_init_once_and_capture_tags_and_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_fake_sdk(monkeypatch)
    environ = {
        "SENTRY_DSN": " https://public@o1.ingest.sentry.io/1 ",
        "VERCEL_GIT_COMMIT_SHA": "abc123",
    }
    assert sentry.init(environ) is True
    assert sentry.init(environ) is True
    assert len(calls.init) == 1
    assert calls.init[0]["dsn"] == "https://public@o1.ingest.sentry.io/1"
    assert calls.init[0]["release"] == "abc123"
    error = RuntimeError("boom")
    sentry.capture(error, function="sarvam_answer")
    assert calls.captured == [(error, {"tags": {"function": "sarvam_answer"}})]
    # A short flush: a report that cannot leave quickly is dropped, not waited for.
    assert calls.flushed == [sentry.FLUSH_TIMEOUT_SECONDS] and sentry.FLUSH_TIMEOUT_SECONDS <= 0.5


def test_reports_are_throttled_per_function_and_error_type(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_fake_sdk(monkeypatch)
    assert sentry.init({"SENTRY_DSN": "https://public@o1.ingest.sentry.io/1"}) is True
    limit = sentry.MAX_EVENTS_PER_WINDOW
    sent = [sentry.capture(ValueError("x"), function="studio", now=10.0) for _ in range(limit + 20)]
    assert sent.count(True) == limit
    assert len(calls.captured) == limit and len(calls.flushed) == limit
    # Another error type or function has its own allowance.
    assert sentry.capture(KeyError("x"), function="studio", now=10.0) is True
    assert sentry.capture(ValueError("x"), function="plan", now=10.0) is True
    # The allowance comes back once the window has passed.
    later = 10.0 + sentry.THROTTLE_WINDOW_SECONDS + 0.1
    assert sentry.capture(ValueError("x"), function="studio", now=later) is True


def test_provider_failures_are_reported_without_their_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_fake_sdk(monkeypatch)
    assert sentry.init({"SENTRY_DSN": "https://public@o1.ingest.sentry.io/1"}) is True

    class ApiError(Exception):
        status_code = 403

    leaked = ApiError(f"{SECRET} rejected; body: Ship to Koregaon Park")
    assert sentry.capture_provider_failure(leaked, function="sarvam_answer") is True
    reported, tags = calls.captured[0]
    assert isinstance(reported, sentry.ProviderCallFailed)
    assert str(reported) == "ApiError (HTTP status 403)"
    assert tags == {"tags": {"function": "sarvam_answer"}}
    assert sentry.capture_provider_failure(TimeoutError("slow"), function="sarvam_answer")
    assert str(calls.captured[1][0]) == "TimeoutError (HTTP status none)"


def test_reporting_failures_never_break_a_function(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_sdk(monkeypatch, fail=True)
    assert sentry.init({"SENTRY_DSN": "https://public@o1.ingest.sentry.io/1"}) is False
    sentry.capture(RuntimeError("x"), function="studio")  # no SDK: a no-op

    sentry.reset_for_tests()
    calls = install_fake_sdk(monkeypatch)
    assert sentry.init({"SENTRY_DSN": "https://public@o1.ingest.sentry.io/1"}) is True

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("network down")

    monkeypatch.setattr(sys.modules["sentry_sdk"], "capture_exception", broken)
    sentry.capture(RuntimeError("x"), function="studio")
    assert calls.captured == []


def test_every_function_initialises_and_reports_through_the_shared_helper() -> None:
    functions = sorted(path for path in API_DIR.glob("*.py") if not path.name.startswith("_"))
    assert {path.stem for path in functions} >= {
        "studio",
        "compress",
        "plan",
        "context",
        "sarvam_answer",
    }
    for path in functions:
        source = path.read_text(encoding="utf-8")
        assert "import _sentry" in source, path.name
        assert "_sentry.init()" in source, path.name
        reported = re.search(rf'_sentry\.capture\(error, function="{path.stem}"\)', source)
        constant = (
            f'FUNCTION = "{path.stem}"' in source
            and "_sentry.capture(error, function=FUNCTION)" in source
        )
        assert reported or constant, path.name


def test_the_helper_is_not_a_route() -> None:
    # Vercel ignores files in api/ whose names start with an underscore.
    assert (API_DIR / "_sentry.py").is_file()
    assert not (API_DIR / "sentry.py").exists()


def test_requirements_pin_the_server_sdk_without_extras() -> None:
    lines = (API_DIR.parent / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert any(re.fullmatch(r"sentry-sdk==\d+\.\d+\.\d+", line) for line in lines)
