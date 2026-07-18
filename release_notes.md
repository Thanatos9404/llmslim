# llmslim v0.3.0 — Hybrid Prompt Compression & Semantic Optimization

We are excited to announce the release of **llmslim v0.3.0**, extending `llmslim` from a high-performance offline prompt compressor into a **Content-Aware Prompt Compression & Semantic Optimization Engine**.

`v0.3.0` introduces a zero-dependency **Provider Abstraction Layer**, versioned **Rewrite Prompt Templates**, a multi-stage **Semantic Validation Pipeline**, and a **Strategy Router** supporting `extractive` (default), `rewrite`, and `hybrid` strategies.

---

## 🌟 Major Highlights

- ⚡ **Zero External Dependencies**: The core library remains 100% offline-first with zero hard dependencies on external LLM provider SDKs (`openai`, `anthropic`, `google-generativeai`, `ollama`).
- 🔄 **Strategy Router (`extractive`, `rewrite`, `hybrid`)**:
  - `extractive` (Default): Offline LexRank + TF-IDF graph centrality sentence selection (< 5ms CPU overhead).
  - `rewrite`: Sends prompts through a provider-backed LLM rewriter with strict multi-stage quality validation.
  - `hybrid`: Pre-compresses long contexts extractively before running semantic rewriting to minimize prefill billing.
- 🛡️ **Multi-Stage Quality Validation Pipeline**: Every rewrite candidate undergoes 4 independent validation checks (`Structural`, `Instruction`, `Entity`, `Similarity`). Failing rewrites automatically trigger a fallback to extractive compression.
- 📐 **Pluggable Similarity Validation**: Ships with a fast offline `TfidfSimilarityValidator` (replaceable by custom embedding or BERTScore validators).
- 📜 **Versioned Prompt Templates**: Pre-configured prompt templates for RAG context, chat history, system prompts, technical documentation, and code context.
- 📊 **Grouped Telemetry (`RewriteMetadata`)**: Clean telemetry object attached to `CompressionResult` tracking similarity scores, instruction retention rates, latency, and failure reasons.

---

## 🚀 Quick Start Example

```python
from llmslim import compress, CallableProvider, RewriteRequest

# 1. Default Extractive Compression (Offline, Fast < 5ms)
slim_ext = compress(my_long_prompt, target_ratio=0.5, strategy="extractive")

# 2. Semantic Rewrite (Custom LLM Provider)
def my_llm_provider(request: RewriteRequest) -> str:
    # Use request.system_prompt and request.user_prompt
    return llm_client.complete(request.user_prompt)

provider = CallableProvider(my_llm_provider, name="custom_llm")

slim_rew = compress(
    my_long_prompt,
    target_ratio=0.5,
    strategy="rewrite",
    provider=provider,
)

# 3. Hybrid Strategy (Extractive -> Rewrite -> Validation)
slim_hyb = compress(
    my_long_prompt,
    target_ratio=0.5,
    strategy="hybrid",
    provider=provider,
)

print(slim_hyb.compressed_text)
print(slim_hyb.detailed_summary())
```

---

## 🔒 Quality Assurance & Test Coverage

- **Unit Tests**: 389 passing assertions across 15 test modules.
- **Coverage**: **92.42%** total line & branch coverage across all core modules.
- **Linters & Types**: 0 errors across `ruff` and `mypy`.
- **Determinism**: 100% byte-identical results in default `extractive` mode.

---

## 🤝 Backward Compatibility

`llmslim v0.3.0` is **100% backward compatible** with `v0.2.0`. Existing function calls to `compress(text, target_ratio=0.5)` continue operating in default `extractive` mode without any API or behavioral changes.

---

## 💖 Star the Repository

If `llmslim` helps you cut LLM API bills and optimize prompt latency, please consider giving us a ⭐ star on GitHub:  
👉 **[https://github.com/Thanatos9404/llmslim](https://github.com/Thanatos9404/llmslim)**
