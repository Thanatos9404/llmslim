export interface DocCallout {
  type: "note" | "tip" | "warning" | "important";
  title?: string;
  content: string;
}

export interface DocFaq {
  question: string;
  answer: string;
}

export interface DocSection {
  id: string;
  title: string;
  content: string; // Markdown / formatted explanation
  codeSnippet?: {
    language: string;
    filename?: string;
    code: string;
  };
  callout?: DocCallout;
  diagram?: {
    title: string;
    type: "mermaid" | "flowchart" | "dag";
    svgMarkup?: string;
  };
}

export interface DocPage {
  slug: string;
  title: string;
  subtitle: string;
  description: string;
  category: "Getting Started" | "Core Concepts" | "API Reference" | "Guides & Strategies" | "Resources";
  searchIntent: string;
  lastUpdated: string;
  readingTime: string;
  sections: DocSection[];
  faqs: DocFaq[];
  relatedPages: { title: string; slug: string }[];
}

export const DOC_CATEGORIES = [
  "Getting Started",
  "Core Concepts",
  "API Reference",
  "Guides & Strategies",
  "Resources",
] as const;

export const DOCS_REGISTRY: Record<string, DocPage> = {
  "getting-started": {
    slug: "getting-started",
    title: "Getting Started with LLMSlim",
    subtitle: "High-performance semantic prompt & context compression in under 2 minutes.",
    description: "Learn how LLMSlim cuts LLM token costs by 40-70% while guaranteeing 100% instruction fidelity across OpenAI, Claude, and local LLM infrastructure.",
    category: "Getting Started",
    searchIntent: "How to use LLMSlim to compress prompts and reduce LLM token expenses.",
    lastUpdated: "July 2026",
    readingTime: "3 min read",
    relatedPages: [
      { title: "Installation Guide", slug: "installation" },
      { title: "Quick Start Guide", slug: "quickstart" },
      { title: "Core Concepts", slug: "core-concepts" },
    ],
    faqs: [
      {
        question: "Does LLMSlim require internet access or external API calls?",
        answer: "No. Core LLMSlim runs 100% offline out-of-the-box using CPU-accelerated TF-IDF centrality and LexRank sentence scoring with zero external API dependencies.",
      },
      {
        question: "Will compressing prompts alter LLM output accuracy?",
        answer: "Empirical evaluation on standard benchmarks shows zero degradation in task execution because LLMSlim's Priority Tier Shield explicitly protects system directives, constraints, and code syntax.",
      },
    ],
    sections: [
      {
        id: "overview",
        title: "Overview & Philosophy",
        content: `LLMSlim is an open-source enterprise prompt compression library designed to eliminate context redundancy, boilerplate fluff, and filler prose before sending requests to Large Language Models (LLMs).

By compressing system prompts, RAG document search contexts, and multi-turn chat histories, LLMSlim reduces input token costs by **40% to 70%** while adding **< 30ms** local processing overhead.`,
        callout: {
          type: "tip",
          title: "Zero Setup Required",
          content: "You can integrate LLMSlim into any existing Python or TypeScript codebase in 1 line of code without modifying your model API callers.",
        },
      },
      {
        id: "why-llmslim",
        title: "Why Prompt Compression Matters",
        content: `As RAG applications scale, context windows expand to 128k–1M tokens. However, model pricing scales linearly per token, and processing long unfocused prompts increases Time-to-First-Token (TTFT) latency.

LLMSlim solves three critical challenges:
1. **Cost Reduction**: Save thousands of dollars monthly on flagship models like GPT-4o, Claude Sonnet, and Gemini Pro.
2. **Latency Optimization**: Shorter prompts process significantly faster on LLM provider infrastructure.
3. **Focus Elevation**: Removing low-value boilerplate prevents LLMs from hallucinating on irrelevant background context.`,
      },
      {
        id: "one-minute-example",
        title: "One-Minute Example",
        content: "Here is how to compress a messy prompt into an optimized token-dense payload:",
        codeSnippet: {
          language: "python",
          filename: "example.py",
          code: `from llmslim import compress

raw_prompt = """
System Directive: You must always respond in JSON format with keys 'status' and 'summary'.
Please be aware that our customer support policy explicitly states that returns are valid for 30 days.
In addition, it is very important to mention that shipping fees are non-refundable under any circumstances whatsoever.
"""

# Compress with 50% target token reduction
result = compress(raw_prompt, target_ratio=0.5)

print(f"Original Tokens: {result.original_tokens}")
print(f"Compressed Tokens: {result.compressed_tokens}")
print(f"Savings Ratio: {result.savings_percent:.1f}%")
print("\\n--- Compressed Prompt ---\\n")
print(result.compressed_text)`,
        },
      },
    ],
  },

  installation: {
    slug: "installation",
    title: "Installing LLMSlim",
    subtitle: "Complete installation guide for Python, Node.js, and CLI environments.",
    description: "Detailed installation instructions for LLMSlim across PyPI, npm, uv, and poetry with hardware acceleration options.",
    category: "Getting Started",
    searchIntent: "How to install LLMSlim via pip, npm, poetry, or source.",
    lastUpdated: "July 2026",
    readingTime: "4 min read",
    relatedPages: [
      { title: "Quick Start Guide", slug: "quickstart" },
      { title: "CLI Reference", slug: "cli" },
      { title: "Configuration", slug: "configuration" },
    ],
    faqs: [
      {
        question: "What Python versions are supported?",
        answer: "LLMSlim supports Python 3.9, 3.10, 3.11, 3.12, and 3.13 across Linux, macOS, and Windows.",
      },
      {
        question: "Are there any heavy native binary requirements?",
        answer: "No. Core installation uses pure Python and standard C-extensions. Optional deep semantic similarity models can be loaded on-demand.",
      },
    ],
    sections: [
      {
        id: "pip-installation",
        title: "Standard PyPI Installation",
        content: "Install the core LLMSlim package using `pip`:",
        codeSnippet: {
          language: "bash",
          filename: "terminal",
          code: "pip install llmslim",
        },
        callout: {
          type: "note",
          title: "Fast Package Manager",
          content: "You can also install with uv: 'uv add llmslim' for sub-second installation speed.",
        },
      },
      {
        id: "semantic-extras",
        title: "Optional Deep Semantic Extra",
        content: "For transformer-based semantic embeddings (cross-sentence similarity analysis), install the `[semantic]` extra:",
        codeSnippet: {
          language: "bash",
          filename: "terminal",
          code: "pip install 'llmslim[semantic]'",
        },
      },
      {
        id: "javascript-installation",
        title: "JavaScript / Node.js Package",
        content: "For Next.js, Node.js, and browser environments, install via `npm` or `pnpm`:",
        codeSnippet: {
          language: "bash",
          filename: "terminal",
          code: "npm install @llmslim/core",
        },
      },
    ],
  },

  quickstart: {
    slug: "quickstart",
    title: "Quick Start Guide",
    subtitle: "Start compressing system prompts and RAG contexts in under 60 seconds.",
    description: "Step-by-step tutorial on integrating LLMSlim into Python pipelines, OpenAI SDK calls, and LangChain agents.",
    category: "Getting Started",
    searchIntent: "Quickstart code examples for LLMSlim prompt compression.",
    lastUpdated: "July 2026",
    readingTime: "5 min read",
    relatedPages: [
      { title: "Python API Reference", slug: "python-api" },
      { title: "Framework Integrations", slug: "framework-integrations" },
      { title: "Examples", slug: "examples" },
    ],
    faqs: [
      {
        question: "How do I wrap an OpenAI chat completion call?",
        answer: "Pass your system or user content through compress() before constructing the messages array in client.chat.completions.create().",
      },
    ],
    sections: [
      {
        id: "openai-integration",
        title: "Integrating with OpenAI SDK",
        content: "Wrap long system instructions or multi-document RAG context before dispatching your OpenAI API request:",
        codeSnippet: {
          language: "python",
          filename: "openai_app.py",
          code: `from openai import OpenAI
from llmslim import compress

client = OpenAI()

long_rag_context = """... 4,000 tokens of unstructured document context ..."""

# Compress to 40% of original token count while preserving key facts
compressed_context = compress(long_rag_context, target_ratio=0.4).compressed_text

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "value": "You are a helpful research assistant."},
        {"role": "user", "content": f"Context: {compressed_context}\\n\\nQuestion: Summarize key revenue metrics."},
    ]
)

print(response.choices[0].message.content)`,
        },
        callout: {
          type: "important",
          title: "Guaranteed Instruction Retention",
          content: "System directives containing 'must', 'never', or formatted constraints are automatically retained by the priority tier engine.",
        },
      },
    ],
  },

  "core-concepts": {
    slug: "core-concepts",
    title: "Core Concepts & Architecture",
    subtitle: "Understanding content auto-detection, priority tier shields, and entropy scoring.",
    description: "In-depth guide to LLMSlim's 6-step compression DAG, LexRank centrality scoring, and entity preservation algorithms.",
    category: "Core Concepts",
    searchIntent: "How LLMSlim algorithm works internally.",
    lastUpdated: "July 2026",
    readingTime: "6 min read",
    relatedPages: [
      { title: "Compression Engine", slug: "compression-engine" },
      { title: "Architecture", slug: "architecture" },
      { title: "Compression Strategies", slug: "compression-strategies" },
    ],
    faqs: [
      {
        question: "What are Priority Tiers?",
        answer: "Priority Tiers rank text boundaries from Priority 1 (Background fluff) to Priority 4 (Critical instructions & code), ensuring essential constraints are never dropped.",
      },
    ],
    sections: [
      {
        id: "dag-pipeline",
        title: "The 6-Step Compression DAG Pipeline",
        content: `LLMSlim executes context reduction through a strictly deterministic Directed Acyclic Graph (DAG):

1. **Format Identification**: Classifies prompt structure (Markdown, JSON, XML, Code, Chat).
2. **Lexical Tokenization**: Maps words, code markers, and entity boundaries.
3. **Priority Shield Evaluation**: Protects system rules, constraints, and JSON schemas.
4. **Information Density Scoring**: Calculates TF-IDF centrality & graph degree.
5. **Entity Retention Check**: Ensures proper nouns, numbers, and technical terms remain intact.
6. **Token Assembly**: Reconstructs a clean, cohesive, token-dense prompt output.`,
        callout: {
          type: "tip",
          title: "Sub-50ms CPU Latency",
          content: "The entire 6-step pipeline executes locally on CPU in under 30ms for standard 2,000-token prompts.",
        },
      },
    ],
  },

  "compression-engine": {
    slug: "compression-engine",
    title: "Compression Engine Details",
    subtitle: "Inside the TF-IDF, LexRank, and Structured Formats engine.",
    description: "Deep dive into LLMSlim's specialized optimizers for JSON, XML, Markdown, and conversational transcripts.",
    category: "Core Concepts",
    searchIntent: "Algorithmic breakdown of LLMSlim compression engine.",
    lastUpdated: "July 2026",
    readingTime: "7 min read",
    relatedPages: [
      { title: "Core Concepts", slug: "core-concepts" },
      { title: "Python API Reference", slug: "python-api" },
    ],
    faqs: [
      {
        question: "How does JSON mode compress structural data?",
        answer: "JSON mode strips duplicate whitespace, normalizes key syntax, and truncates repetitive dictionary entries while retaining structural validity.",
      },
    ],
    sections: [
      {
        id: "format-optimizers",
        title: "Format-Specific Optimizers",
        content: "LLMSlim features dedicated optimizers for structured formats:",
        codeSnippet: {
          language: "python",
          filename: "format_demo.py",
          code: `from llmslim import compress, ContentType

json_data = '{"users": [{"id": 1, "name": "Alice", "role": "admin"}, {"id": 2, "name": "Bob", "role": "admin"}]}'

result = compress(json_data, mode="json", target_ratio=0.5)
print(result.compressed_text)`,
        },
      },
    ],
  },

  architecture: {
    slug: "architecture",
    title: "Engine Architecture & Hardware Telemetry",
    subtitle: "System design, memory layout, and sub-30ms performance telemetry.",
    description: "Comprehensive blueprint of LLMSlim's execution graph, C-extension interfaces, and ONNX acceleration roadmaps.",
    category: "Core Concepts",
    searchIntent: "LLMSlim system architecture and memory performance.",
    lastUpdated: "July 2026",
    readingTime: "5 min read",
    relatedPages: [
      { title: "Core Concepts", slug: "core-concepts" },
      { title: "Benchmarks", slug: "best-practices" },
    ],
    faqs: [
      {
        question: "What memory footprint does LLMSlim consume?",
        answer: "Standard TF-IDF execution uses under 15MB RAM, making it suitable for serverless functions, Lambda Edge, and embedded devices.",
      },
    ],
    sections: [
      {
        id: "system-blueprint",
        title: "System Blueprint",
        content: "Designed for cloud-native infrastructure, serverless runtimes, and high-throughput enterprise gateways.",
      },
    ],
  },

  cli: {
    slug: "cli",
    title: "Command Line Interface (CLI)",
    subtitle: "Compress prompts, run batch telemetry, and calculate cost ROI from terminal.",
    description: "Complete CLI command reference for llmslim compress, analyze, benchmark, and cost commands.",
    category: "API Reference",
    searchIntent: "LLMSlim CLI commands usage and syntax.",
    lastUpdated: "July 2026",
    readingTime: "4 min read",
    relatedPages: [
      { title: "Python API Reference", slug: "python-api" },
      { title: "Configuration", slug: "configuration" },
    ],
    faqs: [
      {
        question: "Can I pipe CLI output directly to curl or jq?",
        answer: "Yes. Use the --quiet or -q flag to output raw compressed text straight to stdout.",
      },
    ],
    sections: [
      {
        id: "cli-commands",
        title: "CLI Command Reference",
        content: "Below are standard terminal commands supported by `llmslim`:",
        codeSnippet: {
          language: "bash",
          filename: "terminal",
          code: `# Compress a prompt file and save output
llmslim compress system_prompt.txt --ratio 0.5 --output slim_prompt.txt

# Analyze content density profile
llmslim analyze document.md

# Estimate annual token cost savings
llmslim cost --original-tokens 10000000 --compressed-tokens 4000000 --model gpt-4o`,
        },
      },
    ],
  },

  "python-api": {
    slug: "python-api",
    title: "Python API Reference",
    subtitle: "Complete function signatures, ContextCompressor class, and return types.",
    description: "Full Python API documentation for compress(), ContextCompressor, analyze(), compress_chat_messages(), and cost estimation utilities.",
    category: "API Reference",
    searchIntent: "LLMSlim Python API doc functions parameters return values.",
    lastUpdated: "July 2026",
    readingTime: "8 min read",
    relatedPages: [
      { title: "Quick Start Guide", slug: "quickstart" },
      { title: "JavaScript API Reference", slug: "javascript-api" },
      { title: "Configuration", slug: "configuration" },
    ],
    faqs: [
      {
        question: "What object is returned by compress()?",
        answer: "A CompressionResult instance containing compressed_text, original_tokens, compressed_tokens, savings_percent, and detailed execution metrics.",
      },
    ],
    sections: [
      {
        id: "compress-function",
        title: "compress() Function Signature",
        content: "The primary entry point for quick prompt context reduction:",
        codeSnippet: {
          language: "python",
          filename: "llmslim/core.py",
          code: `def compress(
    text: str,
    target_ratio: float = 0.5,
    mode: str = "auto",
    detect_content: bool = True,
    preserve_code: bool = True,
    preserve_entities: bool = True,
) -> CompressionResult:
    """Surgically compress input prompt text while preserving key instruction fidelity.
    
    Args:
        text: Input string (prompt, RAG context, or code).
        target_ratio: Target proportion of tokens to retain (e.g., 0.5 = 50% retained).
        mode: Compression mode ("auto", "markdown", "json", "xml", "code", "chat").
        detect_content: Auto-detect format type automatically.
        preserve_code: Shield syntax, functions, and formatting in code blocks.
        preserve_entities: Protect proper nouns, numbers, and technical terms.
        
    Returns:
        CompressionResult object with telemetry metrics and compressed text.
    """`,
        },
      },
    ],
  },

  "javascript-api": {
    slug: "javascript-api",
    title: "JavaScript / TypeScript API Reference",
    subtitle: "Client-side and Server-side Node.js / Edge runtime API docs.",
    description: "Full API documentation for @llmslim/core JavaScript and TypeScript packages across Vercel Edge, Node.js, and Next.js.",
    category: "API Reference",
    searchIntent: "LLMSlim JavaScript TypeScript SDK documentation.",
    lastUpdated: "July 2026",
    readingTime: "5 min read",
    relatedPages: [
      { title: "Python API Reference", slug: "python-api" },
      { title: "Framework Integrations", slug: "framework-integrations" },
    ],
    faqs: [
      {
        question: "Is the JS package compatible with Cloudflare Workers and Vercel Edge?",
        answer: "Yes. @llmslim/core uses zero native Node bindings and runs natively on Vercel Edge, Deno, and Cloudflare Workers.",
      },
    ],
    sections: [
      {
        id: "js-usage",
        title: "TypeScript / Node.js Usage",
        content: "Import and compress prompts in TypeScript applications:",
        codeSnippet: {
          language: "typescript",
          filename: "app.ts",
          code: `import { compress } from "@llmslim/core";

const result = compress(longPrompt, {
  targetRatio: 0.5,
  preserveCode: true,
});

console.log(\`Saved \${result.savingsPercent}% tokens!\`);
console.log(result.compressedText);`,
        },
      },
    ],
  },

  configuration: {
    slug: "configuration",
    title: "Configuration & Custom Tiers",
    subtitle: "Customizing priority tier thresholds, regex rules, and retention parameters.",
    description: "Learn how to configure LLMSlim rules, custom sentence patterns, and tier priorities via code or pyproject.toml.",
    category: "API Reference",
    searchIntent: "How to configure LLMSlim custom rules and options.",
    lastUpdated: "July 2026",
    readingTime: "4 min read",
    relatedPages: [
      { title: "Python API Reference", slug: "python-api" },
      { title: "Compression Strategies", slug: "compression-strategies" },
    ],
    faqs: [
      {
        question: "Can I define custom regex rules for Priority 4 protection?",
        answer: "Yes. Pass custom_patterns to ContextCompressor or configure them globally in your environment.",
      },
    ],
    sections: [
      {
        id: "custom-compressor",
        title: "Configuring ContextCompressor",
        content: "Instantiate `ContextCompressor` with tailored rules:",
        codeSnippet: {
          language: "python",
          filename: "config.py",
          code: `from llmslim import ContextCompressor

compressor = ContextCompressor(
    target_ratio=0.4,
    preserve_code=True,
    preserve_entities=True,
    custom_protected_keywords=["CONFIDENTIAL", "API_KEY", "MUST_NOT"]
)

result = compressor.compress(prompt)`,
        },
      },
    ],
  },

  "compression-strategies": {
    slug: "compression-strategies",
    title: "Compression Strategies Guide",
    subtitle: "Choosing the optimal strategy for System Prompts, RAG Contexts, and Chat Logs.",
    description: "Master tail-focused, head-focused, and semantic density strategies tailored for specific LLM workloads.",
    category: "Guides & Strategies",
    searchIntent: "Prompt compression strategies for RAG and multi-turn chat.",
    lastUpdated: "July 2026",
    readingTime: "6 min read",
    relatedPages: [
      { title: "Prompt Engineering Guide", slug: "prompt-engineering" },
      { title: "Best Practices", slug: "best-practices" },
    ],
    faqs: [
      {
        question: "Which strategy should I use for 50-page PDF RAG contexts?",
        answer: "Use RAG Document Chunk strategy with compress_documents(docs, query='...') to rank sentences by query relevance.",
      },
    ],
    sections: [
      {
        id: "rag-strategy",
        title: "Strategy 1: Query-Aware RAG Context Compression",
        content: "When compressing retrieved vector documents, prioritize content highly relevant to the user query:",
        codeSnippet: {
          language: "python",
          filename: "rag_strategy.py",
          code: `from llmslim import compress_documents

retrieved_docs = ["Chunk 1 text...", "Chunk 2 text...", "Chunk 3 text..."]
user_query = "What is the Q3 net margin for enterprise hardware?"

# Filter & compress RAG contexts by query relevance score
compressed_chunks = compress_documents(
    retrieved_docs,
    query=user_query,
    target_ratio=0.3
)

final_prompt = "\\n---\\n".join([c.compressed_text for c in compressed_chunks])`,
        },
      },
    ],
  },

  "framework-integrations": {
    slug: "framework-integrations",
    title: "Framework Integrations",
    subtitle: "Seamless setup for LangChain, LlamaIndex, CrewAI, AutoGen, and FastAPI.",
    description: "Integration tutorials and code patterns for popular LLM frameworks including LangChain, LlamaIndex, and FastAPI middleware.",
    category: "Guides & Strategies",
    searchIntent: "How to integrate LLMSlim with LangChain LlamaIndex FastAPI.",
    lastUpdated: "July 2026",
    readingTime: "7 min read",
    relatedPages: [
      { title: "Quick Start Guide", slug: "quickstart" },
      { title: "Examples", slug: "examples" },
    ],
    faqs: [
      {
        question: "Is there a LangChain DocumentTransformer available?",
        answer: "Yes. You can use LLMSlimContextCompressor directly as a retriever post-processor or document transformer.",
      },
    ],
    sections: [
      {
        id: "fastapi-middleware",
        title: "FastAPI Compression Middleware",
        content: "Compress outgoing LLM prompts or incoming RAG payloads at the API gateway layer:",
        codeSnippet: {
          language: "python",
          filename: "server.py",
          code: `from fastapi import FastAPI, Request
from llmslim import compress

app = FastAPI()

@app.post("/v1/chat/completions")
async def generate_response(payload: dict):
    # Intercept system prompt and compress
    raw_prompt = payload["messages"][0]["content"]
    slim_prompt = compress(raw_prompt, target_ratio=0.5).compressed_text
    payload["messages"][0]["content"] = slim_prompt
    
    # Forward compressed payload to LLM provider
    return {"status": "dispatched", "compressed_length": len(slim_prompt)}`,
        },
      },
    ],
  },

  "prompt-engineering": {
    slug: "prompt-engineering",
    title: "Prompt Engineering Guide for LLMSlim",
    subtitle: "Designing prompts that compress with maximum token reduction and 100% fidelity.",
    description: "Best practices for writing compression-friendly prompts, role markers, and structured output instructions.",
    category: "Guides & Strategies",
    searchIntent: "Prompt engineering principles for semantic compression.",
    lastUpdated: "July 2026",
    readingTime: "5 min read",
    relatedPages: [
      { title: "Compression Strategies", slug: "compression-strategies" },
      { title: "Best Practices", slug: "best-practices" },
    ],
    faqs: [
      {
        question: "How should I format JSON schema rules in system prompts?",
        answer: "Use explicit fenced code blocks (```json ... ```) or imperative tags ('MUST return JSON'). Priority Tier 4 automatically preserves these sections intact.",
      },
    ],
    sections: [
      {
        id: "imperative-anchors",
        title: "Rule 1: Use Explicit Imperative Anchors",
        content: "Keywords like `MUST`, `NEVER`, `ALWAYS`, `REQUIRED`, and `GUARANTEE` anchor sentences to Priority Tier 4, safeguarding them against removal during high compression ratios.",
      },
    ],
  },

  "best-practices": {
    slug: "best-practices",
    title: "Production Best Practices",
    subtitle: "Enterprise readiness, error handling, caching, and evaluation telemetry.",
    description: "Guidelines for deploying LLMSlim in mission-critical backend environments, monitoring token savings, and caching strategies.",
    category: "Guides & Strategies",
    searchIntent: "LLMSlim enterprise production best practices and evaluation.",
    lastUpdated: "July 2026",
    readingTime: "6 min read",
    relatedPages: [
      { title: "Configuration", slug: "configuration" },
      { title: "Troubleshooting", slug: "troubleshooting" },
    ],
    faqs: [
      {
        question: "Should I cache compressed system prompts?",
        answer: "Yes! System prompts rarely change dynamically. Compress once at server startup or build time to incur 0ms runtime latency for user requests.",
      },
    ],
    sections: [
      {
        id: "startup-caching",
        title: "Pattern 1: Server Startup Pre-Compression",
        content: "Pre-compress standard system prompts at application initialization time:",
        codeSnippet: {
          language: "python",
          filename: "cached_app.py",
          code: `from llmslim import compress

SYSTEM_PROMPT = """... 2,500 token enterprise compliance policy ..."""

# Pre-compress once during startup
COMPRESSED_SYSTEM_PROMPT = compress(SYSTEM_PROMPT, target_ratio=0.4).compressed_text

def build_user_request(user_input: str) -> list:
    return [
        {"role": "system", "content": COMPRESSED_SYSTEM_PROMPT},
        {"role": "user", "content": user_input}
    ]`,
        },
      },
    ],
  },

  faq: {
    slug: "faq",
    title: "Frequently Asked Questions (FAQ)",
    subtitle: "Answers to common security, performance, licensing, and technical questions.",
    description: "Comprehensive repository of all frequently asked questions regarding LLMSlim installation, performance, security, and usage.",
    category: "Resources",
    searchIntent: "LLMSlim FAQ questions security performance license.",
    lastUpdated: "July 2026",
    readingTime: "5 min read",
    relatedPages: [
      { title: "Getting Started", slug: "getting-started" },
      { title: "Troubleshooting", slug: "troubleshooting" },
    ],
    faqs: [
      {
        question: "Is LLMSlim open-source under MIT license?",
        answer: "Yes, LLMSlim is 100% open-source under the permissive MIT license for commercial and personal use.",
      },
      {
        question: "Can LLMSlim run inside cloud serverless environments like AWS Lambda?",
        answer: "Yes. Cold start overhead is under 12ms and memory consumption is under 15MB.",
      },
    ],
    sections: [
      {
        id: "faq-list",
        title: "Frequently Asked Questions",
        content: "Browse key architectural, operational, and licensing details below.",
      },
    ],
  },

  troubleshooting: {
    slug: "troubleshooting",
    title: "Troubleshooting Guide",
    subtitle: "Common errors, edge cases, and diagnostic resolutions.",
    description: "Solutions to common issues, import errors, low compression ratios, and unexpected content truncation.",
    category: "Resources",
    searchIntent: "LLMSlim troubleshooting fix common errors.",
    lastUpdated: "July 2026",
    readingTime: "4 min read",
    relatedPages: [
      { title: "Best Practices", slug: "best-practices" },
      { title: "FAQ", slug: "faq" },
    ],
    faqs: [
      {
        question: "Why did my prompt compress by only 10% when I requested 50%?",
        answer: "If your input text consists almost entirely of Priority 4 imperative directives or code syntax, LLMSlim refuses to compromise instruction fidelity.",
      },
    ],
    sections: [
      {
        id: "common-issues",
        title: "Diagnosing Compression Mismatches",
        content: "If compression ratio differs from target_ratio, run `analyze()` to inspect content priority tier distribution:",
        codeSnippet: {
          language: "python",
          filename: "debug.py",
          code: `from llmslim import analyze

profile = analyze(my_problematic_prompt)
print(f"Content Type: {profile.content_type}")
print(f"Priority Distribution: {profile.priority_distribution}")`,
        },
      },
    ],
  },

  "migration-guide": {
    slug: "migration-guide",
    title: "Migration Guide (v0.1.x to v0.2.x)",
    subtitle: "Upgrading breaking API changes, parameter updates, and new features.",
    description: "Step-by-step migration guide for updating legacy LLMSlim installations to v0.2.0 API standards.",
    category: "Resources",
    searchIntent: "How to upgrade LLMSlim to v0.2.0 breaking changes.",
    lastUpdated: "July 2026",
    readingTime: "3 min read",
    relatedPages: [
      { title: "Getting Started", slug: "getting-started" },
      { title: "Python API Reference", slug: "python-api" },
    ],
    faqs: [
      {
        question: "Are there breaking changes between v0.1.0 and v0.2.0?",
        answer: "The parameter 'ratio' was renamed to 'target_ratio' for clarity, and compress() now returns a CompressionResult dataclass object instead of a raw tuple.",
      },
    ],
    sections: [
      {
        id: "breaking-changes",
        title: "Breaking API Changes in v0.2.0",
        content: "Update your legacy imports and function calls:",
        codeSnippet: {
          language: "python",
          filename: "migration.py",
          code: `# Legacy v0.1.0 call
# text, ratio = compress_text(prompt, ratio=0.5)

# Modern v0.2.0 call
from llmslim import compress

result = compress(prompt, target_ratio=0.5)
compressed_text = result.compressed_text`,
        },
      },
    ],
  },

  examples: {
    slug: "examples",
    title: "Code Examples & Recipes",
    subtitle: "Copy-pasteable production recipes for real-world AI applications.",
    description: "Production-ready code snippets for LangChain, OpenAI, Claude, RAG, Chatbot history, and CLI workflows.",
    category: "Resources",
    searchIntent: "LLMSlim code examples recipes github.",
    lastUpdated: "July 2026",
    readingTime: "5 min read",
    relatedPages: [
      { title: "Quick Start Guide", slug: "quickstart" },
      { title: "Framework Integrations", slug: "framework-integrations" },
    ],
    faqs: [
      {
        question: "Where can I find complete runnable scripts?",
        answer: "Check out the official GitHub repository under the examples/ directory.",
      },
    ],
    sections: [
      {
        id: "recipe-chat-history",
        title: "Recipe: Multi-Turn Chat History Truncation",
        content: "Compress conversational transcripts while preserving system role context:",
        codeSnippet: {
          language: "python",
          filename: "chat_recipe.py",
          code: `from llmslim import compress_chat_messages

conversation_history = [
    {"role": "system", "content": "You are a senior tech lead."},
    {"role": "user", "content": "Can you explain distributed consensus?"},
    {"role": "assistant", "content": "Distributed consensus is... [long 800 word explanation]"},
    {"role": "user", "content": "How does Raft handle leader elections specifically?"}
]

slim_history = compress_chat_messages(conversation_history, target_ratio=0.5)
print(slim_history)`,
        },
      },
    ],
  },
};
