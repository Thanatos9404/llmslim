"""Offline optional dense/hybrid retrieval tests; no model artifact is loaded."""

from __future__ import annotations

import copy
import sys
import types

import pytest

from llmslim.semantic_retrieval import (
    DenseToolRetriever,
    HybridRRFToolRetriever,
    SemanticDependencyError,
    SemanticModelConfig,
    SentenceTransformerBackend,
    semantic_query_text,
    semantic_tool_text,
)
from llmslim.tool_retrieval import BM25ToolRetriever
from llmslim.tools import from_mcp_tool


class _Backend:
    identity = "fake|revision-a|representation-v1|l2|cpu"

    def encode(self, texts):
        vectors = []
        for text in texts:
            lower = text.casefold()
            vectors.append((1.0 if "calendar" in lower else 0.0, 1.0 if "code" in lower else 0.0))
        return tuple(vectors)


def _tool(name: str, description: str, meta=None):
    return from_mcp_tool(
        {
            "name": name,
            "server": "phase46",
            "description": description,
            "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
            "_meta": meta or {},
            "annotations": {"untrusted": "ignore"},
        }
    )


def test_dense_and_rrf_are_deterministic_and_model_fingerprint_keyed():
    calendar, code = (
        _tool("calendar_lookup", "Find calendar meetings."),
        _tool("code_lookup", "Search source code."),
    )
    DenseToolRetriever.clear_cache()
    dense = DenseToolRetriever.cached([calendar, code], _Backend())
    assert dense.rank("calendar appointment")[0].tool == calendar
    assert DenseToolRetriever.cached([calendar, code], _Backend()) is dense
    changed_backend = _Backend()
    changed_backend.identity = "fake|revision-b|representation-v1|l2|cpu"
    assert DenseToolRetriever.cached([calendar, code], changed_backend) is not dense
    hybrid = HybridRRFToolRetriever(BM25ToolRetriever([calendar, code]), dense)
    assert hybrid.rank("calendar meeting")[0].tool == calendar
    with pytest.raises(ValueError, match="identically ordered"):
        HybridRRFToolRetriever(BM25ToolRetriever([code, calendar]), dense)


def test_representation_excludes_untrusted_fields_and_bounds_descriptions():
    tool = _tool("calendar_lookup", "calendar " * 10_000, {"instruction": "code " * 10_000})
    text = semantic_tool_text(tool)
    assert "instruction" not in text
    assert len(text.split()) <= 400
    assert semantic_query_text("Calendar_Query") == "query: calendar query"
    raw = tool.authoritative_copy()
    before = copy.deepcopy(raw)
    DenseToolRetriever([tool], _Backend()).rank("calendar")
    assert raw == before


def test_sentence_backend_is_local_only_and_missing_dependency_is_clear(monkeypatch):
    class _Model:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def encode(self, texts, **kwargs):
            return [[3.0, 4.0] for _ in texts]

    fake_module = types.SimpleNamespace(SentenceTransformer=_Model)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    backend = SentenceTransformerBackend(SemanticModelConfig(model_id="pinned", revision="abc"))
    assert backend.encode(["x"])[0] == pytest.approx((0.6, 0.8))
    assert backend._model.kwargs["local_files_only"] is True
    assert backend._model.kwargs["trust_remote_code"] is False
    monkeypatch.delitem(sys.modules, "sentence_transformers", raising=False)
    original_import = __import__

    def _missing(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _missing)
    with pytest.raises(SemanticDependencyError, match="optional"):
        SentenceTransformerBackend().encode(["x"])
