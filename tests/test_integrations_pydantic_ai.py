"""llmslim_history_processor with real Pydantic AI types and models. Skipped without pydantic-ai.

No network: the agent runs use FunctionModel and TestModel.
"""

from __future__ import annotations

import copy

import pytest

pytest.importorskip("pydantic_ai")

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from llmslim import count_tokens
from llmslim.integrations import pydantic_ai as adapter
from llmslim.integrations.pydantic_ai import (
    fit_messages,
    history_tokens,
    llmslim_history_processor,
)
from tests._history_corpus import (
    FAILURE,
    NOTES,
    SYSTEM_PROMPT,
    TASK,
    ThinkingBinding,
    make_log,
    signature,
)

LATEST = "Now run the refund tests again."


def _history():
    """Two user turns with tool exchanges; the last request returns a tool result."""
    return [
        ModelRequest(parts=[SystemPromptPart(SYSTEM_PROMPT), UserPromptPart(TASK)]),
        ModelResponse(
            parts=[
                TextPart("Running the tests."),
                ToolCallPart("run_tests", {"path": "tests"}, tool_call_id="t1"),
            ]
        ),
        ModelRequest(parts=[ToolReturnPart("run_tests", make_log(lines=400), tool_call_id="t1")]),
        ModelResponse(parts=[ToolCallPart("read_file", {"path": "refund.py"}, tool_call_id="t2")]),
        ModelRequest(
            parts=[
                ToolReturnPart("read_file", {"path": "refund.py", "lines": 120}, tool_call_id="t2")
            ]
        ),
        ModelResponse(parts=[TextPart(NOTES * 2)]),
        ModelRequest(parts=[UserPromptPart(LATEST)]),
        ModelResponse(
            parts=[ToolCallPart("run_tests", {"path": "tests/test_refund.py"}, tool_call_id="t3")]
        ),
        ModelRequest(parts=[ToolReturnPart("run_tests", make_log(lines=200), tool_call_id="t3")]),
    ]


def _pairs(messages):
    """Tool call ids made by the model, and tool call ids answered to it."""
    calls = {
        p.tool_call_id
        for m in messages
        if isinstance(m, ModelResponse)
        for p in m.parts
        if isinstance(p, ToolCallPart)
    }
    answers = {
        p.tool_call_id
        for m in messages
        if isinstance(m, ModelRequest)
        for p in m.parts
        if isinstance(p, ToolReturnPart) or (isinstance(p, RetryPromptPart) and p.tool_name)
    }
    return calls, answers


def _assert_valid(messages, budget=None):
    calls, answers = _pairs(messages)
    assert calls == answers, "every tool call has its return and every return its call"
    kinds = [type(m) for m in messages]
    assert kinds[0] is ModelRequest and kinds[-1] is ModelRequest
    assert all(a is not b for a, b in zip(kinds, kinds[1:])), "requests and responses alternate"
    system = [p for p in messages[0].parts if isinstance(p, SystemPromptPart)]
    assert [p.content for p in system] == [SYSTEM_PROMPT]
    if budget is not None:
        assert history_tokens(messages) <= budget


def test_returns_a_processor_and_changes_nothing_under_budget():
    messages = _history()
    process = llmslim_history_processor(max_tokens=10**6)
    out = process(messages)
    assert all(a is b for a, b in zip(out, messages)) and len(out) == len(messages)


def test_compresses_older_tool_results_first():
    messages = _history()
    budget = history_tokens(messages) // 2
    out, fit = fit_messages(messages, budget)
    _assert_valid(out, budget)
    assert len(out) == len(messages)  # compression alone was enough
    old_log = out[2].parts[0].content
    assert count_tokens(old_log) < count_tokens(messages[2].parts[0].content)
    assert FAILURE in old_log
    assert out[-1] is messages[-1] and out[-2] is messages[-2]  # recent messages untouched
    assert fit.fits and fit.compressed


def test_removes_whole_tool_exchanges_when_compression_is_not_enough():
    messages = _history()
    recent = history_tokens(messages[:1]) + history_tokens(messages[5:])
    out, fit = fit_messages(messages, recent + 5, min_tokens=10**6)  # nothing may be compressed
    _assert_valid(out, recent + 5)
    calls, _ = _pairs(out)
    assert calls == {"t3"}, "both older exchanges went, each with its return"
    assert [m for m in out if m is messages[5]], "the user-facing text of the old turn stays"
    prompts = [p.content for m in out for p in m.parts if isinstance(p, UserPromptPart)]
    assert prompts == [TASK, LATEST]
    assert fit.dropped


def test_removes_old_turns_whole_but_never_the_first():
    messages = [
        ModelRequest(parts=[SystemPromptPart(SYSTEM_PROMPT), UserPromptPart(TASK)]),
        ModelResponse(parts=[TextPart(NOTES)]),
        ModelRequest(parts=[UserPromptPart("Explain the rounding bug in detail.")]),
        ModelResponse(parts=[TextPart(NOTES * 3)]),
        ModelRequest(parts=[UserPromptPart(LATEST)]),
    ]
    budget = history_tokens(messages[:2]) + history_tokens(messages[4:]) + 5
    out, _ = fit_messages(messages, budget, keep_recent=1, min_tokens=10**6)
    _assert_valid(out, budget)
    assert out == [messages[0], messages[1], messages[4]]


def test_a_tool_call_answered_in_a_later_request_is_never_orphaned():
    messages = [
        ModelRequest(parts=[SystemPromptPart(SYSTEM_PROMPT), UserPromptPart(TASK)]),
        ModelResponse(
            parts=[
                ToolCallPart("deploy", {"env": "staging"}, tool_call_id="slow"),
                ToolCallPart("run_tests", {}, tool_call_id="a"),
            ]
        ),
        ModelRequest(parts=[ToolReturnPart("run_tests", make_log(lines=300), tool_call_id="a")]),
        ModelResponse(parts=[ToolCallPart("run_tests", {}, tool_call_id="b")]),
        ModelRequest(
            parts=[
                ToolReturnPart("run_tests", make_log(lines=300), tool_call_id="b"),
                ToolReturnPart("deploy", "deployed to staging", tool_call_id="slow"),
            ]
        ),
        ModelResponse(parts=[TextPart("Deployed.")]),
        ModelRequest(parts=[UserPromptPart(LATEST)]),
    ]
    out, _ = fit_messages(messages, 60, keep_recent=1, min_tokens=10**6)
    calls, answers = _pairs(out)
    assert calls == answers
    assert "slow" in calls  # the exchange holding it could not be removed on its own


def test_recent_tool_result_is_compressed_only_as_a_last_resort():
    messages = _history()
    budget = history_tokens(messages[:1]) + 400
    out, fit = fit_messages(messages, budget)
    _assert_valid(out)
    last = out[-1].parts[0]
    assert last.tool_call_id == "t3"
    assert count_tokens(last.content) < count_tokens(messages[-1].parts[0].content)
    assert FAILURE in last.content
    assert fit.fits and history_tokens(out) <= budget


def test_system_prompt_and_latest_prompt_survive_an_impossible_budget():
    messages = _history()
    out, fit = fit_messages(messages, 1)
    _assert_valid(out)
    assert not fit.fits
    assert any(p.content == LATEST for m in out for p in m.parts if isinstance(p, UserPromptPart))


def test_input_is_not_modified():
    messages = _history()
    snapshot = copy.deepcopy(messages)
    llmslim_history_processor(max_tokens=200)(messages)
    assert messages == snapshot


def test_history_tokens_counts_every_part():
    messages = _history()
    assert history_tokens(messages) > history_tokens(messages[:-1]) > 0
    assert history_tokens([]) == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_tokens": 0},
        {"max_tokens": True},
        {"max_tokens": 100, "keep_recent": 0},
        {"max_tokens": 100, "min_tokens": -1},
        {"max_tokens": 100, "relevance": "psychic"},
        {"max_tokens": 100, "additional_compress_kwargs": {"relevance": "semantic"}},
    ],
)
def test_invalid_options(kwargs):
    with pytest.raises(ValueError):
        llmslim_history_processor(**kwargs)


def _agent(model, budget):
    """An agent with the processor, wired the way the installed Pydantic AI expects."""
    process = llmslim_history_processor(max_tokens=budget)
    try:
        from pydantic_ai.capabilities import ProcessHistory  # Pydantic AI 2.x
    except ImportError:  # Pydantic AI 1.x
        agent = Agent(model, system_prompt=SYSTEM_PROMPT, history_processors=[process])
    else:
        agent = Agent(model, system_prompt=SYSTEM_PROMPT, capabilities=[ProcessHistory(process)])

    @agent.tool_plain
    def run_tests(suite: str) -> str:
        """Run a test suite and return its output."""
        return make_log(suite, 300)

    return agent


def test_agent_run_with_function_model_keeps_pairs_and_budget():
    budget = 900
    seen = []

    def model(messages, info: AgentInfo) -> ModelResponse:
        seen.append(list(messages))
        if len(seen) <= 4:
            return ModelResponse(
                parts=[
                    ToolCallPart("run_tests", {"suite": f"suite{len(seen)}"}, f"call{len(seen)}")
                ]
            )
        return ModelResponse(parts=[TextPart("test_rounding fails in every suite.")])

    result = _agent(FunctionModel(model), budget).run_sync(TASK)
    assert result.output == "test_rounding fails in every suite."
    assert len(seen) == 5
    for messages in seen:
        _assert_valid(messages, budget)
        returns = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        # No return was synthesized by Pydantic AI's own repair: each is a (compressed) test log.
        assert all("test_case" in p.content for p in returns)
    # The last request still carries every earlier tool exchange, compressed.
    assert len(_pairs(seen[-1])[0]) == 4


def test_agent_run_with_test_model():
    agent = _agent(TestModel(), 400)
    result = agent.run_sync(TASK)
    assert result.output
    messages = result.all_messages()
    calls, answers = _pairs(messages)
    assert calls == answers


# Claude thinking: a signed ThinkingPart is bound to the history before it.


def _thinking(tag, provider="anthropic"):
    return ThinkingPart("", signature=signature(tag), provider_name=provider)


def _thinking_history(end_with_tool_round=False):
    """Thinking before the long tool log and after it; optionally ends mid tool round."""
    messages = [
        ModelRequest(parts=[SystemPromptPart(SYSTEM_PROMPT), UserPromptPart(TASK)]),
        ModelResponse(
            parts=[
                _thinking("a"),
                TextPart("Running the tests."),
                ToolCallPart("run_tests", {"path": "tests"}, tool_call_id="t1"),
            ]
        ),
        ModelRequest(parts=[ToolReturnPart("run_tests", make_log(lines=400), tool_call_id="t1")]),
        ModelResponse(parts=[_thinking("b"), TextPart(NOTES * 2)]),
        ModelRequest(parts=[UserPromptPart(LATEST)]),
    ]
    if end_with_tool_round:
        messages += [
            ModelResponse(
                parts=[
                    _thinking("c"),
                    ToolCallPart("run_tests", {"path": "tests"}, tool_call_id="t3"),
                ]
            ),
            ModelRequest(
                parts=[ToolReturnPart("run_tests", make_log("tests", 400), tool_call_id="t3")]
            ),
        ]
    return messages


def _signatures(messages):
    return [p.signature for m in messages for p in m.parts if isinstance(p, ThinkingPart)]


def test_thinking_is_kept_when_nothing_changes():
    messages = _thinking_history(end_with_tool_round=True)
    out, fit = fit_messages(messages, 10**6)
    assert all(a is b for a, b in zip(out, messages)) and len(out) == len(messages)
    assert fit.thinking_stripped == 0 and not fit.changed


def test_thinking_after_the_first_change_is_removed_and_kept_before_it():
    messages = _thinking_history()
    snapshot = copy.deepcopy(messages)
    out, fit = fit_messages(messages, history_tokens(messages) // 2)
    _assert_valid(out)
    assert out[2].parts[0].content != messages[2].parts[0].content  # the old log changed
    assert out[1] is messages[1]
    # Kept before the change, removed after it: an unbroken run from the start.
    assert _signatures(out) == [signature("a")]
    assert [type(p) for p in out[3].parts] == [TextPart]
    assert fit.thinking_stripped == 1 and "1 thinking block(s) removed" in fit.summary()
    assert messages == snapshot


def test_other_providers_reasoning_is_not_touched():
    messages = _thinking_history()
    messages[3] = ModelResponse(parts=[_thinking("b", provider="openai"), TextPart(NOTES * 2)])
    out, fit = fit_messages(messages, history_tokens(messages) // 2)
    assert _signatures(out) == [signature("a"), signature("b")]
    assert fit.thinking_stripped == 0


def test_mid_tool_round_the_earlier_history_waits():
    messages = _thinking_history(end_with_tool_round=True)
    # Room for everything except most of the newest tool result.
    budget = history_tokens(messages[:-1]) + 150
    out, fit = fit_messages(messages, budget)
    _assert_valid(out, budget)
    assert all(a is b for a, b in zip(out[:-1], messages[:-1]))
    assert count_tokens(out[-1].parts[0].content) < count_tokens(messages[-1].parts[0].content)
    assert _signatures(out) == [signature(t) for t in "abc"]
    assert fit.kept_tool_round and fit.thinking_stripped == 0


def test_mid_tool_round_compacts_anyway_when_the_history_would_not_fit():
    messages = _thinking_history(end_with_tool_round=True)
    budget = history_tokens(messages[:-1]) // 2
    out, fit = fit_messages(messages, budget)
    _assert_valid(out, budget)
    assert not fit.kept_tool_round
    assert _signatures(out) == [signature("a")]
    assert fit.thinking_stripped == 2


def test_fitting_is_deterministic_and_replays_unchanged():
    messages = _thinking_history(end_with_tool_round=True)
    budget = history_tokens(messages) // 2
    first, fit = fit_messages(messages, budget)
    again, _ = fit_messages(copy.deepcopy(messages), budget)
    assert again == first
    # Pydantic AI keeps the processed history: the next request sends it unchanged.
    replay, refit = fit_messages(first, budget)
    assert all(a is b for a, b in zip(replay, first)) and not refit.changed


def _describe(message):
    """A message without its Claude thinking, and the signatures of that thinking."""
    rest = tuple(
        (type(p).__name__, getattr(p, "content", None), getattr(p, "args", None))
        for p in message.parts
        if not isinstance(p, ThinkingPart)
    )
    return rest, [p.signature for p in message.parts if isinstance(p, ThinkingPart)]


def _thinking_agent_run(budget):
    """Two user turns of a Claude-like model that thinks before every response."""
    binding = ThinkingBinding(_describe)
    problems = []

    def model(messages, info: AgentInfo) -> ModelResponse:
        problems.extend(binding.violations(messages))
        step = len(binding.bound)
        thinking = ThinkingPart("", signature=binding.produce(messages), provider_name="anthropic")
        # Two tool calls, then an answer, in each run.
        if step % 3 != 2:
            return ModelResponse(
                parts=[thinking, ToolCallPart("run_tests", {"suite": f"s{step}"}, f"call{step}")]
            )
        return ModelResponse(parts=[thinking, TextPart(NOTES * 4)])

    agent = _agent(FunctionModel(model), budget)
    first = agent.run_sync(TASK)
    agent.run_sync(LATEST, message_history=first.all_messages())
    return problems


@pytest.mark.parametrize(
    "budget",
    [
        # Tight: thinking is removed at the second user prompt and, where the open tool round
        # alone is over budget, mid round too.
        800,
        # Roomy: only the newest tool result is compressed, every thinking part is kept.
        6000,
    ],
)
def test_agent_never_replays_thinking_after_changed_history(budget):
    assert _thinking_agent_run(budget) == []


def test_without_the_fix_the_api_would_reject_the_agent_run(monkeypatch):
    monkeypatch.setattr(adapter, "_bound_thinking", lambda part: False)
    problems = _thinking_agent_run(6000)
    assert any("the history before it changed" in problem for problem in problems)
