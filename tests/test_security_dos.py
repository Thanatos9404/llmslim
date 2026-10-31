"""Hostile input stays cheap: the 1.0 security audit's regression tests for algorithmic denial of service.

Each test runs a pathological input against the real code with a generous time bound. Before the fixes each of them
took from tens of seconds to many minutes at these sizes (quadratic time); after them, a small fraction of a second.
The bounds leave room for slow CI machines. ``llmslim serve`` (/v1/context/fit, search), ``llmslim mcp``
(fit_context), the website's Studio functions and the proxy all run this code on text they did not write.
"""

from __future__ import annotations

import re
import time
import unicodedata

import pytest

from llmslim import compress, plan_context
from llmslim._fit import fit_text
from llmslim.analysis import analyze
from llmslim.optimizers.markdown_opt import optimize_markdown
from llmslim.optimizers.xml_opt import optimize_xml
from llmslim.optimizers.yaml_opt import _regex_fallback_optimize
from llmslim.tokenization import split_sentences
from llmslim.tokens import count_tokens

BOUND = 5.0  # seconds; the fixed code takes well under one


@pytest.fixture(autouse=True, scope="module")
def _warm():
    # Load the tokenizer and the lazily imported modules first, so each bound times only the work.
    compress("Warm the tokenizer up. Then time only the work.", target_ratio=0.5, query="warm")


def _seconds(function, *args, **kwargs) -> float:
    started = time.perf_counter()
    function(*args, **kwargs)
    return time.perf_counter() - started


@pytest.mark.parametrize("unit", ["```", "`a`", "`a` ```b``` "])
def test_code_span_placeholders_are_restored_in_linear_time(unit):
    # Each span became a placeholder that was then searched for in every sentence: quadratic in the span count.
    text = unit * (300_000 // len(unit))
    assert _seconds(split_sentences, text) < BOUND
    assert _seconds(compress, text, target_ratio=0.25, query="x") < BOUND


def test_code_span_restoration_is_unchanged():
    text = "Use `a ```code``` b` now. Then ```x. y``` ok. And `c.d` here. Odd \x00BLOCK7\x00 stays."
    assert split_sentences(text) == [
        "Use `a ```code``` b` now.",
        "Then ```x. y``` ok.",
        "And `c.d` here.",
        "Odd \x00BLOCK7\x00 stays.",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "\n" * 200_000,  # every ^\s* pattern rescanned the rest of a blank run from each line start
        " \n" * 100_000,
        "\r\n" * 100_000,
        "[" * 100_000,  # \[([^\]]+)\] scanned to the end from every "["
        "[a" * 50_000,
        "](" * 50_000 + "[a](" * 25_000,
        "<a " * 40_000,  # <tag\s[^>]*> scanned to the end from every "<a"
    ],
)
def test_content_detection_is_linear(text):
    assert _seconds(analyze, text) < BOUND


def test_planning_hostile_structure_stays_bounded():
    # The website's /api/plan and /api/context take 96,000 characters; "[" took 12 s at 90,000.
    def plan(text: str) -> float:
        return _seconds(
            plan_context,
            messages=[{"role": "user", "content": text}],
            documents=[text],
            query="what changed?",
            model="sarvam-105b",
            max_input_tokens=8192,
            reserve_output_tokens=1024,
            safety_margin_tokens=128,
            policy="balanced",
        )

    plan("Warm the planner up. It loads lazily.")
    for unit in ("[", "\n", "<a "):
        assert plan(unit * (45_000 // len(unit))) < BOUND, unit


def test_list_item_priority_patterns_are_linear():
    from llmslim import ranking

    for pattern in (ranking._CRITICAL_RE, ranking._MEDIUM_PRIORITY_RE):
        assert _seconds(list, pattern.finditer("\n" * 200_000)) < BOUND
        assert pattern.search("intro\n  - keep this item")
        assert pattern.search("  12) numbered")


@pytest.mark.parametrize("unit", [" ", "\t", " ", "\t#"])
def test_yaml_inline_comments_are_stripped_in_linear_time(unit):
    line = "key: value" + unit * (200_000 // len(unit)) + "x"
    assert _seconds(_regex_fallback_optimize, line) < BOUND


def test_yaml_inline_comment_stripping_is_unchanged():
    old = re.compile(r"\s+#.*$", re.MULTILINE)
    lines = [
        "key: value  # note",
        "a  b #c",
        "url: http://x#frag",
        "tabs:\tvalue\t\t# c",
        "nbsp: v # c",
        "plain: value",
        "x: '#not a comment'",
    ]
    for line in lines:
        assert _regex_fallback_optimize(line) == old.sub("", line).strip() or not old.sub("", line)


@pytest.mark.parametrize("unit", ["\t", "#\t", ".\t", "\t#"])
def test_codeql_flagged_sentence_and_heading_patterns_are_linear(unit):
    # CodeQL py/polynomial-redos flagged these for runs of "\t"; they are linear (the alerts are false positives).
    text = unit * (300_000 // len(unit))
    assert _seconds(split_sentences, text) < BOUND
    assert _seconds(optimize_markdown, "# " + text, 0.5) < BOUND
    assert _seconds(optimize_markdown, (unit + "\n") * 50_000, 0.5) < BOUND


def test_fit_holds_its_budget_on_any_input():
    # Compression keeps a code block whole; fit_text used to return all 600,000+ tokens of one for a budget of 2,000.
    for text in ("`a`" * 100_000, "```\n" + "x = 1\n" * 30_000 + "```", "word " * 60_000):
        fitted = fit_text(text, 2000, "x")
        assert 0 < count_tokens(fitted) <= 2000 * 1.02


def test_entity_declarations_never_reach_the_xml_parser():
    lol = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        + "".join(
            f'<!ENTITY lol{i} "' + ("&lol;" if i == 1 else f"&lol{i - 1};") * 10 + '">'
            for i in range(1, 10)
        )
        + "]><lolz>&lol9;</lolz>"
    )
    quadratic = '<!DOCTYPE d [<!ENTITY a "' + "x" * 50_000 + '">]><d>' + "&a;" * 50_000 + "</d>"
    external = '<!DOCTYPE d [<!ENTITY e SYSTEM "file:///etc/passwd">]><d>&e;</d>'
    for bomb in (lol, quadratic, external):
        started = time.perf_counter()
        assert optimize_xml(bomb, 0.5) is None
        assert time.perf_counter() - started < 1.0
    # Ordinary XML, with or without a DOCTYPE that declares nothing, is still optimised.
    items = "".join(f"<item>{k}</item>" for k in range(20))
    for document in (f"<root>{items}</root>", f"<!DOCTYPE root><root>{items}</root>"):
        assert optimize_xml(document, 0.5).count("<item>") < 20


def test_web_search_control_character_classes_are_exactly_c0_and_c1():
    # CodeQL py/overly-large-range flagged \x0e-\x1f and \x0b-\x1f; they are the intended C0/C1 control ranges.
    from llmslim.integrations import web_search

    for code in range(0x10000):
        char = chr(code)
        control = unicodedata.category(char) == "Cc"
        assert bool(web_search._QUERY_CONTROL_RE.search(char)) == (control and char not in "\t\n\r")
        assert bool(web_search._CONTROL_RE.search(char)) == (control and char not in "\t\n")
