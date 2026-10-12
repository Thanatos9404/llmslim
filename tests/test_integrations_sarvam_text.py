"""Sarvam language tools and context helpers (fakes only, no network)."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import unicodedata
from types import SimpleNamespace
from typing import Any, Callable, List, Optional, Tuple

import pytest

from llmslim.core import ContextRole
from llmslim.integrations.sarvam import (
    DEFAULT_TEXT_LIMITS,
    TEXT_GUARD_PREFIX,
    AsyncSarvamLanguageTools,
    RateLimitExceeded,
    SarvamAuthenticationError,
    SarvamLanguageTools,
    SarvamMalformedResponseError,
    SarvamServerError,
    UsageCapExceeded,
    UsageGuard,
    UsageLimits,
    aannotate_languages,
    annotate_languages,
    anormalize_scripts,
    normalize_scripts,
    split_for_sarvam,
)
from llmslim.integrations.sarvam_text import _grapheme_boundary
from llmslim.planning.models import ContextItem, ContextKind

SECRET = "sk-text-secret"


def _detect(text: str) -> Tuple[str, str]:
    if any("\u0900" <= char <= "\u097f" for char in text):
        return "hi-IN", "Deva"
    if any("\u0b80" <= char <= "\u0bff" for char in text):
        return "ta-IN", "Taml"
    if " hai" in text or text.startswith("mera"):
        return "hi-IN", "Latn"
    return "en-IN", "Latn"


class _Failure(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"body echoes {SECRET}")
        self.status_code = status


class _FakeText:
    def __init__(
        self,
        *,
        detector: Callable[[str], Tuple[str, str]] = _detect,
        error: Optional[BaseException] = None,
        malformed: bool = False,
    ) -> None:
        self.detector = detector
        self.error = error
        self.malformed = malformed
        self.calls: List[Tuple[str, str, dict]] = []
        # request_options of every call, kept apart so ``calls`` shows the API arguments.
        self.request_options: List[Any] = []

    def _record(self, name: str, text: str, kwargs: dict) -> None:
        self.request_options.append(kwargs.pop("request_options", "missing"))
        self.calls.append((name, text, kwargs))
        if self.error is not None:
            raise self.error

    def identify_language(self, *, input: str, **kwargs: Any) -> Any:
        self._record("identify_language", input, kwargs)
        if self.malformed:
            return SimpleNamespace(language_code=7, script_code=None)
        language, script = self.detector(input)
        return SimpleNamespace(language_code=language, script_code=script)

    def transliterate(self, *, input: str, **kwargs: Any) -> Any:
        self._record("transliterate", input, kwargs)
        if self.malformed:
            return SimpleNamespace(source_language_code="en-IN")
        return SimpleNamespace(
            transliterated_text=f"<{input}>", source_language_code=kwargs["source_language_code"]
        )

    def translate(self, *, input: str, **kwargs: Any) -> Any:
        self._record("translate", input, kwargs)
        return SimpleNamespace(translated_text=input.upper(), source_language_code="hi-IN")


class _AsyncFakeText(_FakeText):
    async def identify_language(self, *, input: str, **kwargs: Any) -> Any:  # type: ignore[override]
        return _FakeText.identify_language(self, input=input, **kwargs)

    async def transliterate(self, *, input: str, **kwargs: Any) -> Any:  # type: ignore[override]
        return _FakeText.transliterate(self, input=input, **kwargs)

    async def translate(self, *, input: str, **kwargs: Any) -> Any:  # type: ignore[override]
        return _FakeText.translate(self, input=input, **kwargs)


def _guard(**limits: Any) -> UsageGuard:
    base = {"requests_per_minute": None, "max_requests": None, "max_units": None, "unit": "inr"}
    base.update(limits)
    return UsageGuard(UsageLimits(**base), name="text-test")


def _tools(
    fake: Optional[_FakeText] = None, **kwargs: Any
) -> Tuple[SarvamLanguageTools, _FakeText]:
    fake = fake or _FakeText()
    return SarvamLanguageTools(client=SimpleNamespace(text=fake), **kwargs), fake


def _async_tools(
    fake: Optional[_AsyncFakeText] = None, **kwargs: Any
) -> Tuple[AsyncSarvamLanguageTools, _AsyncFakeText]:
    fake = fake or _AsyncFakeText()
    return AsyncSarvamLanguageTools(client=SimpleNamespace(text=fake), **kwargs), fake


def _sentences(count: int, word: str = "alpha") -> str:
    return " ".join(f"{word} sentence number {index} ends here." for index in range(count))


# --------------------------------------------------------------------------- splitting


def test_split_keeps_text_at_the_limit_whole_and_splits_one_over() -> None:
    exact = "a" * 999 + "."
    assert split_for_sarvam(exact, 1000) == [exact]
    over = "word " * 200 + "x"  # 1001 characters
    parts = split_for_sarvam(over, 1000)
    assert len(parts) == 2
    assert "".join(parts) == over
    assert all(len(part) <= 1000 for part in parts)
    assert parts[0].endswith(" ") and not parts[1].startswith(" ")


def test_split_prefers_a_late_sentence_end_then_a_word_boundary() -> None:
    text = _sentences(60)
    parts = split_for_sarvam(text, 300)
    assert "".join(parts) == text
    assert all(part.rstrip().endswith(".") for part in parts[:-1])
    hindi = "यह पहला वाक्य है। " * 40
    hindi_parts = split_for_sarvam(hindi, 100)
    assert "".join(hindi_parts) == hindi
    assert all(part.rstrip().endswith("।") for part in hindi_parts[:-1])
    no_sentences = "lorem ipsum " * 50
    word_parts = split_for_sarvam(no_sentences, 64)
    assert all(part.endswith(" ") for part in word_parts[:-1])
    quoted = 'He said "stop." Then ' * 30
    assert all(part.rstrip().endswith(('."', "Then")) for part in split_for_sarvam(quoted, 50)[:-1])
    newline = ("line without stop\n" * 20).strip()
    assert "".join(split_for_sarvam(newline, 40)) == newline


def test_split_never_cuts_inside_a_grapheme_cluster() -> None:
    conjuncts = "क्षत्रिय" * 300  # no spaces: forces hard cuts
    parts = split_for_sarvam(conjuncts, 25)
    assert "".join(parts) == conjuncts
    for part in parts:
        assert len(part) <= 25
        assert unicodedata.category(part[0]) not in ("Mn", "Mc")
        assert unicodedata.combining(part[-1]) != 9  # never ends on a virama
    family = "\U0001f468\u200d\U0001f469\u200d\U0001f467" * 20
    for part in split_for_sarvam(family, 7):
        assert not part.startswith("\u200d") and not part.endswith("\u200d")
    flags = "\U0001f1ee\U0001f1f3" * 10  # regional-indicator pairs
    assert all(len(part) % 2 == 0 for part in split_for_sarvam(flags, 5))
    thumbs = "\U0001f44d\U0001f3fd" * 10
    assert all(not part.startswith("\U0001f3fd") for part in split_for_sarvam(thumbs, 3))
    clusters = split_for_sarvam("क्ष" * 10, 5)  # ka + virama + ssa: one conjunct
    assert all(len(part) % 3 == 0 for part in clusters)
    spaced_marks = "ab " + chr(0x301) + "cd " * 30  # a combining mark after a space
    assert all(not part.startswith(chr(0x301)) for part in split_for_sarvam(spaced_marks, 10))
    crlf = "\r\n".join(["x" * 9] * 10)
    assert all(not part.startswith("\n") for part in split_for_sarvam(crlf, 10))
    assert _grapheme_boundary("ab", 0) and _grapheme_boundary("ab", 2)


def test_split_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError):
        split_for_sarvam("text", 0)
    with pytest.raises(ValueError):
        split_for_sarvam("text", True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        split_for_sarvam(b"bytes", 5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="grapheme"):
        split_for_sarvam("a" + "\u0301" * 20, 5)


# --------------------------------------------------------------------------- language id


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_blank_text_is_rejected_without_a_call(blank: str) -> None:
    tools, fake = _tools()
    for call in (
        lambda: tools.identify_language(blank),
        lambda: tools.transliterate(blank, "en-IN", "hi-IN"),
        lambda: tools.translate(blank, "hi-IN", "en-IN"),
    ):
        with pytest.raises(ValueError, match="non-whitespace"):
            call()
    with pytest.raises(TypeError):
        tools.identify_language(None)  # type: ignore[arg-type]
    assert fake.calls == []


def test_identify_language_sends_at_most_the_requested_parts() -> None:
    tools, fake = _tools(guard=_guard(max_units=10.0))
    exact = "नमस्ते " * 142 + "नमस्ते"  # exactly 1000 characters
    assert len(exact) == 1000
    result = tools.identify_language(exact)
    assert (result.language_code, result.script_code) == ("hi-IN", "Deva")
    assert result.characters_sent == 1000 and result.usage.requests == 1
    assert result.usage.cost_inr == pytest.approx(1000 / 10_000 * 3.5)
    assert tools.guard.snapshot()["units"] == pytest.approx(0.35)

    long_text = exact + " " + exact
    sampled = tools.identify_language(long_text)
    assert sampled.usage.requests == 1
    assert sampled.characters_sent < sampled.total_characters == len(long_text)
    full = tools.identify_language(long_text, max_chunks=5)
    assert full.usage.requests == 3 and not full.mixed
    with pytest.raises(ValueError, match="max_chunks"):
        tools.identify_language("x", max_chunks=0)
    assert all(len(text) <= 1000 for _, text, _ in fake.calls)


def test_identify_language_reports_multi_script_input() -> None:
    tools, _ = _tools()
    hindi = "यह हिंदी में लिखा गया एक लंबा वाक्य है। " * 60
    english = "This part of the note is written in English only. " * 25
    tamil = "இது தமிழ். "
    result = tools.identify_language(hindi + english + tamil, max_chunks=10)
    assert result.mixed
    assert result.language_code == "hi-IN"  # most characters wins
    assert len({segment[0] for segment in result.segments}) > 1
    assert sum(segment[2] for segment in result.segments) == result.characters_sent


# --------------------------------------------------------------------------- transliterate / translate


def test_transliterate_chunks_in_order_and_reassembles_whitespace() -> None:
    tools, fake = _tools(guard=_guard(max_units=10.0))
    text = "  " + ("mera naam Rahul hai. " * 60) + "\n"
    result = tools.transliterate(text, "en-IN", "hi-IN", numerals_format="native")
    sent = [call[1] for call in fake.calls]
    assert len(sent) == 2
    assert all(len(part) <= 1000 for part in sent)
    assert "".join(part.replace("<", "").replace(">", "") for part in [result.text]) == text
    assert result.text.startswith("  <mera") and result.text.endswith("> \n")
    assert fake.calls[0][2] == {
        "source_language_code": "en-IN",
        "target_language_code": "hi-IN",
        "numerals_format": "native",
    }
    characters = sum(len(part) for part in sent)
    assert result.usage.quantity == characters
    assert result.usage.cost_inr == pytest.approx(characters / 10_000 * 20)
    assert tools.guard.snapshot()["units"] == pytest.approx(result.usage.cost_inr)
    assert result.source_language_code == "en-IN" and result.model is None


def test_long_whitespace_runs_are_kept_but_never_sent() -> None:
    tools, fake = _tools()
    text = "start" + " " * 2500 + "end"
    result = tools.transliterate(text, "en-IN", "hi-IN")
    assert result.text == "<start>" + " " * 2500 + "<end>"
    assert [call[1] for call in fake.calls] == ["start", "end"]


def test_translate_respects_the_model_limit_and_validation() -> None:
    tools, fake = _tools()
    text = "यह एक वाक्य है। " * 100  # 1,600 characters
    assert tools.translate(text, "hi-IN", "en-IN").usage.requests == 1
    assert fake.calls[-1][2]["model"] == "sarvam-translate:v1"
    fake.calls.clear()
    mayura = tools.translate(
        text, "auto", "en-IN", model="mayura:v1", mode="code-mixed", output_script="roman"
    )
    assert mayura.usage.requests == 2
    assert mayura.source_language_code == "hi-IN"  # detected by Sarvam
    assert fake.calls[0][2]["mode"] == "code-mixed"
    assert tools.estimate("translate", text, model="mayura:v1").requests == 2

    invalid = [
        {"source_language_code": "xx-IN", "target_language_code": "en-IN"},
        {"source_language_code": "hi-IN", "target_language_code": "hi-IN"},
        {"source_language_code": "auto", "target_language_code": "en-IN"},
        {"source_language_code": "hi-IN", "target_language_code": "en-IN", "mode": "code-mixed"},
        {
            "source_language_code": "hi-IN",
            "target_language_code": "en-IN",
            "output_script": "roman",
        },
        {"source_language_code": "ur-IN", "target_language_code": "en-IN", "model": "mayura:v1"},
        {"source_language_code": "hi-IN", "target_language_code": "en-IN", "model": "gpt"},
        {"source_language_code": "hi-IN", "target_language_code": "en-IN", "speaker_gender": "x"},
        {"source_language_code": None, "target_language_code": "en-IN"},
    ]
    fake.calls.clear()
    for kwargs in invalid:
        with pytest.raises(ValueError):
            tools.translate("text", **kwargs)  # type: ignore[arg-type]
    assert fake.calls == []
    formal = tools.translate(
        "नमस्ते", "hi-IN", "ur-IN", mode="formal", numerals_format="native", speaker_gender="Female"
    )
    assert formal.text == "नमस्ते".upper()
    assert fake.calls[-1][2]["speaker_gender"] == "Female"


def test_transliterate_rejects_unsupported_codes_and_options() -> None:
    tools, fake = _tools()
    for args, kwargs in [
        (("text", "en-IN", "ur-IN"), {}),
        (("text", "xx", "hi-IN"), {}),
        (("text", "hi-IN", "hi-IN"), {}),
        (("text", "en-IN", "hi-IN"), {"spoken_form": "yes"}),
        (("text", "en-IN", "hi-IN"), {"spoken_form_numerals_language": "roman"}),
        (("text", None, "hi-IN"), {}),
    ]:
        with pytest.raises(ValueError):
            tools.transliterate(*args, **kwargs)  # type: ignore[arg-type]
    assert fake.calls == []
    tools.transliterate("namaste", "auto", "hi-IN", spoken_form=True)
    assert fake.calls[0][2]["spoken_form"] is True
    with pytest.raises(ValueError, match="operation"):
        tools.estimate("summarize", "text")
    with pytest.raises(ValueError, match="translation model"):
        tools.estimate("translate", "text", model="gpt")


# --------------------------------------------------------------------------- guard and errors


def test_guard_refuses_before_any_call() -> None:
    tools, fake = _tools(guard=_guard(max_units=0.0001))
    with pytest.raises(UsageCapExceeded):
        tools.transliterate("mera naam", "en-IN", "hi-IN")
    assert fake.calls == []

    long_text = "mera naam Rahul hai. " * 150  # several parts
    assert _tools()[0].estimate("transliterate", long_text).requests > 2
    capped, capped_fake = _tools(guard=_guard(max_requests=2))
    with pytest.raises(UsageCapExceeded, match=r"needs \d+ requests"):
        capped.transliterate(long_text, "en-IN", "hi-IN")
    assert capped_fake.calls == []
    budget, budget_fake = _tools(guard=_guard(max_units=0.01))
    with pytest.raises(UsageCapExceeded, match="usage cap"):
        budget.translate(long_text, "hi-IN", "en-IN")
    assert budget_fake.calls == []
    # More parts than the per-minute rate allows can never succeed: a cap, not a rate limit.
    slow, slow_fake = _tools(guard=_guard(requests_per_minute=2))
    with pytest.raises(UsageCapExceeded, match="can never be admitted") as never:
        slow.transliterate(long_text, "en-IN", "hi-IN")
    assert not isinstance(never.value, RateLimitExceeded)
    assert slow_fake.calls == []
    # An operation that fits the rate but not the current window is a real (waitable) rate limit.
    parts = _tools()[0].estimate("transliterate", long_text).requests
    busy, busy_fake = _tools(guard=_guard(requests_per_minute=parts))
    busy.guard.acquire()
    with pytest.raises(RateLimitExceeded) as info:
        busy.transliterate(long_text, "en-IN", "hi-IN")
    assert info.value.retry_after_seconds == 60.0
    assert busy_fake.calls == []


def test_errors_are_typed_sanitized_and_accounted() -> None:
    guard = _guard(max_units=10.0)
    tools, fake = _tools(_FakeText(error=_Failure(401)), guard=guard)
    with pytest.raises(SarvamAuthenticationError) as captured:
        tools.translate("नमस्ते", "hi-IN", "en-IN")
    assert SECRET not in str(captured.value)
    assert len(fake.calls) == 1
    assert guard.snapshot() == {**guard.snapshot(), "requests": 1, "units": 0.0}

    kept = _guard(max_units=10.0)
    tools, _ = _tools(_FakeText(error=_Failure(500)), guard=kept)
    with pytest.raises(SarvamServerError):
        tools.transliterate("namaste", "en-IN", "hi-IN")
    assert kept.snapshot()["units"] == pytest.approx(7 / 10_000 * 20)

    settled = _guard(max_units=10.0)
    tools, _ = _tools(_FakeText(malformed=True), guard=settled)
    with pytest.raises(SarvamMalformedResponseError):
        tools.transliterate("namaste", "en-IN", "hi-IN")
    with pytest.raises(SarvamMalformedResponseError):
        tools.identify_language("namaste")
    assert settled.snapshot()["requests"] == 2

    empty, _ = _tools(_FakeText(detector=lambda text: (None, None)))  # type: ignore[arg-type,return-value]
    unknown = empty.identify_language("???")
    assert unknown.language_code is None and unknown.script_code is None
    none_client = SarvamLanguageTools(
        client=SimpleNamespace(text=SimpleNamespace(identify_language=lambda input, **_: None))
    )
    with pytest.raises(SarvamMalformedResponseError):
        none_client.identify_language("text")


def test_construction_defaults_env_and_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    tools, _ = _tools()
    assert tools.guard.limits == DEFAULT_TEXT_LIMITS
    assert tools.guard.name == TEXT_GUARD_PREFIX
    assert DEFAULT_TEXT_LIMITS.unit == "inr"
    with pytest.raises(ValueError, match="requires api_key"):
        SarvamLanguageTools()
    with pytest.raises(ValueError, match="requires api_key"):
        AsyncSarvamLanguageTools()
    with pytest.raises(ValueError, match="timeout"):
        SarvamLanguageTools(client=object(), timeout_seconds=0)
    with pytest.raises(TypeError, match="prices"):
        SarvamLanguageTools(client=object(), prices={})  # type: ignore[arg-type]

    for suffix in ("REQUESTS_PER_MINUTE", "MAX_REQUESTS"):
        monkeypatch.delenv(f"LLMSLIM_SARVAM_TEXT_{suffix}", raising=False)
    monkeypatch.setenv("LLMSLIM_SARVAM_TEXT_MAX_UNITS", "1.5")
    monkeypatch.setenv("TEST_SARVAM_KEY", SECRET)
    from_env = SarvamLanguageTools.from_env("TEST_SARVAM_KEY", client=object())
    assert from_env.guard.limits.max_units == 1.5
    assert from_env.guard.limits.requests_per_minute == 60
    assert SECRET not in repr(from_env) and "<redacted>" in repr(from_env)
    own = _guard()
    assert (
        AsyncSarvamLanguageTools.from_env("TEST_SARVAM_KEY", client=object(), guard=own).guard
        is own
    )
    monkeypatch.delenv("TEST_SARVAM_KEY")
    with pytest.raises(ValueError, match="TEST_SARVAM_KEY"):
        SarvamLanguageTools.from_env("TEST_SARVAM_KEY")


# --------------------------------------------------------------------------- context helpers


def _item(item_id: str, content: str, **kwargs: Any) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        content=content,
        kind=ContextKind.RAG_DOCUMENT,
        role=ContextRole.RAG,
        **kwargs,
    )


def test_annotate_languages_returns_new_items_and_skips_blank_or_known() -> None:
    tools, fake = _tools()
    items = [
        _item("a", "यह हिंदी है"),
        _item("b", "   "),
        _item("c", "mera naam Rahul hai"),
        _item("d", "already known", metadata={"language_code": "en-IN"}),
    ]
    annotated = annotate_languages(items, tools)
    assert [item.item_id for item in annotated] == ["a", "b", "c", "d"]
    assert annotated[0].metadata["language_code"] == "hi-IN"
    assert annotated[0].metadata["script_code"] == "Deva"
    assert annotated[0].metadata["language_mixed"] is False
    assert annotated[2].metadata["script_code"] == "Latn"
    assert annotated[1] is items[1] and annotated[3] is items[3]
    assert "language_code" not in items[0].metadata  # originals untouched
    assert annotated[0].content == items[0].content
    assert len(fake.calls) == 2
    with pytest.raises(dataclasses.FrozenInstanceError):
        annotated[0].content = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        annotated[0].metadata["language_code"] = "x"  # type: ignore[index]

    again = annotate_languages(annotated, tools, overwrite=True)
    assert len(fake.calls) == 5
    assert again[3].metadata["language_code"] == "en-IN"


def test_helpers_preflight_the_whole_batch_and_check_types() -> None:
    tools, fake = _tools(guard=_guard(max_requests=1))
    with pytest.raises(UsageCapExceeded):
        annotate_languages([_item("a", "one"), _item("b", "two")], tools)
    assert fake.calls == []
    async_tools, _ = _async_tools()
    with pytest.raises(TypeError, match="SarvamLanguageTools"):
        annotate_languages([], async_tools)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="AsyncSarvamLanguageTools"):
        asyncio.run(aannotate_languages([], tools))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ContextItem"):
        annotate_languages(["plain text"], tools)  # type: ignore[list-item]
    with pytest.raises(TypeError, match="ContextItem"):
        normalize_scripts(["plain text"], tools)  # type: ignore[list-item]
    with pytest.raises(ValueError, match="ur-IN"):
        normalize_scripts([], tools, languages=["ur-IN"])


def test_normalize_scripts_transliterates_only_annotated_romanised_items() -> None:
    tools, fake = _tools()
    roman = "mera naam Rahul hai"
    items = annotate_languages(
        [
            _item("roman", roman),
            _item("native", "मेरा नाम राहुल है"),
            _item("english", "my name is Rahul"),
            _item("required", "kal milte hai", required=True),
            _item("unannotated", "kya hal hai"),
        ][:4],
        tools,
    ) + (_item("unannotated", "kya hal hai"),)
    fake.calls.clear()
    normalized = normalize_scripts(items, tools)
    assert [call[0] for call in fake.calls] == ["transliterate"]
    converted = normalized[0]
    assert converted.item_id == "roman"
    assert converted.content == f"<{roman}>"
    assert converted.token_count == 0
    assert converted.metadata["script_code"] == "Deva"
    assert converted.metadata["transliterated_from"] == "Latn"
    assert (
        converted.metadata["original_content_sha256"]
        == hashlib.sha256(roman.encode("utf-8")).hexdigest()
    )
    assert roman not in str(dict(converted.metadata))
    assert items[0].content == roman  # input item unchanged
    assert normalized[1:] == items[1:]

    with_required = normalize_scripts(items, tools, skip_required=False)
    assert with_required[3].metadata["transliterated_from"] == "Latn"
    tamil_only = normalize_scripts(items, tools, languages=["ta-IN"])
    assert tamil_only == items
    twice = normalize_scripts(normalized, tools)
    assert twice[0] is normalized[0]  # already transliterated: no second call
    mixed = _item(
        "mixed",
        "mera naam",
        metadata={"language_code": "hi-IN", "script_code": "Latn", "language_mixed": True},
    )
    assert normalize_scripts([mixed], tools)[0] is mixed


# --------------------------------------------------------------------------- async parity


def test_async_tools_and_helpers_match_sync_results() -> None:
    sync_tools, _ = _tools()
    async_tools, fake = _async_tools(guard=_guard(max_units=10.0))
    text = "mera naam Rahul hai. " * 60

    async def run() -> Any:
        identified = await async_tools.identify_language(text, max_chunks=2)
        transliterated = await async_tools.transliterate(text, "en-IN", "hi-IN")
        translated = await async_tools.translate("नमस्ते दुनिया", "hi-IN", "en-IN")
        items = await aannotate_languages([_item("r", "mera naam Rahul hai")], async_tools)
        normalized = await anormalize_scripts(items, async_tools)
        return identified, transliterated, translated, items, normalized

    identified, transliterated, translated, items, normalized = asyncio.run(run())
    assert identified == sync_tools.identify_language(text, max_chunks=2)
    assert transliterated == sync_tools.transliterate(text, "en-IN", "hi-IN")
    assert translated == sync_tools.translate("नमस्ते दुनिया", "hi-IN", "en-IN")
    assert items[0].metadata["script_code"] == "Latn"
    assert normalized[0].metadata["transliterated_from"] == "Latn"
    assert async_tools.guard.snapshot()["requests"] == len(fake.calls)

    failing, failing_fake = _async_tools(_AsyncFakeText(error=_Failure(403)), guard=_guard())
    with pytest.raises(SarvamAuthenticationError):
        asyncio.run(failing.identify_language("x"))
    assert failing.guard.snapshot()["units"] == 0
    refused, refused_fake = _async_tools(guard=_guard(max_units=0.00001))
    with pytest.raises(UsageCapExceeded):
        asyncio.run(refused.translate("नमस्ते", "hi-IN", "en-IN"))
    assert refused_fake.calls == []
    with pytest.raises(TypeError):
        asyncio.run(anormalize_scripts([], sync_tools))  # type: ignore[arg-type]


# --------------------------------------------------------------------------- normalization scope


def _roman(item_id: str, kind: ContextKind, role: ContextRole, **kwargs: Any) -> ContextItem:
    return ContextItem(
        item_id=item_id,
        content="mera naam Rahul hai",
        kind=kind,
        role=role,
        metadata={"language_code": "hi-IN", "script_code": "Latn", "language_mixed": False},
        **kwargs,
    )


def test_normalize_scripts_never_rewrites_instructions_or_schemas_by_default() -> None:
    tools, fake = _tools()
    protected = [
        _roman("system", ContextKind.SYSTEM, ContextRole.SYSTEM),
        _roman("developer", ContextKind.DEVELOPER, ContextRole.DEVELOPER),
        _roman("schema", ContextKind.TOOL_SCHEMA, ContextRole.TOOL),
        _roman("assistant", ContextKind.ASSISTANT, ContextRole.ASSISTANT),
        _roman("general", ContextKind.GENERAL, ContextRole.GENERAL),
        # An allowed kind with a trusted role is still not rewritten.
        _roman("user-as-system", ContextKind.USER, ContextRole.SYSTEM),
    ]
    allowed = [
        _roman("user", ContextKind.USER, ContextRole.USER),
        _roman("rag", ContextKind.RAG_DOCUMENT, ContextRole.RAG),
        _roman("memory", ContextKind.MEMORY, ContextRole.RAG),
        _roman("tool-result", ContextKind.TOOL_RESULT, ContextRole.TOOL),
    ]
    result = normalize_scripts(protected + allowed, tools)
    assert result[: len(protected)] == tuple(protected)
    assert all(item is original for item, original in zip(result, protected))
    assert all(
        item.metadata.get("transliterated_from") == "Latn" for item in result[len(protected) :]
    )
    assert len(fake.calls) == len(allowed)


def test_normalize_scripts_kinds_and_roles_are_explicit_and_validated() -> None:
    tools, fake = _tools()
    system = _roman("system", ContextKind.SYSTEM, ContextRole.SYSTEM)
    opted_in = normalize_scripts([system], tools, kinds=["system"], roles=[ContextRole.SYSTEM])
    assert opted_in[0].metadata["transliterated_from"] == "Latn"
    rag = _roman("rag", ContextKind.RAG_DOCUMENT, ContextRole.RAG)
    assert normalize_scripts([rag], tools, kinds=[ContextKind.USER])[0] is rag
    assert len(fake.calls) == 1
    with pytest.raises(ValueError, match="unknown kind"):
        normalize_scripts([rag], tools, kinds=["prompt"])
    with pytest.raises(ValueError, match="unknown role"):
        normalize_scripts([rag], tools, roles=["admin"])
    with pytest.raises(TypeError, match="collection"):
        normalize_scripts([rag], tools, kinds="user")
    async_tools, async_fake = _async_tools()
    converted = asyncio.run(anormalize_scripts([system, rag], async_tools))
    assert converted[0] is system and converted[1].metadata["transliterated_from"] == "Latn"
    assert len(async_fake.calls) == 1


def test_every_text_call_is_sent_without_sdk_retries() -> None:
    tools, fake = _tools(guard=_guard(max_units=10.0))
    tools.identify_language("नमस्ते")
    tools.transliterate("namaste", "en-IN", "hi-IN")
    tools.translate("नमस्ते", "hi-IN", "en-IN")
    assert fake.request_options == [{"max_retries": 0}] * 3
    async_tools, async_fake = _async_tools(guard=_guard(max_units=10.0))
    asyncio.run(async_tools.translate("नमस्ते", "hi-IN", "en-IN"))
    assert async_fake.request_options == [{"max_retries": 0}]
