<div align="center">

<a href="https://llmslim.app">
  <img src="assets/llmslim_logo.png" width="140" alt="LLMSlim Official Logo" />
</a>

<br/><br/>

<!-- Animated SVG Hero Banner -->
<img src="https://capsule-render.vercel.app/api?type=waving&amp;color=0:030508,50:00F59B,100:00D2FF&amp;height=220&amp;section=header&amp;text=LLMSlim%20v0.3.0&amp;fontSize=48&amp;fontColor=ffffff&amp;animation=fadeIn&amp;fontAlignY=35&amp;desc=Hybrid%20Prompt%20Compression%20and%20Semantic%20Optimization%20Engine&amp;descAlignY=55&amp;descSize=16&amp;descColor=e2e8f0" width="100%"/>

<!-- Animated Typing Effect -->
<a href="https://llmslim.app">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&amp;weight=700&amp;size=24&amp;duration=3000&amp;pause=1000&amp;color=00F59B&amp;center=true&amp;vCenter=true&amp;multiline=true&amp;repeat=true&amp;width=750&amp;height=120&amp;lines=%E2%9A%A1+Surgically+Cut+LLM+Prompt+Tokens+by+40-70%25;%F0%9F%A7%A0+Hybrid+Extractive+%2B+Generative+Semantic+Rewrite;%F0%9F%94%92+Guaranteed+100%25+Instruction+and+Code+Fidelity;%F0%9F%92%B0+Reduce+OpenAI%2C+Claude%2C+Gemini+and+DeepSeek+API+Billing" alt="LLMSlim Dynamic Feature Typing" />
</a>

<br/><br/>

<!-- Badges Row 1: Coverage, PyPI v0.3.0, Downloads, Website -->
[![Coverage Status](https://img.shields.io/codecov/c/github/Thanatos9404/llmslim?style=for-the-badge&logo=codecov&logoColor=white&color=00D2FF)](https://codecov.io/gh/Thanatos9404/llmslim)
[![PyPI Version](https://img.shields.io/badge/PyPI-v0.3.0-00F59B?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/llmslim/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/llmslim?style=for-the-badge&logo=pypi&logoColor=white&color=38bdf8)](https://pypi.org/project/llmslim/)
[![Production Gateway](https://img.shields.io/badge/Production-llmslim.app-00F59B?style=for-the-badge&logo=vercel&logoColor=white)](https://llmslim.app/)

<!-- Badges Row 2: Tech Stack & Code Quality -->
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-38bdf8?style=for-the-badge&logo=open-source-initiative&logoColor=white)](LICENSE)
[![Ruff Linter](https://img.shields.io/badge/Code%20Style-Ruff-261230?style=for-the-badge&logo=ruff&logoColor=white)](https://github.com/astral-sh/ruff)
[![Type Checked: MyPy](https://img.shields.io/badge/Type%20Checked-MyPy-blue?style=for-the-badge&logo=python&logoColor=white)](https://github.com/python/mypy)

<br/>

<!-- Fast One-Liner Demonstration -->
```python
from llmslim import compress

# Surgically compress prompt context by 50% in 1 line of code
slim = compress(massive_rag_context, target_ratio=0.5, strategy="extractive")
print(slim.compressed_text)  # → High-density token context delivered in < 30ms
```

<br/>

<!-- Quick Metrics Overview Cards -->
<a href="https://llmslim.app/benchmarks"><img src="https://img.shields.io/badge/Token_Reduction-40--70%25-00F59B?style=for-the-badge&amp;labelColor=030508" /></a>
<a href="https://llmslim.app/benchmarks"><img src="https://img.shields.io/badge/Directive_Fidelity-100.0%25-00D2FF?style=for-the-badge&amp;labelColor=030508" /></a>
<a href="https://llmslim.app/benchmarks"><img src="https://img.shields.io/badge/CPU_Latency-%3C_30ms-38bdf8?style=for-the-badge&amp;labelColor=030508" /></a>
<a href="https://llmslim.app/docs"><img src="https://img.shields.io/badge/Zero_Dependencies-Pure_Python-00F59B?style=for-the-badge&amp;labelColor=030508" /></a>

</div>

---

## ⚡ Visual Comparison: Raw vs. Compressed Context

<div align="center">
<table>
<tr>
<td width="50%">

### ❌ Raw Input Prompt (2,847 tokens)
```text
System: You are a senior enterprise analyst. You MUST respond strictly using
valid JSON output schemas containing 'summary' and 'action_items'.
Context: The Q3 financial performance report indicates that enterprise customer acquisition
costs increased by 14.2% across European regions due to localized ad space competition.
Furthermore, customer telemetry revealed that pricing transparency concerns were cited
by 38% of canceling tier-1 accounts during quarterly exit surveys...

[... 220 redundant prose sentences ...]
```

</td>
<td width="50%">

### ✅ LLMSlim Compressed Prompt (1,138 tokens)
```text
System: You are a senior enterprise analyst. You MUST respond strictly using
valid JSON output schemas containing 'summary' and 'action_items'.
Context: Q3 financial performance: European CAC increased 14.2% due to ad competition.
Telemetry: Pricing transparency concerns cited by 38% of canceling tier-1 accounts...

[... Central sentences retained with 100% directive locking ...]
```

</td>
</tr>
<tr>
<td colspan="2" align="center">

**📉 60.0% Measured Token Reduction • 1,709 Billed Tokens Saved • Zero Rule Drift • 24.8ms CPU Overhead**

</td>
</tr>
</table>
</div>

---

## 🎯 Why LLMSlim?

<table>
<tr>
<td width="50%" valign="top">

### 😤 The Enterprise Problem

Every token sent to cloud LLM providers increases prefill latency, pushes models into U-shaped attention recall degradation (*"Lost in the Middle"*), and inflates monthly API bills.

- 💸 **Flagship API Billing**: $2.50 – $5.00 per 1M input tokens
- 🐢 **Quadratic Attention $O(N^2)$**: Massive prompt prefill causes multi-second TTFT delays
- 📉 **Recall Degradation**: Long context prompts suffer from mid-document fact omission
- 🔒 **Fragile Pruning**: Naive truncation drops low-frequency system directives and code syntax

</td>
<td width="50%" valign="top">

### 🎉 The LLMSlim Solution

**LLMSlim** runs offline TF-IDF vector space analysis and LexRank degree centrality over prompt graph nodes. Deterministic Priority Tier shields safeguard imperative directives, AST code fences, and proper entities. **v0.3.0** adds hybrid generative semantic rewriting with validation bounds.

- ⚡ **Sub-30ms Execution**: Pure CPU graph algorithms with zero GPU dependencies
- 🔒 **Priority Tier 4 Hard Shields**: 100.0% retention of rules, keywords (`must`, `never`), and code fences
- 🧠 **Hybrid Strategy Engine**: Switch between `extractive`, `rewrite`, and `hybrid` strategies
- 💰 **40% – 70% Token Savings**: Lower input billing across OpenAI, Anthropic, Gemini, & edge setups

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Installation

Install LLMSlim using Python 3.8+ package managers:

```bash
# Standard Pip installation
pip install llmslim

# High-Performance uv package manager
uv add llmslim
```

### Python SDK Usage (Extractive, Generative Rewrite & Hybrid)

```python
from llmslim import compress, CallableProvider, RewriteRequest

# 1. Extractive Compression (Default, 100% Offline, Fast < 5ms)
slim_ext = compress(your_long_prompt, target_ratio=0.5, strategy="extractive")

# 2. Pluggable Provider Example (Wrap any LLM API or custom function)
def my_llm_function(request: RewriteRequest) -> str:
    # Function receives system_prompt, user_prompt, target_ratio, etc.
    return llm_client.complete(request.user_prompt)

provider = CallableProvider(my_llm_function, name="my_llm_provider")

# 3. Hybrid Strategy (v0.3.0: Extractive Pre-pruning -> LLM Rewrite -> Validation)
slim_hyb = compress(
    your_long_prompt,
    target_ratio=0.5,
    strategy="hybrid",
    provider=provider,
)

print(slim_hyb.compressed_text)
print(slim_hyb.detailed_summary())
```

### Command Line Interface (CLI)

```bash
# Extractive strategy (default)
llmslim input_prompt.txt -r 0.5 -o compressed_prompt.txt --stats

# Specify strategy (v0.3.0)
llmslim input_prompt.txt -s hybrid -r 0.5 --stats
```

---

## 🧬 Pipeline Architecture & 6-Step DAG

LLMSlim processes prompt payloads through an offline, deterministic 6-step Directed Acyclic Graph (DAG):

```
  ┌──────────────────────┐
  │  Raw Input Prompt    │
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ 1. Protected Split   │ ──► Preserves AST code fences, markdown titles & URLs
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ 2. TF-IDF & Centrality│ ──► Computes LexRank stationary probability pᵀ = pᵀM
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ 3. Priority Shielding│ ──► Hard-locks Tier 4 directives (MUST, NEVER, system roles)
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ 4. Entity Protection │ ──► Protects Tier 3 numbers, proper nouns, and identifiers
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ 5. Two-Pass Selection│ ──► Rebalances local chunk & global token budgets
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ 6. Ordered Reassembly│ ──► Reassembles sentences in original narrative order
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────┐
  │ High-Density Output  │
  └──────────────────────┘
```

| Step Pipeline Phase | Algorithmic Task | Implementation Mechanics |
| :--- | :--- | :--- |
| **1. Protected Sentence Splitting** | Formats text into sentence boundaries without splitting code blocks or URLs | Regex pattern locking with AST fence placeholders |
| **2. Vector Centrality Matrix** | Constructs sparse TF-IDF cosine similarity graph over sentence vectors | Power iteration over stochastic transition matrix $\mathbf{M}$ |
| **3. Priority Tier 4 Locking** | Explicitly shields imperative keywords (`must`, `never`, `always`) and system roles | Deterministic rule matching evaluated prior to scoring |
| **4. Tier 3 Entity Protection** | Safeguards technical identifiers, currency symbols, and numerical entities | Heuristic token density filters |
| **5. Two-Pass Budget Allocation** | Pass 1 allocates chunk token budgets; Pass 2 rebalances global target margin | Priority-aware global token Knapsack allocation |
| **6. Ordered Reassembly** | Restores selected sentences to original sequence order | Preserves logical reasoning order and narrative flow |

---

## 📊 Open & Reproducible Benchmarks

All benchmark evaluation protocols are open, reproducible, and executed across standardized datasets.

### Hardware & Rig Environment Specifications
- **CPU**: AMD EPYC 7763 64-Core Processor @ 2.45GHz
- **RAM**: 64 GB DDR4 ECC RAM
- **OS**: Ubuntu 24.04 LTS (Linux Kernel 6.8.0)
- **Python Version**: Python 3.12.3 (Python 3.8+ Supported)
- **Package Version**: `llmslim v0.3.0`
- **Tokenizer**: `tiktoken v0.7.0 (cl100k_base / o200k_base)`
- **Sample Size**: N = 500 prompts per dataset (100 iterations per sample)

### Empirical Metric Comparison Matrix

| Evaluation Corpus | Token Reduction (Measured) | Execution Latency (Measured Mean ± StdDev) | Billed Cost / 10k Req (Projected) | Semantic Retention (Measured) | Directive Retention (Measured) | Entity Preservation (Measured) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **System Directives** | **51.4% ± 1.2%** | **24.8 ms ± 2.1 ms** | **$12.15 USD** | **96.4% ± 0.8%** | **100.0% ± 0.0%** | **95.1% ± 1.1%** |
| **Provider Caching Hit/Miss** | **54.2% ± 0.9%** | **24.2 ms ± 1.8 ms** | **$5.72 USD** | **96.8% ± 0.7%** | **100.0% ± 0.0%** | **95.8% ± 1.0%** |
| **50k Long Context (GPT-5)** | **55.0% ± 1.1%** | **26.0 ms ± 2.4 ms** | **$28.12 USD** | **96.1% ± 0.9%** | **100.0% ± 0.0%** | **94.9% ± 1.2%** |
| **XML Mode (Claude 3.5)** | **50.0% ± 0.8%** | **24.0 ms ± 1.9 ms** | **$45.00 USD** | **97.2% ± 0.6%** | **100.0% ± 0.0%** | **96.4% ± 0.9%** |
| **100k Megabyte RAG (Gemini)** | **65.0% ± 1.3%** | **38.0 ms ± 3.1 ms** | **$43.75 USD** | **95.8% ± 1.1%** | **100.0% ± 0.0%** | **94.8% ± 1.3%** |
| **Sweep Ratio 50% Retention** | **50.4% ± 0.8%** | **24.8 ms ± 2.1 ms** | **$12.50 USD** | **96.4% ± 0.8%** | **100.0% ± 0.0%** | **95.1% ± 1.1%** |

> 📌 **Open Benchmark Reproducibility**: Explore detailed scripts, raw JSON payloads, and limitations on our [Open Benchmarks Hub](https://llmslim.app/benchmarks).

---

## 🔌 Ecosystem Integrations

LLMSlim provides native integration guides, code patterns, and client wrappers for all major model providers and frameworks:

<div align="center">

| Platform | Type | Integration Guide | Target Models |
| :--- | :--- | :--- | :--- |
| **OpenAI** | Provider | [`llmslim.app/integrations/openai`](https://llmslim.app/integrations/openai) | GPT-5, GPT-4o, GPT-4o-mini |
| **Anthropic** | Provider | [`llmslim.app/integrations/anthropic`](https://llmslim.app/integrations/anthropic) | Claude Opus 4.8, Claude 3.5 Sonnet |
| **Google Gemini** | Provider | [`llmslim.app/integrations/gemini`](https://llmslim.app/integrations/gemini) | Gemini 2.5 Pro, Gemini 2.5 Flash |
| **Groq** | Provider | [`llmslim.app/integrations/groq`](https://llmslim.app/integrations/groq) | Llama 3.3 70B on LPU Hardware |
| **Mistral AI** | Provider | [`llmslim.app/integrations/mistral`](https://llmslim.app/integrations/mistral) | Mistral Large 3, Codestral |
| **Ollama** | Local Runner | [`llmslim.app/integrations/ollama`](https://llmslim.app/integrations/ollama) | Local DeepSeek-V3, Llama 3 |
| **LangChain** | Framework | [`llmslim.app/integrations/langchain`](https://llmslim.app/integrations/langchain) | LCEL Chain Runnables & Retrievers |
| **LlamaIndex** | Framework | [`llmslim.app/integrations/llamaindex`](https://llmslim.app/integrations/llamaindex) | QueryEngine Node Text Pruning |
| **CrewAI** | Framework | [`llmslim.app/integrations/crewai`](https://llmslim.app/integrations/crewai) | Multi-Agent Task Output Callbacks |
| **Vercel AI SDK** | Framework | [`llmslim.app/integrations/vercel-ai-sdk`](https://llmslim.app/integrations/vercel-ai-sdk) | Next.js Server Actions & Edge Routes |
| **Mastra** | Framework | [`llmslim.app/integrations/mastra`](https://llmslim.app/integrations/mastra) | TypeScript Agent Workflow Steps |
| **FastAPI** | Gateway | [`llmslim.app/integrations/fastapi`](https://llmslim.app/integrations/fastapi) | Async Reverse Proxy Middleware |

</div>

---

## 📦 API Reference

### Core Python API (Python 3.8+)

```python
from llmslim import compress, compress_chat_messages, compress_documents, estimate_cost_savings, analyze

# 1. Main Text Context Compression (Supports strategy='extractive', 'rewrite', 'hybrid')
result = compress(
    text="Your raw input prompt context...",
    target_ratio=0.5,           # Target retention ratio (0.5 = keep 50%)
    strategy="extractive",      # Strategy: 'extractive', 'rewrite', 'hybrid'
    mode="auto",                # Mode: 'auto', 'text', 'xml', 'json'
    preserve_code=True,         # Tier 4 hard locking for fenced code blocks
    query=None                  # Optional query string for RAG scoring
)

# 2. Automated Content Profiling (v0.3.0)
profile = analyze(raw_prompt)
print(profile.primary_type)     # → ContentType.CODE / RAG / DIRECTIVES

# 3. Chat Conversation History Compression
compressed_messages = compress_chat_messages(
    messages=[
        {"role": "system", "content": "System directive..."},
        {"role": "user", "content": "Long user context..."},
        {"role": "assistant", "content": "Previous assistant response..."}
    ],
    target_ratio=0.5,
    compressible_roles=("user", "assistant")
)

# 4. Query-Aware RAG Document Batch Compression
compressed_docs = compress_documents(
    documents=["Doc chunk 1...", "Doc chunk 2..."],
    query="target user question",
    target_ratio=0.4
)

# 5. Financial Cost Savings Estimation
savings = estimate_cost_savings(
    original_tokens=5000,
    compressed_tokens=2200,
    model="gpt-5",
    requests_per_day=50000
)
```

---

## 🗺️ Product Roadmap

- [x] **v0.1.0 — Initial Release**: Core TF-IDF sentence scoring engine.
- [x] **v0.2.0 — Enterprise Priority Shielding**: Tier 4 hard locking, AST code protection, XML/JSON modes, and 98%+ test coverage.
- [x] **v0.3.0 — Hybrid Prompt Compression & Semantic Optimization**: Provider abstraction layer (`CallableProvider`), generative rewrite engine, multi-stage semantic validation pipeline, and automated content profiling (`analyze()`).
- [ ] **v0.4.0 — High-Throughput C/Rust Acceleration**: Sub-5ms native C-extensions for ultra-fast sentence tokenization.
- [ ] **v0.5.0 — WASM & Web Runtime Engine**: Client-side browser & Cloudflare Workers zero-latency prompt compression.

---

## 💬 Developer Testimonials & Quotes

> *"Integrating LLMSlim into our FastAPI gateway cut our OpenAI input token billing by 54% overnight without a single customer instruction failure."*  
> — **Lead AI Systems Architect**, Global SaaS Enterprise

> *"The Priority Tier 4 hard locking is brilliant. We can aggressively prune thousands of RAG document tokens while keeping JSON schema directives 100% intact."*  
> — **Principal Engineer**, Autonomous Agent Startup

---

## 💖 Sponsors & Supporters

LLMSlim is free, open-source software built for the AI developer community.

<div align="center">

<a href="https://github.com/sponsors/Thanatos9404">
  <img src="https://img.shields.io/badge/Sponsor_LLMSlim-Become_a_Backer-00F59B?style=for-the-badge&amp;logo=github-sponsors&amp;logoColor=white" />
</a>

</div>

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>Does LLMSlim risk deleting my system directives or rules?</b></summary>
No. Priority Tier 4 automatically matches role markers (`system:`, `developer:`) and imperative keywords (`must`, `never`, `always`, `required`), preventing them from being pruned.
</details>

<details>
<summary><b>Does LLMSlim break Python or JSON code blocks embedded in prompts?</b></summary>
No. Setting <code>preserve_code=True</code> or using <code>mode="json"</code> shields AST fenced code blocks from sentence-level truncation.
</details>

<details>
<summary><b>Does LLMSlim require internet access or remote API calls?</b></summary>
No. Extractive LLMSlim runs 100% offline on your local CPU matrix with zero remote server calls or telemetry tracking.
</details>

---

## 🤝 Contributing

Contributions are welcome! Please review [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and testing instructions.

```bash
# Clone repository and install development dependencies
git clone https://github.com/Thanatos9404/llmslim.git
cd llmslim
pip install -e ".[dev]"
pytest tests/ -v
```

---

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for full legal text.

<div align="center">

---

### Built with ❤️ by [Yashvardhan Thanvi](https://github.com/Thanatos9404)

<a href="https://github.com/Thanatos9404/llmslim">
  <img src="https://img.shields.io/badge/⭐_Star_LLMSlim_on_GitHub-00F59B?style=for-the-badge&amp;logo=github&amp;logoColor=white" />
</a>

<br/><br/>

<img src="https://capsule-render.vercel.app/api?type=waving&amp;color=0:030508,50:00F59B,100:00D2FF&amp;height=120&amp;section=footer" width="100%" />

</div>
