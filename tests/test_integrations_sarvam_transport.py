"""The real ``sarvamai`` SDK over ``httpx.MockTransport``: no retries of billable calls and no
redirects that would carry the subscription key to another origin. No network."""

from __future__ import annotations

import asyncio
import functools
import importlib.util
import io
import json
import sys
import wave
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, List, Tuple

import pytest

httpx = pytest.importorskip("httpx")
sarvamai = pytest.importorskip("sarvamai")

from benchmarks import live_secondary_reader as live  # noqa: E402
from llmslim.integrations import _sarvam_common as common  # noqa: E402
from llmslim.integrations import sarvam as sarvam_module  # noqa: E402
from llmslim.integrations import sarvam_documents as documents_module  # noqa: E402
from llmslim.integrations import sarvam_text as text_module  # noqa: E402
from llmslim.integrations.sarvam import (  # noqa: E402
    AsyncSarvamDocumentSource,
    AsyncSarvamLanguageTools,
    AsyncSarvamProvider,
    SarvamDocumentSource,
    SarvamLanguageTools,
    SarvamProvider,
    SarvamProviderError,
    SarvamServerError,
    UsageGuard,
    UsageLimits,
)

KEY = "sk-transport-test-key-never-leaks"
SARVAM_HOST = "api.sarvam.ai"
ELSEWHERE = "collector.example"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
EXAMPLE = Path(__file__).parents[1] / "examples" / "sarvam_voice_agent.py"


def _guard() -> UsageGuard:
    return UsageGuard(
        UsageLimits(requests_per_minute=None, max_requests=None, max_units=1000.0, unit="inr"),
        name="transport-test",
    )


def _flaky(success: Any) -> Tuple[Any, List[Any]]:
    """A transport answering 503, 503, then 200 with ``success``: what the SDK would retry into."""

    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        if len(seen) <= 2:
            return httpx.Response(503, json={"error": {"message": "busy"}})
        return httpx.Response(200, json=success)

    return httpx.MockTransport(handler), seen


def _redirecting() -> Tuple[Any, List[Any]]:
    """Sarvam's origin answers 307 to another host; anything reaching that host is recorded."""

    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        if request.url.host == SARVAM_HOST:
            return httpx.Response(307, headers={"location": f"https://{ELSEWHERE}/collect"})
        return httpx.Response(200, json=CHAT_OK)  # a convincing answer from the wrong host

    return httpx.MockTransport(handler), seen


def _posts(seen: List[Any]) -> List[Any]:
    return [request for request in seen if request.method == "POST"]


def _patch_builders(monkeypatch: pytest.MonkeyPatch, transport: Any) -> None:
    """Make every client built from a key use ``transport`` (the builders stay the real ones)."""

    sync = functools.partial(common.sync_client, transport=transport)
    asynchronous = functools.partial(common.async_client, transport=transport)
    for module in (sarvam_module, text_module, documents_module):
        monkeypatch.setattr(module, "sync_client", sync)
        monkeypatch.setattr(module, "async_client", asynchronous)


CHAT_OK = {
    "id": "c1",
    "created": 0,
    "model": "sarvam-105b",
    "object": "chat.completion",
    "choices": [
        {"finish_reason": "stop", "index": 0, "message": {"role": "assistant", "content": "ok"}}
    ],
    "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
}
MESSAGES = [{"role": "user", "content": "hello"}]


# --------------------------------------------------------------------------- no retries


def test_sync_chat_sends_one_post_on_a_503_with_built_and_injected_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport, seen = _flaky(CHAT_OK)
    _patch_builders(monkeypatch, transport)
    guard = _guard()
    with SarvamProvider(KEY, guard=guard) as provider:
        with pytest.raises(SarvamServerError):
            provider.chat(MESSAGES)
    assert len(_posts(seen)) == 1 and seen[0].url.path == "/v1/chat/completions"
    assert guard.snapshot()["requests"] == 1
    assert guard.snapshot()["units"] > 0  # a 5xx may be billed: the reservation is kept

    # An injected SDK client keeps its own retry default; the per-call option still wins.
    transport, seen = _flaky(CHAT_OK)
    injected = sarvamai.SarvamAI(
        api_subscription_key=KEY, httpx_client=httpx.Client(transport=transport)
    )
    guard = _guard()
    with pytest.raises(SarvamServerError):
        SarvamProvider(client=injected, guard=guard).chat(MESSAGES)
    assert len(_posts(seen)) == 1
    assert guard.snapshot()["requests"] == 1


def test_async_chat_sends_one_post_on_a_503() -> None:
    transport, seen = _flaky(CHAT_OK)
    injected = sarvamai.AsyncSarvamAI(
        api_subscription_key=KEY, httpx_client=httpx.AsyncClient(transport=transport)
    )
    guard = _guard()
    provider = AsyncSarvamProvider(client=injected, guard=guard)
    with pytest.raises(SarvamServerError):
        asyncio.run(provider.chat(MESSAGES))
    assert len(_posts(seen)) == 1
    assert guard.snapshot()["requests"] == 1


@pytest.mark.parametrize(
    ("call", "success"),
    [
        (lambda tools: tools.identify_language("नमस्ते"), {"language_code": "hi-IN"}),
        (
            lambda tools: tools.transliterate("namaste", "en-IN", "hi-IN"),
            {"transliterated_text": "नमस्ते", "source_language_code": "en-IN"},
        ),
        (
            lambda tools: tools.translate("नमस्ते", "hi-IN", "en-IN"),
            {"translated_text": "hello", "source_language_code": "hi-IN"},
        ),
    ],
)
def test_text_tools_send_one_post_on_a_503(
    monkeypatch: pytest.MonkeyPatch, call: Callable[[Any], Any], success: Any
) -> None:
    transport, seen = _flaky(success)
    _patch_builders(monkeypatch, transport)
    guard = _guard()
    with SarvamLanguageTools(KEY, guard=guard) as tools:
        with pytest.raises(SarvamServerError):
            call(tools)
    assert len(_posts(seen)) == 1
    assert guard.snapshot()["requests"] == 1


def test_async_text_tools_send_one_post_on_a_503(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, seen = _flaky({"translated_text": "hello", "source_language_code": "hi-IN"})
    _patch_builders(monkeypatch, transport)
    guard = _guard()

    async def run() -> None:
        async with AsyncSarvamLanguageTools(KEY, guard=guard) as tools:
            await tools.translate("नमस्ते", "hi-IN", "en-IN")

    with pytest.raises(SarvamServerError):
        asyncio.run(run())
    assert len(_posts(seen)) == 1
    assert guard.snapshot()["requests"] == 1


def test_document_job_creation_is_one_post_on_a_503(monkeypatch: pytest.MonkeyPatch) -> None:
    started = {"job_id": "job-1", "status": "Accepted", "run_id": "run-1"}
    transport, seen = _flaky(started)
    _patch_builders(monkeypatch, transport)
    guard = _guard()
    with SarvamDocumentSource(KEY, guard=guard) as source:
        with pytest.raises(SarvamServerError):
            source.digitize_bytes(PNG, file_name="page.png", language="hi-IN")
    assert len(seen) == 1 and seen[0].method == "POST"
    assert guard.snapshot()["requests"] == 1 and guard.snapshot()["units"] == pytest.approx(0.5)

    transport, seen = _flaky(started)
    _patch_builders(monkeypatch, transport)
    async_guard = _guard()

    async def run() -> None:
        async with AsyncSarvamDocumentSource(KEY, guard=async_guard) as source:
            await source.digitize_bytes(PNG, file_name="page.png", language="hi-IN")

    with pytest.raises(SarvamServerError):
        asyncio.run(run())
    assert len(seen) == 1
    assert async_guard.snapshot()["requests"] == 1


def test_benchmark_sarvam_reader_sends_one_post_per_call(tmp_path: Path) -> None:
    transport, seen = _flaky(CHAT_OK)
    reader = live.SarvamReader.from_env({live.SARVAM_KEY_ENV: KEY}, transport=transport)
    dataset = tmp_path / "one.json"
    dataset.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "name": "one",
                "cases": [
                    {
                        "id": "rel",
                        "category": "rag",
                        "language": "English",
                        "budget": 180,
                        "query": "release identifier",
                        "documents": ["Release identifier REL-600 is approved."],
                        "expected_facts": ["REL-600"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    guard = UsageGuard(live.SARVAM_GUARD_DEFAULTS, name="sarvam_bench")
    try:
        result = live.run_suite(
            reader,
            guard,
            output_path=tmp_path / "live.json",
            dataset_path=dataset,
            arms=("full",),
            log=lambda *_: None,
        )
    finally:
        reader.close()
    assert len(_posts(seen)) == 1
    assert guard.snapshot()["requests"] == 1
    assert result["cases"][0]["arms"]["full"]["status"] == "error"
    assert result["totals"]["billed_calls"] == 1


@pytest.fixture(scope="module")
def voice() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sarvam_voice_agent_transport", EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _wav(path: Path, seconds: float = 1.0) -> Path:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * int(seconds * 8000))
    path.write_bytes(buffer.getvalue())
    return path


def test_voice_example_speech_calls_send_one_post_on_a_503(
    voice: ModuleType, tmp_path: Path
) -> None:
    clip = _wav(tmp_path / "q.wav")
    transport, seen = _flaky({"transcript": "नमस्ते", "language_code": "hi-IN"})
    client = sarvamai.SarvamAI(
        api_subscription_key=KEY, httpx_client=httpx.Client(transport=transport)
    )
    guard = _guard()
    with pytest.raises(SarvamServerError):
        voice.transcribe(client, guard, str(clip))
    assert len(_posts(seen)) == 1 and guard.snapshot()["requests"] == 1

    transport, seen = _flaky({"audios": []})
    client = sarvamai.SarvamAI(
        api_subscription_key=KEY, httpx_client=httpx.Client(transport=transport)
    )
    guard = _guard()
    with pytest.raises(SarvamServerError):
        voice.synthesize(client, guard, "नमस्ते", "hi-IN", str(tmp_path / "a.wav"))
    assert len(_posts(seen)) == 1 and guard.snapshot()["requests"] == 1


# --------------------------------------------------------------------------- no redirects


def test_the_probe_detects_a_leak_when_redirects_are_followed() -> None:
    # Control: the SDK's own default (follow_redirects=True) sends the key to the other host.
    transport, seen = _redirecting()
    leaky = sarvamai.SarvamAI(
        api_subscription_key=KEY,
        httpx_client=httpx.Client(transport=transport, follow_redirects=True),
    )
    leaky.chat.completions(
        messages=MESSAGES, model="sarvam-105b", request_options=common.no_retries()
    )
    leaked = [request for request in seen if request.url.host == ELSEWHERE]
    assert leaked and leaked[0].headers.get("api-subscription-key") == KEY


def _assert_not_followed(seen: List[Any]) -> None:
    assert [request.url.host for request in seen] == [SARVAM_HOST]


def test_built_sync_clients_never_follow_a_cross_origin_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for build, call in (
        (lambda: SarvamProvider(KEY), lambda owner: owner.chat(MESSAGES)),
        (lambda: SarvamLanguageTools(KEY), lambda owner: owner.identify_language("नमस्ते")),
        (
            lambda: SarvamDocumentSource(KEY),
            lambda owner: owner.digitize_bytes(PNG, file_name="p.png", language="hi-IN"),
        ),
    ):
        transport, seen = _redirecting()
        _patch_builders(monkeypatch, transport)
        with build() as owner:
            with pytest.raises(SarvamProviderError) as info:
                call(owner)
        assert info.value.status_code == 307
        _assert_not_followed(seen)


def test_built_async_clients_never_follow_a_cross_origin_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run(build: Callable[[], Any], call: Callable[[Any], Any]) -> None:
        async with build() as owner:
            await call(owner)

    for build, call in (
        (lambda: AsyncSarvamProvider(KEY), lambda owner: owner.chat(MESSAGES)),
        (lambda: AsyncSarvamLanguageTools(KEY), lambda owner: owner.identify_language("नमस्ते")),
        (
            lambda: AsyncSarvamDocumentSource(KEY),
            lambda owner: owner.digitize_bytes(PNG, file_name="p.png", language="hi-IN"),
        ),
    ):
        transport, seen = _redirecting()
        _patch_builders(monkeypatch, transport)
        with pytest.raises(SarvamProviderError):
            asyncio.run(run(build, call))
        _assert_not_followed(seen)


def test_builders_configure_httpx_without_redirects() -> None:
    sdk, http = common.sync_client(KEY, 12.0, "test")
    async_sdk, async_http = common.async_client(KEY, 12.0, "test")
    try:
        assert http.follow_redirects is False and async_http.follow_redirects is False
        assert http.timeout.read == 12.0 and http.timeout.connect == 10.0
        assert sdk._client_wrapper.httpx_client.httpx_client is http
        assert async_sdk._client_wrapper.httpx_client.httpx_client is async_http
    finally:
        http.close()
        asyncio.run(async_http.aclose())


def test_benchmark_reader_never_follows_a_cross_origin_redirect() -> None:
    transport, seen = _redirecting()
    reader = live.SarvamReader.from_env({live.SARVAM_KEY_ENV: KEY}, transport=transport)
    try:
        with pytest.raises(live.ReaderError):
            reader.answer(MESSAGES, 16)
    finally:
        reader.close()
    _assert_not_followed(seen)
    assert reader._owned_http is None


def test_voice_example_builds_its_sdk_client_without_redirects(
    voice: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict = {}

    class Stop(Exception):
        pass

    def recorder(**kwargs: Any) -> Any:
        captured.update(kwargs)
        raise Stop

    monkeypatch.setattr(sarvamai, "SarvamAI", recorder)
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    with pytest.raises(Stop):
        voice.main([str(_wav(tmp_path / "q.wav"))])
    assert captured["follow_redirects"] is False
