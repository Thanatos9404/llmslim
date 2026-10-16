"""Pipeline helper tests for llmslim (RAG and Chat)."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

from llmslim import pipelines
from llmslim.integrations._history import is_signed_thinking
from llmslim.pipelines import compress_chat_messages, compress_documents
from tests._history_corpus import NOTES, TASK, ThinkingBinding, make_log, signature


def test_compress_documents_basic():
    """Verify compress_documents returns a CompressionResult for each input document."""
    docs = [
        "Authentication requires JWT tokens. Access tokens expire after 15 minutes. Always transmit over HTTPS.",
        "Database indexing with PostgreSQL GIN indexes speeds up JSONB queries significantly.",
    ]
    results = compress_documents(docs, target_ratio=0.5)

    assert len(results) == 2
    assert results[0].original_text == docs[0]
    assert results[1].original_text == docs[1]


def test_compress_documents_with_query():
    """Verify compress_documents respects query parameter for relevance-aware compression."""
    docs = [
        "OAuth 2.0 is an authorization framework. JSON Web Tokens (JWT) are used for authentication. Access tokens expire quickly.",
        "PostgreSQL supports JSONB columns. GIN indexes optimize key lookup. B-tree indexes handle simple equality.",
    ]
    query = "How does JWT authentication work?"
    results = compress_documents(docs, query=query, target_ratio=0.5)

    assert len(results) == 2
    # Document 1 (relevant to JWT) should retain JWT content
    assert "JWT" in results[0].compressed_text or "Tokens" in results[0].compressed_text


def test_compress_chat_messages_system_prompt_preserved():
    """Verify system prompts are left completely untouched in compress_chat_messages."""
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. You must always answer in valid JSON. Never hallucinate.",
        },
        {
            "role": "user",
            "content": "Explain machine learning concepts in detail. Machine learning is a branch of AI that focuses on building applications that learn from data. Supervised learning uses labeled data. Unsupervised learning finds patterns in unlabeled data. Reinforcement learning uses reward signals. Deep learning uses neural networks with many hidden layers.",
        },
    ]

    compressed = compress_chat_messages(messages, target_ratio=0.5)

    assert len(compressed) == 2
    # System prompt must be 100% identical
    assert compressed[0]["content"] == messages[0]["content"]
    # User prompt should be compressed
    assert len(compressed[1]["content"]) <= len(messages[1]["content"])


def test_compress_chat_messages_custom_compressible_roles():
    """Verify compressible_roles parameter allows compressing system prompts if explicitly requested."""
    messages = [
        {"role": "system", "content": "System prompt with extra details. " * 10},
        {"role": "user", "content": "User prompt."},
    ]

    compressed = compress_chat_messages(
        messages, target_ratio=0.5, compressible_roles=["system", "user"]
    )

    assert len(compressed) == 2
    # System prompt should be compressed when explicitly included in compressible_roles
    assert len(compressed[0]["content"]) < len(messages[0]["content"])


def test_compress_chat_messages_min_tokens_threshold():
    """Verify short chat turns below min_tokens threshold are untouched."""
    messages = [
        {"role": "system", "content": "System prompt."},
        {"role": "user", "content": "Short question?"},
        {"role": "assistant", "content": "Short answer."},
    ]

    compressed = compress_chat_messages(messages, target_ratio=0.5, min_tokens=50)

    assert compressed[0]["content"] == messages[0]["content"]
    assert compressed[1]["content"] == messages[1]["content"]
    assert compressed[2]["content"] == messages[2]["content"]


# Claude thinking in Anthropic content blocks: signed blocks are bound to the history before them.

LONG_LOG = "Here is the test output:\n" + make_log(lines=300)


def _thinking(tag, text=""):
    return {"type": "thinking", "thinking": text, "signature": signature(tag)}


def _tool_use(call_id):
    return {"type": "tool_use", "id": call_id, "name": "run_tests", "input": {"path": "tests"}}


def _tool_result(call_id, output="2 failed, 40 passed"):
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": call_id, "content": output}],
    }


def _anthropic_history():
    """Thinking before the long message, then after it; ends with a new user message."""
    return [
        {"role": "user", "content": TASK},
        {
            "role": "assistant",
            "content": [_thinking("a"), {"type": "text", "text": "Send the log."}],
        },
        {"role": "user", "content": LONG_LOG},
        {
            "role": "assistant",
            "content": [
                _thinking("b", "The rounding test fails."),
                {"type": "redacted_thinking", "data": signature("b2")},
                {"type": "text", "text": NOTES},
            ],
        },
        {"role": "user", "content": "Now fix it."},
    ]


def _signatures(messages):
    return [
        block.get("signature") or block.get("data")
        for message in messages
        if isinstance(message["content"], list)
        for block in message["content"]
        if is_signed_thinking(block)
    ]


def test_chat_messages_without_a_change_keep_every_thinking_block():
    messages = _anthropic_history()
    out = compress_chat_messages(messages, min_tokens=10**6)
    assert out == messages
    assert all(a["content"] is b["content"] for a, b in zip(out, messages))


def test_chat_messages_thinking_after_the_first_change_is_removed():
    messages = _anthropic_history()
    snapshot = copy.deepcopy(messages)
    out = compress_chat_messages(messages, target_ratio=0.3)
    assert out[2]["content"] != LONG_LOG
    # Kept before the change, removed after it: still an unbroken run from the start.
    assert _signatures(out) == [signature("a")]
    assert out[3]["content"] == [{"type": "text", "text": NOTES}]
    assert out[1] == messages[1]
    assert messages == snapshot, "the input and its content lists are not modified"


def test_chat_messages_keep_the_thinking_of_an_unfinished_tool_round():
    messages = _anthropic_history()[:4] + [
        {"role": "user", "content": "Run the refund tests."},
        {"role": "assistant", "content": [_thinking("c"), _tool_use("t1")]},
        _tool_result("t1"),
    ]
    out = compress_chat_messages(messages, target_ratio=0.3)
    assert out[2]["content"] != LONG_LOG
    assert _signatures(out) == [signature("a"), signature("c")]
    assert out[5] == messages[5]
    # Once a user message closes the round, its thinking goes too.
    closed = messages + [
        {"role": "assistant", "content": [_thinking("d"), {"type": "text", "text": "Fixed."}]},
        {"role": "user", "content": "Thanks."},
    ]
    assert _signatures(compress_chat_messages(closed, target_ratio=0.3)) == [signature("a")]


def test_chat_messages_open_round_in_openai_format_and_sdk_blocks():
    thinking = SimpleNamespace(type="thinking", thinking="", signature=signature("c"))
    messages = [
        {"role": "user", "content": LONG_LOG},
        {
            "role": "assistant",
            "content": [SimpleNamespace(type="thinking", thinking="", signature=signature("b"))],
        },
        {"role": "user", "content": "Run them again."},
        {
            "role": "assistant",
            "content": [thinking],
            "tool_calls": [
                {"id": "t1", "type": "function", "function": {"name": "run", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "t1", "content": "ok"},
    ]
    out = compress_chat_messages(messages, target_ratio=0.3)
    assert out[1]["content"] == []
    assert out[3]["content"] == [thinking]


def test_chat_messages_are_deterministic():
    messages = _anthropic_history()
    assert compress_chat_messages(messages, target_ratio=0.3) == compress_chat_messages(
        copy.deepcopy(messages), target_ratio=0.3
    )


def _describe(message):
    content = message["content"]
    if not isinstance(content, list):
        return json.dumps(message, sort_keys=True), []
    rest = {**message, "content": [b for b in content if not is_signed_thinking(b)]}
    return json.dumps(rest, sort_keys=True), [
        b.get("signature") or b["data"] for b in content if is_signed_thinking(b)
    ]


ASKS = (
    "Please look at the refund code. " + NOTES,
    "Now update the invoice module and the changelog. The invoice totals look wrong too. " + NOTES,
    "Finally check the CI configuration and the Python versions it runs.",
)


def _converse(prepare):
    """Three user requests; the model calls a tool twice per request, then answers.

    Every request is checked as Anthropic would check it. Returns the problems found.
    """
    binding = ThinkingBinding(_describe)
    history, problems = [], []
    for turn, ask in enumerate(ASKS):
        history.append({"role": "user", "content": ask})
        for step in range(3):
            request = prepare(history)
            problems += binding.violations(request)
            if step:  # mid tool round: the turn waiting on its results keeps its thinking
                assert _describe(request[-2])[1], "the open tool round lost its thinking"
            block = _thinking("x") | {"signature": binding.produce(request)}
            if step < 2:
                call_id = f"t{turn}{step}"
                history.append({"role": "assistant", "content": [block, _tool_use(call_id)]})
                history.append(_tool_result(call_id, make_log(f"suite{turn}{step}", 120)))
            else:
                history.append(
                    {"role": "assistant", "content": [block, {"type": "text", "text": "Done."}]}
                )
    return problems


def _with_latest_question(history):
    """Compression focused on the latest user question: earlier turns change between requests."""
    query = next(m["content"] for m in reversed(history) if isinstance(m["content"], str))
    return compress_chat_messages(history, target_ratio=0.5, query=query)


def test_a_conversation_never_replays_thinking_after_changed_history():
    assert _converse(_with_latest_question) == []
    assert _converse(lambda history: compress_chat_messages(history, target_ratio=0.5)) == []


def test_without_the_strip_the_api_would_reject_the_conversation(monkeypatch):
    monkeypatch.setattr(pipelines, "_strip_thinking_after", lambda messages, first_edit: None)
    problems = _converse(_with_latest_question)
    assert any("the history before it changed" in problem for problem in problems)
