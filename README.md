# LLMSlim v0.4.0

LLMSlim is a Python library for extractive, rewrite, and hybrid LLM-context
compression. Its default compression path remains local and deterministic.

## Tool-aware context, without rewriting the contract

v0.4.0 introduces a contract-safe tool-schema layer for agent and MCP
workflows. It can normalize supported provider shapes, deterministically
canonicalize copied JSON, fingerprint complete definitions with SHA-256, check
exact contract equivalence, and measure safe catalog representation changes.
Authoritative raw schemas are never rewritten for execution.

Tool retrieval is included for research only. TF-IDF, BM25, optional semantic
retrieval, hybrid RRF, selective exposure, and lazy hydration are not enabled
by `compress()` and must not be used as authorization or execution decisions.

## Install

```bash
pip install llmslim

# Optional local semantic retrieval support
pip install "llmslim[semantic]"
```

Python 3.8+ is supported. The semantic extra is optional; the normal package
does not require `sentence-transformers`, PyTorch, or model downloads.

## Compression quick start

```python
from llmslim import ContextRole, compress

result = compress(
    "Long context goes here...",
    target_ratio=0.5,
    strategy="extractive",
    context_role=ContextRole.GENERAL,
)

print(result.compressed_text)
print(result.original_tokens, result.compressed_tokens)
```

`extractive` is the default local strategy. `rewrite` and `hybrid` require a
caller-supplied provider. See [SECURITY.md](SECURITY.md) for the provenance
boundary applied to `ContextRole` values.

## Stable tool-contract APIs

Import stable tool-contract APIs from `llmslim.tools`:

```python
from llmslim.tools import (
    canonical_json,
    contract_equivalent,
    fingerprint_tool_schema,
    from_mcp_tool,
    optimize_tool_schema,
)

raw = {
    "name": "calendar.search_events",
    "description": "Find calendar events.",
    "inputSchema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
}

tool = from_mcp_tool(raw, namespace="calendar")
result = optimize_tool_schema(tool)

assert result.equivalence.status.value == "EXACT"
assert fingerprint_tool_schema(tool) == fingerprint_tool_schema(result.optimized)
print(canonical_json(result.optimized.raw))
```

Supported adapters cover MCP, OpenAI function, Anthropic tools, and a generic
shape. They preserve copied raw definitions; cross-provider output is an
adapter view, not proof that another provider will accept or authorize it.
Read the [tool API guide](docs/tool-apis.md) before integrating.

## Experimental tool retrieval — research only

```python
from llmslim.tool_retrieval import BM25ToolRetriever
from llmslim.tools import from_mcp_tool

catalog = [from_mcp_tool(raw, namespace="calendar")]
hits = BM25ToolRetriever(catalog).rank("find my events", limit=1)
print(hits[0].tool.tool_id)
```

The optional dense backend uses `intfloat/multilingual-e5-small` at pinned
revision `0e60b8d9d2166d80387f86e3b48ec9ced55f4d15`. It is local-cache-only:
the package never downloads it automatically. Details and limitations are in
[the experimental retrieval guide](docs/tool-apis.md#experimental-tool-retrieval).

## Benchmarks and limitations

The v0.4.0 schema-tax measurement covers 375 schemas across 18 catalogs. Its
lossless reduction was **0 tokens (0.00%)**, because the baseline was already
compact canonical JSON. That valid result is not hidden or generalized as a
universal schema-savings claim.

On the frozen Phase 4.5/4.6 corpus, dynamic retrieval policies retained about
98% all-required recall by failing open to the full catalog frequently; median
tokens avoided was zero. Dense and hybrid retrieval did not improve the
safety–selectivity frontier. Retrieval therefore remains **RESEARCH_ONLY**.

External ToolRet validation was attempted but not completed within the declared
CPU/resource budget; no ToolRet metric is claimed. See the checked-in
[Phase 4 report](docs/phase-4/BENCHMARK_REPORT.md),
[Phase 4.5 report](docs/phase-4.5/BENCHMARK_REPORT.md), and
[Phase 4.6 report](docs/phase-4.6/BENCHMARK_REPORT.md).

## Availability

v0.4.0 ships a Python package only. There is no published `@llmslim/core` npm
package, Rust engine, or WASM runtime. Those remain future possibilities, not
current product capabilities.

## Release and security information

See [CHANGELOG.md](CHANGELOG.md), [release notes](release_notes.md), and
[SECURITY.md](SECURITY.md). Report vulnerabilities privately as described in
the security policy.

## License

MIT. See [LICENSE](LICENSE).
