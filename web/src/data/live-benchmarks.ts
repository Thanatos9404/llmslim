/**
 * Real-model benchmark results: Claude Haiku 5.5 (`claude-haiku-5-5`, effort low) through the Claude API, official
 * datasets, prompts and scoring. Every number comes from a run in the public repository: round 3
 * (benchmarks/live/round3, LLMSlim Core 0.9.0 against Mem0, Zep, LLMLingua-2, LongLLMLingua and RAG, cost first) and,
 * for long documents and agents, round 2 (benchmarks/live, Core 0.8.0). Nothing is estimated. Weak results stay in.
 */

export type ArmKind = "full" | "llmslim" | "previous" | "baseline" | "competitor"

export type Arm = {
  name: string
  kind: ArmKind
  score: number
  /** Mean context or input tokens sent per question. */
  tokens?: number
  /** USD per 1,000 questions at list prices, end to end (see METHOD_NOTES). */
  cost?: number
}

export type LiveSuite = {
  id: string
  name: string
  what: string
  metric: string
  n: string
  arms: Arm[]
  takeaway: string
  caveat?: string
  /** A second view of the same suite: another budget, the sample a competitor ran on, or a fresh held-out sample. */
  extra?: { label: string; n: string; arms: Arm[] }
}

/** Competing systems we ran ourselves on their own pre-registered samples: same reader, questions and budget. */
export type HeadToHead = {
  columns: [string, string, string]
  rows: { system: string; model: string; scoreA: string; scoreB: string; scoreC: string; cost: string; time: string; best?: boolean }[]
  note: string
  /** The competitors' papers and code, and our raw results and run scripts, so anyone can check or rerun it. */
  sources: { label: string; url: string }[]
}

export const LIVE_MODEL = "Claude Haiku 5.5"
export const LIVE_DATE = "October 2026"
/** When the /benchmarks and /results content last changed: their sitemap lastmod. Update it with the content. */
export const RESULTS_LAST_UPDATED = "15 Oct 2026"
/** Round 3, the current results: the release they were measured on. */
export const CORE_VERSION_TESTED = "0.9.0"
/** Round 2 (long documents and agents): Core 0.8.0, 12 Oct 2026. */
export const CORE_VERSION_LONG_DOCS = "0.8.0"
export const PLATFORM_VERSION_TESTED = "0.9.1"
export const ROUND3_REPORT = "https://github.com/Thanatos9404/llmslim/blob/main/benchmarks/live/round3/RESULTS.md"

/** Round 3: held-out test questions, read once, costs per 1,000 questions as run (see METHOD_NOTES). */
export const LIVE_SUITES: LiveSuite[] = [
  {
    id: "locomo",
    name: "LoCoMo",
    what: "Questions about 8 long conversations between two people, each about 27k tokens over up to 35 sessions. The memory systems' own benchmark.",
    metric: "accuracy (Mem0's judge)",
    n: "1,307 test questions, about 2,500 tokens",
    arms: [
      { name: "Full history, read from the prompt cache", kind: "full", score: 95.1, tokens: 27133, cost: 0.83 },
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 93.0, tokens: 2495, cost: 0.95 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 91.7, tokens: 2492, cost: 0.89 },
      { name: "Mem0, top 50 memories", kind: "competitor", score: 91.0, tokens: 2425, cost: 2.66 },
      { name: "RAG over turns", kind: "baseline", score: 85.2, tokens: 2430, cost: 0.90 },
      { name: "Zep", kind: "competitor", score: 74.4, tokens: 2738, cost: 6.24 },
      { name: "LongLLMLingua (300-question sample)", kind: "competitor", score: 73.3, tokens: 2005, cost: 7.01 },
      { name: "LLMLingua-2", kind: "competitor", score: 34.1, tokens: 1988, cost: 0.43 },
      { name: "Most recent turns", kind: "baseline", score: 20.7, tokens: 2438, cost: 0.37 },
    ],
    takeaway: "With its reranker LLMSlim answers 93.0%, against 91.0% for Mem0's top 50 memories, at about a third of the cost per question: most of Mem0's and Zep's cost is the model calls that build their memory. LLMSlim is on the cost frontier at every budget; Mem0, Zep, LongLLMLingua and RAG are not.",
    caveat: "Because a conversation's questions were asked back to back, the full history was read from the prompt cache: 95.1% for $0.83 per 1,000 questions. Without the cache it costs $4.48. At 10,000 tokens LLMSlim scores 94.3% for $2.02.",
    extra: { label: "About 1,000 tokens", n: "1,307 test questions", arms: [
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 90.5, cost: 0.70 },
      { name: "Mem0, top 20 memories", kind: "competitor", score: 88.7, cost: 2.43 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 87.5, cost: 0.67 },
      { name: "RAG over turns", kind: "baseline", score: 78.9, cost: 0.68 },
    ] },
  },
  {
    id: "longmemeval",
    name: "LongMemEval-S",
    what: "Answer a question from about 50 earlier chat sessions (111k tokens of history per question).",
    metric: "accuracy (official judge)",
    n: "180 test questions, about 10,000 tokens",
    arms: [
      { name: "RAG over turns (Qwen3-Embedding-0.6B)", kind: "baseline", score: 80.6, tokens: 9912, cost: 4.45 },
      { name: "Full history", kind: "full", score: 77.8, tokens: 111372, cost: 90.21 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 77.8, tokens: 10008, cost: 2.13 },
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 74.4, tokens: 10007, cost: 2.21 },
      { name: "LLMLingua-2", kind: "competitor", score: 15.6, tokens: 7809, cost: 8.43 },
      { name: "Most recent sessions", kind: "baseline", score: 11.1, tokens: 9948, cost: 2.09 },
    ],
    takeaway: "At 10,000 tokens LLMSlim answers as many questions as the whole history, 77.8%, for $2.13 per 1,000 instead of $90.21 (prompts over 100k tokens are billed at the higher rate). LLMLingua-2 answers 16%.",
    caveat: "Dense retrieval over turns is ahead: 80.6% at 10,000 tokens and 76.1% at 2,500, at about twice the cost. Neither gap is significant on 180 questions, but both point the same way. A fix that narrowed it on development questions did not hold up on test, so it is not in 0.9.0.",
    extra: { label: "About 2,500 tokens", n: "180 test questions", arms: [
      { name: "RAG over turns", kind: "baseline", score: 76.1, cost: 3.32 },
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 74.4, cost: 1.05 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 70.6, cost: 0.98 },
      { name: "LLMLingua-2", kind: "competitor", score: 7.2, cost: 6.58 },
    ] },
  },
  {
    id: "memory-systems",
    name: "LongMemEval-S, against Mem0 and Zep",
    what: "The same task on the pre-registered questions Mem0 and Zep were run on. Each question has its own 500-message history, so each one needs its own memory.",
    metric: "accuracy (official judge)",
    n: "Mem0's 60-question sample, about 2,500 tokens",
    arms: [
      { name: "RAG over turns", kind: "baseline", score: 80.0, tokens: 2473, cost: 3.36 },
      { name: "Full history", kind: "full", score: 78.3, tokens: 111417, cost: 90.20 },
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 78.3, tokens: 2501, cost: 1.04 },
      { name: "Mem0, top 200 memories", kind: "competitor", score: 76.7, tokens: 11347, cost: 220.88 },
      { name: "Mem0, top 50 memories", kind: "competitor", score: 75.0, tokens: 2848, cost: 219.50 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 71.7, tokens: 2501, cost: 0.96 },
    ],
    takeaway: "LLMSlim with its reranker matches the whole history and Mem0's best setting for $1.04 per 1,000 questions. Mem0 costs $220.88, almost all of it the extraction calls that build a memory of each history (about $0.22 a question). On Zep's sample, Zep answers 58.3% for $697.56 per 1,000 questions; LLMSlim answers 87.5% for $0.94.",
    caveat: "Small samples: the 95% intervals are about ±10 points on 60 questions and ±17 on 24. Mem0's and Zep's embedding and database compute is not counted, which favours them.",
    extra: { label: "Zep's 24-question sample", n: "24 questions", arms: [
      { name: "Full history", kind: "full", score: 91.7, cost: 90.22 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 87.5, cost: 0.94 },
      { name: "Mem0, top 50 memories", kind: "competitor", score: 87.5, cost: 219.48 },
      { name: "Zep", kind: "competitor", score: 58.3, cost: 697.56 },
    ] },
  },
  {
    id: "nq",
    name: "NaturalQuestions, 20 documents",
    what: "Open-domain questions with 20 retrieved passages, the answer in one of them, cut to 25% of the tokens.",
    metric: "accuracy (answer in response)",
    n: "2,255 test questions",
    arms: [
      { name: "Full context", kind: "full", score: 78.4, tokens: 2908, cost: 0.65 },
      { name: "Plain reranker", kind: "baseline", score: 73.9, tokens: 686, cost: 0.30 },
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 73.5, tokens: 668, cost: 0.33 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 60.6, tokens: 660, cost: 0.30 },
      { name: "Passages in order", kind: "baseline", score: 55.9, tokens: 692, cost: 0.30 },
      { name: "LLMLingua-2", kind: "competitor", score: 52.5, tokens: 684, cost: 0.87 },
    ],
    takeaway: "With its reranker LLMSlim matches a plain reranker (73.5% against 73.9%) and is 21 points ahead of LLMLingua-2 at the same budget. On LongLLMLingua's 1,000-question sample it is level with LongLLMLingua (72.7% against 70.5%, within noise) at a quarter of its cost.",
    caveat: "The default lexical mode scores 60.6%: paraphrased questions need semantic matching, so use the reranker for open-domain retrieval.",
    extra: { label: "LongLLMLingua's 1,000-question sample", n: "1,000 questions", arms: [
      { name: "Full context", kind: "full", score: 77.2, cost: 0.65 },
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 72.7, cost: 0.33 },
      { name: "LongLLMLingua", kind: "competitor", score: 70.5, cost: 1.32 },
      { name: "LLMLingua-2", kind: "competitor", score: 52.0, cost: 0.86 },
    ] },
  },
  {
    id: "hotpotqa",
    name: "HotpotQA (distractor)",
    what: "Multi-hop questions over 10 Wikipedia paragraphs, 2 of them relevant, cut to 40% of the tokens.",
    metric: "exact match",
    n: "2,000 test questions",
    arms: [
      { name: "Full context", kind: "full", score: 58.0, tokens: 1315, cost: 0.24 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 52.4, tokens: 522, cost: 0.13 },
      { name: "LLMSlim 0.9 + reranker", kind: "llmslim", score: 52.2, tokens: 522, cost: 0.15 },
      { name: "Plain reranker", kind: "baseline", score: 50.5, tokens: 487, cost: 0.13 },
      { name: "LLMLingua-2", kind: "competitor", score: 46.7, tokens: 491, cost: 0.47 },
      { name: "Passages in order", kind: "baseline", score: 36.1, tokens: 491, cost: 0.16 },
    ],
    takeaway: "The default LLMSlim scores 52.4%, against 50.5% for the plain reranker and 46.7% for LLMLingua-2, and on LongLLMLingua's sample it is level with LongLLMLingua (53.3% against 50.4%, within noise). It has the lowest cost per correct answer of any compressor here, level with the plain reranker.",
    caveat: "Full context is still 5.6 points ahead: on a 1.3k-token context there is little to remove.",
    extra: { label: "LongLLMLingua's 1,000-question sample", n: "1,000 questions", arms: [
      { name: "Full context", kind: "full", score: 58.5, cost: 0.24 },
      { name: "LLMSlim 0.9", kind: "llmslim", score: 53.3, cost: 0.13 },
      { name: "LongLLMLingua", kind: "competitor", score: 50.4, cost: 0.77 },
      { name: "LLMLingua-2", kind: "competitor", score: 48.9, cost: 0.47 },
    ] },
  },
]

/** Round 2, Core 0.8.0 (12 Oct 2026): long documents. Costs are the answer call on Haiku 5.5 per 1,000 questions. */
export const LONG_DOC_SUITES: LiveSuite[] = [
  {
    id: "longbench",
    name: "LongBench v1",
    what: "Seven long-context tasks: document QA, multi-hop QA, summarisation, few-shot QA and code completion (15.5k tokens on average).",
    metric: "macro average of official metrics",
    n: "210 samples, 30 per task",
    arms: [
      { name: "Full context", kind: "full", score: 54.9, tokens: 15532, cost: 1.812 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 54.9, tokens: 5232, cost: 0.778 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 54.2, tokens: 5229, cost: 0.778 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 52.4, tokens: 5164, cost: 0.779 },
      { name: "Middle truncation, same budget", kind: "baseline", score: 45.2, tokens: 5147, cost: 0.785 },
    ],
    takeaway: "The same macro score as full context (95% CI −4.5 to +4.6) on a third of the tokens, and +9.8 over truncation. On the original sample RepoBench-P (cross-file code, 30 samples) scored above full context, 57.2 against 44.3; it did not on the fresh sample.",
    caveat: "MuSiQue multi-hop QA is still below full context (58.8 against 64.9; 61.2 with the reranker), though most of the 0.8 pre-release drop (48.3) is recovered.",
    extra: { label: "Fresh questions, never used in development", n: "210 new samples", arms: [
      { name: "Full context", kind: "full", score: 55.1 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 55.4 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 55.0 },
      { name: "Middle truncation, same budget", kind: "baseline", score: 46.8 },
    ] },
  },
  {
    id: "longbench-v2",
    name: "LongBench v2 (short split)",
    what: "Hard multiple-choice questions over long documents, codebases and structured data (30k tokens on average).",
    metric: "accuracy",
    n: "180 questions",
    arms: [
      { name: "Full context", kind: "full", score: 60.0, tokens: 30493, cost: 7.621 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 55.6, tokens: 8469, cost: 1.688 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 53.9, tokens: 8470, cost: 1.689 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 51.1, tokens: 8566, cost: 1.902 },
      { name: "Middle truncation, same budget", kind: "baseline", score: 48.3, tokens: 8566, cost: 1.942 },
    ],
    takeaway: "72% fewer tokens and 78% lower cost. With the reranker, 4.4 points below full context (95% CI −11.7 to +2.8), and the best compressed arm.",
    caveat: "Questions that need the whole document lose accuracy: hard multiple choice over 30k tokens is where compression costs the most.",
  },
]

export type AgentFinding = { name: string; what: string; rows: { arm: string; result: string; detail: string }[]; takeaway: string }

export const AGENT_FINDINGS: AgentFinding[] = [
  {
    name: "SWE-bench Verified Mini",
    what: "50 real GitHub issues (Django, Sphinx); a bash-tool agent edits the repository; graded by the official test harness.",
    rows: [
      { arm: "Agent, no compression (two runs)", result: "36 and 38 of 50", detail: "58k and 48k prompt tokens per task" },
      { arm: "LLMSlim Core 0.8 on outputs over 800 tokens", result: "38 of 50", detail: "28 outputs compressed; 51k prompt tokens per task" },
      { arm: "LLMSlim Core 0.7.2, same setting", result: "34 of 50", detail: "30 outputs compressed; 59k prompt tokens per task" },
    ],
    takeaway: "Core 0.8 matches the best uncompressed run with a cost per task between the two: no harm, little saving. A careful agent keeps its context near 8k tokens, so there is not much to remove. Published work found LLMLingua-2 on tool output cost an agent 8 points.",
  },
  {
    name: "InjecAgent (enhanced attacks)",
    what: "1,054 cases where a tool result carries an attacker instruction; success means the agent calls the attacker's tool.",
    rows: [
      { arm: "Native tool-use history", result: "0 of 1,054", detail: "attack success 0.0%; 1 repeated call" },
      { arm: "Platform 0.9.0 flow (request after the tool results)", result: "0 of 1,054", detail: "attack success 0.0%; 50 repeated calls" },
      { arm: "Platform 0.9.1 agent turn (continue_turn)", result: "0 of 1,054", detail: "attack success 0.0%; 0 repeated calls" },
    ],
    takeaway: "The reader model resisted every attack on its own, so this benchmark shows no defence effect with this model. It did expose an agent-loop gap, now fixed: before agent turns, the Platform put the user's request after the tool results and the model repeated its call 50 times. With continue_turn, the turn is shown in the order it happened and no call is repeated.",
  },
]

/** Published numbers from other systems. Different reader models: compare the gap to full context, not raw scores. */
export type PublishedResult = {
  system: string
  benchmark: string
  reader: string
  score: string
  fullContext: string
  tokens: string
  source: string
  url: string
}

export const PUBLISHED: PublishedResult[] = [
  { system: "Zep", benchmark: "LongMemEval-S", reader: "GPT-4o", score: "71.2%", fullContext: "60.2%", tokens: "1.6k", source: "Zep paper (self-reported)", url: "https://arxiv.org/abs/2501.13956" },
  { system: "Mem0", benchmark: "LongMemEval-S", reader: "GPT-4o-mini", score: "53.6 to 66.4%", fullContext: "55.4 to 56.8%", tokens: "n/a", source: "Third-party re-runs (MemOS, LightMem papers)", url: "https://arxiv.org/abs/2507.03724" },
  { system: "LongLLMLingua (4x)", benchmark: "NQ, 20 documents", reader: "GPT-3.5-Turbo", score: "71.2 to 75.0", fullContext: "54.1 to 75.7", tokens: "748", source: "LongLLMLingua paper", url: "https://arxiv.org/abs/2310.06839" },
  { system: "LLMLingua-2 (3.9x)", benchmark: "NQ, 20 documents", reader: "GPT-3.5-Turbo", score: "39.9 to 48.6", fullContext: "54.1 to 75.7", tokens: "748", source: "LLMLingua-2 paper", url: "https://arxiv.org/abs/2403.12968" },
  { system: "LLMLingua-2 (3k)", benchmark: "LongBench v1", reader: "GPT-3.5-Turbo", score: "42.4", fullContext: "44.0", tokens: "3,392", source: "LLMLingua-2 paper", url: "https://arxiv.org/abs/2403.12968" },
  { system: "LLMLingua-2 on tool output", benchmark: "SWE-bench Verified (50)", reader: "Not stated", score: "54%", fullContext: "62%", tokens: "n/a", source: "SWE-Pruner paper", url: "https://arxiv.org/abs/2601.16746" },
]

export const METHOD_NOTES = [
  "Reader: Claude Haiku 5.5 at effort low for every system, with the same answer prompt (Mem0's own, vendored verbatim) and the same judges. Only the context changes.",
  "Cost first. Every table prices 1,000 questions end to end at list prices: the reader's answer call, Mem0's and Zep's ingestion calls, and each system's build time as cloud machine time (a T4 GPU at $0.526 an hour, or 2 vCPUs at $0.0892). Judge calls are not counted for anyone, and neither is Mem0's and Zep's embedding and database compute, which favours them.",
  "Held-out test questions. The splits were committed before any result. LLMSlim was tuned on development questions only, and the test questions were read once per version. A change that helped on development questions but not on test was not shipped.",
  "Judges: LoCoMo uses Mem0's judge, from Mem0's own harness; LongMemEval uses the official LongMemEval judge prompts. The full report also gives Mem0's more lenient judge on LongMemEval, and LoCoMo's token F1.",
  "Competitors ran their own way: Mem0 OSS 2.2.1 through Mem0's benchmark harness, Zep (Graphiti 0.30.2 on Neo4j) through Zep's, and LLMLingua-2 and LongLLMLingua (LLaMA-2-7B in float16, the paper's settings) at the same token budget. Every Mem0 and Zep model call went to Haiku 5.5 through one metering proxy.",
  "Every compressor's context was built in public Kaggle notebooks pinned to a commit, whose manifests hash every input and output, so anyone can rerun them and compare byte for byte.",
  "Confidence intervals are paired bootstrap 95% over the same questions.",
  "The optional reranker is cross-encoder/ms-marco-MiniLM-L-6-v2 (22M parameters). Install it with pip install \"llmslim[semantic]\" and pass relevance=\"semantic\". Without it, LLMSlim runs no model at all.",
  "LongBench v1 and v2 and the agent results were measured on Core 0.8.0 (12 Oct 2026). 0.9.0 changes only how plain-text chat transcripts are selected.",
]

export const HEAD_TO_HEAD: HeadToHead = {
  columns: ["NaturalQuestions (1,000)", "HotpotQA (1,000)", "LoCoMo (300)"],
  rows: [
    { system: "LLMSlim 0.9 + reranker", model: "22M cross-encoder", scoreA: "72.7", scoreB: "52.8", scoreC: "93.3", cost: "$0.33", time: "1.3 s on a CPU" },
    { system: "LLMSlim 0.9", model: "none", scoreA: "59.6", scoreB: "53.3", scoreC: "91.7", cost: "$0.30", time: "18 ms on a CPU" },
    { system: "LongLLMLingua", model: "LLaMA-2-7B, float16", scoreA: "70.5", scoreB: "50.4", scoreC: "73.3", cost: "$1.32", time: "6.9 s on a T4 GPU" },
    { system: "LLMLingua-2", model: "XLM-RoBERTa-large", scoreA: "52.0", scoreB: "48.9", scoreC: "33.0", cost: "$0.86", time: "3.5 s on a T4 GPU" },
    { system: "Full context", model: "none", scoreA: "77.2", scoreB: "58.5", scoreC: "94.7", cost: "$0.65", time: "" },
  ],
  note: "LongLLMLingua runs a 7B model for about 7 seconds a question, so it ran on pre-registered samples: 1,000 NaturalQuestions and HotpotQA questions and 300 LoCoMo questions, at about 2,500 tokens. Every system is scored here on those same questions. Against LongLLMLingua, LLMSlim with its reranker is level on NaturalQuestions (+2.2 points, 95% interval −0.8 to +5.3) and ahead on LoCoMo (+20.0, 15.0 to 25.0); the default LLMSlim is level on HotpotQA (+2.9, −0.1 to +5.7). Scores are accuracy, exact match on HotpotQA and Mem0's judge on LoCoMo. Cost is per 1,000 NaturalQuestions questions, end to end. Time is the median to compress one NaturalQuestions question.",
  sources: [
    { label: "LLMLingua-2 paper (arXiv 2403.12968)", url: "https://arxiv.org/abs/2403.12968" },
    { label: "LongLLMLingua paper (arXiv 2310.06839)", url: "https://arxiv.org/abs/2310.06839" },
    { label: "LLMLingua code (microsoft/LLMLingua)", url: "https://github.com/microsoft/LLMLingua" },
    { label: "Round 3 report and tables", url: ROUND3_REPORT },
    { label: "Per-question results", url: "https://github.com/Thanatos9404/llmslim/tree/main/benchmarks/live/round3/results" },
    { label: "Kaggle build notebooks and run scripts", url: "https://github.com/Thanatos9404/llmslim/tree/main/benchmarks/live/round3" },
  ],
}

/** Where LLMSlim loses in round 3, from the report's own section of the same name. */
export const WEAK_SPOTS: { title: string; body: string }[] = [
  { title: "Open-domain retrieval without the reranker", body: "On NaturalQuestions the default lexical mode scores 60.6%, against 73.9% for a plain reranker. Paraphrased questions need semantic matching. With its optional reranker LLMSlim scores 73.5%." },
  { title: "Dense retrieval on LongMemEval", body: "RAG over turns scores 80.6% to LLMSlim's 77.8% at 10,000 tokens, and 76.1% to 74.4% at 2,500, at about twice the cost. Neither gap is significant on 180 questions, but both point the same way. A fix that narrowed it on development questions did not hold up on test, so it was not shipped." },
  { title: "Multi-hop and temporal questions at 1,000 tokens", body: "Overall, Mem0's top 20 memories and LLMSlim are within noise (88.7% and 87.5%), but Mem0 is clearly better on LoCoMo's multi-hop (88.7% against 80.3%) and temporal (93.4% against 85.7%) questions, where its extracted facts pack evidence from many sessions into few tokens. With the reranker LLMSlim is ahead overall (90.5%)." },
  { title: "A cached full history", body: "When a conversation's questions come back to back, the cached full history (95.1% for $0.83 per 1,000 questions) is cheaper than LLMSlim at 10,000 tokens and more accurate than any compressed context. LLMSlim is the cheaper choice when the context changes between questions, when questions arrive too far apart for the cache, or when a history is long enough to be billed at the long-prompt rate." },
]
