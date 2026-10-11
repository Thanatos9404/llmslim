/**
 * Real-model benchmark results: Claude Haiku 5.5 (`claude-haiku-5-5`, effort low) through the Claude API,
 * official datasets, prompts and scoring. Every number here comes from a run in benchmarks/live-haiku-5.5
 * of the public repository; nothing is estimated. Weak results stay in.
 */

export type ArmKind = "full" | "llmslim" | "previous" | "baseline" | "competitor"

export type Arm = {
  name: string
  kind: ArmKind
  score: number
  /** Mean context or input tokens sent per question. */
  tokens?: number
  /** USD per 1,000 questions on Claude Haiku 5.5. */
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
}

export const LIVE_MODEL = "Claude Haiku 5.5"
export const LIVE_DATE = "October 2026"
export const CORE_VERSION_TESTED = "0.8.0"
export const PLATFORM_VERSION_TESTED = "0.9.1"

export const LIVE_SUITES: LiveSuite[] = [
  {
    id: "longmemeval",
    name: "LongMemEval-S",
    what: "Answer a question from about 50 earlier chat sessions (115k tokens of history).",
    metric: "accuracy (official judge prompts)",
    n: "90 questions, 15 per type",
    arms: [
      { name: "Full history", kind: "full", score: 82.2, tokens: 114006, cost: 90.72 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 70.0, tokens: 7985, cost: 1.45 },
      { name: "LLMSlim Platform 0.9.1", kind: "llmslim", score: 63.3, tokens: 7600, cost: 1.36 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 25.6, tokens: 10482, cost: 1.86 },
      { name: "LLMSlim Platform 0.9.0", kind: "previous", score: 18.9, tokens: 7287, cost: 1.30 },
      { name: "Most recent sessions", kind: "baseline", score: 14.4, tokens: 6693, cost: 1.23 },
    ],
    takeaway: "At 8k tokens, Core 0.8 keeps 85% of full-history accuracy for 1/62 of the cost. On knowledge-update questions it matches full history (86.7% vs 80.0%).",
    caveat: "Multi-session aggregation and preference questions remain the weakest types.",
  },
  {
    id: "hotpotqa",
    name: "HotpotQA (distractor)",
    what: "Multi-hop questions over 10 Wikipedia paragraphs, 2 of them relevant.",
    metric: "answer F1",
    n: "200 questions",
    arms: [
      { name: "Full context", kind: "full", score: 74.9, tokens: 2179, cost: 0.245 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 68.0, tokens: 935, cost: 0.134 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 61.7, tokens: 1159, cost: 0.180 },
      { name: "Truncate to the same budget", kind: "baseline", score: 49.5, tokens: 1147, cost: 0.194 },
      { name: "No context", kind: "baseline", score: 43.8, tokens: 84, cost: 0.120 },
    ],
    takeaway: "57% fewer input tokens and 45% lower cost than full context, +18.5 F1 over truncation at the same budget.",
    caveat: "Short contexts leave little to remove: full context still answers best when it is only 2k tokens.",
  },
  {
    id: "nq",
    name: "NaturalQuestions, 20 documents",
    what: "Open-domain questions with 20 retrieved passages; the answer sits in one, placed first, 10th or 20th.",
    metric: "accuracy (answer in response)",
    n: "300 questions (100 per position)",
    arms: [
      { name: "Full context", kind: "full", score: 86.3, tokens: 2889, cost: 0.694 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 66.7, tokens: 659, cost: 0.328 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 62.3, tokens: 727, cost: 0.355 },
      { name: "Keep passages in order", kind: "baseline", score: 52.0, tokens: 669, cost: 0.343 },
    ],
    takeaway: "Unlike truncation, accuracy does not depend on where the answer sits (65 to 69% at every position; truncation swings from 29 to 95%).",
    caveat: "At 4.4x compression this is LLMSlim's weakest suite: 20 points below full context.",
  },
]

LIVE_SUITES.push(
  {
    id: "longbench",
    name: "LongBench v1",
    what: "Seven long-context tasks: document QA, multi-hop QA, summarisation, few-shot QA and code completion (15.5k tokens on average).",
    metric: "macro average of official metrics",
    n: "210 samples, 30 per task",
    arms: [
      { name: "Full context", kind: "full", score: 54.9, tokens: 15532, cost: 1.812 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 52.9, tokens: 5216, cost: 0.777 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 52.4, tokens: 5164, cost: 0.779 },
      { name: "Middle truncation, same budget", kind: "baseline", score: 45.2, tokens: 5147, cost: 0.785 },
    ],
    takeaway: "Within 2 points of full context (95% CI -6.3 to +2.3) on a third of the tokens, and +7.7 over truncation. On cross-file code (RepoBench-P) and 2WikiMQA it beats full context.",
    caveat: "MuSiQue multi-hop QA fell from 58.5 (0.7.2) to 48.3: whole-passage selection can miss the bridging passage.",
  },
  {
    id: "longbench-v2",
    name: "LongBench v2 (short split)",
    what: "Hard multiple-choice questions over long documents, codebases and structured data (30k tokens on average).",
    metric: "accuracy",
    n: "180 questions",
    arms: [
      { name: "Full context", kind: "full", score: 60.0, tokens: 30493, cost: 7.621 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 53.3, tokens: 8484, cost: 1.697 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 51.1, tokens: 8566, cost: 1.902 },
      { name: "Middle truncation, same budget", kind: "baseline", score: 48.3, tokens: 8566, cost: 1.942 },
    ],
    takeaway: "72% fewer tokens and 78% lower cost than full context, the best of the compressed arms.",
    caveat: "Questions that need the whole document lose accuracy: 6.7 points below full context.",
  },
)

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
      { arm: "Native tool-use history", result: "0 of 1,054", detail: "attack success 0.0%" },
      { arm: "LLMSlim Platform rendering", result: "0 of 1,054", detail: "attack success 0.0%; 50 redundant tool calls" },
    ],
    takeaway: "Claude Haiku 5.5 resisted every attack on its own, so this benchmark shows no defence effect with this model. The Platform's text rendering of tool results caused 4.7% redundant calls, which is the next fix.",
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
  "Reader model: Claude Haiku 5.5 at effort low for every arm. Only the context changes between arms.",
  "Official prompts and metrics for each dataset. LongMemEval uses its official judge prompts, run with Haiku 5.5 as the judge.",
  "Truncation and recency baselines get exactly the token count LLMSlim produced, so comparisons are at equal budget.",
  "Confidence intervals are paired bootstrap 95% over the same questions.",
  "Development checks used separate questions; reported numbers come from questions not used to tune anything.",
]
