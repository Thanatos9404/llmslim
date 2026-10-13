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
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from llmslim import count_tokens
from llmslim.integrations.pydantic_ai import (
    fit_messages,
    history_tokens,
    llmslim_history_processor,
)
from tests._history_corpus import FAILURE, NOTES, SYSTEM_PROMPT, TASK, make_log

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
