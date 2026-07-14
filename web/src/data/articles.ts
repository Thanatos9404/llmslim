export interface ArticleSection {
  id: string;
  title: string;
  content: string;
  mathFormula?: string;
  codeSnippet?: {
    language: string;
    filename?: string;
    code: string;
  };
  tableData?: {
    headers: string[];
    rows: (string | number)[][];
  };
}

export interface DeepArticle {
  slug: string;
  title: string;
  subtitle: string;
  abstract: string;
  author: string;
  authorRole: string;
  publishedDate: string;
  lastUpdated: string;
  readingTime: string;
  category: "Algorithms" | "Systems & Architecture" | "Context Engineering" | "Benchmarking Methodology";
  mathIntuitionSummary: string;
  sections: ArticleSection[];
  keyTakeaways: string[];
  references: { title: string; url: string; citationKey: string }[];
}

export const ARTICLE_CATEGORIES = [
  "Algorithms",
  "Systems & Architecture",
  "Context Engineering",
  "Benchmarking Methodology",
] as const;

export const ARTICLES_REGISTRY: Record<string, DeepArticle> = {
  "how-prompt-compression-works": {
    slug: "how-prompt-compression-works",
    title: "Graph Centrality & TF-IDF Vectorization for In-Context Redundancy Reduction",
    subtitle: "Mathematical Derivation of LexRank Stationary Distributions and Priority Tier Filtering",
    abstract: "A formal mathematical and algorithmic breakdown of how graph centrality over TF-IDF term matrices ranks and prunes redundant sentences in long context prompts while safeguarding imperative instructions.",
    author: "Yashvardhan Thanvi",
    authorRole: "LLMSlim Author & Core Maintainer",
    publishedDate: "July 15, 2026",
    lastUpdated: "July 15, 2026",
    readingTime: "10 min read",
    category: "Algorithms",
    mathIntuitionSummary: "Computes sentence importance via the stationary probability distribution vector p^T = p^T M over a damped Markov transition matrix derived from pairwise TF-IDF cosine similarities.",
    keyTakeaways: [
      "TF-IDF vector space modeling measures local term specificity across sentence boundaries.",
      "LexRank graph centrality constructs a stochastic transition matrix to identify central informational nodes.",
      "Priority Tier Shields explicitly override statistical pruning for critical directives, code syntax, and structural schemas."
    ],
    references: [
      {
        citationKey: "Erkan & Radev (2004)",
        title: "LexRank: Graph-based Lexical Centrality as Salience in Text Summarization (Journal of Artificial Intelligence Research)",
        url: "https://arxiv.org/abs/1109.2128",
      },
      {
        citationKey: "Salton & Buckley (1988)",
        title: "Term-weighting approaches in automatic text retrieval (Information Processing & Management)",
        url: "https://doi.org/10.1016/0306-4573(88)90021-0",
      },
    ],
    sections: [
      {
        id: "tfidf-vectorization",
        title: "1. Vector Space Modeling & TF-IDF Weighting",
        content: `Prompt compression aims to select a subset of sentences $S' \\subset S$ from a document $D = (s_1, s_2, \\dots, s_N)$ that minimizes total token count while maximizing retained semantic information.

Each sentence $s_i$ is mapped to a sparse TF-IDF vector $\\mathbf{v}_i \\in \\mathbb{R}^{|V|}$ over vocabulary $V$:

$$\\text{TF}(t, s_i) = \\frac{f_{t, s_i}}{\\sum_{t' \\in s_i} f_{t', s_i}}$$

$$\\text{IDF}(t, D) = \\log \\left( \\frac{1 + N}{1 + |\\{s \\in D : t \\in s\\}|} \\right) + 1$$

$$\\mathbf{v}_{i, t} = \\text{TF}(t, s_i) \\times \\text{IDF}(t, D)$$`,
        mathFormula: "W_{ij} = \\frac{\\mathbf{v}_i \\cdot \\mathbf{v}_j}{\\|\\mathbf{v}_i\\| \\|\\mathbf{v}_j\\|}",
      },
      {
        id: "lexrank-derivation",
        title: "2. Graph Construction & Stationary Distribution Derivation",
        content: `A similarity graph $G = (V_G, E_G)$ is formed where vertices $V_G = \\{s_1, \\dots, s_N\\}$. Edges exist between sentences where cosine similarity $W_{ij} \\ge \\theta$ (threshold $\\theta = 0.1$).

The stochastic transition matrix $\\mathbf{M} \\in \\mathbb{R}^{N \\times N}$ is formulated with a damping factor $d = 0.85$:

$$\\mathbf{M} = d \\mathbf{B} + \\frac{1 - d}{N} \\mathbf{1}_{N \\times N}$$

where $B_{ij} = \\frac{W_{ij}}{\\sum_{k} W_{ik}}$.

The stationary probability vector $\\mathbf{p}$ is solved using power iteration until convergence:

$$\\mathbf{p}^{(k+1)} = \\mathbf{M}^T \\mathbf{p}^{(k)}$$`,
        codeSnippet: {
          language: "python",
          filename: "lexrank_core.py",
          code: `import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

def compute_sentence_centrality(sentences: list[str], threshold: float = 0.1, damping: float = 0.85) -> np.ndarray:
    """Computes LexRank stationary probability distribution vector over sentence TF-IDF cosine matrix."""
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf = vectorizer.fit_transform(sentences)
    
    # Compute pairwise similarity matrix
    sim_matrix = (tfidf * tfidf.T).toarray()
    n = len(sentences)
    
    # Apply similarity threshold
    adj = np.where(sim_matrix >= threshold, sim_matrix, 0.0)
    row_sums = adj.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    
    # Stochastic matrix formulation
    b_matrix = adj / row_sums
    m_matrix = damping * b_matrix + ((1.0 - damping) / n) * np.ones((n, n))
    
    # Power iteration
    p = np.ones(n) / n
    for _ in range(50):
        next_p = m_matrix.T @ p
        if np.linalg.norm(next_p - p) < 1e-6:
            break
        p = next_p
    return p`,
        },
      },
      {
        id: "priority-shield-integration",
        title: "3. Priority Tier Rule Layer",
        content: `Statistical centrality alone cannot distinguish an essential imperative instruction (e.g., "Must return valid JSON") from background prose. 

LLMSlim integrates a deterministic priority map $f: s_i \\mapsto \\{1, 2, 3, 4\\}$ evaluated prior to token selection:
- **Tier 4 (Locked Directive)**: System role definitions, imperative constraint words (\`must\`, \`never\`, \`always\`), code fences (\`\`\`\`).
- **Tier 3 (Entity Protection - High Priority)**: Sentences containing proper nouns, numbers, currency symbols, and technical identifiers.
- **Tier 2 (Informative Prose)**: Sentences ranked strictly by LexRank probability $p_i$.
- **Tier 1 (Redundant Padding)**: Sentences below similarity cutoff.`,
      },
    ],
  },

  "attention-economics-and-complexity": {
    slug: "attention-economics-and-complexity",
    title: "Quadratic Attention Scaling O(N^2) & In-Context Token Reduction Economics",
    subtitle: "Deriving Computation Savings in Transformer Self-Attention Layers",
    abstract: "A mathematical analysis of Transformer self-attention complexity and how input token reduction directly lowers prefill floating-point operations (FLOPs) and provider billing metrics.",
    author: "Yashvardhan Thanvi",
    authorRole: "LLMSlim Author & Core Maintainer",
    publishedDate: "July 15, 2026",
    lastUpdated: "July 15, 2026",
    readingTime: "8 min read",
    category: "Algorithms",
    mathIntuitionSummary: "Self-attention matrix multiplication QK^T requires O(N^2 d) operations for sequence length N, yielding quadratic FLOP reductions when prompt sequence length is compressed.",
    keyTakeaways: [
      "Self-attention compute complexity scales quadratically O(N^2) with prompt length N.",
      "Compressing prompt length by retention factor gamma reduces query-key matrix multiplication FLOPs to gamma^2 N^2.",
      "API provider billing scales linearly with billed tokens while serving latency decreases during the prefill phase."
    ],
    references: [
      {
        citationKey: "Vaswani et al. (2017)",
        title: "Attention Is All You Need (Advances in Neural Information Processing Systems)",
        url: "https://arxiv.org/abs/1706.03762",
      },
      {
        citationKey: "Dao et al. (2022)",
        title: "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
        url: "https://arxiv.org/abs/2205.14135",
      },
    ],
    sections: [
      {
        id: "attention-flops-derivation",
        title: "1. Mathematical Derivation of Attention FLOPs",
        content: `Standard Scaled Dot-Product Attention computes:

$$\\text{Attention}(Q, K, V) = \\text{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V$$

For sequence length $N$, batch size $B=1$, number of heads $H$, and head dimension $d_k$:
1. $Q K^T$: Matrix multiplication between $(N \\times d_k)$ and $(d_k \\times N)$ yields $(N \\times N)$. This operation requires $2 N^2 d_k$ FLOPs per head.
2. Softmax multiplication with $V$: Matrix multiplication between $(N \\times N)$ and $(N \\times d_k)$ requires $2 N^2 d_k$ FLOPs per head.

Total multi-head self-attention prefill FLOPs:

$$\\text{FLOPs}_{\\text{Attn}} = 4 H N^2 d_k = 4 N^2 d_{\\text{model}}$$

When sequence length $N$ is compressed to $N' = \\gamma N$ (where $\\gamma \\in (0, 1)$):

$$\\text{FLOPs}_{\\text{Attn}}' = 4 (\\gamma N)^2 d_{\\text{model}} = \\gamma^2 \\cdot \\text{FLOPs}_{\\text{Attn}}$$`,
        mathFormula: "\\text{Ratio}_{\\text{FLOPs}} = \\frac{\\text{FLOPs}'}{\\text{FLOPs}} = \\gamma^2",
      },
      {
        id: "flop-table",
        title: "2. Relative FLOP Reduction Factor Table",
        content: "Theoretical compute scaling factor relative to baseline sequence length $N$:",
        tableData: {
          headers: ["Retention Factor (gamma)", "Token Reduction (1 - gamma)", "Attention Compute Factor (gamma^2)", "FLOP Savings"],
          rows: [
            ["1.0 (Baseline)", "0%", "1.00", "0%"],
            ["0.8", "20%", "0.64", "36%"],
            ["0.6", "40%", "0.36", "64%"],
            ["0.5", "50%", "0.25", "75%"],
            ["0.3", "70%", "0.09", "91%"],
          ],
        },
      },
    ],
  },

  "lost-in-the-middle-mitigation": {
    slug: "lost-in-the-middle-mitigation",
    title: "Mitigating U-Shaped Attention Recall Decay in Long Context Prompts",
    subtitle: "Structuring Information Density to Overcome Position-Dependent Attention Loss",
    abstract: "An examination of empirical attention position bias in Transformer architectures and how sentence-level centrality ranking repositions core information relative to head and tail context bounds.",
    author: "Yashvardhan Thanvi",
    authorRole: "LLMSlim Author & Core Maintainer",
    publishedDate: "July 15, 2026",
    lastUpdated: "July 15, 2026",
    readingTime: "9 min read",
    category: "Context Engineering",
    mathIntuitionSummary: "Transformers exhibit maximum retrieval fidelity at context boundaries (0-15% and 85-100%). Pruning redundant middle prose elevates critical sentences into higher attention regions.",
    keyTakeaways: [
      "Information positioned in the middle 30-70% of long context prompts suffers from systematic recall degradation.",
      "Extracting central informational sentences reduces total prompt volume and moves key facts closer to instruction boundaries.",
      "Combines query relevance scoring with position preservation to maintain narrative coherence."
    ],
    references: [
      {
        citationKey: "Liu et al. (2023)",
        title: "Lost in the Middle: How Language Models Use Long Contexts (Transactions of the Association for Computational Linguistics)",
        url: "https://arxiv.org/abs/2307.03172",
      },
    ],
    sections: [
      {
        id: "middle-bias-phenomenon",
        title: "1. The Lost-in-the-Middle Phenomenon",
        content: `Research by Liu et al. (2023) established that decoder language models exhibit a U-shaped performance curve when retrieving information from input documents:

- **Head Bias**: High recall accuracy when target information resides near the initial system directives ($0-15\\%$ of context).
- **Tail Bias**: High recall accuracy when target information resides adjacent to the final prompt query ($85-100\\%$ of context).
- **Middle Degradation**: Statistically significant drop in recall performance when critical facts reside in the middle $30-70\\%$ region.

By identifying and removing non-essential filler sentences from document contexts, LLMSlim reduces overall sequence length, effectively moving mid-document facts closer to high-attention boundaries.`,
      },
      {
        id: "rag-document-compression",
        title: "2. Query-Aware Document Compression Implementation",
        content: "Using `compress_documents()` to extract relevant sentences across retrieved vector chunks:",
        codeSnippet: {
          language: "python",
          filename: "rag_pruner.py",
          code: `from llmslim import compress_documents

retrieved_chunks = [
    "Doc Chunk 1: Background corporate history founded in 2012...",
    "Doc Chunk 2: Q3 Financial Results: Net operating income reached $4.2M, representing a 14% YoY increase...",
    "Doc Chunk 3: Additional administrative overhead details and disclaimers..."
]

query = "What was the Q3 net operating income?"

# Compress documents with query-focused sentence scoring
compressed_docs = compress_documents(retrieved_chunks, query=query, target_ratio=0.4)

for idx, doc in enumerate(compressed_docs):
    print(f"--- Chunk {idx+1} ---")
    print(doc.compressed_text)`,
        },
      },
    ],
  },

  "priority-tier-protection": {
    slug: "priority-tier-protection",
    title: "Deterministic Safety Shields: Priority Tier Protection Mechanisms",
    subtitle: "Formal Syntactic Safeguards for Directives, Code Blocks, and Structured Data",
    abstract: "Technical breakdown of how LLMSlim prevents the accidental deletion of system rules, code syntax, and imperative directives during statistical context pruning.",
    author: "Yashvardhan Thanvi",
    authorRole: "LLMSlim Author & Core Maintainer",
    publishedDate: "July 15, 2026",
    lastUpdated: "July 15, 2026",
    readingTime: "7 min read",
    category: "Systems & Architecture",
    mathIntuitionSummary: "Overrides TF-IDF and centrality scores for sentences matching Tier 4 deterministic regex patterns and AST code fence boundaries.",
    keyTakeaways: [
      "Pure statistical sentence scoring risks dropping low-frequency imperative directives.",
      "Priority Tier 4 locks system role definitions, constraint keywords (MUST, NEVER), and code fences.",
      "Ensures AST syntactic integrity for Python, JavaScript, and JSON code snippets embedded in prompts."
    ],
    references: [
      {
        citationKey: "LLMSlim Core Docs",
        title: "LLMSlim Core Engine Architecture & Priority Shield Implementation",
        url: "https://llmslim.app/docs/core-concepts",
      },
    ],
    sections: [
      {
        id: "priority-tier-specification",
        title: "1. Priority Tier Classification Specification",
        content: `To ensure prompt compression never breaks application invariants, sentences are classified into four discrete priority tiers:

- **Tier 4 (Hard Lock - 100% Retention)**: Imperative keywords (\`must\`, \`never\`, \`always\`, \`required\`), role declarations (\`System:\`, \`User:\`), and fenced code blocks.
- **Tier 3 (Entity Protection - High Priority)**: Sentences containing proper nouns, numbers, currency symbols, and technical identifiers.
- **Tier 2 (Informative Content - Scored)**: Standard informative sentences evaluated by graph centrality.
- **Tier 1 (Structural Padding - Eligible for Pruning)**: Low-centrality conversational fluff.`,
        codeSnippet: {
          language: "python",
          filename: "llmslim/modes.py",
          code: `import re

TIER_4_PATTERNS = [
    re.compile(r"\\b(must|never|always|required|strictly|do not|shall not)\\b", re.IGNORECASE),
    re.compile(r"^(system|developer|user|assistant):", re.IGNORECASE),
]

def evaluate_sentence_priority(sentence: str, is_inside_code_fence: bool) -> int:
    """Evaluates deterministic priority tier for a given sentence boundary."""
    if is_inside_code_fence:
        return 4
    for pattern in TIER_4_PATTERNS:
        if pattern.search(sentence):
            return 4
    return 2  # Default candidate for centrality scoring`,
        },
      },
    ],
  },

  "structured-output-normalization": {
    slug: "structured-output-normalization",
    title: "AST Syntax-Aware Normalization for JSON, XML, and YAML Prompts",
    subtitle: "Compressing Structural Data Payloads Without Invocation Failures",
    abstract: "A deep dive into format-specific optimizers for JSON, XML, and Markdown prompts that preserve schema definitions while removing whitespace and duplicate metadata.",
    author: "Yashvardhan Thanvi",
    authorRole: "LLMSlim Author & Core Maintainer",
    publishedDate: "July 15, 2026",
    lastUpdated: "July 15, 2026",
    readingTime: "7 min read",
    category: "Systems & Architecture",
    mathIntuitionSummary: "Parses structured inputs into AST node trees, normalizes formatting whitespace, and prunes low-entropy array elements while validating schema structure.",
    keyTakeaways: [
      "Compressing JSON or XML via raw text token truncation causes syntax errors and parse failures.",
      "LLMSlim format optimizers validate AST integrity before and after structural reduction.",
      "Safely compresses large JSON API payloads passed into function-calling LLMs."
    ],
    references: [
      {
        citationKey: "ECMA-404",
        title: "The JSON Data Interchange Syntax Standard (Ecma International)",
        url: "https://www.json.org",
      },
    ],
    sections: [
      {
        id: "json-optimizer-code",
        title: "1. Structural JSON Compression Pattern",
        content: "Using format-specific modes in LLMSlim:",
        codeSnippet: {
          language: "python",
          filename: "json_opt_example.py",
          code: `from llmslim import compress

json_prompt = """{
  "request_id": "req_99281a",
  "instructions": "Extract entities from payload",
  "schema": {
    "type": "object",
    "properties": {
      "user_name": {"type": "string"},
      "user_id": {"type": "integer"}
    }
  }
}"""

# Perform AST syntax-aware normalization and compression
result = compress(json_prompt, mode="json", target_ratio=0.5)

print(f"Original Tokens: {result.original_tokens}")
print(f"Compressed Tokens: {result.compressed_tokens}")
print(result.compressed_text)`,
        },
      },
    ],
  },

  "offline-graph-vs-neural-compression": {
    slug: "offline-graph-vs-neural-compression",
    title: "Architectural Comparison: Offline Graph Methods vs. Neural Perplexity Pruning",
    subtitle: "Evaluating Throughput, Hardware Footprint, and Latency Metrics for Edge & Cloud Gateways",
    abstract: "An objective engineering analysis comparing zero-dependency offline algorithms (TF-IDF/LexRank) against neural language model prompt compressors (e.g., LLMLingua).",
    author: "Yashvardhan Thanvi",
    authorRole: "LLMSlim Author & Core Maintainer",
    publishedDate: "July 15, 2026",
    lastUpdated: "July 15, 2026",
    readingTime: "9 min read",
    category: "Benchmarking Methodology",
    mathIntuitionSummary: "Neural methods calculate conditional perplexity H(x_i | x_<i) using a small local model; offline graph methods compute TF-IDF cosine centrality over CPU matrices.",
    keyTakeaways: [
      "Offline graph compression incurs zero GPU memory allocations and minimal CPU overhead.",
      "Neural compression uses small LMs to evaluate token perplexity but introduces model cold-start and VRAM dependencies.",
      "Hybrid architectures combine rule-based priority locking with CPU graph centrality for reliable API gateways."
    ],
    references: [
      {
        citationKey: "Jiang et al. (2023)",
        title: "LLMLingua: Compressing Prompts for Accelerated Inference (EMNLP 2023)",
        url: "https://arxiv.org/abs/2310.05736",
      },
    ],
    sections: [
      {
        id: "architectural-comparison",
        title: "1. Operational Tradeoff Matrix",
        content: "System requirements and trade-offs between offline graph compressors and neural perplexity models:",
        tableData: {
          headers: ["Dimension", "Offline Graph (LLMSlim)", "Neural Perplexity (LLMLingua)"],
          rows: [
            ["GPU VRAM Requirement", "0 MB (Pure CPU)", "2,048 MB - 8,192 MB"],
            ["External Dependencies", "None (Standard NumPy / SciPy)", "PyTorch / Transformers Model Weights"],
            ["Execution Characteristics", "Deterministic P99 Latency", "Varied by Batch Size & GPU Queue"],
            ["Instruction Shielding", "Explicit Rule-Based Locking", "Probabilistic Perplexity Threshold"],
            ["Deployment Targets", "Lambda, Edge, CLI, Microservices", "GPU Node Clusters"],
          ],
        },
      },
    ],
  },

  "enterprise-gateway-integration": {
    slug: "enterprise-gateway-integration",
    title: "Reverse Proxy Gateway Integration: Context Compression in Production Python Gateways",
    subtitle: "Deploying Transparent Pre-Dispatch Context Optimization in Enterprise Services",
    abstract: "A complete step-by-step engineering blueprint for deploying LLMSlim context compression inside FastAPI API gateways and async HTTP clients.",
    author: "Yashvardhan Thanvi",
    authorRole: "LLMSlim Author & Core Maintainer",
    publishedDate: "July 15, 2026",
    lastUpdated: "July 15, 2026",
    readingTime: "8 min read",
    category: "Systems & Architecture",
    mathIntuitionSummary: "Intercepts POST payloads, measures prompt token length, applies compression if length exceeds threshold N_min, and forwards payload to provider.",
    keyTakeaways: [
      "Gateway proxy patterns decouple prompt optimization logic from downstream application code.",
      "Threshold-based routing compresses long RAG contexts while bypassing short query requests.",
      "Preserves original system messages and API request/response contracts."
    ],
    references: [
      {
        citationKey: "FastAPI Documentation",
        title: "FastAPI Middleware & Asynchronous Routing Architecture",
        url: "https://fastapi.tiangolo.com/tutorial/middleware/",
      },
    ],
    sections: [
      {
        id: "fastapi-gateway-code",
        title: "1. Production FastAPI Interceptor Implementation",
        content: "Implementing a transparent reverse proxy route:",
        codeSnippet: {
          language: "python",
          filename: "gateway_proxy.py",
          code: `from fastapi import FastAPI, Request, Response
import httpx
from llmslim import compress

app = FastAPI()
http_client = httpx.AsyncClient()

MIN_COMPRESSION_THRESHOLD = 500  # Only compress prompts over 500 tokens

@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request):
    payload = await request.json()
    messages = payload.get("messages", [])
    
    # Process system and context messages
    for msg in messages:
        content = msg.get("content", "")
        if len(content) > MIN_COMPRESSION_THRESHOLD:
            compressed = compress(content, target_ratio=0.5).compressed_text
            msg["content"] = compressed

    # Forward to target LLM provider (e.g. OpenAI)
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    provider_res = await http_client.post(
        "https://api.openai.com/v1/chat/completions",
        json=payload,
        headers=headers
    )
    
    return Response(
        content=provider_res.content,
        status_code=provider_res.status_code,
        headers=dict(provider_res.headers)
    )`,
        },
      },
    ],
  },
};
