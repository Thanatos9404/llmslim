"""JSON tool results keep every list item, compactly, instead of a window of lines."""

from __future__ import annotations

import json

import pytest

from llmslim._json_output import shorten_json
from llmslim._tool_output import shorten_tool_output
from llmslim.tokens import count_tokens


def issues(n: int = 80, special: int = 57) -> list:
    return [
        {
            "number": 4000 + i,
            "title": "Refund rounding is off by one cent for half-even amounts"
            if i == special
            else f"Flaky test in module {i % 17}",
            "state": "open",
            "user": {"login": f"user{i}", "id": 1000 + i, "type": "User"},
            "labels": [{"name": "bug"}, {"name": f"area-{i % 5}"}],
            "comments": i % 9,
            "created_at": f"2026-09-{1 + i % 28:02d}T10:00:00Z",
            "body": "Steps to reproduce: run the suite twice. " * 3,
        }
        for i in range(n)
    ]


def item_lines(text: str) -> list:
    return [json.loads(line) for line in text.splitlines() if line.startswith("{")]


def test_every_item_stays_and_the_related_one_is_whole():
    text = json.dumps(issues(), indent=2)
    out = shorten_json(text, 3500, "refund rounding")
    items = item_lines(out)
    assert [i["number"] for i in items] == list(range(4000, 4080))
    special = next(i for i in items if i["number"] == 4057)
    assert special["labels"] == [{"name": "bug"}, {"name": "area-2"}] and special[
        "body"
    ].startswith("Steps")
    other = next(i for i in items if i["number"] == 4000)
    assert set(other) <= {
        "number",
        "title",
        "state",
        "created_at",
        "body",
        "user",
        "labels",
        "comments",
    }
    assert out.splitlines()[0].startswith("JSON list at (top level): 80 items")
    assert count_tokens(out) <= 3500


def test_compaction_levels_are_tried_before_anything_is_dropped():
    text = json.dumps(issues(), indent=2)
    roomy = item_lines(shorten_json(text, 9000))
    assert (
        roomy[0]["user"] == {"login": "user0", "id": 1000, "type": "User"}
        and roomy[0]["labels"] == "[2 items]"
    )
    assert roomy[0]["body"].endswith("…") and len(roomy[0]["body"]) <= 80
    tight = item_lines(shorten_json(text, 3500))
    assert len(tight) == 80 and set(tight[0]) == {"number", "title", "state", "created_at"}


def test_items_are_dropped_from_the_middle_with_a_marker_naming_them():
    text = json.dumps(issues(200), indent=2)
    out = shorten_json(text, 1500, "refund rounding")
    marker = next(line for line in out.splitlines() if line.startswith("…"))
    numbers = [i["number"] for i in item_lines(out)]
    assert 4057 in numbers and 4000 in numbers and 4199 in numbers  # related, first and last stay
    dropped = int(marker.split()[1].lstrip("["))
    assert dropped == 200 - len(numbers) and "more items not shown" in marker
    assert count_tokens(out) <= 1500 * 1.03


def test_lists_inside_envelopes_keep_the_envelope():
    text = json.dumps({"total_count": 80, "incomplete_results": False, "items": issues()}, indent=2)
    out = shorten_json(text, 3500)
    lines = out.splitlines()
    assert (
        lines[0].startswith("JSON list at .items: 80 items")
        and lines[1] == 'Around the list: {"total_count":80,"incomplete_results":false}'
    )
    assert len(item_lines(out)) == 80


@pytest.mark.parametrize(
    "text",
    [
        "[INFO] server started on :8080\n[INFO] ready",
        "plain text",
        "",
        json.dumps({"a": 1, "b": "two"}),
        json.dumps([1, 2]),
        json.dumps("a string"),
    ],
)
def test_anything_else_is_left_to_the_line_based_path(text):
    assert shorten_json(text, 500) is None


def test_scalar_lists_and_determinism():
    numbers = json.dumps(list(range(3000)))
    out = shorten_json(numbers, 400)
    assert out is not None and "more items not shown" in out
    text = json.dumps(issues(), indent=2)
    assert shorten_json(text, 2600, "refund") == shorten_json(text, 2600, "refund")


def test_the_tool_output_note_says_what_was_kept():
    new_text, before, after = shorten_tool_output(json.dumps(issues(), indent=2), "refund rounding")
    assert (
        new_text.startswith("[LLMSlim shortened this tool output from")
        and "every list item" in new_text
    )
    assert before > after * 3
    log = "\n".join(f"line {i} ok" for i in range(2000)) + "\nERROR: disk full"
    text, _, _ = shorten_tool_output(log, None)
    assert "errors and the lines most related" in text and "ERROR: disk full" in text


def test_bash_printing_json_goes_through_the_json_path():
    from llmslim.proxy import ProxyStore, rewrite_request

    body = {
        "messages": [
            {"role": "user", "content": "List the open issues."},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "c1",
                        "name": "Bash",
                        "input": {"command": "gh issue list --json number,title,body"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "c1",
                        "content": json.dumps(issues(), indent=2),
                    }
                ],
            },
        ]
    }
    new_body, report = rewrite_request(body, ProxyStore())
    text = new_body["messages"][-1]["content"][0]["content"]
    assert report.compressed == 1 and "JSON list at (top level): 80 items" in text
