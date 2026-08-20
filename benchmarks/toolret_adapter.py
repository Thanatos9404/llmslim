"""Optional adapter for the official externally downloaded ToolRet data.

This module is benchmark-only.  It neither vendors ToolRet data nor changes
LLMSlim package dependencies; callers explicitly provide the downloaded root.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Sequence

from llmslim.semantic_retrieval import (
    DenseToolRetriever,
    HybridRRFToolRetriever,
    SentenceTransformerBackend,
)
from llmslim.tool_retrieval import BM25ToolRetriever
from llmslim.tools import from_mcp_tool


class ToolRetAdapterError(RuntimeError):
    """Raised when the optional external benchmark data is unavailable."""


def _read_parquet(path: Path) -> Any:
    try:
        import pyarrow.parquet as parquet  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ToolRetAdapterError(
            "ToolRet adapter needs benchmark-only pyarrow; it is not an LLMSlim dependency."
        ) from exc
    return parquet.read_table(path).to_pylist()


def _metric(
    ranks: Sequence[Sequence[str]], labels: Sequence[Sequence[str]], k: int
) -> Dict[str, float]:
    recalls, all_required, reciprocal = [], [], []
    for ranked, expected_values in zip(ranks, labels):
        expected, top = set(expected_values), list(ranked[:k])
        recalls.append(len(expected & set(top)) / len(expected) if expected else 1.0)
        all_required.append(float(expected.issubset(set(top))))
        first = next((index + 1 for index, value in enumerate(top) if value in expected), None)
        reciprocal.append(1.0 / first if first else 0.0)
    return {
        "required_tool_recall": sum(recalls) / len(recalls),
        "all_required_recall": sum(all_required) / len(all_required),
        "mrr_at_k": sum(reciprocal) / len(reciprocal),
    }


def run_toolret_apibank_web(root: Path) -> Dict[str, Any]:
    """Run the predeclared 101-query ApiBank/web-corpus representative subset.

    It is intentionally labelled a subset: all 101 official ApiBank queries are
    ranked against the complete official ToolRet `web` corpus, not against the
    whole 43k-tool multi-category benchmark.
    """
    query_file = root / "queries" / "apibank" / "queries-00000-of-00001.parquet"
    tool_file = root / "tools" / "web" / "tools-00000-of-00001.parquet"
    if not query_file.exists() or not tool_file.exists():
        raise ToolRetAdapterError(
            "expected ToolRet ApiBank queries and web tools under supplied root"
        )
    queries, source_tools = _read_parquet(query_file), _read_parquet(tool_file)
    catalog = [
        from_mcp_tool(
            {
                "name": str(row["id"]),
                "server": "toolret",
                "description": str(row["documentation"])[:64_000],
                "inputSchema": {"type": "object", "properties": {}},
            }
        )
        for row in source_tools
    ]
    expected = [
        ["toolret/" + str(label["id"]) for label in json.loads(row["labels"])] for row in queries
    ]
    bm25 = BM25ToolRetriever(catalog)
    dense = DenseToolRetriever(catalog, SentenceTransformerBackend())
    hybrid = HybridRRFToolRetriever(bm25, dense, rrf_k=60)
    results: Dict[str, Any] = {}
    for name, retriever in (("bm25", bm25), ("dense", dense), ("hybrid_rrf", hybrid)):
        started = time.perf_counter()
        ranks = [
            [hit.tool.tool_id for hit in retriever.rank(str(row["query"]), limit=20)]
            for row in queries
        ]
        elapsed = (time.perf_counter() - started) * 1000
        results[name] = {
            "recall_at": {str(k): _metric(ranks, expected, k) for k in (5, 10, 20)},
            "total_query_latency_ms": elapsed,
            "mean_query_latency_ms": elapsed / len(queries),
        }
    return {
        "status": "SUBSET",
        "label": "TOOLRET SUBSET — NOT FULL BENCHMARK",
        "dataset": {
            "queries_repo": "mangopy/ToolRet-Queries",
            "queries_revision": "b8c76ad3349ff17497b6bdb28bb5b8f61a0f6445",
            "tools_repo": "mangopy/ToolRet-Tools",
            "tools_revision": "e06c38c75612b6536bd959e08cdd345894aba6a7",
            "task": "apibank",
            "query_count": len(queries),
            "tool_category": "web",
            "tool_count": len(catalog),
        },
        "representation": "LLMSlim semantic_tool_text_v1; external documentation is capped at 64K characters before bounded retrieval text; no metadata",
        "results": results,
    }
