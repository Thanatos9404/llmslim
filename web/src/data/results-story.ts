/**
 * Numbers behind /results. Every value comes from a run in the public repository's benchmarks/live harness, with
 * Claude Haiku 5.5 reading every context. "Original" questions are the ones reported since the first round;
 * "fresh" questions were drawn after development was frozen and run once.
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
    id: "longmemeval", name: "LongMemEval-S", short: "Chat memory",
    question: "Answer from about 50 earlier chat sessions", metric: "accuracy", max: 100, unit: "%",
    arms: [
      { name: "Whole history", score: 82.2, kind: "full" },
      { name: "LLMSlim + reranker", score: 76.7, kind: "llmslim" },
      { name: "LLMSlim", score: 68.9, kind: "lite" },
      { name: "Most recent sessions", score: 14.4, kind: "baseline" },
    ],
    info: [["Questions", "90 · 15 per type"], ["Budget", "8,000 tokens"], ["Context", "114,006 → 7,984 tokens"], ["Cost per 1k", "$90.72 → $1.45"], ["Fresh 90", "76.7% vs 72.2% whole history"]],
    verdict: "Within noise of the whole history at 1/62 of the cost",
    pixels: { total: 100, lit: 7, label: "7% of the history kept" },
  },
  {
    id: "nq", name: "NaturalQuestions", short: "Retrieval",
    question: "20 retrieved passages, the answer in one", metric: "accuracy", max: 100, unit: "%",
    arms: [
      { name: "Every passage", score: 86.3, kind: "full" },
      { name: "LLMSlim + reranker", score: 75.0, kind: "llmslim" },
      { name: "LLMSlim", score: 65.7, kind: "lite" },
      { name: "Passages in order", score: 52.0, kind: "baseline" },
    ],
    info: [["Questions", "300 · answer at 1st, 10th, 20th"], ["Budget", "25%"], ["Context", "2,889 → 668 tokens"], ["By position", "74 / 75 / 76% (cut: 95 / 32 / 29%)"], ["Fresh 300", "75.7% vs 88.0% every passage"]],
    verdict: "Finds the answer wherever it sits",
    pixels: { total: 100, lit: 23, label: "23% of the passages kept" },
  },
  {
    id: "hotpotqa", name: "HotpotQA", short: "Multi-hop",
    question: "Two of ten paragraphs hold the answer", metric: "answer F1", max: 100, unit: "",
    arms: [
      { name: "All ten paragraphs", score: 74.9, kind: "full" },
      { name: "LLMSlim + reranker", score: 69.4, kind: "llmslim" },
      { name: "LLMSlim", score: 67.5, kind: "lite" },
      { name: "Cut to the same size", score: 49.5, kind: "baseline" },
    ],
    info: [["Questions", "200"], ["Budget", "40%"], ["Context", "2,179 → 939 tokens"], ["Exact match", "56.0 vs 57.0 all paragraphs"], ["Fresh 200", "71.8 vs 77.5 F1"]],
    verdict: "Exact match level with full context on 43% of the tokens",
    pixels: { total: 100, lit: 43, label: "43% of the paragraphs kept" },
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
    info: [["Samples", "210 · 30 per task"], ["Budget", "3,000 tokens"], ["Context", "15,532 → 5,232 tokens"], ["vs full", "+0.0 (95% CI −4.5 to +4.6)"], ["Fresh 210", "55.0 vs 55.1 full context"]],
    verdict: "The same score on a third of the tokens",
    pixels: { total: 100, lit: 34, label: "34% of the document kept" },
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
    info: [["Questions", "180 · short split"], ["Budget", "25%"], ["Context", "30,493 → 8,469 tokens"], ["Cost per 1k", "$7.62 → $1.69"], ["vs full", "−4.4 (95% CI −11.7 to +2.8)"]],
    verdict: "72% fewer tokens, the best compressed score",
    pixels: { total: 100, lit: 28, label: "28% of the document kept" },
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
    verdict: "No harm inside a coding agent",
    pixels: { total: 50, lit: 38, label: "38 of 50 issues resolved" },
  },
  {
    id: "injecagent", name: "InjecAgent", short: "Agent turns",
    question: "1,054 tool results carrying an injected instruction", metric: "repeated tool calls", max: 50, unit: "", lowerIsBetter: true,
    arms: [
      { name: "Request after the tool results", score: 50, kind: "baseline" },
      { name: "Calls beside their results", score: 43, kind: "lite" },
      { name: "Native tool-use history", score: 1, kind: "full" },
      { name: "Platform agent turn", score: 0, kind: "llmslim" },
    ],
    info: [["Cases", "1,054 · enhanced attacks"], ["Attack success", "0 in every setup"], ["Fix", "prepare(continue_turn=True)"], ["Platform", "0.9.1"], ["Reader", "Resisted every attack alone"]],
    verdict: "Agent turns in order: zero repeated calls",
    pixels: { total: 50, lit: 0, label: "0 of 50 repeated calls" },
  },
]

/** Head to head on NaturalQuestions: two sets of 150 questions, same reader, same budget. */
export const RACE = {
  questions: 150,
  full: 87.3,
  fullFresh: 90.7,
  fullAll: 89.0,
  rows: [
    { name: "LLMSlim + reranker", model: "22M cross-encoder", score: 74.0, fresh: 83.3, all: 78.7, ms: 98, hardware: "GPU · ~0.3 s on CPU", kind: "llmslim" },
    { name: "LongLLMLingua", model: "LLaMA-2-7B, 4-bit", score: 80.0, fresh: 76.0, all: 78.0, ms: 9500, hardware: "GPU", kind: "competitor" },
    { name: "LLMLingua-2", model: "XLM-RoBERTa-large", score: 64.7, fresh: 73.3, all: 69.0, ms: 2942, hardware: "GPU · ~43 s on CPU", kind: "competitor" },
    { name: "LLMSlim", model: "No model", score: 63.3, fresh: 74.0, all: 68.7, ms: 23, hardware: "CPU", kind: "lite" },
    { name: "Cut to fit", model: "No model", score: 49.3, fresh: 47.3, all: 48.3, ms: 0, hardware: "", kind: "baseline" },
  ],
} as const

/** LLMSlim with the reranker on original and fresh questions, with full context on each. */
export const CONSISTENCY = [
  { suite: "LongMemEval", metric: "accuracy", original: 76.7, fresh: 76.7, fullOriginal: 82.2, fullFresh: 72.2 },
  { suite: "NaturalQuestions", metric: "accuracy", original: 75.0, fresh: 75.7, fullOriginal: 86.3, fullFresh: 88.0 },
  { suite: "HotpotQA", metric: "answer F1", original: 69.4, fresh: 71.8, fullOriginal: 74.9, fullFresh: 77.5 },
  { suite: "LongBench v1", metric: "macro", original: 54.2, fresh: 55.4, fullOriginal: 54.9, fullFresh: 55.1 },
] as const

/** The short version of where full context still leads; the full report has the rest. */
export const STILL_AHEAD = "Full context still leads on open-domain retrieval and multi-hop questions, by about 5 to 12 points."
