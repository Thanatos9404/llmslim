"""Sarvam chat providers, shared error mapping, prices and cache telemetry (fakes only)."""

from __future__ import annotations

import asyncio
import typing
from types import SimpleNamespace
from typing import Any, List, Optional

import pytest

from llmslim.cache import PROVIDER_CAPABILITIES
from llmslim.cache_adapters import parse_cache_telemetry
from llmslim.hosted import HostedSarvamService
from llmslim.integrations import _sarvam_common as common
from llmslim.integrations.sarvam import (
    CHAT_GUARD_PREFIX,
    DEFAULT_CHAT_LIMITS,
    SARVAM_PRICES,
    AsyncSarvamProvider,
    SarvamAuthenticationError,
    SarvamInvalidRequestError,
    SarvamMalformedResponseError,
    SarvamPaymentRequiredError,
    SarvamPriceTable,
    SarvamProvider,
    SarvamProviderError,
    SarvamRateLimitError,
    SarvamServerError,
    SarvamServiceUsage,
    SarvamTimeoutError,
    SarvamUsage,
    UsageCapExceeded,
    UsageGuard,
    UsageLimits,
    map_sarvam_error,
    sarvam_chat_cost_inr,
)
from llmslim.planning.profiles import BUILTIN_MODEL_PROFILES
from llmslim.rewrite import RewriteRequest

SECRET = "sk-live-should-never-leak"


def _response(
    content: Any = "ok",
    *,
    prompt: Optional[int] = 100,
    completion: Optional[int] = 20,
    cached: Optional[int] = None,
    reasoning: Optional[int] = None,
    usage: bool = True,
) -> Any:
    details = SimpleNamespace(cached_tokens=cached) if cached is not None else None
    completion_details = (
        SimpleNamespace(reasoning_tokens=reasoning) if reasoning is not None else None
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=(
            SimpleNamespace(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=(prompt or 0) + (completion or 0),
                prompt_tokens_details=details,
                completion_tokens_details=completion_details,
            )
            if usage
            else None
        ),
    )


class _Completions:
    def __init__(self, response: Any = None, error: Optional[BaseException] = None) -> None:
        self.response = response if response is not None else _response()
        self.error = error
        self.calls: List[dict] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class _AsyncCompletions(_Completions):
    async def __call__(self, **kwargs: Any) -> Any:  # type: ignore[override]
        return _Completions.__call__(self, **kwargs)


def _client(completions: Any) -> Any:
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _guard(**limits: Any) -> UsageGuard:
    base = {"requests_per_minute": None, "max_requests": None, "max_units": None, "unit": "inr"}
    base.update(limits)
    return UsageGuard(UsageLimits(**base), name="test")


def _clear_chat_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for suffix in ("REQUESTS_PER_MINUTE", "MAX_REQUESTS", "MAX_UNITS"):
        monkeypatch.delenv(f"LLMSLIM_SARVAM_CHAT_{suffix}", raising=False)


# --------------------------------------------------------------------------- prices


def test_sarvam_profiles_use_the_published_2026_10_12_prices() -> None:
    for model in ("sarvam-105b", "sarvam-105b-conversations"):
        profile = BUILTIN_MODEL_PROFILES[model]
        assert profile.input_cost_per_million == 15.0
        assert profile.cached_input_cost_per_million == 5.0
        assert profile.output_cost_per_million == 60.0
        assert profile.currency == "INR"
        assert profile.pricing_as_of == "2026-10-12"
        assert profile.source == "https://docs.sarvam.ai/api/getting-started/pricing"


def test_chat_cost_bills_cached_input_at_the_cached_rate() -> None:
    assert sarvam_chat_cost_inr("sarvam-105b", 1_000_000, 1_000_000) == pytest.approx(75.0)
    assert sarvam_chat_cost_inr(
        "sarvam-105b", 1_000_000, 1_000_000, cached_tokens=400_000
    ) == pytest.approx(71.0)
    # A cached count above the prompt is clamped, never negative.
    assert sarvam_chat_cost_inr("sarvam-105b", 10, 0, cached_tokens=50) == pytest.approx(
        10 * 5.0 / 1_000_000
    )
    no_cached_rate = BUILTIN_MODEL_PROFILES["generic-128k"]
    assert sarvam_chat_cost_inr("x", 10, 10, cached_tokens=5, profile=no_cached_rate) == 0.0


def test_price_table_is_dated_and_validated() -> None:
    assert SARVAM_PRICES.as_of == "2026-10-12"
    assert SARVAM_PRICES.language_identification_per_10k_chars == 3.5
    assert SARVAM_PRICES.transliteration_per_10k_chars == 20.0
    assert SARVAM_PRICES.translation_per_10k_chars == 20.0
    assert SARVAM_PRICES.document_digitization_per_page == 0.5
    assert SARVAM_PRICES.speech_to_text_per_hour == 30.0
    assert SARVAM_PRICES.text_to_speech_per_10k_chars == 30.0
    with pytest.raises(ValueError, match="translation_per_10k_chars"):
        SarvamPriceTable(translation_per_10k_chars=-1)
    with pytest.raises(ValueError):
        SarvamPriceTable(document_digitization_per_page=True)  # type: ignore[arg-type]
    usage = SarvamServiceUsage("translation", 1, 10, "characters", 0.02, "2026-10-12")
    assert usage.to_dict()["classification"] == "ESTIMATED"


# --------------------------------------------------------------------------- sync provider


def test_direct_construction_has_no_guard_and_reports_cached_usage() -> None:
    completions = _Completions(_response(cached=40, reasoning=7))
    provider = SarvamProvider(client=_client(completions))
    assert provider.guard is None
    assert provider.chat([{"role": "user", "content": "hello"}]) == "ok"
    usage = provider.last_usage
    assert usage == SarvamUsage(100, 20, 120, cached_tokens=40, reasoning_tokens=7)
    assert usage is not None and usage.to_dict()["cached_tokens"] == 40
    assert completions.calls[0]["stream"] is False
    assert completions.calls[0]["model"] == "sarvam-105b"


def test_guard_refuses_before_the_client_is_called() -> None:
    completions = _Completions()
    guard = _guard(max_units=0.000001)
    provider = SarvamProvider(client=_client(completions), guard=guard)
    with pytest.raises(UsageCapExceeded):
        provider.chat([{"role": "user", "content": "hello"}])
    assert completions.calls == []
    assert guard.snapshot()["requests"] == 0


def test_guard_settles_with_provider_reported_usage() -> None:
    guard = _guard(max_units=10.0)
    provider = SarvamProvider(client=_client(_Completions(_response(cached=50))), guard=guard)
    provider.rewrite(RewriteRequest("text", system_prompt="be brief", user_prompt="shorten"))
    expected = sarvam_chat_cost_inr("sarvam-105b", 100, 20, cached_tokens=50)
    assert guard.snapshot()["units"] == pytest.approx(expected, abs=1e-6)
    assert guard.snapshot()["requests"] == 1


def test_missing_usage_keeps_the_conservative_reservation() -> None:
    guard = _guard(max_units=10.0)
    provider = SarvamProvider(client=_client(_Completions(_response(usage=False))), guard=guard)
    content = "न" * 50
    provider.chat([{"role": "user", "content": content}], max_tokens=10)
    reserved = sarvam_chat_cost_inr("sarvam-105b", len(content.encode("utf-8")) + 16, 10)
    assert guard.snapshot()["units"] == pytest.approx(reserved, abs=1e-6)
    assert provider.last_usage is None


def test_reservation_is_bounded_by_the_context_window() -> None:
    guard = _guard(max_units=100.0)
    provider = SarvamProvider(client=_client(_Completions(_response(usage=False))), guard=guard)
    provider.chat([{"role": "user", "content": "क" * 200_000}], max_tokens=100)
    bound = sarvam_chat_cost_inr("sarvam-105b", 131_072, 100)
    assert guard.snapshot()["units"] == pytest.approx(bound, abs=1e-6)


def test_malformed_response_is_typed_but_still_settled() -> None:
    guard = _guard(max_units=10.0)
    response = _response(content="   ")
    provider = SarvamProvider(client=_client(_Completions(response)), guard=guard)
    with pytest.raises(SarvamMalformedResponseError):
        provider.chat([{"role": "user", "content": "hello"}])
    assert provider.last_usage is not None
    assert guard.snapshot()["units"] == pytest.approx(sarvam_chat_cost_inr("sarvam-105b", 100, 20))
    for bad in (SimpleNamespace(choices=[]), SimpleNamespace(choices="text"), object(), {}):
        broken = SarvamProvider(client=_client(_Completions(bad)))
        with pytest.raises(SarvamMalformedResponseError):
            broken.chat([{"role": "user", "content": "hello"}])


def test_dict_shaped_responses_are_read() -> None:
    response = {
        "choices": [{"message": {"content": "dict ok"}}],
        "usage": {
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }
    provider = SarvamProvider(client=_client(_Completions(response)))
    assert provider.chat([{"role": "user", "content": "hi"}]) == "dict ok"
    assert provider.last_usage == SarvamUsage(3, 2, 5, cached_tokens=0)
    weird = {"choices": [{"message": {"content": "x"}}], "usage": {"prompt_tokens": "3"}}
    provider = SarvamProvider(client=_client(_Completions(weird)))
    provider.chat([{"role": "user", "content": "hi"}])
    assert provider.last_usage == SarvamUsage(None, None, None)


def test_message_and_option_validation() -> None:
    provider = SarvamProvider(client=_client(_Completions()))
    with pytest.raises(ValueError, match="empty"):
        provider.chat([])
    with pytest.raises(ValueError, match="role"):
        provider.chat([{"role": "robot", "content": "x"}])
    with pytest.raises(ValueError, match="content"):
        provider.chat([{"role": "user", "content": ""}])
    with pytest.raises(ValueError, match="max_tokens"):
        provider.chat([{"role": "user", "content": "x"}], max_tokens=0)
    with pytest.raises(TypeError, match="guard"):
        SarvamProvider(client=object(), guard="no")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires api_key"):
        AsyncSarvamProvider()


_STATUS_CASES = [
    (401, SarvamAuthenticationError, True),
    (403, SarvamAuthenticationError, True),
    (402, SarvamPaymentRequiredError, True),
    (429, SarvamRateLimitError, True),
    (400, SarvamInvalidRequestError, True),
    (422, SarvamInvalidRequestError, True),
    (408, SarvamTimeoutError, False),
    (504, SarvamTimeoutError, False),
    (500, SarvamServerError, False),
    (503, SarvamServerError, False),
    (200, SarvamMalformedResponseError, False),
]


class _StatusError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"headers: authorization={SECRET}")
        self.status_code = status


@pytest.mark.parametrize("status,error_type,released", _STATUS_CASES)
def test_http_status_errors_are_typed_sanitized_and_accounted(
    status: int, error_type: type, released: bool
) -> None:
    guard = _guard(max_units=10.0)
    completions = _Completions(error=_StatusError(status))
    provider = SarvamProvider(client=_client(completions), guard=guard)
    with pytest.raises(error_type) as captured:
        provider.chat([{"role": "user", "content": "hello"}])
    assert SECRET not in str(captured.value)
    assert captured.value.__cause__ is None and captured.value.__suppress_context__
    assert captured.value.status_code == status
    assert provider.last_usage is None
    assert len(completions.calls) == 1  # never retried
    snapshot = guard.snapshot()
    assert snapshot["requests"] == 1
    assert (snapshot["units"] == 0) is released


def test_sdk_error_classes_map_by_type() -> None:
    pytest.importorskip("sarvamai")
    from sarvamai.core.api_error import ApiError
    from sarvamai.errors import (
        BadGatewayError,
        ForbiddenError,
        GatewayTimeoutError,
        InternalServerError,
        PaymentRequiredError,
        ServiceUnavailableError,
        TooManyRequestsError,
        UnauthorizedError,
        UnprocessableEntityError,
    )

    cases = [
        (UnauthorizedError(body={"key": SECRET}), SarvamAuthenticationError),
        (ForbiddenError(body=SECRET), SarvamAuthenticationError),
        (TooManyRequestsError(body=SECRET), SarvamRateLimitError),
        (PaymentRequiredError(body=SECRET), SarvamPaymentRequiredError),
        (GatewayTimeoutError(body=SECRET), SarvamTimeoutError),
        (InternalServerError(body=SECRET), SarvamServerError),
        (BadGatewayError(body=SECRET), SarvamServerError),
        (ServiceUnavailableError(body=SECRET), SarvamServerError),
        (UnprocessableEntityError(body=SECRET), SarvamInvalidRequestError),
        (ApiError(status_code=200, body=SECRET), SarvamMalformedResponseError),
    ]
    for exc, expected in cases:
        mapped = map_sarvam_error(exc)
        assert type(mapped) is expected, exc
        assert SECRET not in str(mapped)


def test_transport_and_parse_errors_map_by_class_name() -> None:
    httpx = pytest.importorskip("httpx")
    assert isinstance(map_sarvam_error(httpx.ReadTimeout(SECRET)), SarvamTimeoutError)
    connect = map_sarvam_error(httpx.ConnectError(SECRET))
    assert type(connect) is SarvamProviderError and SECRET not in str(connect)
    assert isinstance(
        map_sarvam_error(type("ValidationError", (Exception,), {})()),
        SarvamMalformedResponseError,
    )
    assert isinstance(
        map_sarvam_error(type("PermissionDeniedError", (Exception,), {})()),
        SarvamAuthenticationError,
    )
    response_error = Exception(SECRET)
    response_error.response = SimpleNamespace(status_code=404)  # type: ignore[attr-defined]
    assert isinstance(map_sarvam_error(response_error), SarvamInvalidRequestError)
    flagged = Exception()
    flagged.status_code = True  # type: ignore[attr-defined]
    assert type(map_sarvam_error(flagged)) is SarvamProviderError
    existing = SarvamTimeoutError("already sanitized")
    assert map_sarvam_error(existing) is existing
    assert map_sarvam_error(RuntimeError(), job_id="job-9").job_id == "job-9"


def test_repr_and_from_env_never_expose_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_chat_env(monkeypatch)
    monkeypatch.setenv("TEST_SARVAM_KEY", SECRET)
    provider = SarvamProvider.from_env("TEST_SARVAM_KEY", client=_client(_Completions()))
    async_provider = AsyncSarvamProvider.from_env("TEST_SARVAM_KEY", client=object())
    for item in (provider, async_provider):
        assert SECRET not in repr(item)
        assert "credentials=<redacted>" in repr(item)
    monkeypatch.delenv("MISSING_SARVAM_KEY", raising=False)
    with pytest.raises(ValueError, match="MISSING_SARVAM_KEY"):
        SarvamProvider.from_env("MISSING_SARVAM_KEY")


def test_from_env_attaches_the_chat_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_chat_env(monkeypatch)
    monkeypatch.setenv("TEST_SARVAM_KEY", "k")
    default = SarvamProvider.from_env("TEST_SARVAM_KEY", client=object())
    assert default.guard is not None
    assert default.guard.limits == DEFAULT_CHAT_LIMITS
    assert default.guard.name == CHAT_GUARD_PREFIX

    monkeypatch.setenv("LLMSLIM_SARVAM_CHAT_MAX_REQUESTS", "1")
    completions = _Completions()
    capped = SarvamProvider.from_env("TEST_SARVAM_KEY", client=_client(completions))
    capped.chat([{"role": "user", "content": "one"}])
    with pytest.raises(UsageCapExceeded):
        capped.chat([{"role": "user", "content": "two"}])
    assert len(completions.calls) == 1

    opted_out = SarvamProvider.from_env("TEST_SARVAM_KEY", client=object(), guard=None)
    assert opted_out.guard is None
    own = _guard(max_units=1.0)
    assert SarvamProvider.from_env("TEST_SARVAM_KEY", client=object(), guard=own).guard is own


def test_live_clients_are_built_only_from_an_explicit_key() -> None:
    pytest.importorskip("sarvamai")
    from llmslim.integrations.sarvam import (
        AsyncSarvamDocumentSource,
        AsyncSarvamLanguageTools,
        SarvamDocumentSource,
        SarvamLanguageTools,
    )

    # Construction opens no connection; it only wires the official SDK client.
    for cls in (
        SarvamProvider,
        AsyncSarvamProvider,
        SarvamLanguageTools,
        AsyncSarvamLanguageTools,
        SarvamDocumentSource,
        AsyncSarvamDocumentSource,
    ):
        built = cls(SECRET)
        assert SECRET not in repr(built)
        assert built._client is not None


def test_hosted_default_factory_still_admits_a_maximal_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("sarvamai")
    _clear_chat_env(monkeypatch)
    monkeypatch.setenv("SARVAM_API_KEY", "test-only-key")
    # hosted.py builds one provider per request through SarvamProvider.from_env.
    provider = HostedSarvamService._default_provider_factory(
        None,  # type: ignore[arg-type]
        "sarvam-105b",
        4096,
        25.0,
    )
    assert provider.guard is not None and provider.guard.limits == DEFAULT_CHAT_LIMITS
    completions = _Completions(_response(prompt=131_072, completion=4096))
    provider._client = _client(completions)
    assert provider.chat([{"role": "user", "content": "क" * 200_000}], max_tokens=4096) == "ok"
    assert len(completions.calls) == 1


# --------------------------------------------------------------------------- async provider


def test_async_provider_parity() -> None:
    guard = _guard(max_units=10.0)
    completions = _AsyncCompletions(_response(cached=10))
    provider = AsyncSarvamProvider(client=_client(completions), guard=guard)
    assert provider.is_available()
    result = asyncio.run(provider.arewrite(RewriteRequest("text", user_prompt="prompt")))
    assert result == "ok"
    assert completions.calls[0]["messages"] == [{"role": "user", "content": "prompt"}]
    assert guard.snapshot()["units"] == pytest.approx(
        sarvam_chat_cost_inr("sarvam-105b", 100, 20, cached_tokens=10)
    )

    refusing = _guard(max_requests=1)
    refusing.acquire()
    idle = _AsyncCompletions()
    blocked = AsyncSarvamProvider(client=_client(idle), guard=refusing)
    with pytest.raises(UsageCapExceeded):
        asyncio.run(blocked.chat([{"role": "user", "content": "x"}]))
    assert idle.calls == []

    failing = AsyncSarvamProvider(
        client=_client(_AsyncCompletions(error=_StatusError(429))), guard=_guard(max_units=1.0)
    )
    with pytest.raises(SarvamRateLimitError):
        asyncio.run(failing.chat([{"role": "user", "content": "x"}]))
    assert failing.guard is not None and failing.guard.snapshot()["units"] == 0
    assert failing.last_usage is None


def test_async_last_usage_is_isolated_per_task() -> None:
    class Varying:
        async def __call__(self, **kwargs: Any) -> Any:
            prompt = len(kwargs["messages"][0]["content"])
            await asyncio.sleep(0)
            return _response(prompt=prompt, completion=1)

    provider = AsyncSarvamProvider(client=_client(Varying()))

    async def one(text: str) -> Optional[int]:
        await provider.chat([{"role": "user", "content": text}])
        await asyncio.sleep(0)
        usage = provider.last_usage
        return usage.prompt_tokens if usage else None

    async def both() -> Any:
        return await asyncio.gather(one("a" * 3), one("b" * 7))

    assert asyncio.run(both()) == [3, 7]


# --------------------------------------------------------------------------- cache telemetry


def test_sarvam_cache_telemetry_distinguishes_hit_miss_and_unreported() -> None:
    hit = parse_cache_telemetry(
        "sarvam",
        {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 9,
                "prompt_tokens_details": {"cached_tokens": 30},
            }
        },
    )
    assert (hit.input_tokens, hit.cache_read_tokens, hit.output_tokens) == (100, 30, 9)
    assert hit.provider_cache_hit is True
    assert hit.cache_hit_ratio == pytest.approx(0.3)

    miss = parse_cache_telemetry(
        "sarvam",
        {"usage": {"prompt_tokens": 100, "completion_tokens": 9, "prompt_tokens_details": None}},
    )
    assert miss.cache_read_tokens is None and miss.provider_cache_hit is None

    zero = parse_cache_telemetry(
        "sarvam",
        {"usage": {"prompt_tokens": 100, "prompt_tokens_details": {"cached_tokens": 0}}},
    )
    assert zero.cache_read_tokens == 0 and zero.provider_cache_hit is False

    inconsistent = parse_cache_telemetry(
        "sarvam", {"usage": {"prompt_tokens": 10, "prompt_tokens_details": {"cached_tokens": 50}}}
    )
    assert inconsistent.input_tokens == 10 and inconsistent.cache_read_tokens is None

    legacy = parse_cache_telemetry("sarvam", {"usage": {"input_tokens": 5, "output_tokens": 2}})
    assert (legacy.input_tokens, legacy.output_tokens, legacy.cache_read_tokens) == (5, 2, None)
    assert PROVIDER_CAPABILITIES["sarvam"].verified is False


def test_sarvam_cache_telemetry_reads_sdk_response_objects() -> None:
    pytest.importorskip("sarvamai")
    from sarvamai.core.pydantic_utilities import parse_obj_as
    from sarvamai.types import CreateChatCompletionResponse

    payload = {
        "id": "chatcmpl-1",
        "created": 0,
        "model": "sarvam-105b",
        "object": "chat.completion",
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {"role": "assistant", "content": "नमस्ते"},
            }
        ],
        "usage": {
            "prompt_tokens": 64,
            "completion_tokens": 8,
            "total_tokens": 72,
            "prompt_tokens_details": {"cached_tokens": 32},
            "completion_tokens_details": {"reasoning_tokens": 3},
        },
    }
    response = parse_obj_as(CreateChatCompletionResponse, payload)  # type: ignore[arg-type]
    telemetry = parse_cache_telemetry("sarvam", response)
    assert (telemetry.input_tokens, telemetry.cache_read_tokens) == (64, 32)
    provider = SarvamProvider(client=_client(_Completions(response)))
    assert provider.chat([{"role": "user", "content": "hi"}]) == "नमस्ते"
    assert provider.last_usage == SarvamUsage(64, 8, 72, cached_tokens=32, reasoning_tokens=3)


# --------------------------------------------------------------------------- SDK literal parity


def test_language_code_sets_match_the_installed_sdk_literals() -> None:
    pytest.importorskip("sarvamai")
    from sarvamai.types import (
        DocDigitizationSupportedLanguage,
        NumeralsFormat,
        TranslateMode,
        TranslateModel,
        TranslateSourceLanguage,
        TranslateSpeakerGender,
        TranslateTargetLanguage,
        TranslatiterateTargetLanguage,
        TransliterateMode,
        TransliterateSourceLanguage,
    )

    def literal(alias: Any) -> set:
        for arg in typing.get_args(alias):
            if typing.get_origin(arg) is typing.Literal:
                return set(typing.get_args(arg))
        raise AssertionError(alias)

    assert literal(TranslateSourceLanguage) == common.TRANSLATE_SOURCE_LANGUAGES
    assert literal(TranslateTargetLanguage) == common.TRANSLATE_TARGET_LANGUAGES
    assert literal(TransliterateSourceLanguage) == common.TRANSLITERATE_SOURCE_LANGUAGES
    assert literal(TranslatiterateTargetLanguage) == common.TRANSLITERATE_TARGET_LANGUAGES
    assert literal(DocDigitizationSupportedLanguage) == common.DOCUMENT_LANGUAGES
    assert literal(TranslateModel) == common.TRANSLATE_MODELS
    assert literal(TranslateMode) == common.TRANSLATE_MODES
    assert literal(TransliterateMode) == common.OUTPUT_SCRIPTS
    assert literal(NumeralsFormat) == common.NUMERALS_FORMATS
    assert literal(TranslateSpeakerGender) == common.SPEAKER_GENDERS
    assert set(common.NATIVE_SCRIPTS) <= common.TRANSLITERATE_TARGET_LANGUAGES
