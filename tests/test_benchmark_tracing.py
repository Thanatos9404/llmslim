"""Offline tests for the opt-in LangSmith tracing helper used by benchmarks only."""

from __future__ import annotations

import json
import sys
import types
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from benchmarks import _tracing as tracing
from benchmarks._tracing import (
    BenchmarkTracer,
    TracingRefused,
    dataset_sha256,
    is_public_dataset,
)
from llmslim.integrations._guard import UsageGuard, UsageLimits

ROOT = Path(__file__).resolve().parents[1]
V06 = ROOT / "benchmarks" / "datasets" / "v06_context_planning.json"
KEY = "ls-test-key-must-never-leak-789"
ON = {"LLMSLIM_LANGSMITH_TRACING": "1", "LANGSMITH_API_KEY": KEY}


def _call(tracer: BenchmarkTracer, **overrides: Any) -> bool:
    values: Dict[str, Any] = {
        "name": "sarvam-105b case-1 full",
        "inputs": {"messages": [{"role": "user", "content": "q"}]},
        "outputs": {"answer": "a"},
        "prompt_tokens": 120,
        "completion_tokens": 8,
        "cost": 0.0023,
        "currency": "INR",
        "latency_ms": 812.5,
        "metadata": {"case_id": "case-1", "arm": "full", "reader_role": "secondary"},
    }
    values.update(overrides)
    return tracer.record_reader_call(**values)


class FakeLangSmithClient:
    instances: List["FakeLangSmithClient"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.runs: List[Dict[str, Any]] = []
        self.flushed = False
        FakeLangSmithClient.instances.append(self)

    def create_run(self, name: str, inputs: Any, run_type: str, **kwargs: Any) -> None:
        self.runs.append({"name": name, "inputs": inputs, "run_type": run_type, **kwargs})

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def fake_langsmith(monkeypatch: pytest.MonkeyPatch) -> type:
    FakeLangSmithClient.instances = []
    module = types.ModuleType("langsmith")
    module.Client = FakeLangSmithClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langsmith", module)
    return FakeLangSmithClient


@pytest.fixture
def no_langsmith(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "langsmith", None)  # import raises ImportError


def test_tracing_is_off_without_both_flag_and_key() -> None:
    for env in ({}, {"LANGSMITH_API_KEY": KEY}, {"LLMSLIM_LANGSMITH_TRACING": "1"}):
        tracer = BenchmarkTracer.from_env(dataset_public=False, env=env)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert _call(tracer) is False
        assert tracer.enabled is False
        assert tracer.summary() == {
            "enabled": False,
            "project": None,
            "recorded": 0,
            "dropped": 0,
        }
        tracer.close()


def test_tracing_refuses_datasets_not_marked_public() -> None:
    with pytest.raises(TracingRefused, match="not marked public"):
        BenchmarkTracer.from_env(dataset_public=False, env=ON)


def test_public_flag_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert is_public_dataset(V06) is True
    assert tracing.PUBLIC_DATASETS["benchmarks/datasets/v06_context_planning.json"] == (
        dataset_sha256(V06)
    )
    copy = tmp_path / "copy.json"
    copy.write_bytes(V06.read_bytes())
    assert is_public_dataset(copy) is False  # same content, but not pinned and not flagged
    flagged = tmp_path / "flagged.json"
    flagged.write_text(json.dumps({"public": True, "cases": []}), encoding="utf-8")
    assert is_public_dataset(flagged) is True
    truthy = tmp_path / "truthy.json"
    truthy.write_text(json.dumps({"public": "yes", "cases": []}), encoding="utf-8")
    assert is_public_dataset(truthy) is False  # only the JSON value true counts
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert is_public_dataset(broken) is False
    assert is_public_dataset(tmp_path / "missing.json") is False
    monkeypatch.setitem(
        tracing.PUBLIC_DATASETS, "benchmarks/datasets/v06_context_planning.json", "0" * 64
    )
    assert is_public_dataset(V06) is False  # an edited dataset is not public until reviewed


def test_crlf_and_lf_checkouts_hash_the_same(tmp_path: Path) -> None:
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "a": 1\n}\n')
    crlf.write_bytes(b'{\r\n  "a": 1\r\n}\r\n')
    assert dataset_sha256(lf) == dataset_sha256(crlf)


def test_records_through_the_langsmith_sdk(fake_langsmith: type) -> None:
    tracer = BenchmarkTracer.from_env(
        dataset_public=True, env=dict(ON, LANGSMITH_PROJECT="bench-x")
    )
    assert _call(tracer) is True
    client = fake_langsmith.instances[0]
    assert client.kwargs["api_key"] == KEY
    assert client.kwargs["auto_batch_tracing"] is False
    run = client.runs[0]
    assert run["project_name"] == "bench-x"
    assert run["run_type"] == "llm"
    assert run["inputs"] == {"messages": [{"role": "user", "content": "q"}]}
    assert run["outputs"]["answer"] == "a"
    assert run["outputs"]["usage_metadata"] == {
        "input_tokens": 120,
        "output_tokens": 8,
        "total_tokens": 128,
        "total_cost": 0.0023,
    }
    metadata = run["extra"]["metadata"]
    assert metadata["cost"] == 0.0023 and metadata["currency"] == "INR"
    assert metadata["latency_ms"] == 812.5 and metadata["reader_role"] == "secondary"
    assert (run["end_time"] - run["start_time"]).total_seconds() == pytest.approx(0.8125, abs=1e-3)
    assert run["dotted_order"].endswith(run["id"]) and run["trace_id"] == run["id"]
    assert tracer.summary() == {"enabled": True, "project": "bench-x", "recorded": 1, "dropped": 0}
    assert KEY not in repr(tracer)
    tracer.close()
    assert client.flushed is True


def test_default_project_name(fake_langsmith: type) -> None:
    tracer = BenchmarkTracer.from_env(dataset_public=True, env=ON)
    assert tracer.project == "llmslim-benchmarks"
    _call(tracer, prompt_tokens=None, completion_tokens=None, cost=None)
    run = fake_langsmith.instances[0].runs[0]
    assert run["project_name"] == "llmslim-benchmarks"
    assert "usage_metadata" not in run["outputs"]


def test_sdk_without_auto_batch_keyword_is_still_used(monkeypatch: pytest.MonkeyPatch) -> None:
    class OldClient(FakeLangSmithClient):
        def __init__(self, api_key: str, api_url: str) -> None:
            super().__init__(api_key=api_key, api_url=api_url)

    module = types.ModuleType("langsmith")
    module.Client = OldClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langsmith", module)
    FakeLangSmithClient.instances = []
    tracer = BenchmarkTracer.from_env(dataset_public=True, env=ON)
    assert _call(tracer) is True
    assert FakeLangSmithClient.instances[-1].runs


def test_falls_back_to_the_rest_api_over_httpx(no_langsmith: None) -> None:
    httpx = pytest.importorskip("httpx")
    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        return httpx.Response(202, json={})

    tracer = BenchmarkTracer.from_env(
        dataset_public=True,
        env=dict(ON, LANGSMITH_ENDPOINT="https://eu.api.smith.langchain.com/"),
        http_transport=httpx.MockTransport(handler),
    )
    assert _call(tracer) is True
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://eu.api.smith.langchain.com/runs"
    assert request.headers["x-api-key"] == KEY
    body = json.loads(request.content)
    assert body["session_name"] == "llmslim-benchmarks"
    assert body["run_type"] == "llm" and body["name"] == "sarvam-105b case-1 full"
    assert KEY not in request.content.decode("utf-8")
    tracer.close()


def test_rest_error_disables_tracing_with_one_warning(no_langsmith: None) -> None:
    httpx = pytest.importorskip("httpx")
    tracer = BenchmarkTracer.from_env(
        dataset_public=True,
        env=ON,
        http_transport=httpx.MockTransport(lambda request: httpx.Response(401, json={})),
    )
    with pytest.warns(RuntimeWarning, match="disabled after an error") as caught:
        assert _call(tracer) is False
        assert _call(tracer) is False
    assert len(caught) == 1
    assert tracer.enabled is False and tracer.recorded == 0
    assert KEY not in str(caught[0].message)


def test_no_backend_is_a_no_op_with_exactly_one_warning(
    no_langsmith: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "httpx", None)
    tracer = BenchmarkTracer.from_env(dataset_public=True, env=ON)
    with pytest.warns(RuntimeWarning, match="neither the langsmith SDK nor httpx") as caught:
        for _ in range(3):
            assert _call(tracer) is False
    assert len(caught) == 1
    assert tracer.enabled is False


def test_sdk_constructor_failure_falls_back_to_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    httpx = pytest.importorskip("httpx")

    class BrokenClient:
        def __init__(self, **kwargs: Any) -> None:
            raise RuntimeError("misconfigured")

    module = types.ModuleType("langsmith")
    module.Client = BrokenClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langsmith", module)
    seen: List[Any] = []
    tracer = BenchmarkTracer.from_env(
        dataset_public=True,
        env=ON,
        http_transport=httpx.MockTransport(
            lambda request: seen.append(request) or httpx.Response(200, json={})
        ),
    )
    assert _call(tracer) is True and len(seen) == 1


def test_guard_cap_stops_tracing_and_rate_limit_drops_a_trace(fake_langsmith: type) -> None:
    capped = BenchmarkTracer.from_env(
        dataset_public=True,
        env=ON,
        guard=UsageGuard(UsageLimits(requests_per_minute=None, max_requests=1)),
    )
    with pytest.warns(RuntimeWarning, match="stopped") as caught:
        assert _call(capped) is True
        assert _call(capped) is False
        assert _call(capped) is False
    assert len(caught) == 1
    assert capped.summary()["dropped"] == 1 and capped.enabled is False

    clock = SimpleNamespace(now=0.0)
    limited = BenchmarkTracer.from_env(
        dataset_public=True,
        env=ON,
        guard=UsageGuard(
            UsageLimits(requests_per_minute=1, max_requests=None), clock=lambda: clock.now
        ),
    )
    with pytest.warns(RuntimeWarning, match="dropped"):
        assert _call(limited) is True
        assert _call(limited) is False
    assert limited.enabled is True and limited.dropped == 1
    clock.now += 61
    assert _call(limited) is True


def test_guard_defaults_and_env_overrides() -> None:
    tracer = BenchmarkTracer.from_env(
        dataset_public=True, env=dict(ON, LLMSLIM_LANGSMITH_MAX_REQUESTS="7")
    )
    assert tracer.guard is not None
    assert tracer.guard.name == "langsmith"
    assert tracer.guard.limits.requests_per_minute == 120
    assert tracer.guard.limits.max_requests == 7
    default = BenchmarkTracer(enabled=True, api_key=KEY)
    assert default.guard is not None and default.guard.limits.max_requests == 5000
    assert BenchmarkTracer(enabled=False).guard is None


def test_runner_traces_each_billed_call(fake_langsmith: type, tmp_path: Path) -> None:
    from benchmarks import live_secondary_reader as live
    from tests.test_benchmark_secondary_reader import (
        FakeSarvamSDK,
        _priced_registry,
    )

    sdk = FakeSarvamSDK()
    tracer = BenchmarkTracer.from_env(dataset_public=True, env=ON)
    result = live.run_suite(
        live.SarvamReader(sdk, registry=_priced_registry()),
        UsageGuard(UsageLimits(requests_per_minute=None, max_units=100.0, unit="inr")),
        output_path=tmp_path / "live.json",
        dataset_path=live.DATASET,
        limit=2,
        tracer=tracer,
        log=lambda *_: None,
    )
    runs = fake_langsmith.instances[0].runs
    assert len(runs) == len(sdk.requests) == result["totals"]["billed_calls"]
    assert result["tracing"]["recorded"] == len(runs)
    metadata = runs[0]["extra"]["metadata"]
    assert metadata["reader_role"] == "secondary"
    assert metadata["headline_reader"] == "Claude Haiku 5.5"
    assert metadata["dataset_sha256"] == dataset_sha256(V06)


def test_main_refuses_tracing_a_private_dataset_before_any_call(tmp_path: Path) -> None:
    from benchmarks import live_secondary_reader as live

    dataset = tmp_path / "private.json"
    dataset.write_text(json.dumps({"schema_version": "1.0", "cases": []}), encoding="utf-8")

    def factory(*_: Any) -> Any:
        raise AssertionError("no reader may be built")

    env = dict(ON, LLMSLIM_RUN_LIVE_SARVAM="1", SARVAM_API_KEY="sv-key")
    with pytest.raises(TracingRefused):
        live.main(["--dataset", str(dataset)], env=env, reader_factory=factory)


def test_llmslim_library_never_imports_benchmark_code() -> None:
    offenders = []
    for path in (ROOT / "llmslim").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and (
                "benchmarks" in stripped or "_tracing" in stripped or "langsmith" in stripped
            ):
                offenders.append(f"{path.relative_to(ROOT)}: {stripped}")
    assert offenders == []
