"""llmslim.proxy: first-sight tool-output compression that replays the same bytes, so caching and thinking survive."""

from __future__ import annotations

import copy
import json

import pytest

from llmslim.proxy import COMPRESSIBLE_TOOLS, Policy, ProxyStore, block_key, rewrite_request
from llmslim.proxy.rewrite import compress_output
from llmslim.tokens import count_tokens


def make_log(failures: int = 1, lines: int = 600) -> str:
    out = [f"tests/test_api.py::test_case_{i} PASSED" for i in range(lines)]
    for n in range(failures):
        out.insert(
            300 + n,
            f"tests/test_refund.py::test_rounding_{n} FAILED - AssertionError: 10.05 != 10.04",
        )
    out.append(f"=== {failures} failed, {lines} passed in 12.34s ===")
    return "\n".join(out)


def bash_call(call_id: str, command: str = "pytest -q") -> dict:
    return {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}
        ],
    }


def result(call_id: str, content, **extra) -> dict:
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": call_id, "content": content, **extra}],
    }


def request(*messages) -> dict:
    return {
        "model": "claude-haiku-5-5",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Run the tests."}, *messages],
    }


@pytest.fixture
def store():
    store = ProxyStore()
    yield store
    store.close()


# ---------------------------------------------------------------- the rewrite


def test_new_long_output_is_compressed_once_and_marked(store):
    body = request(bash_call("c1"), result("c1", make_log()))
    original = copy.deepcopy(body)
    new_body, report = rewrite_request(body, store)
    assert body == original  # the input is never modified
    text = new_body["messages"][-1]["content"][0]["content"]
    assert text.startswith("[LLMSlim shortened this tool output from")
    assert "test_rounding_0 FAILED" in text and "1 failed, 600 passed" in text
    assert report.compressed == 1 and report.replayed == 0 and report.saved > 0
    assert report.tokens_after == count_tokens(text) and report.tools == {"Bash": 1}
    assert store.get(block_key("c1", make_log()))[0] == text


def test_later_requests_replay_the_same_bytes_and_old_blocks_stay(store):
    first, _ = rewrite_request(request(bash_call("c1"), result("c1", make_log())), store)
    sent = first["messages"][-1]["content"][0]["content"]
    thinking = {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "One failure.", "signature": "sig"},
            {"type": "text", "text": "test_rounding fails."},
        ],
    }
    later = request(
        bash_call("c1"), result("c1", make_log()), thinking, {"role": "user", "content": "Fix it."}
    )
    again, report = rewrite_request(later, store)
    assert again["messages"][2]["content"][0]["content"] == sent  # byte for byte
    assert again["messages"][3] is later["messages"][3]  # thinking untouched
    assert report.compressed == 0 and report.replayed == 1 and report.saved > 0


def test_new_output_counts_even_when_a_system_message_follows(store):
    """Claude Code appends a role "system" message after the tool result."""
    body = request(
        bash_call("c1"),
        result("c1", make_log()),
        {"role": "system", "content": [{"type": "text", "text": "<reminder>"}]},
    )
    new_body, report = rewrite_request(body, store)
    assert report.compressed == 1 and new_body["messages"][-1] is body["messages"][-1]


def test_output_the_proxy_never_saw_is_left_alone(store):
    """Started mid-session: an old long output is not in the newest message and was never compressed."""
    body = request(
        bash_call("old"),
        result("old", make_log()),
        {"role": "assistant", "content": "Done."},
        {"role": "user", "content": "Next?"},
    )
    new_body, report = rewrite_request(body, store)
    assert new_body is body and not report.changed


@pytest.mark.parametrize(
    "tool",
    [
        "Read",
        "Edit",
        "Write",
        "NotebookEdit",
        "Agent",
        "Task",
        "TaskGet",
        "Skill",
        "LSP",
        "ReadMcpResourceTool",
        "SomeFutureTool",
    ],
)
def test_only_listed_tools_are_compressed(store, tool):
    call = {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": "r1", "name": tool, "input": {"file_path": "big.py"}}
        ],
    }
    body = request(call, result("r1", make_log()))
    new_body, report = rewrite_request(body, store)
    assert new_body is body and not report.changed


def test_unknown_calls_short_output_and_plain_messages_pass_through(store):
    for body in (
        request(result("nobody", make_log())),  # no matching tool_use
        request(bash_call("c1"), result("c1", "3 passed in 0.1s")),  # short
        {"model": "m", "messages": [{"role": "user", "content": "hi"}]},
        {"model": "m", "messages": []},
        {"model": "m"},
    ):
        new_body, report = rewrite_request(body, store)
        assert new_body is body and not report.changed


def test_list_content_keeps_images_and_cache_control(store):
    image = {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "iVBORw0KGgo="},
    }
    parts = [{"type": "text", "text": make_log()}, image]
    body = request(
        bash_call("c1"), result("c1", parts, cache_control={"type": "ephemeral"}, is_error=False)
    )
    new_body, report = rewrite_request(body, store)
    block = new_body["messages"][-1]["content"][0]
    assert block["cache_control"] == {"type": "ephemeral"} and block["is_error"] is False
    assert block["content"][1] == image and block["content"][0]["text"].startswith("[LLMSlim")
    assert report.compressed == 1


def test_mcp_tools_are_opt_in(store):
    call = {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "m1",
                "name": "mcp__github__list_issues",
                "input": {"query": "rounding"},
            }
        ],
    }
    body = request(call, result("m1", make_log()))
    assert not rewrite_request(body, store)[
        1
    ].changed  # MCP tools may return live state: off by default
    assert (
        rewrite_request(
            body, ProxyStore(), Policy(tools=COMPRESSIBLE_TOOLS | {"mcp__github__list_issues"})
        )[1].compressed
        == 1
    )
    assert rewrite_request(body, ProxyStore(), Policy(mcp=True))[1].compressed == 1
    assert not rewrite_request(
        body, ProxyStore(), Policy(mcp=True, never=frozenset({"mcp__github__list_issues"}))
    )[1].changed
    assert {"Bash", "PowerShell", "Grep"} <= COMPRESSIBLE_TOOLS and "Read" not in COMPRESSIBLE_TOOLS


def test_compression_is_deterministic_across_stores():
    body = request(bash_call("c1"), result("c1", make_log(failures=3)))
    one, _ = rewrite_request(body, ProxyStore())
    two, _ = rewrite_request(body, ProxyStore())
    assert json.dumps(one) == json.dumps(two)


def test_the_first_decision_wins(store):
    key = block_key("c1", "x")
    store.put(key, tool="Bash", original="x", compressed="first", before=10, after=2)
    store.put(key, tool="Bash", original="x", compressed="second", before=10, after=3)
    assert store.get(key) == ("first", 10, 2) and store.original(key) == "x"


def test_policy_validation_and_compress_output_limits():
    with pytest.raises(ValueError):
        Policy(keep_ratio=1.5)
    with pytest.raises(ValueError):
        Policy(min_tokens=0)
    assert compress_output("short", None, Policy()) is None
    text, before, after = compress_output(make_log(), "pytest -q", Policy())
    assert before > after and after <= before * 0.5


def test_stats_record_requests_and_survive_reopening(tmp_path):
    path = tmp_path / "proxy.db"
    store = ProxyStore(path)
    body = request(bash_call("c1"), result("c1", make_log()))
    _, report = rewrite_request(body, store)
    store.record(report)
    store.close()
    again = ProxyStore(path)
    stats = again.stats()
    assert (
        stats["requests_changed"] == 1
        and stats["outputs_compressed"] == 1
        and stats["tokens_saved"] == report.saved
    )
    _, replay = rewrite_request(
        request(
            bash_call("c1"),
            result("c1", make_log()),
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "go"},
        ),
        again,
    )
    assert replay.replayed == 1
    again.close()
