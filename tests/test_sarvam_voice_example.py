"""Offline checks of examples/sarvam_voice_agent.py with fake Sarvam clients."""

from __future__ import annotations

import base64
import importlib.util
import io
import sys
import wave
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, List, Optional

import pytest

from llmslim.integrations.sarvam import (
    SarvamAuthenticationError,
    SarvamMalformedResponseError,
    SarvamServerError,
    UsageCapExceeded,
    UsageGuard,
    UsageLimits,
)

EXAMPLE = Path(__file__).parents[1] / "examples" / "sarvam_voice_agent.py"


@pytest.fixture(scope="module")
def voice() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sarvam_voice_agent_example", EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def wav_bytes(seconds: float, rate: int = 16_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


def guard(**limits: Any) -> UsageGuard:
    base = {"requests_per_minute": None, "max_requests": None, "max_units": None, "unit": "inr"}
    base.update(limits)
    return UsageGuard(UsageLimits(**base), name="speech-test")


class _Failure(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__("secret body")
        self.status_code = status_code


class FakeSpeech:
    def __init__(
        self, transcript: Any = "नमस्ते, मौसम कैसा है?", error: Optional[BaseException] = None
    ) -> None:
        self.transcript = transcript
        self.error = error
        self.calls: List[dict] = []

    def transcribe(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(transcript=self.transcript, language_code="hi-IN")


class FakeVoice:
    def __init__(self, audios: Any = None) -> None:
        self.audios = audios
        self.calls: List[dict] = []

    def convert(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.audios is not None:
            return SimpleNamespace(audios=self.audios)
        seconds = len(kwargs["text"]) / 1000.0
        return SimpleNamespace(audios=[base64.b64encode(wav_bytes(seconds, 8000)).decode()])


def test_costs_and_durations(voice: ModuleType, tmp_path: Path) -> None:
    assert voice.stt_cost_inr(3600) == pytest.approx(30.0)
    assert voice.tts_cost_inr(10_000) == pytest.approx(30.0)
    clip = tmp_path / "q.wav"
    clip.write_bytes(wav_bytes(1.5))
    assert voice.wav_duration_seconds(str(clip)) == pytest.approx(1.5)
    other = tmp_path / "q.mp3"
    other.write_bytes(b"ID3 not a wav")
    assert voice.wav_duration_seconds(str(other)) is None
    assert voice.DEFAULT_SPEECH_LIMITS.unit == "inr"


def test_transcribe_is_guarded_and_typed(voice: ModuleType, tmp_path: Path) -> None:
    clip = tmp_path / "q.wav"
    clip.write_bytes(wav_bytes(12.0))
    speech_guard = guard(max_units=20.0)
    fake = FakeSpeech()
    client = SimpleNamespace(speech_to_text=fake)
    transcript, language = voice.transcribe(client, speech_guard, str(clip), language_code="hi-IN")
    assert (transcript, language) == ("नमस्ते, मौसम कैसा है?", "hi-IN")
    assert fake.calls[0]["model"] == "saaras:v3"
    assert fake.calls[0]["file"][0] == "q.wav" and fake.calls[0]["file"][2] == "audio/wav"
    assert speech_guard.snapshot()["units"] == pytest.approx(voice.stt_cost_inr(12.0))

    refused = FakeSpeech()
    with pytest.raises(UsageCapExceeded):
        voice.transcribe(
            SimpleNamespace(speech_to_text=refused), guard(max_units=0.0001), str(clip)
        )
    assert refused.calls == []
    long_clip = tmp_path / "long.wav"
    long_clip.write_bytes(wav_bytes(31.0, 8000))
    with pytest.raises(ValueError, match="batch"):
        voice.transcribe(client, guard(), str(long_clip))
    with pytest.raises(ValueError, match="language"):
        voice.transcribe(client, guard(), str(clip), language_code="xx")

    released = guard(max_units=1.0)
    failing = SimpleNamespace(speech_to_text=FakeSpeech(error=_Failure(401)))
    with pytest.raises(SarvamAuthenticationError):
        voice.transcribe(failing, released, str(clip))
    assert released.snapshot()["units"] == 0
    kept = guard(max_units=1.0)
    with pytest.raises(SarvamServerError):
        voice.transcribe(
            SimpleNamespace(speech_to_text=FakeSpeech(error=_Failure(500))), kept, str(clip)
        )
    assert kept.snapshot()["units"] > 0
    with pytest.raises(SarvamMalformedResponseError):
        voice.transcribe(
            SimpleNamespace(speech_to_text=FakeSpeech(transcript=" ")), guard(), str(clip)
        )

    unknown = tmp_path / "q.ogg"
    unknown.write_bytes(b"OggS")
    estimate = guard(max_units=1.0)
    voice.transcribe(client, estimate, str(unknown))
    assert estimate.snapshot()["units"] == pytest.approx(voice.stt_cost_inr(30.0))


def test_plan_and_reply_language(voice: ModuleType) -> None:
    messages = voice.plan_voice_turn(
        [{"role": "assistant", "content": "पिछला उत्तर"}],
        "आज मौसम कैसा है?",
        documents=["Weather: clear skies, 31°C in Jaipur."],
    )
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "आज मौसम कैसा है?" in messages[1]["content"]
    assert voice.reply_language(None, "hi-IN") == "hi-IN"
    assert voice.reply_language(None, "ur-IN") == "en-IN"
    assert voice.reply_language("ta-IN", "hi-IN") == "ta-IN"
    with pytest.raises(ValueError):
        voice.reply_language("ur-IN", None)


def test_synthesize_chunks_merges_and_guards(voice: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "answer.wav"
    speech_guard = guard(max_units=20.0)
    fake = FakeVoice()
    text = "यह उत्तर का एक वाक्य है। " * 120  # about 3,000 characters
    written = voice.synthesize(
        SimpleNamespace(text_to_speech=fake), speech_guard, text, "hi-IN", str(out), speaker="shubh"
    )
    assert len(fake.calls) == 2
    assert all(len(call["text"]) <= 2500 for call in fake.calls)
    assert fake.calls[0]["model"] == "bulbul:v3" and fake.calls[0]["speaker"] == "shubh"
    assert out.stat().st_size == written
    with wave.open(str(out), "rb") as merged:
        assert merged.getframerate() == 8000
        sent = sum(len(call["text"]) for call in fake.calls)
        assert merged.getnframes() == pytest.approx(sent * 8, abs=2)
    assert speech_guard.snapshot()["units"] == pytest.approx(voice.tts_cost_inr(sent))

    blocked = FakeVoice()
    with pytest.raises(UsageCapExceeded, match="INR"):
        voice.synthesize(
            SimpleNamespace(text_to_speech=blocked), guard(max_units=0.001), text, "hi-IN", str(out)
        )
    with pytest.raises(UsageCapExceeded, match="2 requests"):
        voice.synthesize(
            SimpleNamespace(text_to_speech=blocked), guard(max_requests=1), text, "hi-IN", str(out)
        )
    assert blocked.calls == []
    with pytest.raises(ValueError, match="cannot speak"):
        voice.synthesize(SimpleNamespace(text_to_speech=fake), guard(), "hi", "ur-IN", str(out))
    with pytest.raises(ValueError, match="nothing"):
        voice.synthesize(SimpleNamespace(text_to_speech=fake), guard(), "   ", "hi-IN", str(out))
    with pytest.raises(SarvamMalformedResponseError):
        voice.synthesize(
            SimpleNamespace(text_to_speech=FakeVoice(audios=[])), guard(), "hi", "hi-IN", str(out)
        )


def test_merge_wav_rejects_mixed_formats(voice: ModuleType) -> None:
    with pytest.raises(ValueError, match="no audio"):
        voice.merge_wav([])
    with pytest.raises(ValueError, match="different"):
        voice.merge_wav([wav_bytes(0.1, 8000), wav_bytes(0.1, 16_000)])


def test_main_refuses_without_a_key_or_audio(
    voice: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Any
) -> None:
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert voice.main([str(tmp_path / "q.wav")]) == 2
    assert "SARVAM_API_KEY" in capsys.readouterr().err
    monkeypatch.setenv("SARVAM_API_KEY", "test-only")
    assert voice.main([str(tmp_path / "missing.wav")]) == 2
    assert "not found" in capsys.readouterr().err
