/**
 * Round 6 (BEAM-1M, 24-27 Oct 2026) for the memory comparison pages: LLMSlim 0.12 with its reranker against Mem0 and
 * Zep. Each number is written as benchmarks/live/round6/RESULTS.md prints it and keeps the summary.json field it comes
 * from (benchmarks/live/round6/summary.json), so tests/unit/round6-memory.test.ts can read that file and check every
 * value here against its field, to the precision shown. The pages format these values; they compute nothing new.
 */
import { siteConfig } from "@/config/site"

export { ROUND6_REPORT } from "@/data/live-benchmarks"
export const ROUND6_SUMMARY = `${siteConfig.github}/blob/main/benchmarks/live/round6/summary.json`
export const ROUND6_DATES = "24–27 Oct 2026"

/** summary.json `subsets`: all 35 conversations, or the seeded 30 that Zep ran on. */
export type Round6Subset = "all" | "zep"

/** One arm on one subset, summary.json `subsets.<subset>.arms.<arm>`. */
export type Round6Arm = {
  subset: Round6Subset
  arm: string
  /** `context_tokens_cl100k`, to the nearest token. */
  tokens: number
  /** `score.mean`, with `score.lo` and `score.hi`: the 95% t interval over conversations. */
  score: number
  low: number
  high: number
  /** `cost_per_1000_questions_usd.total`, in USD. */
  cost: number
}

export type Round6Comparison = "M2500" | "M10000" | "Z2500" | "Z10000"

/**
 * LLMSlim 0.12 minus a competitor, in points: summary.json `comparisons.<key>.difference`, or
 * `comparisons.<key>.per_type.<type>` for one question type. `low` and `high` are the 95% t interval.
 */
export type Round6Diff = { key: Round6Comparison; type?: string; mean: number; low: number; high: number }

export const ROUND6_ARMS = {
  all: {
    llmslim2500: { subset: "all", arm: "llmslim_fix_2500", tokens: 2436, score: 44.6, low: 41.9, high: 47.3, cost: 1.22 },
    mem0Top50: { subset: "all", arm: "mem0_top50", tokens: 3020, score: 43.4, low: 40.9, high: 45.8, cost: 73.12 },
    llmslim10000: { subset: "all", arm: "llmslim_fix_10000", tokens: 9766, score: 47.3, low: 44.3, high: 50.3, cost: 2.61 },
    mem0Top200: { subset: "all", arm: "mem0_top200", tokens: 12095, score: 46.7, low: 44.1, high: 49.3, cost: 74.53 },
  },
  zep: {
    llmslim2500: { subset: "zep", arm: "llmslim_fix_2500", tokens: 2434, score: 45.9, low: 43.3, high: 48.5, cost: 1.2 },
    mem0Top50: { subset: "zep", arm: "mem0_top50", tokens: 2984, score: 44.7, low: 42.3, high: 47.1, cost: 71.19 },
    llmslim10000: { subset: "zep", arm: "llmslim_fix_10000", tokens: 9755, score: 48.3, low: 45.1, high: 51.4, cost: 2.6 },
    mem0Top200: { subset: "zep", arm: "mem0_top200", tokens: 11912, score: 48.4, low: 46.1, high: 50.6, cost: 72.58 },
    zep: { subset: "zep", arm: "zep", tokens: 3397, score: 38.4, low: 35.6, high: 41.2, cost: 330.07 },
  },
} as const satisfies Record<Round6Subset, Record<string, Round6Arm>>

/** The four headline comparisons, with the paired cluster bootstrap 95% interval (`bootstrap_lo`, `bootstrap_hi`). */
export const ROUND6_DIFFS = {
  M2500: { key: "M2500", mean: 1.2, low: -0.7, high: 3.2, bootstrapLow: -0.6, bootstrapHigh: 3.0 },
  M10000: { key: "M10000", mean: 0.6, low: -1.6, high: 2.7, bootstrapLow: -1.5, bootstrapHigh: 2.5 },
  Z2500: { key: "Z2500", mean: 7.5, low: 4.5, high: 10.4, bootstrapLow: 4.8, bootstrapHigh: 10.1 },
  Z10000: { key: "Z10000", mean: 9.9, low: 6.8, high: 12.9, bootstrapLow: 7.1, bootstrapHigh: 12.6 },
} as const satisfies Record<Round6Comparison, Round6Diff & { bootstrapLow: number; bootstrapHigh: number }>

/**
 * Where LLMSlim trails Mem0: every question type more than 3 points behind, as the report's "Where LLMSlim loses"
 * lists them (summary.json `weak_spots_vs_mem0`), all 35 conversations, 70 questions per type.
 */
export const ROUND6_WEAK_SPOTS_VS_MEM0: readonly Round6Diff[] = [
  { key: "M2500", type: "summarization", mean: -8.9, low: -13.1, high: -4.7 },
  { key: "M10000", type: "summarization", mean: -4.0, low: -7.8, high: -0.2 },
  { key: "M10000", type: "multi_session_reasoning", mean: -6.0, low: -10.1, high: -1.8 },
  { key: "M2500", type: "information_extraction", mean: -4.6, low: -12.3, high: 3.2 },
  { key: "M10000", type: "information_extraction", mean: -4.9, low: -12.3, high: 2.6 },
]

/** Every question type where LLMSlim 0.12 is below Zep at either budget, on Zep's 30 conversations: only one. */
export const ROUND6_BELOW_ZEP: readonly Round6Diff[] = [
  { key: "Z2500", type: "temporal_reasoning", mean: -2.4, low: -8.5, high: 3.6 },
]

/** Other figures the prose quotes, each with its summary.json path. Costs in USD. */
export const ROUND6_FIGURES = {
  /** Mem0's memory-building LLM calls per 1,000 questions, all 35 conversations. */
  mem0MemoryBuilding: { value: 56.28, path: "subsets.all.arms.mem0_top50.cost_per_1000_questions_usd.memory_building_llm" },
  /** Mem0's compute per 1,000 questions, all 35 conversations. */
  mem0Compute: { value: 16.14, path: "subsets.all.arms.mem0_top50.cost_per_1000_questions_usd.compute" },
  /** Zep's memory-building LLM calls per 1,000 questions, on its 30 conversations. */
  zepMemoryBuilding: { value: 320.21, path: "subsets.zep.arms.zep.cost_per_1000_questions_usd.memory_building_llm" },
  /** One conversation stored and then asked 20 or 100 questions, at 2,500 tokens: all 35 conversations. */
  mem0PerConversation20: { value: 1.462, path: "subsets.all.arms.mem0_top50.cost_per_conversation_usd.20_questions" },
  mem0PerConversation100: { value: 1.521, path: "subsets.all.arms.mem0_top50.cost_per_conversation_usd.100_questions" },
  llmslimPerConversation20: { value: 0.024, path: "subsets.all.arms.llmslim_fix_2500.cost_per_conversation_usd.20_questions" },
  llmslimPerConversation100: { value: 0.122, path: "subsets.all.arms.llmslim_fix_2500.cost_per_conversation_usd.100_questions" },
  /** The same on Zep's 30 conversations. */
  zepPerConversation20: { value: 6.601, path: "subsets.zep.arms.zep.cost_per_conversation_usd.20_questions" },
  zepPerConversation100: { value: 6.667, path: "subsets.zep.arms.zep.cost_per_conversation_usd.100_questions" },
  llmslimOnZepPerConversation20: { value: 0.024, path: "subsets.zep.arms.llmslim_fix_2500.cost_per_conversation_usd.20_questions" },
  llmslimOnZepPerConversation100: { value: 0.12, path: "subsets.zep.arms.llmslim_fix_2500.cost_per_conversation_usd.100_questions" },
  /** On Zep's 30 conversations, LLMSlim at 10,000 tokens minus Mem0's top 200, in points. */
  llmslimVsMem0OnZep10000: { value: -0.1, path: "subsets.zep.arms.llmslim_fix_10000.vs_mem0_same_budget.mean" },
  /** The judge's check before any test answer was judged: 40 deliberately wrong answers, their mean, and the bar. */
  judgeWrongAnswers: { value: 40, path: "judge.check.wrong_answers" },
  judgeWrongMean: { value: 4.8, path: "judge.check.mean_points" },
  judgeBar: { value: 15, path: "judge.check.bar_points" },
  conversations: { value: 35, path: "subsets.all.conversations" },
  zepConversations: { value: 30, path: "subsets.zep.conversations" },
  questions: { value: 700, path: "subsets.all.arms.llmslim_fix_2500.questions" },
  zepQuestions: { value: 600, path: "subsets.zep.arms.zep.questions" },
} as const satisfies Record<string, { value: number; path: string }>

/** How many times Mem0's cost per 1,000 questions is LLMSlim's, at 2,500 and 10,000 tokens, as the report states it. */
export const ROUND6_COST_MULTIPLES = { at2500: "60x", at10000: "28.6x" } as const

/** BEAM's question types, as the report names them. */
export const QUESTION_TYPES: Record<string, string> = {
  abstention: "Abstention",
  contradiction_resolution: "Contradiction resolution",
  event_ordering: "Event ordering",
  information_extraction: "Information extraction",
  instruction_following: "Instruction following",
  knowledge_update: "Knowledge update",
  multi_session_reasoning: "Multi-session reasoning",
  preference_following: "Preference following",
  summarization: "Summarization",
  temporal_reasoning: "Temporal reasoning",
}

// ------------------------------------------------------------------ formatting, as the pages print numbers

const MINUS = "−"

/** 1.2 -> "+1.2", -0.7 -> "−0.7", with a true minus sign. */
export const signed = (value: number) => (value > 0 ? `+${value.toFixed(1)}` : value < 0 ? `${MINUS}${(-value).toFixed(1)}` : "0.0")
/** A signed point estimate and its interval for prose: "+1.2 points (95% CI −0.7 to +3.2)" reads from these parts. */
export const range = (low: number, high: number) => `${signed(low)} to ${signed(high)}`
/** Points behind, for prose: -8.9 -> "8.9". */
export const behind = (value: number) => (-value).toFixed(1)
export const usd = (value: number, digits = 2) => `$${value.toFixed(digits)}`
export const tokens = (value: number) => value.toLocaleString("en-US")
/** "44.6 (41.9–47.3)", the results tables' score format. */
export const scoreText = (arm: Round6Arm) => `${arm.score.toFixed(1)} (${arm.low.toFixed(1)}–${arm.high.toFixed(1)})`
/** "+1.2 (−0.7, +3.2)", the paired-difference tables' format. */
export const diffText = (diff: Round6Diff) => `${signed(diff.mean)} (${signed(diff.low)}, ${signed(diff.high)})`
/** Level when the interval includes zero, Ahead when it is all above, Behind when it is all below. */
export const readingOf = (diff: Round6Diff) => (diff.low > 0 ? "Ahead" : diff.high < 0 ? "Behind" : "Level") as "Ahead" | "Behind" | "Level"
export const budgetOf = (key: Round6Comparison) => (key.endsWith("10000") ? "10,000 tokens" : "2,500 tokens")
