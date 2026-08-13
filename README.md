# LLMSlim v0.3.1

LLMSlim is a Python library for extractive, rewrite, and hybrid LLM-context compression. It uses offline TF-IDF and sentence-ranking signals to reduce redundant context while preserving high-value content.

> **v0.3.1 security hardening:** LLMSlim mitigates compression-induced instruction elevation by preventing untrusted RAG/tool/assistant content from gaining protected priority through imperative or safety-critical wording. This is a compression safety boundary, not complete prompt-injection prevention.

## What's new in v0.3.1

- Adds provenance-aware `ContextRole` priority handling.
- Caps untrusted `rag`, `tool`, and `assistant` content at Tier 2 and prevents it from becoming `must_keep`.
- Protects inline code spans and adds CJK sentence boundaries (`。`, `！`, `？`).
- Uses nonce-tagged rewrite fences when a payload contains fence-like text, without changing the payload.
- Exposes `CompressionResult.token_counter_used` and warns once when the heuristic token fallback is active.
- Makes the benchmark runner report observed pytest results instead of hardcoded counts.
- Removes unused selection helpers.

## Verified release gate

| Check | Result |
| --- | --- |
| Python test suite | 432 passed, 0 failed |
| Branch coverage | 92.57% |
| Ruff | Passed |
| Benchmark runner | 432 passed, 0 failed; reliability 100/100 |

The bundled benchmark corpus has 43 samples across its checked-in datasets. Benchmark and latency results depend on input, machine, tokenizer availability, and selected strategy; LLMSlim does not promise a universal latency or retention percentage.

## Install

```bash
pip install llmslim

# Optional exact OpenAI-compatible token counts
pip install "llmslim[fast-tokens]"
```

Python 3.8+ is supported.

## Quick start

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
print(result.token_counter_used)  # "tiktoken" or "heuristic"
```

LLMSlim supports:

- `extractive` (default): local sentence selection.
- `rewrite`: provider-backed rewrite with validation.
- `hybrid`: extractive pre-compression followed by rewrite.

`rewrite` and `hybrid` require a caller-supplied provider.

## Provenance and compression safety

`ContextRole` describes who authored the input:

| Role | Treatment |
| --- | --- |
| `system`, `developer` | Trusted instructions; protected priority is available. |
| `user` | Semi-trusted; imperative wording can be high priority but is not safety-tier locked solely by wording. |
| `assistant`, `tool`, `rag` | Untrusted; capped at Tier 2 and never `must_keep`. |
| `general` | Legacy default behavior for `compress(text)`. |

```python
from llmslim import ContextRole, compress_documents

# Retrieved documents are untrusted by default.
documents = compress_documents(
    ["Retrieved document text..."],
    query="What is the account status?",
    target_ratio=0.4,
)

# Use an explicit label only when the caller knows the provenance.
trusted = compress(
    "Developer-authored instruction...",
    context_role=ContextRole.DEVELOPER,
)
```

LLMSlim trusts caller-provided labels and cannot authenticate provenance. Untrusted text may still be selected by relevance; it simply cannot gain the protected budget through imperative-looking wording. Applications still need normal defense in depth.

## Chat pipeline behavior

```python
from llmslim import compress_chat_messages

messages = [
    {"role": "system", "content": "Return JSON."},
    {"role": "user", "content": "Long request context..."},
    {"role": "assistant", "content": "Long prior response..."},
]

compressed = compress_chat_messages(messages, target_ratio=0.5)
```

`compress_documents()` now defaults to RAG provenance. `compress_chat_messages()` propagates each message role (`system`, `developer`, `user`, `assistant`, `tool`); system messages remain uncompressed by default.

## CLI

```bash
llmslim input.txt --ratio 0.5 --stats
llmslim input.txt --strategy hybrid --ratio 0.5
```

## Development

```bash
pip install -e ".[dev]"
pytest tests
pytest --cov=llmslim --cov-branch --cov-report=term-missing
ruff check llmslim benchmarks/benchmark.py tests
python benchmark.py
```

## Availability and roadmap

The released runtime is Python. There is no published `@llmslim/core` npm package, Rust engine, or WASM runtime in v0.3.1. Those may be explored in future releases but are not current product capabilities.

See [CHANGELOG.md](CHANGELOG.md), [release notes](release_notes.md), and [Phase 1 release gate](docs/phase-1/RELEASE_GATE.md) for details.

## Security reporting

Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE).
