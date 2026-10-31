"""Memory.search output on fixed histories (tests/_memory_search_cases.py), pinned in a golden file."""

from __future__ import annotations

import json

import pytest

from llmslim.memory import InMemoryStore, SQLiteStore
from llmslim.tokens import get_active_token_counter_name
from tests import _memory_search_cases as cases

GOLDEN = json.loads(cases.GOLDEN.read_text(encoding="utf-8"))
needs_tiktoken = pytest.mark.skipif(
    get_active_token_counter_name() != "tiktoken",
    reason="the golden output was recorded with tiktoken's cl100k_base",
)
CASE_IDS = [case[0] for case in cases.CASES]


@pytest.fixture
def splitter():
    with cases.builtin_splitter():
        yield


def store_for(kind, tmp_path):
    return InMemoryStore() if kind == "memory" else SQLiteStore(tmp_path / "memory.db")


def test_every_case_is_pinned():
    assert sorted(GOLDEN) == sorted(CASE_IDS)


@needs_tiktoken
@pytest.mark.parametrize("kind", ["memory", "sqlite"])
@pytest.mark.parametrize("case", cases.CASES, ids=CASE_IDS)
def test_search_output_matches_the_golden_file(case, kind, tmp_path, splitter):
    pinned = cases.pinned(cases.run(case, store_for(kind, tmp_path)))
    expected = GOLDEN[case[0]]
    assert pinned["text"] == expected["text"]
    assert pinned == expected
