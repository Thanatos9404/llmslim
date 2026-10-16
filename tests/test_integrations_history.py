"""Framework-free tests for the shared core of the gptme, Hermes Agent and Pydantic AI adapters.

These run in every environment; the framework-specific tests skip when a framework is missing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llmslim import ContextCompressor, ContextRole, count_tokens
from llmslim.core import CompressionResult
from llmslim.integrations._history import (
    CALL,
    OTHER,
    PROMPT,
    REPLY,
    HistoryFit,
    HistoryItem,
    first_edited,
    fit_history,
    is_signed_thinking,
    open_tool_round,
    placeholder_text,
    protect_before,
    validate_history_options,
)
from tests._history_corpus import NOTES, SYSTEM_PROMPT, TASK, make_log
from tests._integration_corpus import PreferringScorer

LOG = make_log()


def _history(**overrides):
    """system prompt, task, an old tool log, old notes, a recent tool log, the latest request."""
    items = [
        HistoryItem(SYSTEM_PROMPT, ContextRole.SYSTEM, protected=True),
        HistoryItem(TASK, ContextRole.USER, protected=True),
        HistoryItem(LOG, ContextRole.TOOL),
        HistoryItem(NOTES, ContextRole.ASSISTANT),
        HistoryItem(make_log("recent"), ContextRole.TOOL, recent=True),
        HistoryItem("Now add the changelog entry.", ContextRole.USER, protected=True),
    ]
    for index, item in overrides.items():
        items[int(index[1:])] = item
    return items


def _tokens(texts):
    return sum(count_tokens(t) for t in texts if t is not None)


def test_without_a_budget_nothing_changes():
    items = _history()
    fit = fit_history(items, None)
    assert fit.texts == [item.text for item in items]
    assert not fit.changed and fit.fits
    assert fit.tokens == fit.original_tokens == _tokens(item.text for item in items)


def test_caps_apply_without_a_budget_and_keep_the_failure():
    items = _history(i2=HistoryItem(LOG, ContextRole.TOOL, cap=200))
    fit = fit_history(items, None)
    assert fit.compressed == [2]
    assert count_tokens(fit.texts[2]) < count_tokens(LOG)
    assert "10.05 != 10.04" in fit.texts[2]
    assert fit.texts[:2] == [SYSTEM_PROMPT, TASK]


def test_budget_compresses_older_items_and_leaves_the_rest_alone():
    items = _history()
    older = count_tokens(LOG) + count_tokens(NOTES)
    budget = fit_history(items, None).tokens - older // 2
    fit = fit_history(items, budget)
    assert fit.fits and fit.tokens <= budget
    assert fit.tokens == _tokens(fit.texts)
    assert set(fit.compressed) <= {2, 3}
    assert not fit.dropped
    # Protected items are untouched, and the recent tool log is not needed.
    assert fit.texts[0] == SYSTEM_PROMPT and fit.texts[1] == TASK
    assert fit.texts[4] == items[4].text and fit.texts[5] == items[5].text
    assert "10.05 != 10.04" in fit.texts[2]


def test_dropping_uses_placeholders_oldest_first():
    items = _history(i4=HistoryItem("recent output", ContextRole.TOOL, protected=True))
    protected = _tokens(item.text for item in items if item.protected)
    fit = fit_history(items, protected + 20, min_tokens=10_000)  # nothing may be compressed
    assert fit.dropped == [2, 3]
    assert fit.texts[2] == placeholder_text(items[2], count_tokens(LOG))
    assert fit.texts[3].startswith("[") and "assistant message" in fit.texts[3]
    assert not fit.compressed


def test_placeholder_is_used_only_when_it_is_shorter():
    items = [HistoryItem("tiny", ContextRole.TOOL), HistoryItem(LOG, ContextRole.TOOL)]
    fit = fit_history(items, 30, min_tokens=10_000)
    assert fit.dropped == [1]
    assert fit.texts[0] == "tiny"


def test_remove_mode_drops_whole_groups_in_the_given_order():
    items = [
        HistoryItem(SYSTEM_PROMPT, ContextRole.SYSTEM, protected=True),
        HistoryItem("call search", ContextRole.ASSISTANT, compressible=False),
        HistoryItem(LOG, ContextRole.TOOL),
        HistoryItem("call search again", ContextRole.ASSISTANT, compressible=False),
        HistoryItem(make_log("b"), ContextRole.TOOL),
        HistoryItem(TASK, ContextRole.USER, protected=True),
    ]
    budget = _tokens([SYSTEM_PROMPT, TASK, "call search again", make_log("b")])
    fit = fit_history(
        items,
        budget,
        drop_order=[[0, 1], [], [1, 2], [3, 4]],
        drop="remove",
        min_tokens=10_000,
    )
    # [0, 1] holds a protected item and the empty group is skipped; [1, 2] goes as a whole.
    assert fit.texts[1] is None and fit.texts[2] is None
    assert fit.dropped == [1, 2]
    assert fit.texts[3:5] == [items[3].text, items[4].text]
    assert fit.fits


def test_recent_items_are_compressed_only_as_a_last_resort():
    items = _history()
    # Room for everything except the two logs: the old one goes first.
    budget = _tokens(item.text for i, item in enumerate(items) if i != 2) - 50
    fit = fit_history(items, budget, min_tokens=10_000)
    assert 2 in fit.dropped
    assert fit.texts[4] == items[4].text  # dropping the old log was enough

    # A budget below the recent log: it is compressed too, and keeps the failure.
    small = _tokens([SYSTEM_PROMPT, TASK, "Now add the changelog entry."]) + 150
    fit = fit_history(_history(), small)
    assert 4 in fit.compressed
    assert "10.05 != 10.04" in fit.texts[4]
    assert fit.fits


def test_older_items_are_refitted_after_the_recent_ones_are_compressed():
    items = [
        HistoryItem(SYSTEM_PROMPT, ContextRole.SYSTEM, protected=True),
        HistoryItem(make_log("old"), ContextRole.TOOL),
        HistoryItem(make_log("new", 400), ContextRole.TOOL, recent=True),
    ]
    budget = count_tokens(make_log("new", 400)) // 3
    fit = fit_history(items, budget, drop="remove")
    # The old log had no room while the recent one was whole; it gets some afterwards.
    assert fit.texts[1] is not None and 1 in fit.compressed
    assert not fit.dropped
    assert fit.fits and fit.tokens == _tokens(fit.texts)


def test_uncompressible_older_items_come_back_when_there_is_room():
    items = [
        HistoryItem(SYSTEM_PROMPT, ContextRole.SYSTEM, protected=True),
        HistoryItem("x " * 30, ContextRole.USER, compressible=False),
        HistoryItem(make_log("new", 400), ContextRole.TOOL, recent=True),
    ]
    budget = count_tokens(make_log("new", 400)) // 3
    fit = fit_history(items, budget, drop="remove")
    assert fit.texts[1] == items[1].text
    assert not fit.dropped and fit.fits


def test_older_groups_are_dropped_when_nothing_else_fits():
    items = [
        HistoryItem(SYSTEM_PROMPT, ContextRole.SYSTEM, protected=True),
        HistoryItem(NOTES * 20, ContextRole.ASSISTANT),
        HistoryItem("y " * 400, ContextRole.USER, compressible=False),
        HistoryItem(make_log("new", 400), ContextRole.TOOL, recent=True),
    ]
    budget = count_tokens(SYSTEM_PROMPT) + 120
    fit = fit_history(items, budget, drop="remove", drop_order=[[1], [2]])
    assert fit.texts[1] is None and fit.texts[2] is None
    assert fit.dropped == [1, 2]


def test_over_budget_when_the_protected_items_alone_exceed_it():
    items = _history()
    fit = fit_history(items, 5)
    assert not fit.fits
    assert fit.protected_tokens > 5
    assert "protected messages alone use" in fit.summary()
    assert fit.texts[0] == SYSTEM_PROMPT


def test_over_budget_when_what_is_left_cannot_shrink():
    items = [
        HistoryItem("tiny", ContextRole.TOOL, protected=True),
        HistoryItem("z " * 300, ContextRole.USER, compressible=False, recent=True),
    ]
    fit = fit_history(items, 50)
    assert not fit.fits
    assert "cannot be compressed or dropped" in fit.summary()


def test_summary_and_changed():
    fit = HistoryFit(texts=["a"], original_tokens=1200, tokens=300, budget=400, compressed=[0])
    assert fit.changed and fit.fits
    assert fit.summary() == "1,200 -> 300 tokens; budget 400; 1 compressed, 0 dropped"
    assert HistoryFit(texts=[], original_tokens=0, tokens=0, budget=None).summary() == (
        "0 -> 0 tokens; 0 compressed, 0 dropped"
    )


def test_placeholder_text_names_the_kind_of_content():
    assert placeholder_text(HistoryItem("x", ContextRole.TOOL), 1234) == (
        "[1,234 tokens of earlier tool output omitted by LLMSlim]"
    )
    assert "user message" in placeholder_text(HistoryItem("x", "user"), 5)
    assert "context" in placeholder_text(HistoryItem("x", ContextRole.RAG), 5)


def test_query_and_relevance_reach_the_compressor():
    scorer = PreferringScorer("refund")
    items = [HistoryItem(NOTES * 3, ContextRole.ASSISTANT)]
    fit = fit_history(items, count_tokens(NOTES), query="refund rounding", relevance=scorer)
    assert scorer.calls
    assert fit.fits and "refund" in fit.texts[0].lower()


def test_text_compressed_to_nothing_gets_a_placeholder(monkeypatch):
    def empty(self, text, target_ratio=0.5, query=None, context_role=None, **kwargs):
        return CompressionResult(
            original_text=text,
            compressed_text="  ",
            original_tokens=count_tokens(text),
            compressed_tokens=0,
            target_ratio=target_ratio,
            sentences_total=0,
            sentences_kept=0,
            num_chunks=0,
            backend="test",
            elapsed_ms=0.0,
        )

    monkeypatch.setattr(ContextCompressor, "compress", empty)
    items = [HistoryItem(LOG, ContextRole.TOOL)]
    fit = fit_history(items, 100)
    assert fit.texts[0] == placeholder_text(items[0], count_tokens(LOG))
    assert fit.compressed == [0]


def test_empty_history_and_empty_text():
    assert fit_history([], 10).texts == []
    fit = fit_history([HistoryItem("", ContextRole.TOOL)], 0)
    assert fit.texts == [""] and fit.fits


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_tokens": -1},
        {"min_tokens": True},
        {"min_tokens": 1.5},
        {"relevance": "psychic"},
        {"additional_compress_kwargs": {"context_role": "tool"}},
        {"additional_compress_kwargs": {"no_such_option": 1}},
        {"additional_compress_kwargs": {"selection": "random"}},
    ],
)
def test_invalid_options(kwargs):
    options = {"min_tokens": 50, "relevance": "lexical", "additional_compress_kwargs": None}
    options.update(kwargs)
    with pytest.raises(ValueError):
        validate_history_options(**options)


def test_invalid_fit_arguments():
    with pytest.raises(ValueError):
        fit_history([], 10, drop="delete")
    with pytest.raises(ValueError):
        fit_history([], -1)


def test_additional_options_are_used():
    items = [HistoryItem(NOTES * 3, ContextRole.ASSISTANT)]
    fit = fit_history(
        items, count_tokens(NOTES), additional_compress_kwargs={"selection": "proportional"}
    )
    assert fit.fits and fit.compressed == [0]


def test_first_edited_is_the_first_changed_or_dropped_message():
    fit = HistoryFit(
        texts=[], original_tokens=0, tokens=0, budget=None, compressed=[3], dropped=[5]
    )
    assert first_edited(fit, [0, 1, 1, 2, 2, 3]) == 2
    assert first_edited(fit, range(6)) == 3
    unchanged = HistoryFit(texts=[], original_tokens=0, tokens=0, budget=None)
    assert first_edited(unchanged, range(6)) is None


@pytest.mark.parametrize(
    ("kinds", "thinking", "expected"),
    [
        # The latest model turn calls a tool and its result is back: the round is open.
        ([PROMPT, CALL, OTHER], [False, True, False], (1, 2)),
        # The tool has not run yet.
        ([PROMPT, REPLY, PROMPT, CALL], [False, True, False, True], (3, 4)),
        # Several steps in one round: everything up to the last thinking stays.
        ([PROMPT, CALL, OTHER, CALL, OTHER], [False, True, False, True, False], (1, 4)),
        ([PROMPT, CALL, OTHER, CALL, OTHER], [False, True, False, False, False], (1, 2)),
        # Thinking before the latest user message is not part of the round.
        ([PROMPT, REPLY, PROMPT, CALL, OTHER], [False, True, False, False, False], None),
        # A new user message closes the round; so does a final answer.
        ([PROMPT, CALL, OTHER, PROMPT], [False, True, False, False], None),
        ([PROMPT, CALL, OTHER, REPLY], [False, True, False, True], None),
        ([OTHER, PROMPT], [False, False], None),
        ([], [], None),
        # No user message at all: the round starts at the beginning.
        ([OTHER, CALL, OTHER], [False, True, False], (0, 2)),
    ],
)
def test_open_tool_round(kinds, thinking, expected):
    assert open_tool_round(kinds, thinking) == expected


def test_protect_before_protects_whole_messages():
    items = [HistoryItem(LOG, ContextRole.TOOL) for _ in range(4)]
    guarded = protect_before(items, [0, 1, 1, 2], 2)
    assert [item.protected for item in guarded] == [True, True, True, False]
    assert not any(item.protected for item in items)  # the input is not changed


def test_a_protected_prefix_is_left_alone_and_what_follows_is_compressed():
    items = [
        HistoryItem(SYSTEM_PROMPT, ContextRole.SYSTEM, protected=True),
        HistoryItem(LOG, ContextRole.TOOL),
        HistoryItem(NOTES, ContextRole.ASSISTANT),
        HistoryItem(make_log("new", 300), ContextRole.TOOL, recent=True),
    ]
    budget = _tokens([SYSTEM_PROMPT, LOG, NOTES]) + 120
    fit = fit_history(protect_before(items, range(4), 3), budget)
    assert fit.texts[:3] == [SYSTEM_PROMPT, LOG, NOTES]
    assert fit.compressed == [3] and fit.fits
    assert first_edited(fit, range(4)) == 3


def test_is_signed_thinking_for_dicts_and_sdk_objects():
    assert is_signed_thinking({"type": "thinking", "thinking": "", "signature": "abc"})
    assert is_signed_thinking({"type": "redacted_thinking", "data": "abc"})
    assert not is_signed_thinking({"type": "thinking", "thinking": "x", "signature": ""})
    assert not is_signed_thinking({"type": "redacted_thinking"})
    assert not is_signed_thinking({"type": "text", "text": "x", "signature": "abc"})
    assert is_signed_thinking(SimpleNamespace(type="thinking", thinking="", signature="abc"))
    assert not is_signed_thinking(SimpleNamespace(type="tool_use", id="t1"))
    assert not is_signed_thinking("thinking")


def test_summary_reports_removed_thinking_and_a_kept_tool_round():
    fit = HistoryFit(texts=[], original_tokens=900, tokens=500, budget=600, compressed=[1])
    fit.thinking_stripped = 2
    assert fit.summary() == (
        "900 -> 500 tokens; budget 600; 1 compressed, 0 dropped; "
        "2 thinking block(s) removed after the first change"
    )
    waiting = HistoryFit(texts=[], original_tokens=900, tokens=800, budget=600, protected_tokens=10)
    waiting.kept_tool_round = True
    assert waiting.summary().endswith(
        "still over budget: earlier messages wait for the open tool round to end"
    )
