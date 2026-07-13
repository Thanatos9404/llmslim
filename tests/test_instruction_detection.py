"""Instruction detection & preservation tests for llmslim."""

from __future__ import annotations

import pytest

from llmslim import compress
from llmslim.ranking import _CRITICAL_RE, _instruction_score

INSTRUCTION_PATTERNS = {
    "Role definition": "You are an expert cloud architect and senior backend engineer.",
    "Prohibition": "Never suggest deprecated APIs or unencrypted HTTP connections.",
    "Obligation": "You must always validate user input with pydantic models.",
    "Requirement": "Ensure all database queries use parameterized prepared statements.",
    "JSON Output": "Respond in valid JSON matching the schema provided above.",
    "Markdown Output": "Format your response using Markdown headings and bullet lists.",
    "Warning label": "WARNING: Deleting table records causes irreversible data loss.",
    "Constraint limit": "Limit response length to at most 200 words.",
    "Tool usage": "Use the tool python_interpreter to execute complex math calculations.",
    "Code block directive": "Always format code using triple backticks: ```python",
    "Safety directive": "Refrain from generating harmful, offensive, or illegal content.",
    "System label": "System: Respond only with exact entity matches.",
}


@pytest.mark.parametrize("category,sentence", list(INSTRUCTION_PATTERNS.items()))
def test_instruction_score_detection(category, sentence):
    """Verify that _instruction_score detects instructions across all directive categories."""
    score = _instruction_score(sentence)
    assert score > 0.0, f"Failed to detect instruction signal in category '{category}'"


@pytest.mark.parametrize("category,sentence", list(INSTRUCTION_PATTERNS.items()))
def test_critical_pattern_matching(category, sentence):
    """Verify that high-confidence directive patterns match _CRITICAL_RE."""
    # Sentences containing must, never, you are, WARNING:, etc. match critical patterns
    if category in ["Role definition", "Prohibition", "Obligation", "Requirement", "Warning label"]:
        assert (
            _CRITICAL_RE.search(sentence) is not None
        ), f"Category '{category}' should match critical directive pattern"


def test_instruction_preservation_ratio():
    """Verify that instructions are prioritized over filler text during compression."""
    prompt = (
        "This document describes background context about software design. "
        "Background details can sometimes be long and verbose. "
        "You are an expert AI software engineer. "
        "You must always provide type hints in Python functions. "
        "Never use global state variables. "
        "This is an extra sentence containing generic background information. "
        "Another sentence with non-essential details about history. "
        "Always test code with pytest before deploying to production."
    )

    result = compress(prompt, target_ratio=0.5)
    compressed = result.compressed_text

    # Instructions should be preserved
    assert "You are an expert AI software engineer" in compressed or "You must always" in compressed
    assert "Never use global state" in compressed or "Always test code" in compressed
