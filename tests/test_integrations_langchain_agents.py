"""LLMSlimToolOutputMiddleware in a real LangChain agent (create_agent), with a scripted chat model."""

from __future__ import annotations

import asyncio
from typing import Any, List

import pytest

pytest.importorskip("langchain.agents.middleware")

from langchain.agents import create_agent  # noqa: E402
from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from pydantic import Field  # noqa: E402

from llmslim.integrations.langchain_agents import LLMSlimToolOutputMiddleware  # noqa: E402

FAILURE = "tests/billing/test_refund.py::test_rounding FAILED - AssertionError: Decimal('10.05') != Decimal('10.04')"


def long_log() -> str:
    lines = [f"tests/test_api.py::test_endpoint_{i} PASSED" for i in range(500)]
    lines.insert(320, FAILURE)
    lines.append("=== 1 failed, 500 passed ===")
    return "\n".join(lines)


@tool
def run_tests(command: str) -> str:
    """Run the test suite and return its output."""
    return long_log()


@tool
def read_file(path: str) -> str:
    """Return a file's contents."""
    return "\n".join(f"line {i}: value = {i * 7}" for i in range(600))


@tool
def status(name: str) -> str:
    """A short status."""
    return "ok"


class ScriptedModel(BaseChatModel):
    """Answers with the given messages in order and records what it was sent."""

    responses: List[AIMessage]
    seen: List[Any] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append([message.model_copy(deep=True) for message in messages])
        return ChatResult(generations=[ChatGeneration(message=self.responses[len(self.seen) - 1])])


def call(name: str, call_id: str, **args) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}]
    )


def tool_messages(messages):
    return [message for message in messages if isinstance(message, ToolMessage)]


def test_long_results_are_shortened_once_and_kept_in_state():
    model = ScriptedModel(
        responses=[
            call("run_tests", "c1", command="pytest -q"),
            AIMessage(content="test_rounding fails."),
            AIMessage(content="It is in tests/billing/test_refund.py."),
        ]
    )
    agent = create_agent(
        model,
        tools=[run_tests],
        middleware=[LLMSlimToolOutputMiddleware()],
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "t1"}}
    state = agent.invoke({"messages": [HumanMessage("Run the tests.")]}, config)

    (sent,) = tool_messages(model.seen[1])
    assert sent.content.startswith("[LLMSlim shortened this tool output from")
    assert FAILURE in sent.content and "1 failed, 500 passed" in sent.content
    assert "Call the tool again with a narrower request" in sent.content
    (stored,) = tool_messages(state["messages"])
    assert stored.content == sent.content and stored.id == sent.id
    assert (
        stored.response_metadata["llmslim"]["tokens_before"]
        > stored.response_metadata["llmslim"]["tokens_after"]
    )

    # A later turn on the same thread sends exactly the same bytes, so the prefix (and any thinking after it) holds.
    agent.invoke({"messages": [HumanMessage("Which file?")]}, config)
    (again,) = tool_messages(model.seen[2])
    assert again.content == sent.content
    assert [m.content for m in model.seen[2][: len(model.seen[1])]] == [
        m.content for m in model.seen[1]
    ]


def test_excluded_unknown_short_and_non_text_results_are_left_alone():
    model = ScriptedModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"path": "a.py"},
                        "id": "r1",
                        "type": "tool_call",
                    },
                    {"name": "status", "args": {"name": "x"}, "id": "s1", "type": "tool_call"},
                ],
            ),
            AIMessage(content="done"),
        ]
    )
    agent = create_agent(
        model,
        tools=[read_file, status],
        middleware=[LLMSlimToolOutputMiddleware(never={"read_file"})],
    )
    agent.invoke({"messages": [HumanMessage("Read it.")]})
    contents = {m.name: m.content for m in tool_messages(model.seen[1])}
    assert contents["status"] == "ok" and contents["read_file"].startswith("line 0: value = 0")

    only = LLMSlimToolOutputMiddleware(only={"run_tests"})
    assert (
        only._eligible("run_tests") and not only._eligible("read_file") and not only._eligible(None)
    )
    image = ToolMessage(
        content=[{"type": "image_url", "image_url": {"url": "data:,"}}], tool_call_id="i1", id="m1"
    )
    assert LLMSlimToolOutputMiddleware()._shorten([call("x", "i1"), image]) is None


def test_results_the_model_has_already_seen_are_never_rewritten():
    seen = ToolMessage(content=long_log(), tool_call_id="c1", name="run_tests", id="old")
    history = [
        HumanMessage("go"),
        call("run_tests", "c1"),
        seen,
        AIMessage(content="I saw it all."),
    ]
    assert LLMSlimToolOutputMiddleware()._shorten(history) is None


def test_the_async_path_matches_the_sync_one():
    model = ScriptedModel(
        responses=[call("run_tests", "c1", command="pytest"), AIMessage(content="ok")]
    )
    agent = create_agent(model, tools=[run_tests], middleware=[LLMSlimToolOutputMiddleware()])
    asyncio.run(agent.ainvoke({"messages": [HumanMessage("Run the tests.")]}))
    (sent,) = tool_messages(model.seen[1])
    assert sent.content.startswith("[LLMSlim shortened") and FAILURE in sent.content


def test_options_are_validated():
    with pytest.raises(ValueError):
        LLMSlimToolOutputMiddleware(keep_ratio=0)
    with pytest.raises(ValueError):
        LLMSlimToolOutputMiddleware(min_tokens=0)


def test_json_results_are_left_alone_unless_asked():
    import json

    rows = [
        {"id": i, "title": f"Issue {i}", "body": "Steps to reproduce: run it twice. " * 4}
        for i in range(120)
    ]
    messages = [
        HumanMessage("List the issues."),
        AIMessage("", tool_calls=[{"id": "c1", "name": "list_issues", "args": {}}]),
        ToolMessage(json.dumps(rows, indent=2), tool_call_id="c1", name="list_issues", id="m1"),
    ]
    assert LLMSlimToolOutputMiddleware().before_model({"messages": messages}, None) is None
    update = LLMSlimToolOutputMiddleware(compress_json=True).before_model(
        {"messages": messages}, None
    )
    assert update is not None and "JSON list" in update["messages"][0].content
