/**
 * Numbers behind /results. Every value comes from a run in the public repository, with Claude Haiku 5.5 reading
 * every context: round 3 (benchmarks/live/round3, Core 0.9, held-out test questions, cost first) for chat memory and
 * retrieval, and round 2 (benchmarks/live, Core 0.8) for long documents and agents.
 */

/** Named once, in the fine print. */
export const READER = "Claude Haiku 5.5"

export type ArmKind = "full" | "llmslim" | "lite" | "baseline" | "competitor"
export type Arm = { name: string; score: number; kind: ArmKind }

export type Benchmark = {
  id: string
  name: string
  short: string
  question: string
  metric: string
  max: number
  unit: string
  lowerIsBetter?: boolean
  arms: Arm[]
  info: [string, string][]
  verdict: string
  /** A strip of squares: how much was kept, or how many tasks came out right. */
  pixels: { total: number; lit: number; label: string }
}

export const BENCHMARKS: Benchmark[] = [
  {
    id: "locomo", name: "LoCoMo", short: "Chat memory",
    question: "Questions about long conversations between two people", metric: "accuracy", max: 100, unit: "%",
    arms: [
      { name: "Whole history", score: 95.1, kind: "full" },
      { name: "LLMSlim + reranker", score: 93.0, kind: "llmslim" },
      { name: "Mem0, top 50 memories", score: 91.0, kind: "competitor" },
      { name: "Zep", score: 74.4, kind: "competitor" },
    ],
    info: [["Questions", "1,307 held-out"], ["Budget", "about 2,500 tokens"], ["Context", "27,133 → 2,495 tokens"], ["Cost per 1k", "$0.95 · Mem0 $2.66 · Zep $6.24"], ["LongLLMLingua", "73.3% on its 300 questions"]],
    verdict: "More answers right than Mem0, at about a third of the cost",
    pixels: { total: 100, lit: 9, label: "9% of the tokens kept" },
  },
  {
    id: "longmemeval", name: "LongMemEval-S", short: "Long histories",
    question: "Answer from about 50 earlier chat sessions", metric: "accuracy", max: 100, unit: "%",
    arms: [
      { name: "Dense retrieval over turns", score: 80.6, kind: "baseline" },
      { name: "Whole history", score: 77.8, kind: "full" },
      { name: "LLMSlim", score: 77.8, kind: "llmslim" },
      { name: "LLMLingua-2", score: 15.6, kind: "competitor" },
    ],
    info: [["Questions", "180 held-out"], ["Budget", "10,000 tokens"], ["Context", "111,372 → 10,008 tokens"], ["Cost per 1k", "$90.21 → $2.13"], ["Mem0, its 60", "76.7% for $220.88 · LLMSlim 78.3% for $1.04"]],
    verdict: "As accurate as the whole history at 1/42 of the cost",
    pixels: { total: 100, lit: 9, label: "9% of the tokens kept" },
  },
  {
    id: "nq", name: "NaturalQuestions", short: "Retrieval",
    question: "20 retrieved passages, the answer in one", metric: "accuracy", max: 100, unit: "%",
    arms: [
      { name: "Every passage", score: 78.4, kind: "full" },
      { name: "LLMSlim + reranker", score: 73.5, kind: "llmslim" },
      { name: "LLMSlim", score: 60.6, kind: "lite" },
      { name: "LLMLingua-2", score: 52.5, kind: "competitor" },
    ],
    info: [["Questions", "2,255 held-out"], ["Budget", "25%"], ["Context", "2,908 → 668 tokens"], ["Cost per 1k", "$0.65 → $0.33"], ["LongLLMLingua", "70.5% vs 72.7% on its 1,000"]],
    verdict: "Level with a plain reranker, ahead of the LLMLingua family",
    pixels: { total: 100, lit: 23, label: "23% of the tokens kept" },
  },
  {
    id: "hotpotqa", name: "HotpotQA", short: "Multi-hop",
    question: "Two of ten paragraphs hold the answer", metric: "exact match", max: 100, unit: "",
    arms: [
      { name: "All ten paragraphs", score: 58.0, kind: "full" },
      { name: "LLMSlim", score: 52.4, kind: "llmslim" },
      { name: "Plain reranker", score: 50.5, kind: "baseline" },
      { name: "LLMLingua-2", score: 46.7, kind: "competitor" },
    ],
    info: [["Questions", "2,000 held-out"], ["Budget", "40%"], ["Context", "1,315 → 522 tokens"], ["Cost per 1k", "$0.24 → $0.13"], ["LongLLMLingua", "50.4 vs 53.3 on its 1,000"]],
    verdict: "90% of the full-context score on 40% of the tokens",
    pixels: { total: 100, lit: 40, label: "40% of the tokens kept" },
  },
  {
    id: "longbench", name: "LongBench v1", short: "Long docs",
    question: "Seven tasks over 15.5k-token documents", metric: "macro score", max: 70, unit: "",
    arms: [
      { name: "Full context", score: 54.9, kind: "full" },
      { name: "LLMSlim", score: 54.9, kind: "llmslim" },
      { name: "LLMSlim + reranker", score: 54.2, kind: "lite" },
      { name: "Middle truncation", score: 45.2, kind: "baseline" },
    ],
    info: [["Samples", "210 · Core 0.8"], ["Budget", "3,000 tokens"], ["Context", "15,532 → 5,232 tokens"], ["vs full", "+0.0 (95% CI −4.5 to +4.6)"], ["Fresh 210", "55.0 vs 55.1 full context"]],
    verdict: "The same score on a third of the tokens",
    pixels: { total: 100, lit: 34, label: "34% of the tokens kept" },
  },
  {
    id: "longbench-v2", name: "LongBench v2", short: "Hard docs",
    question: "Multiple choice over 30k-token documents", metric: "accuracy", max: 100, unit: "%",
    arms: [
      { name: "Full context", score: 60.0, kind: "full" },
      { name: "LLMSlim + reranker", score: 55.6, kind: "llmslim" },
      { name: "LLMSlim", score: 53.9, kind: "lite" },
      { name: "Middle truncation", score: 48.3, kind: "baseline" },
    ],
    info: [["Questions", "180 · Core 0.8"], ["Budget", "25%"], ["Context", "30,493 → 8,469 tokens"], ["Cost per 1k", "$7.62 → $1.69"], ["vs full", "−4.4 (95% CI −11.7 to +2.8)"]],
    verdict: "72% fewer tokens, the best compressed score",
    pixels: { total: 100, lit: 28, label: "28% of the tokens kept" },
  },
  {
    id: "swe", name: "SWE-bench Verified", short: "Coding agent",
    question: "50 real GitHub issues, graded by the official harness", metric: "issues resolved", max: 50, unit: "",
    arms: [
      { name: "No compression, best run", score: 38, kind: "full" },
      { name: "LLMSlim 0.8", score: 38, kind: "llmslim" },
      { name: "No compression, second run", score: 36, kind: "baseline" },
      { name: "LLMSlim 0.7.2", score: 34, kind: "lite" },
    ],
    info: [["Issues", "25 Django · 25 Sphinx"], ["Compressed", "Outputs over 800 tokens"], ["Prompt tokens", "48–58k → 51k per task"], ["Cost per task", "$0.0027–0.0032 → $0.0029"], ["Agent", "bash tool, official images"]],
    verdict: "No measured harm inside a coding agent",
    pixels: { total: 50, lit: 38, label: "38 of 50 issues resolved" },
  },
  {
    id: "injecagent", name: "InjecAgent", short: "Agent turns",
    question: "1,054 tool results carrying an injected instruction", metric: "repeated tool calls", max: 50, unit: "", lowerIsBetter: true,
    arms: [
      { name: "Request after the tool results", score: 50, kind: "baseline" },
      { name: "Calls beside their results", score: 43, kind: "lite" },
      { name: "Native tool-use history", score: 1, kind: "full" },
      { name: "Vault agent turn", score: 0, kind: "llmslim" },
    ],
    info: [["Cases", "1,054 · enhanced attacks"], ["Attack success", "0 in every setup"], ["Fix", "prepare(continue_turn=True)"], ["Vault", "0.9.1"], ["Reader", "Resisted every attack alone"]],
    verdict: "Agent turns in order: zero repeated calls",
    pixels: { total: 50, lit: 0, label: "0 of 50 repeated calls" },
  },
]

export type RacePoint = {
  name: string; model: string; score: number; cost: number; kind: ArmKind
  /** Where the label sits: above or below the point. Default: below for lite and baseline points, above otherwise. */
  place?: "above" | "below"
  /** Label offset from the point, in chart units, when two labels would collide. */
  dy?: number
}
export type RaceSet = {
  key: string
  label: string
  /** What was measured, for the chart's caption. */
  n: string
  metric: string
  /** The reference line: the whole context, and what it costs. */
  full: { score: number; cost: number; label: string }
  /** The system the cost ratio is drawn against. */
  rival: string
  y: [number, number]
  rows: RacePoint[]
  note: string
}

/** Accuracy against what 1,000 questions cost end to end (round 3): one set per benchmark sample. */
export const RACE: RaceSet[] = [
  {
    key: "locomo", label: "LoCoMo", n: "1,307 questions, about 2,500 tokens", metric: "accuracy", rival: "Mem0",
    full: { score: 95.1, cost: 0.83, label: "Whole history, cached" }, y: [70, 100],
    rows: [
      { name: "LLMSlim + reranker", model: "22M cross-encoder", score: 93.0, cost: 0.95, kind: "llmslim" },
      { name: "LLMSlim", model: "No model", score: 91.7, cost: 0.89, kind: "lite" },
      { name: "Mem0", model: "Top 50 memories", score: 91.0, cost: 2.66, kind: "competitor" },
      { name: "RAG over turns", model: "Qwen3-Embedding-0.6B", score: 85.2, cost: 0.90, kind: "baseline" },
      { name: "Zep", model: "Graphiti on Neo4j", score: 74.4, cost: 6.24, kind: "competitor" },
      { name: "LongLLMLingua", model: "LLaMA-2-7B, its 300 questions", score: 73.3, cost: 7.01, kind: "competitor", place: "below" },
    ],
    note: "Mem0's and Zep's cost is mostly the model calls that build their memory. LLMLingua-2 scores 34.1% and is off this chart. The whole history was read from the prompt cache; without it, it costs $4.48.",
  },
  {
    key: "mem0", label: "vs Mem0", n: "LongMemEval, Mem0's 60 questions", metric: "accuracy", rival: "Mem0",
    full: { score: 78.3, cost: 90.20, label: "Whole history" }, y: [65, 85],
    rows: [
      { name: "LLMSlim + reranker", model: "22M cross-encoder", score: 78.3, cost: 1.04, kind: "llmslim" },
      { name: "LLMSlim", model: "No model", score: 71.7, cost: 0.96, kind: "lite" },
      { name: "Mem0", model: "Top 200 memories", score: 76.7, cost: 220.88, kind: "competitor" },
      { name: "RAG over turns", model: "Qwen3-Embedding-0.6B", score: 80.0, cost: 3.36, kind: "baseline" },
    ],
    note: "Each LongMemEval question has its own 500-message history, so Mem0 builds a memory for each: about $0.22 a question. Small sample: the 95% intervals are about ±10 points.",
  },
  {
    key: "zep", label: "vs Zep", n: "LongMemEval, Zep's 24 questions", metric: "accuracy", rival: "Zep",
    full: { score: 91.7, cost: 90.22, label: "Whole history" }, y: [50, 100],
    rows: [
      { name: "LLMSlim", model: "No model", score: 87.5, cost: 0.94, kind: "llmslim" },
      { name: "Mem0", model: "Top 50 memories", score: 87.5, cost: 219.48, kind: "competitor" },
      { name: "RAG over turns", model: "Qwen3-Embedding-0.6B", score: 83.3, cost: 3.28, kind: "baseline" },
      { name: "Zep", model: "Graphiti on Neo4j", score: 58.3, cost: 697.56, kind: "competitor" },
    ],
    note: "Building Zep's graph of a 500-message history costs about $0.70 a question. On 24 questions the 95% intervals are about ±17 points.",
  },
  {
    key: "nq", label: "NaturalQuestions", n: "LongLLMLingua's 1,000 questions, 25% of the tokens", metric: "accuracy", rival: "LongLLMLingua",
    full: { score: 77.2, cost: 0.65, label: "Every passage" }, y: [45, 82],
    rows: [
      { name: "LLMSlim + reranker", model: "22M cross-encoder", score: 72.7, cost: 0.33, kind: "llmslim" },
      { name: "LLMSlim", model: "No model", score: 59.6, cost: 0.30, kind: "lite" },
      { name: "LongLLMLingua", model: "LLaMA-2-7B, float16", score: 70.5, cost: 1.32, kind: "competitor", place: "below" },
      { name: "LLMLingua-2", model: "XLM-RoBERTa-large", score: 52.0, cost: 0.86, kind: "competitor" },
      { name: "Plain reranker", model: "22M cross-encoder", score: 73.6, cost: 0.29, kind: "baseline", dy: -22 },
    ],
    note: "LLMSlim with its reranker is level with LongLLMLingua (+2.2 points, 95% interval −0.8 to +5.3) at a quarter of its cost, and level with a plain reranker. The default lexical mode needs the reranker for paraphrased questions.",
  },
  {
    key: "hotpot", label: "HotpotQA", n: "LongLLMLingua's 1,000 questions, 40% of the tokens", metric: "exact match", rival: "LongLLMLingua",
    full: { score: 58.5, cost: 0.24, label: "All ten paragraphs" }, y: [45, 60],
    rows: [
      { name: "LLMSlim", model: "No model", score: 53.3, cost: 0.13, kind: "llmslim" },
      { name: "LLMSlim + reranker", model: "22M cross-encoder", score: 52.8, cost: 0.15, kind: "lite" },
      { name: "LongLLMLingua", model: "LLaMA-2-7B, float16", score: 50.4, cost: 0.77, kind: "competitor" },
      { name: "LLMLingua-2", model: "XLM-RoBERTa-large", score: 48.9, cost: 0.47, kind: "competitor" },
      { name: "Plain reranker", model: "22M cross-encoder", score: 51.6, cost: 0.13, kind: "baseline" },
    ],
    note: "The default LLMSlim is level with LongLLMLingua (+2.9 points, 95% interval −0.1 to +5.7) at a sixth of its cost. Full context still leads by about 5 points.",
  },
]

/** The short version of where LLMSlim still trails; the benchmarks page has the rest. */
export const STILL_AHEAD = "Full context still leads on NaturalQuestions and HotpotQA by about 5 points, and dense retrieval over turns leads on LongMemEval at both budgets, within noise."
