"""Offline tests for the secondary-reader live benchmark. No network: fake SDK clients and
httpx mock transports only."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from benchmarks import live_secondary_reader as live
from benchmarks.live_secondary_report import (
    main as report_main,
)
from benchmarks.live_secondary_report import (
    paired_bootstrap_ci,
    render_markdown,
)
from benchmarks.v06_answer_scorer import (
    contains_item,
    expected_items,
    normalize,
    score_answer,
    score_text,
)
from benchmarks.v06_planner import load_cases
from llmslim.integrations._guard import UsageGuard, UsageLimits
from llmslim.planning.models import ModelProfile
from llmslim.planning.profiles import ModelProfileRegistry
from llmslim.tokens import count_tokens

SARVAM_LABEL = "Secondary reader: Sarvam 105B — headline results use Claude Haiku 5.5"
NEBIUS_KEY = "nb-test-key-must-never-leak-123"
SARVAM_KEY = "sv-test-key-must-never-leak-456"

TINY_CASES: List[Dict[str, Any]] = [
    {
        "id": "hi-fit",
        "category": "multilingual",
        "language": "Hindi",
        "budget": 400,
        "query": "ग्राहक भुगतान स्थिति",
        "documents": ["ग्राहक ID GRAHAK-17 का भुगतान 18 सितंबर 2026 को पूरा हुआ। कुल राशि ₹45,600 थी।"],
        "expected_facts": ["GRAHAK-17", "18 सितंबर 2026", "₹45,600"],
    },
    {
        "id": "chat-bind",
        "category": "chat",
        "language": "English",
        "budget": 520,
        "history_turns": 20,
        "early_fact": "Project ORBIT-771 uses region ap-south-1 and deadline 30 November 2026.",
        "query": "Which region and deadline belong to ORBIT-771?",
        "expected_facts": ["ORBIT-771", "ap-south-1", "30 November 2026"],
        "required_instructions": ["Never invent a project detail"],
    },
    {
        "id": "tools-over",
        "category": "tools",
        "language": "English",
        "budget": 300,
        "tool_count": 12,
        "boundary_tool": True,
        "query": "use tool_011_boundary_target",
        "expected_tools": ["tool_011_boundary_target"],
    },
]


def _write_dataset(path: Path, cases: List[Dict[str, Any]], **extra: Any) -> Path:
    payload = {"schema_version": "1.0", "name": "tiny", "cases": cases, **extra}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def tiny_dataset(tmp_path: Path) -> Path:
    return _write_dataset(tmp_path / "tiny.json", TINY_CASES)


def _echo_context(messages: List[Dict[str, str]]) -> str:
    """A 'perfect' fake reader: answers with the evidence it was given, tags removed."""

    user = messages[-1]["content"]
    context = user.split("\n\nQuestion:", 1)[0]
    return re.sub(r"<[^>]+>", " ", context)


class FakeSarvamSDK:
    """Stands in for ``sarvamai.SarvamAI``: ``client.chat.completions(**kwargs)``."""

    def __init__(
        self,
        *,
        usage: Optional[Dict[str, Any]] = None,
        no_usage: bool = False,
        content: Optional[str] = None,
        errors: Optional[List[Exception]] = None,
    ) -> None:
        self.chat = self
        self.requests: List[Dict[str, Any]] = []
        self._usage = usage or {"prompt_tokens": 1000, "completion_tokens": 40, "cached": 200}
        self._no_usage = no_usage
        self._content = content
        self._errors = list(errors or [])

    def completions(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        if self._errors:
            raise self._errors.pop(0)
        content = self._content if self._content is not None else _echo_context(kwargs["messages"])
        usage = None
        if not self._no_usage:
            cached = self._usage.get("cached")
            usage = SimpleNamespace(
                prompt_tokens=self._usage["prompt_tokens"],
                completion_tokens=self._usage["completion_tokens"],
                total_tokens=self._usage["prompt_tokens"] + self._usage["completion_tokens"],
                prompt_tokens_details=(
                    None if cached is None else SimpleNamespace(cached_tokens=cached)
                ),
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=usage
        )


class UnauthorizedError(Exception):
    pass


class ServerTimeoutError(Exception):
    pass


def _priced_registry(**overrides: Any) -> ModelProfileRegistry:
    values: Dict[str, Any] = {
        "model_id": "sarvam-105b",
        "provider": "sarvam",
        "context_window": 131_072,
        "input_cost_per_million": 15.0,
        "cached_input_cost_per_million": 5.0,
        "output_cost_per_million": 60.0,
        "currency": "INR",
        "pricing_as_of": "2026-10-12",
        "source": "https://docs.sarvam.ai/api/getting-started/pricing",
    }
    values.update(overrides)
    return ModelProfileRegistry([ModelProfile(**values)])


def _sarvam_reader(sdk: FakeSarvamSDK) -> live.SarvamReader:
    return live.SarvamReader(sdk, registry=_priced_registry())


def _sarvam_guard(**limits: Any) -> UsageGuard:
    base: Dict[str, Any] = {
        "requests_per_minute": None,
        "max_requests": 200,
        "max_units": 3000.0,
        "unit": "inr",
    }
    base.update(limits)
    return UsageGuard(UsageLimits(**base), name="sarvam_bench")


def _run(reader: Any, guard: UsageGuard, dataset: Path, tmp_path: Path, **kwargs: Any):
    output = tmp_path / "live-test.json"
    result = live.run_suite(
        reader,
        guard,
        output_path=output,
        report_path=tmp_path / "live-test.md",
        dataset_path=dataset,
        log=lambda *_: None,
        **kwargs,
    )
    return result, output


# --------------------------------------------------------------------------- scorer


@pytest.mark.parametrize(
    ("answer", "item"),
    [
        ("ग्राहक GRAHAK-17 का भुगतान १८ सितंबर २०२६ को हुआ।", "18 सितंबर 2026"),  # Devanagari digits
        ("ऑर्डर MR-88 पाठवली आहे; तारीख 21 सप्टेंबर 2026.", "२१ सप्टेंबर २०२६"),  # Marathi
        ("চুক্তি BNG-204 অনুমোদিত; শেষ তারিখ 30 নভেম্বর 2026।", "৩০ নভেম্বর ২০২৬"),  # Bengali
        ("விநியோகம் TN-77 நிறைவடைந்தது, மாலை 6:15 IST.", "நிறைவடைந்தது"),  # Tamil
        ("టికెట్ TG-63 పరిష్కరించబడింది; కోడ్ ౮౮౪౨౧.", "88421"),  # Telugu digits
        ("ઇન્વૉઇસ GJ-51 ચૂકવાઈ ગયું છે, રકમ ₹ 31,250.", "₹31,250"),  # Gujarati, spaced rupee
        ("ഭാഗം: അപേക്ഷ ML-314 അം\u200dഗീകരിച്ചു.", "അംഗീകരിച്ചു"),  # zero-width joiner
        ("भुगतान 18 सितम्बर 2026 को हुआ", "18 सितंबर 2026"),  # anusvara spelling variant
    ],
)
def test_scorer_matches_indic_scripts_and_variants(answer: str, item: str) -> None:
    assert score_text(answer, [item])["all_found"] is True


def test_scorer_handles_hinglish_and_currency_forms() -> None:
    case = {
        "id": "hinglish",
        "expected_facts": ["CUST-HI-8", "19 September", "₹72,300"],
    }
    answer = (
        "Customer **CUST-HI-8** ka payment 19 September ko complete hua; amount Rs. 72,300 hai."
    )
    assert score_answer(answer, case) == {
        "score": 1.0,
        "all_found": True,
        "found": ["CUST-HI-8", "19 September", "₹72,300"],
        "missing": [],
    }
    assert score_text("INR 87,50,000 approved", ["8,750,000"])["all_found"] is True
    partial = score_answer("CUST-HI-8 ka payment ho gaya", case)
    assert partial["score"] == pytest.approx(1 / 3)
    assert partial["missing"] == ["19 September", "₹72,300"]


def test_scorer_rejects_ascii_prefix_and_suffix_collisions() -> None:
    assert contains_item(normalize("invoice GJ-512 paid"), normalize("GJ-51")) is False
    assert contains_item(normalize("code 188421"), normalize("88421")) is False
    assert contains_item(normalize("code 88421."), normalize("88421")) is True
    assert contains_item(normalize("status: GREEN"), normalize("green")) is True
    assert contains_item("anything", "") is True
    # Indic suffixes are not boundaries: an inflected form still matches.
    assert score_text("ऑर्डर पाठवलीत", ["पाठवली"])["all_found"] is True


def test_scorer_requires_known_answers() -> None:
    with pytest.raises(ValueError):
        expected_items({"id": "empty"})
    with pytest.raises(ValueError):
        score_text("text", [])
    assert expected_items({"expected_facts": ["a"], "expected_tools": ["t"]}) == ["a", "t"]


# --------------------------------------------------------------------------- equal budget


def test_equal_budget_and_scorer_hold_on_the_frozen_suite() -> None:
    """Every arm respects the equal budget, and every fact is found in its own full context
    (the normalization never breaks a match against the text a fact came from)."""

    infeasible = []
    for case in load_cases():
        prepared = live.prepare_case(case)
        assert score_text(prepared.contexts["full"] or "", prepared.items)["score"] == 1.0
        tokens = prepared.context_tokens
        assert tokens["truncate"] is not None
        assert tokens["truncate"] <= prepared.equal_budget
        if prepared.contexts["llmslim"] is None:
            infeasible.append(case["id"])
            assert prepared.equal_budget == prepared.budget
        else:
            assert tokens["llmslim"] is not None
            assert tokens["llmslim"] <= prepared.budget
            assert prepared.equal_budget == tokens["llmslim"]
    assert infeasible == ["tools-large-overflow"]


def test_enforce_equal_budget_refuses_oversized_contexts() -> None:
    prepared = live.prepare_case(TINY_CASES[0])
    prepared.context_tokens["llmslim"] = prepared.budget + 1
    with pytest.raises(live.BudgetViolation):
        live.enforce_equal_budget(prepared)
    prepared = live.prepare_case(TINY_CASES[0])
    prepared.context_tokens["truncate"] = prepared.equal_budget + 1
    with pytest.raises(live.BudgetViolation):
        live.enforce_equal_budget(prepared)


def test_over_budget_plan_is_never_sent_and_scores_zero(tiny_dataset: Path, tmp_path: Path) -> None:
    sdk = FakeSarvamSDK()
    result, _ = _run(_sarvam_reader(sdk), _sarvam_guard(), tiny_dataset, tmp_path)
    assert result["complete"] is True
    over = next(case for case in result["cases"] if case["id"] == "tools-over")
    assert over["arms"]["llmslim"]["status"] == "over_budget"
    assert over["arms"]["llmslim"]["score"] == 0.0
    assert over["arms"]["llmslim"]["billed"] is False
    budget = over["budget_tokens"]
    tool_requests = [
        request
        for request in sdk.requests
        if "use tool_011_boundary_target" in request["messages"][-1]["content"]
    ]
    assert len(tool_requests) == 2  # full (the reference) and truncate; never LLMSlim
    sent = sorted(
        count_tokens(request["messages"][-1]["content"].split("\n\nQuestion:", 1)[0][9:])
        for request in tool_requests
    )
    assert sent[0] <= budget < sent[1]


def test_identical_prompts_are_sent_once_and_shared(tiny_dataset: Path, tmp_path: Path) -> None:
    sdk = FakeSarvamSDK()
    result, _ = _run(_sarvam_reader(sdk), _sarvam_guard(), tiny_dataset, tmp_path)
    by_id = {case["id"]: case for case in result["cases"]}
    fit = by_id["hi-fit"]
    assert fit["budget_binds"] is False
    assert fit["arms"]["llmslim"]["reused_from"] == "full"
    assert fit["arms"]["truncate"]["reused_from"] == "full"
    assert fit["arms"]["llmslim"]["billed"] is False
    assert fit["arms"]["llmslim"]["cost"] == fit["arms"]["full"]["cost"]
    assert by_id["chat-bind"]["budget_binds"] is True
    # hi-fit: 1 call; chat-bind: full + llmslim + truncate (truncate differs from LLMSlim);
    # tools-over: full + truncate.
    assert len(sdk.requests) == result["totals"]["billed_calls"]
    assert all(request["max_tokens"] == live.DEFAULT_MAX_OUTPUT_TOKENS for request in sdk.requests)
    assert all(request["model"] == "sarvam-105b" for request in sdk.requests)


# --------------------------------------------------------------------------- guard, caps, settle


def test_pricing_cost_math() -> None:
    pricing = live.SARVAM_FALLBACK_PRICING
    assert pricing.cost(1_000_000, 0) == pytest.approx(15.0)
    assert pricing.cost(0, 1_000_000) == pytest.approx(60.0)
    assert pricing.cost(1000, 200, 400) == pytest.approx((600 * 15 + 400 * 5 + 200 * 60) / 1e6)
    assert pricing.cost(100, 0, 500) == pytest.approx(100 * 5 / 1e6)  # cached clamps to prompt


def test_reservation_is_a_worst_case_upper_bound() -> None:
    messages = live.build_messages({"query": "q"}, "ग्राहक GRAHAK-17")
    estimate = live.reservation_estimate(messages, 64, live.SARVAM_FALLBACK_PRICING)
    prompt_bytes = sum(len(m["content"].encode("utf-8")) for m in messages)
    assert estimate >= live.SARVAM_FALLBACK_PRICING.cost(prompt_bytes, 64)
    assert estimate == pytest.approx(
        live.SARVAM_FALLBACK_PRICING.cost(
            prompt_bytes + live.MESSAGE_OVERHEAD_TOKENS * len(messages), 64
        )
    )


def test_settle_replaces_reservations_with_reported_cost(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    sdk = FakeSarvamSDK(usage={"prompt_tokens": 900, "completion_tokens": 30, "cached": 100})
    guard = _sarvam_guard()
    result, _ = _run(_sarvam_reader(sdk), guard, tiny_dataset, tmp_path)
    per_call = (800 * 15 + 100 * 5 + 30 * 60) / 1e6
    calls = result["totals"]["billed_calls"]
    assert guard.snapshot()["units"] == pytest.approx(per_call * calls)
    assert result["totals"]["cost_reported"] == pytest.approx(per_call * calls)
    assert result["totals"]["cached_tokens"] == 100 * calls
    for case in result["cases"]:
        for entry in case["arms"].values():
            if entry.get("billed"):
                assert entry["reserved"] > entry["cost"]


def test_unreported_usage_keeps_the_conservative_reservation(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    guard = _sarvam_guard()
    result, _ = _run(
        _sarvam_reader(FakeSarvamSDK(no_usage=True)), guard, tiny_dataset, tmp_path, limit=1
    )
    reserved = result["cases"][0]["arms"]["full"]["reserved"]
    assert result["cases"][0]["arms"]["full"]["cost"] is None
    assert guard.snapshot()["units"] == pytest.approx(reserved, abs=1e-6)
    assert result["totals"]["cost_reserved_without_usage"] == pytest.approx(reserved, abs=1e-6)


def test_cap_refusal_happens_before_any_call_and_writes_partial_results(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    sdk = FakeSarvamSDK()
    guard = _sarvam_guard(max_units=0.000001)
    result, output = _run(_sarvam_reader(sdk), guard, tiny_dataset, tmp_path)
    assert sdk.requests == []
    assert result["complete"] is False
    assert "usage cap" in result["stop_reason"]
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["complete"] is False
    assert saved["cases"][0]["arms"]["full"]["status"] == "not_run"
    assert saved["totals"]["billed_calls"] == 0
    report = (tmp_path / "live-test.md").read_text(encoding="utf-8")
    assert "INCOMPLETE RUN" in report
    assert SARVAM_LABEL in report


def test_request_cap_stops_mid_run_with_partial_results(tiny_dataset: Path, tmp_path: Path) -> None:
    sdk = FakeSarvamSDK()
    result, output = _run(
        _sarvam_reader(sdk), _sarvam_guard(max_requests=2), tiny_dataset, tmp_path
    )
    assert len(sdk.requests) == 2
    assert result["complete"] is False
    assert "request cap" in result["stop_reason"]
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert [case["id"] for case in saved["cases"]] == ["hi-fit", "chat-bind"]
    assert saved["cases"][0]["complete"] is True
    assert saved["cases"][1]["complete"] is False


def test_rate_limit_waits_explicitly_then_continues(tiny_dataset: Path, tmp_path: Path) -> None:
    clock = SimpleNamespace(now=100.0)
    guard = UsageGuard(
        UsageLimits(requests_per_minute=1, max_requests=50, max_units=3000.0, unit="inr"),
        name="sarvam_bench",
        clock=lambda: clock.now,
    )
    waits: List[float] = []

    def fake_sleep(seconds: float) -> None:
        waits.append(seconds)
        clock.now += seconds

    sdk = FakeSarvamSDK()
    result, _ = _run(_sarvam_reader(sdk), guard, tiny_dataset, tmp_path, limit=2, sleep=fake_sleep)
    assert result["complete"] is True
    assert len(waits) == len(sdk.requests) - 1
    assert all(wait > 0 for wait in waits)


def test_auth_error_stops_the_run_and_releases_the_reservation(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    sdk = FakeSarvamSDK(errors=[UnauthorizedError("bad key " + SARVAM_KEY)])
    guard = _sarvam_guard()
    result, output = _run(_sarvam_reader(sdk), guard, tiny_dataset, tmp_path)
    assert len(sdk.requests) == 1
    assert "authentication failed" in result["stop_reason"]
    assert guard.snapshot()["units"] == 0.0
    assert SARVAM_KEY not in output.read_text(encoding="utf-8")


def test_failed_call_is_not_shared_and_is_excluded_from_pairs(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    sdk = FakeSarvamSDK(errors=[ServerTimeoutError("slow")])
    result, _ = _run(_sarvam_reader(sdk), _sarvam_guard(), tiny_dataset, tmp_path, limit=1)
    arms = result["cases"][0]["arms"]
    assert arms["full"]["status"] == "error"
    assert arms["full"]["error"] == "Sarvam request timed out"
    assert arms["llmslim"]["reused_from"] is None  # identical prompt, but sent again
    assert arms["llmslim"]["status"] == "answered"
    report = render_markdown(result)
    assert "Not in the table" in report
    assert "Failed calls (excluded from the comparison)" in report


def test_cost_above_the_worst_case_reservation_stops_the_run(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    sdk = FakeSarvamSDK(usage={"prompt_tokens": 10_000_000, "completion_tokens": 1, "cached": None})
    result, _ = _run(_sarvam_reader(sdk), _sarvam_guard(), tiny_dataset, tmp_path)
    assert len(sdk.requests) == 1
    assert result["complete"] is False
    assert "exceeded the worst-case reservation" in result["stop_reason"]


def test_run_suite_validates_arms_currency_and_output_limit(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    reader = _sarvam_reader(FakeSarvamSDK())
    with pytest.raises(ValueError, match="full-context arm"):
        _run(reader, _sarvam_guard(), tiny_dataset, tmp_path, arms=("llmslim",))
    with pytest.raises(ValueError, match="subset"):
        _run(reader, _sarvam_guard(), tiny_dataset, tmp_path, arms=("full", "bogus"))
    with pytest.raises(ValueError, match="does not match"):
        _run(reader, _sarvam_guard(unit="usd"), tiny_dataset, tmp_path)
    with pytest.raises(ValueError, match="positive"):
        _run(reader, _sarvam_guard(), tiny_dataset, tmp_path, max_output_tokens=0)


# --------------------------------------------------------------------------- Sarvam reader


def test_sarvam_reader_goes_through_sarvam_provider_and_reports_cached_tokens() -> None:
    sdk = FakeSarvamSDK(usage={"prompt_tokens": 120, "completion_tokens": 9, "cached": 20})
    reader = _sarvam_reader(sdk)
    result = reader.answer([{"role": "user", "content": "Context:\nx\n\nQuestion: y"}], 77)
    assert (result.prompt_tokens, result.completion_tokens, result.cached_tokens) == (120, 9, 20)
    request = sdk.requests[0]
    assert request["max_tokens"] == 77
    assert request["reasoning_effort"] == "low"
    assert request["stream"] is False
    assert reader.pricing.origin == "llmslim.planning.profiles"
    assert reader.label == SARVAM_LABEL
    assert reader.describe()["role"] == "secondary"
    assert "credentials=<redacted>" in repr(reader)


def test_sarvam_reader_reports_no_usage_when_the_provider_returns_none() -> None:
    reader = _sarvam_reader(FakeSarvamSDK(no_usage=True))
    result = reader.answer([{"role": "user", "content": "hello"}], 8)
    assert result.usage_reported is False
    assert reader._usage() == (None, None, None)


def test_sarvam_reader_maps_empty_answers_and_errors() -> None:
    reader = _sarvam_reader(FakeSarvamSDK(content="   "))
    with pytest.raises(live.ReaderEmptyAnswer) as empty:
        reader.answer([{"role": "user", "content": "q"}], 8)
    assert empty.value.result is not None and empty.value.result.prompt_tokens == 1000
    reader = _sarvam_reader(FakeSarvamSDK(errors=[UnauthorizedError("x")]))
    with pytest.raises(live.ReaderAuthError):
        reader.answer([{"role": "user", "content": "q"}], 8)
    reader = _sarvam_reader(FakeSarvamSDK(errors=[RuntimeError("boom")]))
    with pytest.raises(live.ReaderError, match="Sarvam request failed"):
        reader.answer([{"role": "user", "content": "q"}], 8)


def test_sarvam_prices_come_from_the_profile_registry() -> None:
    pricing, notes = live.sarvam_pricing("sarvam-105b", _priced_registry())
    assert (pricing.input_per_million, pricing.cached_input_per_million) == (15.0, 5.0)
    assert pricing.output_per_million == 60.0 and pricing.as_of == "2026-10-12"
    assert pricing.origin == "llmslim.planning.profiles" and notes == []

    default_profile = ModelProfileRegistry().require("sarvam-105b")
    default_pricing, _ = live.sarvam_pricing("sarvam-105b")
    assert default_pricing.input_per_million == default_profile.input_cost_per_million
    assert default_pricing.output_per_million == default_profile.output_cost_per_million

    stale, stale_notes = live.sarvam_pricing(
        "sarvam-105b", _priced_registry(pricing_as_of="2026-09-18")
    )
    assert stale.as_of == "2026-09-18" and "older" in stale_notes[0]

    fallback, fallback_notes = live.sarvam_pricing(
        "sarvam-105b", _priced_registry(output_cost_per_million=None)
    )
    assert fallback is live.SARVAM_FALLBACK_PRICING and "no complete price" in fallback_notes[0]
    missing, _ = live.sarvam_pricing("no-such-model", ModelProfileRegistry())
    assert missing is live.SARVAM_FALLBACK_PRICING


def test_sarvam_from_env_requires_the_key() -> None:
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        live.SarvamReader.from_env({})


# --------------------------------------------------------------------------- Nebius reader


def _nebius_pricing() -> live.Pricing:
    pricing = live.nebius_pricing(0.13, 0.40, None)
    assert pricing is not None
    return pricing


def _nebius_reader(handler: Any) -> live.NebiusReader:
    httpx = pytest.importorskip("httpx")
    return live.NebiusReader(
        NEBIUS_KEY,
        "meta-llama/Llama-3.3-70B-Instruct",
        pricing=_nebius_pricing(),
        transport=httpx.MockTransport(handler),
    )


def test_nebius_request_shape_and_no_key_leakage() -> None:
    httpx = pytest.importorskip("httpx")
    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "REL-600"}}],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 4,
                    "total_tokens": 54,
                    "prompt_tokens_details": {"cached_tokens": 10},
                },
            },
        )

    reader = _nebius_reader(handler)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Context:\nREL-600\n\nQuestion: id?"},
    ]
    result = reader.answer(messages, 64)
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.tokenfactory.nebius.com/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {NEBIUS_KEY}"
    assert json.loads(request.content) == {
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "messages": messages,
        "max_tokens": 64,
    }
    assert (result.text, result.prompt_tokens, result.completion_tokens) == ("REL-600", 50, 4)
    assert result.cached_tokens == 10
    assert NEBIUS_KEY not in repr(reader)
    assert NEBIUS_KEY not in json.dumps(reader.describe())
    assert reader.label == (
        "Secondary reader: meta-llama/Llama-3.3-70B-Instruct on Nebius Token Factory — "
        "headline results use Claude Haiku 5.5"
    )
    reader.close()


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        ({"status": 401, "json": {"error": "bad"}}, live.ReaderAuthError, "HTTP 401"),
        ({"status": 429, "json": {}}, live.ReaderError, "HTTP 429"),
        ({"status": 500, "json": {}}, live.ReaderError, "HTTP 500"),
        ({"status": 200, "text": "not json"}, live.ReaderError, "non-JSON"),
        ({"status": 200, "json": {"choices": []}}, live.ReaderEmptyAnswer, "no answer"),
    ],
)
def test_nebius_errors_are_sanitized(response: Dict[str, Any], error: type, message: str) -> None:
    httpx = pytest.importorskip("httpx")

    def handler(request: Any) -> Any:
        if "json" in response:
            return httpx.Response(response["status"], json=response["json"])
        return httpx.Response(response["status"], text=response["text"])

    reader = _nebius_reader(handler)
    with pytest.raises(error, match=message) as info:
        reader.answer([{"role": "user", "content": "q"}], 32)
    assert NEBIUS_KEY not in str(info.value)


@pytest.mark.parametrize("failure", ["timeout", "connect"])
def test_nebius_transport_failures_are_sanitized(failure: str) -> None:
    httpx = pytest.importorskip("httpx")

    def handler(request: Any) -> Any:
        if failure == "timeout":
            raise httpx.ReadTimeout("timed out " + NEBIUS_KEY, request=request)
        raise httpx.ConnectError("refused " + NEBIUS_KEY, request=request)

    reader = _nebius_reader(handler)
    with pytest.raises(live.ReaderError) as info:
        reader.answer([{"role": "user", "content": "q"}], 32)
    assert NEBIUS_KEY not in str(info.value)


def test_nebius_refuses_more_than_64_output_tokens_before_any_request() -> None:
    httpx = pytest.importorskip("httpx")
    seen: List[Any] = []
    reader = _nebius_reader(lambda request: seen.append(request) or httpx.Response(200, json={}))
    for bad in (65, 1024, 0):
        with pytest.raises(ValueError, match="64 output tokens"):
            reader.answer([{"role": "user", "content": "q"}], bad)
    assert seen == []
    with pytest.raises(ValueError, match="64 output tokens"):
        live.resolve_max_output_tokens("nebius", 65)
    assert live.resolve_max_output_tokens("nebius", None) == 64
    assert live.resolve_max_output_tokens("sarvam", None) == live.DEFAULT_MAX_OUTPUT_TOKENS
    with pytest.raises(ValueError, match="positive"):
        live.resolve_max_output_tokens("sarvam", 0)


def test_run_suite_refuses_an_output_limit_above_the_readers_cap(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    httpx = pytest.importorskip("httpx")
    seen: List[Any] = []
    reader = _nebius_reader(lambda request: seen.append(request) or httpx.Response(200, json={}))
    guard = live.build_guard("nebius", {})
    with pytest.raises(ValueError, match="limited to 64"):
        _run(reader, guard, tiny_dataset, tmp_path, max_output_tokens=128)
    assert seen == []


@pytest.mark.parametrize(
    ("prices", "message"),
    [
        ((None, None, None), "needs the model's price"),
        ((0.13, None, None), "pass both"),
        ((None, 0.40, None), "pass both"),
        ((0.0, 0.40, None), "positive"),
        ((0.13, -1.0, None), "positive"),
        ((float("nan"), 0.40, None), "positive"),
        ((0.13, 0.40, -0.1), "non-negative"),
    ],
)
def test_nebius_refuses_without_a_known_price(prices: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        live.validate_nebius_pricing(live.nebius_pricing(*prices))


def test_nebius_pricing_from_the_command_line() -> None:
    pricing = _nebius_pricing()
    assert pricing.currency == "USD" and pricing.origin == "command-line"
    assert pricing.cached_input_per_million == 0.13  # defaults to the input price
    cheaper_cache = live.nebius_pricing(0.13, 0.40, 0.05)
    assert cheaper_cache is not None and cheaper_cache.cached_input_per_million == 0.05
    with pytest.raises(ValueError, match="USD"):
        live.validate_nebius_pricing(live.SARVAM_FALLBACK_PRICING)
    with pytest.raises(ValueError, match="needs the model's price"):
        live.NebiusReader(NEBIUS_KEY, "model", pricing=None)
    with pytest.raises(ValueError, match="NEBIUS_API_KEY"):
        live.NebiusReader("", "model", pricing=pricing)
    with pytest.raises(ValueError, match="model is required"):
        live.NebiusReader(NEBIUS_KEY, " ", pricing=pricing)


def test_nebius_guard_defaults_are_ten_requests_and_ten_cents() -> None:
    guard = live.build_guard("nebius", {})
    assert guard.limits == UsageLimits(
        requests_per_minute=10, max_requests=10, max_units=0.10, unit="usd"
    )
    assert guard.name == "nebius_bench"
    sarvam = live.build_guard("sarvam", {"LLMSLIM_SARVAM_BENCH_MAX_UNITS": "50"})
    assert sarvam.limits.max_units == 50.0 and sarvam.limits.unit == "inr"
    assert live.build_guard("sarvam", {}).limits == live.SARVAM_GUARD_DEFAULTS


def test_nebius_cap_refuses_a_reservation_that_would_exceed_ten_cents(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    httpx = pytest.importorskip("httpx")
    seen: List[Any] = []
    reader = live.NebiusReader(
        NEBIUS_KEY,
        "some-model",
        pricing=live.nebius_pricing(500.0, 500.0, None),  # absurd price: one call > $0.10
        transport=httpx.MockTransport(
            lambda request: seen.append(request) or httpx.Response(200, json={})
        ),
    )
    result, output = _run(
        reader, live.build_guard("nebius", {}), tiny_dataset, tmp_path, max_output_tokens=64
    )
    assert seen == []
    assert result["complete"] is False and "usage cap of 0.1 usd" in result["stop_reason"]
    assert NEBIUS_KEY not in output.read_text(encoding="utf-8")


def test_nebius_run_stops_after_ten_requests(tmp_path: Path) -> None:
    httpx = pytest.importorskip("httpx")
    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "answer"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 5},
            },
        )

    cases = [dict(TINY_CASES[1], id=f"chat-bind-{index}") for index in range(5)]
    dataset = _write_dataset(tmp_path / "five.json", cases)
    reader = live.NebiusReader(
        NEBIUS_KEY, "some-model", pricing=_nebius_pricing(), transport=httpx.MockTransport(handler)
    )
    clock = SimpleNamespace(now=0.0)
    guard = UsageGuard(live.NEBIUS_GUARD_DEFAULTS, name="nebius_bench", clock=lambda: clock.now)

    def fake_sleep(seconds: float) -> None:
        clock.now += seconds

    result, output = _run(reader, guard, dataset, tmp_path, max_output_tokens=64, sleep=fake_sleep)
    assert len(seen) == 10
    assert all(json.loads(request.content)["max_tokens"] <= 64 for request in seen)
    assert result["complete"] is False and "request cap of 10" in result["stop_reason"]
    assert guard.snapshot()["units"] <= 0.10
    assert NEBIUS_KEY not in output.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- opt-in gates


def _refuse(**_: Any) -> Any:
    raise AssertionError("the reader must not be built when the run is refused")


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"SARVAM_API_KEY": SARVAM_KEY},
        {"LLMSLIM_RUN_LIVE_SARVAM": "1"},
        {"LLMSLIM_RUN_LIVE_SARVAM": "true", "SARVAM_API_KEY": SARVAM_KEY},
    ],
)
def test_sarvam_run_requires_flag_and_key(env: Dict[str, str], tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        live.main(
            ["--reader", "sarvam", "--output", str(tmp_path / "x.json")],
            env=env,
            reader_factory=lambda *_: _refuse(),
        )
    assert not (tmp_path / "x.json").exists()


NEBIUS_PRICE_ARGS = ["--price-input", "0.13", "--price-output", "0.40"]


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({}, "off by default"),
        ({"NEBIUS_API_KEY": NEBIUS_KEY, "NEBIUS_MODEL": "m"}, "LLMSLIM_NEBIUS_ALLOW_LIVE"),
        # No other live flag unlocks Nebius.
        (
            {
                "NEBIUS_API_KEY": NEBIUS_KEY,
                "LLMSLIM_RUN_LIVE_SARVAM": "1",
                "LLMSLIM_RUN_LIVE_NEBIUS": "1",
                "LLMSLIM_RUN_LIVE_V07": "1",
            },
            "LLMSLIM_NEBIUS_ALLOW_LIVE",
        ),
        ({"LLMSLIM_NEBIUS_ALLOW_LIVE": "yes", "NEBIUS_API_KEY": NEBIUS_KEY}, "off by default"),
        ({"LLMSLIM_NEBIUS_ALLOW_LIVE": "1"}, "NEBIUS_API_KEY"),
    ],
)
def test_nebius_run_requires_its_own_flag_and_key(
    env: Dict[str, str], message: str, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match=message):
        live.main(
            ["--reader", "nebius", "--model", "m", *NEBIUS_PRICE_ARGS],
            env=env,
            reader_factory=lambda *_: _refuse(),
        )
    with pytest.raises(RuntimeError, match=message):
        live.NebiusReader.from_env(env, model="m", pricing=_nebius_pricing())


def test_nebius_run_refuses_missing_price_model_or_large_output_before_any_request(
    tmp_path: Path,
) -> None:
    env = {"LLMSLIM_NEBIUS_ALLOW_LIVE": "1", "NEBIUS_API_KEY": NEBIUS_KEY}
    with pytest.raises(ValueError, match="needs the model's price"):
        live.main(
            ["--reader", "nebius", "--model", "m"], env=env, reader_factory=lambda *_: _refuse()
        )
    with pytest.raises(ValueError, match="pass both"):
        live.main(
            ["--reader", "nebius", "--model", "m", "--price-input", "0.1"],
            env=env,
            reader_factory=lambda *_: _refuse(),
        )
    with pytest.raises(ValueError, match="64 output tokens"):
        live.main(
            ["--reader", "nebius", "--model", "m", *NEBIUS_PRICE_ARGS, "--max-output-tokens", "65"],
            env=env,
            reader_factory=lambda *_: _refuse(),
        )
    with pytest.raises(RuntimeError, match="NEBIUS_MODEL"):
        live.NebiusReader.from_env(env, model=None, pricing=_nebius_pricing())
    with pytest.raises(ValueError, match="needs the model's price"):
        live.NebiusReader.from_env(dict(env, NEBIUS_MODEL="m"), model=None, pricing=None)
    assert list(tmp_path.iterdir()) == []


def test_nebius_main_end_to_end_with_a_mock_transport(tmp_path: Path) -> None:
    httpx = pytest.importorskip("httpx")
    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "REL-600"}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 3},
            },
        )

    dataset = _write_dataset(
        tmp_path / "one.json",
        [
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
    )
    env = {"LLMSLIM_NEBIUS_ALLOW_LIVE": "1", "NEBIUS_API_KEY": NEBIUS_KEY, "NEBIUS_MODEL": "m-1"}

    def factory(args: Any, source: Any) -> live.NebiusReader:
        pricing = live.nebius_pricing(args.price_input, args.price_output, args.price_cached)
        return live.NebiusReader.from_env(
            source, model=args.model, pricing=pricing, transport=httpx.MockTransport(handler)
        )

    output = tmp_path / "live-nebius.json"
    code = live.main(
        [
            "--reader",
            "nebius",
            *NEBIUS_PRICE_ARGS,
            "--dataset",
            str(dataset),
            "--output",
            str(output),
        ],
        env=env,
        reader_factory=factory,
    )
    assert code == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["complete"] is True
    assert saved["reader"]["model"] == "m-1" and saved["reader"]["role"] == "secondary"
    assert len(seen) == 1 and json.loads(seen[0].content)["max_tokens"] == 64
    assert saved["cases"][0]["arms"]["full"]["score"] == 1.0
    assert NEBIUS_KEY not in output.read_text(encoding="utf-8")
    report = output.with_suffix(".md").read_text(encoding="utf-8")
    assert "Secondary reader: m-1 on Nebius Token Factory" in report
    assert NEBIUS_KEY not in report


def test_sarvam_main_end_to_end_with_a_fake_sdk(tiny_dataset: Path, tmp_path: Path) -> None:
    sdk = FakeSarvamSDK()
    env = {"LLMSLIM_RUN_LIVE_SARVAM": "1", "SARVAM_API_KEY": SARVAM_KEY}
    output = tmp_path / "live-sarvam.json"
    code = live.main(
        ["--reader", "sarvam", "--dataset", str(tiny_dataset), "--output", str(output)],
        env=env,
        reader_factory=lambda *_: _sarvam_reader(sdk),
    )
    assert code == 0
    text = output.read_text(encoding="utf-8")
    assert SARVAM_KEY not in text
    saved = json.loads(text)
    assert saved["classification"] == "MEASURED_LIVE_SECONDARY_READER"
    assert saved["credential_fields_persisted"] is False
    assert saved["tracing"]["enabled"] is False
    assert saved["dataset"]["public"] is False  # a temporary dataset is never public


def test_default_output_path_is_gitignored() -> None:
    from datetime import datetime, timezone

    path = live.default_output_path(
        "nebius/Meta Llama", datetime(2026, 10, 12, tzinfo=timezone.utc)
    )
    assert path.parent == live.RESULTS_DIR
    assert path.name == "live-nebius-meta-llama-v06-suite-20261012T000000Z.json"
    ignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "benchmarks/results/live-*.json" in ignore
    assert "benchmarks/results/live-*.md" in ignore


# --------------------------------------------------------------------------- report


def test_paired_bootstrap_is_deterministic_and_seeded() -> None:
    diffs = [0.0, 1.0, -1.0, 0.5, 0.0, 1.0, 0.0, -0.5]
    first = paired_bootstrap_ci(diffs)
    random.seed(12345)
    random.random()
    assert paired_bootstrap_ci(diffs) == first
    assert first is not None and first[0] <= sum(diffs) / len(diffs) <= first[1]
    assert paired_bootstrap_ci([0.0] * 5) == (0.0, 0.0)
    assert paired_bootstrap_ci([0.3]) is None
    assert paired_bootstrap_ci([]) is None


def test_markdown_report_is_labelled_and_lists_weak_spots(
    tiny_dataset: Path, tmp_path: Path
) -> None:
    result, output = _run(_sarvam_reader(FakeSarvamSDK()), _sarvam_guard(), tiny_dataset, tmp_path)
    report = render_markdown(result)
    assert report.splitlines()[2] == f"> **{SARVAM_LABEL}.**"
    assert "not a headline LLMSlim benchmark" in report
    assert "NOT THE v0.6 SUITE" in report  # a three-case dataset is not the frozen suite
    assert result["full_suite"] is False and result["dataset"]["frozen_v06_suite"] is False
    assert "INCOMPLETE" not in report
    for heading in ("## Results", "## By language", "## By category", "## Weak spots", "## Spend"):
        assert heading in report
    assert "| Hindi | 1 |" in report and "n=1, no interval" in report
    assert "`tools-over`" in report and "could not meet the budget" in report
    assert "The budget binds on only 2 of 3 case(s)" in report
    assert "seed 7" in report and "4,000 resamples" in report
    assert "₹" in report
    # The CLI renders the same report from the saved JSON.
    target = tmp_path / "again.md"
    assert report_main([str(output), "--output", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == render_markdown(
        json.loads(output.read_text(encoding="utf-8"))
    )


def test_markdown_report_reports_reader_misses_and_failures_honestly() -> None:
    def arm(score: float, status: str = "answered", **extra: Any) -> Dict[str, Any]:
        return {
            "status": status,
            "score": score,
            "all_found": score == 1.0,
            "missing": [] if score == 1.0 else ["X-1"],
            "context_recall": 1.0,
            "context_tokens": 100,
            "prompt_tokens": 120,
            "cost": 0.001,
            **extra,
        }

    cases = [
        {
            "id": f"en-{index}",
            "language": "English",
            "category": "rag",
            "budget_binds": True,
            "arms": {"full": arm(1.0), "llmslim": arm(0.5), "truncate": arm(0.0)},
        }
        for index in range(3)
    ]
    cases.append(
        {
            "id": "zero",
            "language": "Tamil",
            "category": "multilingual",
            "budget_binds": True,
            "arms": {
                "full": arm(0.0, "empty_answer"),
                "llmslim": arm(0.0),
                "truncate": arm(0.0),
            },
        }
    )
    result = {
        "complete": True,
        "full_suite": True,
        "arms": ["full", "llmslim", "truncate"],
        "cases": cases,
        "reader": {"label": SARVAM_LABEL, "display_name": "Sarvam 105B"},
        "pricing": {"currency": "INR"},
        "dataset": {"cases_requested": 4},
        "totals": {},
        "guard": {},
    }
    report = render_markdown(result)
    assert "LLMSlim scored below full context on 3 case(s)" in report
    assert "the facts were in the LLMSlim context; the reader missed them" in report
    assert "Every arm scored 0 on 1 case(s):** `zero`" in report
    assert "Empty answers (scored 0):** full 1" in report
    assert "**English:** LLMSlim 50.0 vs full 100.0 (n=3)" in report
    assert "SUBSET" not in report and "INCOMPLETE" not in report


def test_a_subset_of_the_frozen_suite_is_labelled_subset(tmp_path: Path) -> None:
    result, _ = _run(
        _sarvam_reader(FakeSarvamSDK()), _sarvam_guard(), live.DATASET, tmp_path, limit=1
    )
    assert result["dataset"]["frozen_v06_suite"] is True
    assert result["dataset"]["public"] is True
    assert result["full_suite"] is False and result["complete"] is True
    report = render_markdown(result)
    assert "SUBSET RUN" in report and "NOT THE v0.6 SUITE" not in report
