# Tool APIs

LLMSlim v0.4.0 separates stable tool-contract infrastructure from
**EXPERIMENTAL / RESEARCH_ONLY** retrieval. Neither area authorizes a tool,
executes a tool, fetches remote references, or authenticates provenance.

## Stable tool-contract infrastructure

Import from `llmslim.tools`.

```python
from llmslim.tools import (
    canonical_json,
    contract_equivalent,
    fingerprint_tool_schema,
    from_mcp_tool,
    inspect_schema,
    optimize_tool_catalog,
)
```

`from_mcp_tool`, `from_openai_tool`, `from_anthropic_tool`, and
`from_generic_tool` copy a supported provider definition into `ToolSchema`.
`ToolSchema.authoritative_copy()` returns a fresh copy for an executor. Adapter
output is a representation; callers must validate it with the target provider.

`canonical_json(value)` produces compact, deterministic JSON while retaining
every value and array order. `fingerprint_tool_schema(tool)` calculates SHA-256
over the complete canonical raw definition. `contract_equivalent(before, after)`
returns `EXACT` only when complete canonical definitions match; it never claims
general JSON Schema semantic equivalence.

```python
raw = {
    "name": "calendar.search_events",
    "description": "Find calendar events.",
    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
}
tool = from_mcp_tool(raw, namespace="calendar")

inspection = inspect_schema(tool.input_schema or {})
print(inspection.valid_json_value, inspection.warnings)

catalog = optimize_tool_catalog([tool])
assert catalog.per_tool[0].equivalence.status.value == "EXACT"
assert fingerprint_tool_schema(tool) == fingerprint_tool_schema(catalog.optimized[0])
print(canonical_json(catalog.optimized[0].raw))
```

Schema inspection does not dereference external `$ref` values. The only
production operator is deterministic canonical JSON serialization; it is kept
only after an exact complete-contract check.

## Experimental tool retrieval

> **RESEARCH ONLY — NOT ENABLED AUTOMATICALLY.**

`llmslim.tool_retrieval` provides local deterministic TF-IDF and BM25 ranking.
`llmslim.semantic_retrieval` provides optional dense and hybrid RRF ranking.
Their bounded representations exclude annotations and `_meta`; full raw
schemas are never used as executable output of ranking.

```python
from llmslim.tool_retrieval import BM25ToolRetriever

hits = BM25ToolRetriever([tool]).rank("find calendar events", limit=1)
for hit in hits:
    print(hit.rank, hit.tool.tool_id, hit.score)
```

`select_tools`, `plan_tool_context`, and `LazyToolRegistry` are also
experimental. A selected schema is a model-context suggestion only. Execution
must use an independently validated authoritative contract and application
authorization policy. Conservative policies intentionally fail open to the
full catalog when ranking is weak or ambiguous.

## Optional semantic retrieval

Install explicitly:

```bash
pip install "llmslim[semantic]"
```

The backend uses the off-the-shelf MIT-licensed
`intfloat/multilingual-e5-small` model, pinned to
`0e60b8d9d2166d80387f86e3b48ec9ced55f4d15`. It produces 384-dimensional
embeddings. LLMSlim does not train or include model weights. Runtime loading is
CPU-only, `local_files_only=True`, and `trust_remote_code=False`; the caller
must explicitly cache the pinned model first. A missing dependency or model
raises `SemanticDependencyError` rather than downloading anything.

```python
from llmslim.semantic_retrieval import DenseToolRetriever, SentenceTransformerBackend

backend = SentenceTransformerBackend()  # lazy; local cache only
retriever = DenseToolRetriever([tool], backend)
print(retriever.rank("find calendar events", limit=1)[0].tool.tool_id)
```

The frozen Phase 4.6 evidence does not support a production retrieval claim:
dense and hybrid policies fail open frequently and have zero median token
avoidance. See `docs/phase-4.6/` for the protocol, model card, and reports.
