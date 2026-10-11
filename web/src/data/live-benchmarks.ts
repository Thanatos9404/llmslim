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
  /** The same configurations on a fresh held-out sample, run once after development was frozen. */
  fresh?: { n: string; arms: Arm[] }
}

/** Competing compressors we ran ourselves: same reader, same questions, same token budget. */
export type HeadToHead = {
  columns: [string, string, string]
  rows: { system: string; model: string; scoreA: string; scoreB: string; scoreAll: string; tokens: string; time: string; best?: boolean }[]
  note: string
  /** The competitors' papers and code, and our raw results and run script, so anyone can check or rerun it. */
  sources: { label: string; url: string }[]
}

export const LIVE_MODEL = "Claude Haiku 5.5"
export const LIVE_DATE = "October 2026"
/** When the /benchmarks and /results content last changed: their sitemap lastmod. Update it with the content. */
export const RESULTS_LAST_UPDATED = "12 Oct 2026"
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
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 76.7, tokens: 7984, cost: 1.45 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 68.9, tokens: 7985, cost: 1.45 },
      { name: "LLMSlim Platform 0.9.1", kind: "llmslim", score: 63.3, tokens: 7600, cost: 1.36 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 25.6, tokens: 10482, cost: 1.86 },
      { name: "Most recent sessions", kind: "baseline", score: 14.4, tokens: 6693, cost: 1.23 },
    ],
    takeaway: "With the reranker, 8k tokens score within noise of the whole 115k-token history (95% CI −15.6 to +4.4) at 1/62 of the cost at Haiku 5.5 list prices (14× fewer tokens; full-history prompts bill at the over-100k-token rate). On the original sample, multi-session and time questions score one question above the full history (15 per type); on the fresh sample multi-session falls below it (60.0 against 73.3).",
    caveat: "Preference questions (a recommendation that should use a stated taste) are the weakest type: 40% against 87% on this sample.",
    fresh: { n: "90 new questions", arms: [
      { name: "Full history", kind: "full", score: 72.2 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 76.7 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 67.8 },
      { name: "Most recent sessions", kind: "baseline", score: 14.4 },
    ] },
  },
  {
    id: "nq",
    name: "NaturalQuestions, 20 documents",
    what: "Open-domain questions with 20 retrieved passages; the answer sits in one, placed first, 10th or 20th.",
    metric: "accuracy (answer in response)",
    n: "300 cases (100 questions × 3 answer positions)",
    arms: [
      { name: "Full context", kind: "full", score: 86.3, tokens: 2889, cost: 0.694 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 75.0, tokens: 668, cost: 0.331 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 65.7, tokens: 659, cost: 0.327 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 62.3, tokens: 727, cost: 0.355 },
      { name: "Keep passages in order", kind: "baseline", score: 52.0, tokens: 669, cost: 0.343 },
    ],
    takeaway: "With the reranker, 75% on a quarter of the tokens wherever the answer sits (74 to 76% at every position), against 95% to 29% for keeping passages in order. Ahead of LLMLingua-2 at the same budget. LongLLMLingua, which runs a 7B model, is level with it over 300 cases: ahead on the original set, behind on the fresh one (below).",
    caveat: "At 4.4x compression this is still 11 points below full context with the reranker, and 21 without it.",
    fresh: { n: "300 new cases (100 questions × 3 answer positions)", arms: [
      { name: "Full context", kind: "full", score: 88.0 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 75.7 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 67.3 },
      { name: "Keep passages in order", kind: "baseline", score: 48.3 },
    ] },
  },
  {
    id: "hotpotqa",
    name: "HotpotQA (distractor)",
    what: "Multi-hop questions over 10 Wikipedia paragraphs, 2 of them relevant.",
    metric: "answer F1",
    n: "200 questions",
    arms: [
      { name: "Full context", kind: "full", score: 74.9, tokens: 2179, cost: 0.245 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 69.4, tokens: 939, cost: 0.137 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 67.5, tokens: 936, cost: 0.133 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 61.7, tokens: 1159, cost: 0.180 },
      { name: "Truncate to the same budget", kind: "baseline", score: 49.5, tokens: 1147, cost: 0.194 },
      { name: "No context", kind: "baseline", score: 43.8, tokens: 84, cost: 0.120 },
    ],
    takeaway: "57% fewer input tokens and 44% lower cost than full context. Exact match with the reranker: 56.0 against 57.0 with every paragraph (54.5 against 59.0 on the fresh sample).",
    caveat: "Short contexts leave little to remove: on a 2k-token context, full context still has the best F1.",
    fresh: { n: "200 new questions", arms: [
      { name: "Full context", kind: "full", score: 77.5 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 71.8 },
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 70.1 },
      { name: "Truncate to the same budget", kind: "baseline", score: 41.1 },
    ] },
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
      { name: "LLMSlim Core 0.8", kind: "llmslim", score: 54.9, tokens: 5232, cost: 0.778 },
      { name: "LLMSlim Core 0.8 + reranker", kind: "llmslim", score: 54.2, tokens: 5229, cost: 0.778 },
      { name: "LLMSlim Core 0.7.2", kind: "previous", score: 52.4, tokens: 5164, cost: 0.779 },
      { name: "Middle truncation, same budget", kind: "baseline", score: 45.2, tokens: 5147, cost: 0.785 },
    ],
    takeaway: "The same macro score as full context (95% CI −4.5 to +4.6) on a third of the tokens, and +9.8 over truncation. On the original sample RepoBench-P (cross-file code, 30 samples) scored above full context, 57.2 against 44.3; it did not on the fresh sample.",
    caveat: "MuSiQue multi-hop QA is still below full context (58.8 against 64.9; 61.2 with the reranker), though most of the 0.8 pre-release drop (48.3) is recovered.",
    fresh: { n: "210 new samples", arms: [
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
  "Reader model: Claude Haiku 5.5 at effort low for every arm. Only the context changes between arms.",
  "Official prompts and metrics for each dataset. LongMemEval uses its official judge prompts, run with Haiku 5.5 as the judge.",
  "Truncation and recency baselines get exactly the token count LLMSlim produced, so comparisons are at equal budget.",
  "Confidence intervals are paired bootstrap 95% over the same questions. On NaturalQuestions each question appears three times (answer 1st, 10th and 20th) and the intervals resample those cases, so they are narrower than intervals that resample whole questions.",
  "Tuning used only separate development questions (free offline checks of what survives compression). After the code was frozen, every suite was also run once on a fresh sample nobody had looked at; those numbers are shown beside the originals.",
  "The optional reranker is cross-encoder/ms-marco-MiniLM-L-6-v2 (22M parameters, trained on MS MARCO web search only). Install it with pip install \"llmslim[semantic]\" and pass relevance=\"semantic\". Without it, LLMSlim uses no model at all.",
  "LLMLingua-2 and LongLLMLingua were run by us with their published settings, on the same questions, budget and reader.",
]

export const HEAD_TO_HEAD: HeadToHead = {
  columns: ["Original (150 cases)", "Fresh (150 cases)", "All (300 cases)"],
  rows: [
    { system: "LLMSlim Core 0.8 + reranker", model: "22M cross-encoder", scoreA: "74.0", scoreB: "83.3", scoreAll: "78.7", tokens: "668", time: "0.1 s on a GPU", best: true },
    { system: "LongLLMLingua", model: "LLaMA-2-7B (4-bit)", scoreA: "80.0", scoreB: "76.0", scoreAll: "78.0", tokens: "630", time: "9.3 s on a GPU" },
    { system: "LLMLingua-2", model: "XLM-RoBERTa-large", scoreA: "64.7", scoreB: "73.3", scoreAll: "69.0", tokens: "680", time: "2.3 s on a GPU, about 43 s on CPU" },
    { system: "LLMSlim Core 0.8", model: "none", scoreA: "63.3", scoreB: "74.0", scoreAll: "68.7", tokens: "658", time: "25 ms on CPU" },
    { system: "Cut to the same size", model: "none", scoreA: "49.3", scoreB: "47.3", scoreAll: "48.3", tokens: "627", time: "instant" },
  ],
  note: "NaturalQuestions with 20 retrieved passages and a 25% budget; full context scores 87.3 and 90.7 on the two sets. Each set is 50 questions × 3 answer positions (1st, 10th, 20th), so the 300 cases come from 100 questions. Over all 300 cases LLMSlim with the reranker and LongLLMLingua are level (78.7 and 78.0: +0.7 points, 95% interval −4.7 to +6.0), and LLMSlim is ahead of LLMLingua-2 by 9.7 points (95% interval 3.7 to 15.7). LongLLMLingua uses the paper's NQ settings with LLaMA-2-7B-chat; the paper does not state its precision, and we ran it in 4-bit NF4 to fit a 6 GB GPU. Tokens are means and times are medians over the 300 cases, to compress one question on our machine (LLMLingua-2's CPU time is the mean of a separate CPU run on the original set).",
  sources: [
    { label: "LLMLingua-2 paper (arXiv 2403.12968)", url: "https://arxiv.org/abs/2403.12968" },
    { label: "LongLLMLingua paper (arXiv 2310.06839)", url: "https://arxiv.org/abs/2310.06839" },
    { label: "LLMLingua code (microsoft/LLMLingua)", url: "https://github.com/microsoft/LLMLingua" },
    { label: "Per-question results", url: "https://github.com/Thanatos9404/llmslim/tree/main/benchmarks/live/results" },
    { label: "Script to rerun the competitors", url: "https://github.com/Thanatos9404/llmslim/blob/main/benchmarks/live/competitors.sh" },
  ],
}
