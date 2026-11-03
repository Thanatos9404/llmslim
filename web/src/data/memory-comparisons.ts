/**
 * Comparison pages for memory systems (/compare/mem0, /compare/zep). The page and its Markdown twin
 * (/compare/<slug>.md, llms-full.txt) both render from this data.
 *
 * Benchmark numbers come only from what is public on main: round 6 (benchmarks/live/round6, LLMSlim 0.12 on BEAM-1M,
 * 24-27 Oct 2026, published as results only; the numbers are in src/data/round6-memory.ts, checked against its
 * summary.json by a unit test), round 3 (benchmarks/live/round3/RESULTS.md, LLMSlim Core 0.9.0, 13-15 Oct 2026), as
 * on /benchmarks and in the README, and the evidence measurements in docs/roadmap/1.0.md. Paired differences are the
 * reports' own, reading "LLMSlim minus the other system". Wording as on the LLMLingua page: "level" whenever the 95%
 * interval includes zero; on round 6, "on par with Mem0" and "ahead of Zep" (on its 30 conversations), as the round 6
 * report words them, never "beats Mem0". Costs are per 1,000 questions end to end. Each round is one entry in
 * `benchmarks`, the latest first, so a later round is one more block.
 *
 * Competitor facts come from their own documentation and pricing pages, read on PRICES_CHECKED; the URLs are in
 * each page's sources. Nothing here describes another product beyond what its own pages say.
 */
import { siteConfig } from "@/config/site"
import { ROUND3_REPORT } from "@/data/live-benchmarks"
import {
  INSTALL_MAIN, MEM0_ADD_LOOP, MEM0_ADD_LOOP_OUTPUT, MEM0_CHECK, MEM0_CHECK_OUTPUT, MEM0_EXPORT, MEM0_IMPORT_COMMANDS,
  MEM0_IMPORT_OUTPUT, MEM0_SAMPLE, ZEP_ADD_LOOP, ZEP_ADD_LOOP_OUTPUT, ZEP_CHECK, ZEP_CHECK_OUTPUT, ZEP_EXPORT,
  ZEP_IMPORT_COMMAND, ZEP_IMPORT_OUTPUT, ZEP_SAMPLE, type CodeSample,
} from "@/data/migration-snippets"
import { PLANS, formatPrice } from "@/data/pricing"
import {
  QUESTION_TYPES, ROUND6_ARMS, ROUND6_BELOW_ZEP, ROUND6_COST_MULTIPLES, ROUND6_DATES, ROUND6_DIFFS, ROUND6_FIGURES, ROUND6_REPORT, ROUND6_SUMMARY,
  ROUND6_WEAK_SPOTS_VS_MEM0, behind, budgetOf, diffText, range, readingOf, scoreText, signed, tokens, usd, type Round6Arm, type Round6Diff,
} from "@/data/round6-memory"

/** When the competitors' pricing pages and docs were read. */
export const PRICES_CHECKED = "2 November 2026"

export type GlanceRow = { aspect: string; llmslim: string; rival: string }

/** One row of a results table: a system at a budget, as RESULTS.md reports it. */
export type ResultRow = {
  system: string
  /** Mean context tokens, or "all" for the whole history. */
  tokens: string
  /** Accuracy with its 95% bootstrap interval. */
  score: string
  /** USD per 1,000 questions, end to end, as run. */
  cost: string
  kind: "llmslim" | "rival" | "other"
  /** The budget this row was run at, when one table holds several: rows of one budget are grouped under it. */
  budget?: string
}

export type ResultTable = {
  title: string
  rows: ResultRow[]
  note: string
  /** The score column's heading, when the score is not an accuracy ("Accuracy (95% CI)"). */
  scoreLabel?: string
}

/** A paired difference on the same questions: LLMSlim minus the other system, with its 95% interval. */
export type PairedDiff = { comparison: string; benchmark: string; difference: string; reading: "Level" | "Ahead" | "Behind" }

/** Question types where LLMSlim trails, as paired differences; `columns` name the first two columns. */
export type WeakSpots = { title: string; columns: [string, string]; rows: PairedDiff[]; note: string }

/** One benchmark round. A later round is one more of these, first in the list. */
export type BenchmarkBlock = {
  id: string
  /** The newest round leads as the latest results; earlier rounds follow it, labelled as earlier. */
  status: "latest" | "earlier"
  kicker: string
  heading: [string, string]
  intro: string
  /** For an earlier round: one line that places it against the latest. */
  context?: string
  tables: ResultTable[]
  pairedDiffs: PairedDiff[]
  pairedNote: string
  weakSpots?: WeakSpots
  caveats: { title: string; body: string }[]
  links: { label: string; url: string }[]
  /** What the Markdown twin calls the links; "Sources and reruns" when absent. A results-only round has no reruns. */
  linksLabel?: string
}

/** The page and its Markdown twin label a round by its status: the latest leads, earlier rounds say so. */
export const roundLabel = (block: Pick<BenchmarkBlock, "status">) => (block.status === "latest" ? "Latest results" : "Earlier round")

export type PriceRow = { plan: string; price: string; includes: string }

export type Pricing = {
  intro: string
  rival: { rows: PriceRow[]; url: string }
  notes: string[]
}

export type MigrationStep = { title: string; body: string; samples: CodeSample[]; after?: string }

export type MemoryComparison = {
  slug: string
  /** The other product's name, as it is written in headings. */
  rival: string
  /** Search title; it names the brand, so no suffix is added. */
  title: string
  description: string
  kicker: string
  heading: [string, string]
  lede: string
  lastUpdated: string
  meta: string[]
  disclosure: string
  shortAnswer: string[]
  glance: GlanceRow[]
  about: { name: string; cite: string; url: string; body: string }[]
  aboutNote: string
  differences: { title: string; body: string }[]
  benchmarks: BenchmarkBlock[]
  chooseThem: { title: string; body: string }[]
  chooseUs: string[]
  pricing: Pricing
  migration: { intro: string; steps: MigrationStep[]; notes: string[]; guide: { label: string; href: string } }
  faqs: ReadonlyArray<readonly [question: string, answer: string]>
  sources: { label: string; url: string }[]
}

const ROUND3 = `${siteConfig.github}/tree/main/benchmarks/live/round3`
const ROADMAP_ISSUES = `${siteConfig.github}/blob/main/docs/roadmap/1.0.md#known-quality-issues-to-fix-before-10`
const MIGRATION_GUIDE = `${siteConfig.github}/blob/main/docs/MIGRATE_FROM_MEM0.md`

/** The heading over LLMSlim's prices: Orbit is not available until 1.0, and every view of the table says so. */
export const LLMSLIM_PRICES_TITLE = "LLMSlim (Orbit opens with LLMSlim 1.0)"

/** "An SLA" in the middle of a list reads "an SLA"; "SAML" and "1 project" stay as they are. */
const midSentence = (text: string) => (/^[A-Z][a-z]/.test(text) ? text[0].toLowerCase() + text.slice(1) : text)

/** LLMSlim's own prices: Core, and Orbit's plans from src/data/pricing.ts, so every page shows the same numbers. */
export function llmslimPriceRows(): PriceRow[] {
  const orbit = PLANS.map((plan): PriceRow => ({
    plan: `Orbit ${plan.name}`,
    price: plan.prices
      ? plan.prices.usd.monthly === 0
        ? "Free"
        : `${formatPrice(plan.prices.usd.monthly, "usd")} a month, or ${formatPrice(plan.prices.usd.annual, "usd")} a year`
      : "Custom",
    includes: [...plan.limits, ...(plan.seats ? [plan.seats.usd] : [])].map((item, index) => (index === 0 ? item : midSentence(item))).join(", ") + ".",
  }))
  return [
    { plan: "Core", price: "Free, MIT", includes: "Self-hosted, with no account and no limits on projects, turns or searches. No model calls, so memory adds nothing to an LLM bill; you run the machine and, if you want one, the database." },
    ...orbit,
  ]
}

const ORBIT_NOTE = "LLMSlim Orbit, the hosted edition, opens with LLMSlim 1.0 and is not available yet; these are its plans at launch, from /pricing. Nothing is charged before it opens."

/** The caveat both pages share: round 3 measured Core 0.9.0, before the Memory API changed how it reads a history. */
const MEASURED_ON_09 = {
  title: "Measured on Core 0.9.0, not on the 0.12 Memory API",
  body: "Round 3 measured LLMSlim selecting from whole sessions with compress_documents. Since 0.12.0, Memory.search reads a history turn by turn. On 230 LoCoMo development questions, counting the questions whose labelled evidence is all in the context (no reader in the loop), the 0.12 read path kept all of it for 75.7% of questions at 2,500 tokens, against 85.7% for the path benchmarked here. Fixes on main raise that to 80.0%; the rest of the gap is open, and is listed in the 1.0 roadmap's known quality issues.",
}

// ------------------------------------------------------------------ Round 6, shared by both pages

const R6 = ROUND6_ARMS
const D6 = ROUND6_DIFFS
const F6 = ROUND6_FIGURES
const ROUND6_KICKER = `Round 6 · LLMSlim 0.12 · ${ROUND6_DATES}`
const ROUND6_SCORE = "Score out of 100 (95% CI)"
const BUDGET_2500 = "2,500-token budget"
const BUDGET_10000 = "10,000-token budget"

const row6 = (system: string, arm: Round6Arm, kind: ResultRow["kind"], budget: string): ResultRow =>
  ({ budget, system, tokens: tokens(arm.tokens), score: scoreText(arm), cost: usd(arm.cost), kind })
const diff6 = (diff: Round6Diff, comparison: string, benchmark: string): PairedDiff =>
  ({ comparison, benchmark, difference: diffText(diff), reading: readingOf(diff) })
const typeName = (diff: Round6Diff) => QUESTION_TYPES[diff.type ?? ""] ?? diff.type ?? ""
/** "summarization by 8.9 points at 2,500 tokens (95% CI −13.1 to −4.7)" reads from these parts. */
const trails = (diff: Round6Diff) => `${behind(diff.mean)} points at ${budgetOf(diff.key)} (95% CI ${range(diff.low, diff.high)})`

const [SUMMARIZATION_2500, SUMMARIZATION_10000, MULTI_SESSION_10000, EXTRACTION_2500, EXTRACTION_10000] = ROUND6_WEAK_SPOTS_VS_MEM0

/** The round's weak spots against Mem0, in one sentence, for the short answers. */
const ROUND6_LOSSES = `summarization trails by ${trails(SUMMARIZATION_2500)} and ${behind(SUMMARIZATION_10000.mean)} at 10,000 (${range(SUMMARIZATION_10000.low, SUMMARIZATION_10000.high)}), and multi-session reasoning by ${trails(MULTI_SESSION_10000)}. Information extraction is ${behind(EXTRACTION_2500.mean)} and ${behind(EXTRACTION_10000.mean)} points behind, within noise`

const ROUND6_INTRO_COMMON = `LLMSlim was developed on BEAM's smaller tiers only, none of this data was opened while it was tuned, and every system was read and judged once. Claude Haiku 5.5 read every context with BEAM's answer prompt, three times per question, and BEAM's rubric judge, also on Haiku 5.5, scored each read: the score is the mean rubric score out of 100. Costs are per 1,000 questions at list prices, with BEAM's 20 questions per conversation`

const ROUND6_CAVEATS = {
  resultsOnly: { title: "Published as results only", body: "The round 6 report and its summary.json hold every aggregate number. The protocol, the harness and the per-question answers are not published with this round." },
  oneReader: { title: "One reader and one judge", body: `Every answer is Claude Haiku 5.5's, and the judge is Haiku 5.5 too. A stronger reader could change both the scores and the gaps. Before any test answer was judged, the judge scored ${F6.judgeWrongAnswers.value} deliberately wrong answers at ${F6.judgeWrongMean.value.toFixed(1)} points on average, under the bar of ${F6.judgeBar.value}, but it is one model.` },
  reranker: { title: "With the reranker, not the default mode", body: "LLMSlim ran with its optional reranker (relevance=\"semantic\"), a 22M-parameter cross-encoder on the CPU, and made no LLM call when storing or searching. The default lexical mode, with no model, was not scored in this round." },
  commit: { title: "0.12.0 is not byte for byte the benchmarked commit", body: "\"LLMSlim 0.12\" is commit 16a2708, which became 0.12.0 after hardening. In the hardening's parity checks 0.12.0 returned the same bytes on 14,377 of 14,377 English test rows, but the 1,400 round-6 contexts were not rebuilt with 0.12.0: evidence of equivalence on English text, not a rerun." },
  oneBenchmark: { title: "One benchmark", body: "BEAM-1M is synthetic, long, English chat between a user and an assistant. Other histories (shorter, multilingual, multi-party, tool-heavy) may rank the systems differently." },
}

const ROUND6_LINKS = [
  { label: "Round 6 report and tables", url: ROUND6_REPORT },
  { label: "Round 6 numbers (summary.json)", url: ROUND6_SUMMARY },
]

const ROUND6_REPRODUCE = "Round 6 is published as results only: its report and summary.json in benchmarks/live/round6 hold every aggregate number, and the protocol, the harness and the per-question answers are not published with it."

// ------------------------------------------------------------------ Mem0

export const MEM0_COMPARISON: MemoryComparison = {
  slug: "mem0",
  rival: "Mem0",
  title: "Mem0 Alternative: LLMSlim vs Mem0 for Agent Memory",
  description: "LLMSlim vs Mem0: verbatim memory with no LLM calls on write, LoCoMo and LongMemEval results with cost and 95% intervals, both pricing pages, and a tested Mem0 migration.",
  kicker: "Comparison · Mem0 alternative",
  heading: ["LLMSlim vs Mem0.", "An honest comparison."],
  lede: "Mem0 is a memory layer for AI agents: by default an LLM reads what you add and stores the facts it extracts. LLMSlim Core is an MIT-licensed Python library that stores every turn word for word and, when you search, returns the turns that answer the question within a token budget, with no LLM call on either side. Here is how they differ, what three public benchmarks show, what each costs, and how to bring your Mem0 memories across.",
  lastUpdated: "November 3, 2026",
  meta: ["Updated November 3, 2026", "Latest results: LLMSlim 0.12, round 6 (BEAM-1M)", "Earlier: LLMSlim Core 0.9, round 3", "Reader: Claude Haiku 5.5", `Prices checked ${PRICES_CHECKED}`],
  disclosure: "We build LLMSlim. We are not affiliated with Mem0. We ran Mem0's open-source library (mem0ai 2.2.1) ourselves: through Mem0's own benchmark harness in round 3, and in round 6 with its memories given to the reader in the format of Mem0's own BEAM harness. Mem0's hosted Platform was not benchmarked. Mem0 did not run, review or endorse this comparison.",
  shortAnswer: [
    "Mem0 extracts facts with an LLM when you add memories; LLMSlim stores the turns themselves and selects from them when you search, with no model call on either side. Both are open source (Mem0 under Apache-2.0, LLMSlim under MIT) and both run on your own machines. Mem0 also runs as a hosted Platform today; LLMSlim's hosted edition, Orbit, opens with LLMSlim 1.0.",
    `On par with Mem0 in round 6, the latest results: on BEAM-1M, ${F6.questions.value} held-out questions about ${F6.conversations.value} conversations of about 946,000 tokens each, read by Claude Haiku 5.5, LLMSlim 0.12 with its reranker scored ${R6.all.llmslim2500.score.toFixed(1)} out of 100 against ${R6.all.mem0Top50.score.toFixed(1)} for Mem0's top 50 memories at 2,500 tokens (${signed(D6.M2500.mean)} points, 95% CI ${range(D6.M2500.low, D6.M2500.high)}), and ${R6.all.llmslim10000.score.toFixed(1)} against ${R6.all.mem0Top200.score.toFixed(1)} for Mem0's top 200 at 10,000 (${signed(D6.M10000.mean)}, ${range(D6.M10000.low, D6.M10000.high)}). Neither difference is significant, so we do not claim to beat Mem0.`,
    `${usd(R6.all.llmslim2500.cost)} and ${usd(R6.all.llmslim10000.cost)} per 1,000 BEAM-1M questions at list prices, against ${usd(R6.all.mem0Top50.cost)} and ${usd(R6.all.mem0Top200.cost)} for Mem0: ${ROUND6_COST_MULTIPLES.at2500} and ${ROUND6_COST_MULTIPLES.at10000} cheaper, because Mem0 makes an LLM call for every exchange it stores and LLMSlim makes none. The ratios assume BEAM's 20 questions per conversation; with more, the gap narrows.`,
    `Where LLMSlim loses on BEAM-1M: against Mem0, ${ROUND6_LOSSES}.`,
    "In round 3, an earlier round on LoCoMo and LongMemEval-S: level on accuracy on LoCoMo. At about 2,500 tokens, read by Claude Haiku 5.5, LLMSlim Core 0.9 answered 91.7% with no model and 93.0% with its optional 22M-parameter reranker, against 91.0% for Mem0's top 50 memories. The default LLMSlim and Mem0 are level (+0.8 points, 95% CI −0.9 to +2.5); at about 10,000 tokens LLMSlim is ahead (94.3% against 91.6%, +2.7, 95% CI +1.2 to +4.1).",
    "In round 3, about a third of the cost: $0.89 to $0.95 per 1,000 LoCoMo questions end to end, against $2.66 for Mem0, most of it the model calls that build Mem0's memory.",
    "In round 3, on Mem0's own 60 LongMemEval questions, LLMSlim with its reranker answered 78.3% for $1.04 per 1,000 questions, against 76.7% for $220.88 for Mem0's top 200 memories: each question has its own 500-message history, so Mem0 builds a memory for each. On 60 questions the 95% intervals are about ±10 points.",
    "Where Mem0 is better in round 3: at about 1,000 tokens it is clearly ahead on LoCoMo's multi-hop (88.7% against 80.3%) and temporal (93.4% against 85.7%) questions, where its extracted facts pack evidence from many sessions into few tokens. Overall at that budget the default LLMSlim and Mem0 are within noise (87.5% and 88.7%); with its reranker LLMSlim scored 90.5%.",
    "The round-3 results are for LLMSlim Core 0.9.0 selecting from whole sessions. The Memory API of 0.12 reads a history differently, and on two-person conversations it keeps less of the evidence than the version benchmarked in round 3; see what round 3 does not show.",
  ],
  glance: [
    { aspect: "What it stores", llmslim: "Every turn, word for word, under its date and scope", rival: "Facts an LLM extracts from what you add (infer=True, the default); with infer=False, the messages as given" },
    { aspect: "Model calls when you add", llmslim: "None", rival: "An LLM call to extract facts, by default" },
    { aspect: "How search works", llmslim: "Ranks stored turns against the question by shared words, with no model, and returns them within a token budget; an optional 22M-parameter cross-encoder rescores", rival: "Embeds the question and returns the memories with the most similar embeddings; an optional reranker refines the order" },
    { aspect: "What you run", llmslim: "One Python package. Memory in SQLite (built into Python), Postgres or, from 1.0, MongoDB", rival: "Platform: hosted by Mem0. Open source: you provision and pay for an LLM, an embedder and a vector store" },
    { aspect: "Interfaces", llmslim: "Python API, llmslim serve (HTTP), llmslim mcp (MCP server), a TypeScript client", rival: "Python and TypeScript SDKs, the Platform's REST API, an MCP integration" },
    { aspect: "Graph and consolidation", llmslim: "None: stored turns are never rewritten", rival: "Platform only: graph memory over extracted entities, and Dream, which merges duplicates and supersedes outdated facts" },
    { aspect: "Moving between them", llmslim: "Mem0Memory keeps Mem0 2.x method names, filters and result shapes; llmslim import mem0 reads what get_all returns (1.0)", rival: "get_all lists a scope's memories; the Platform's memory export writes JSON shaped by a schema you define" },
    { aspect: "License", llmslim: "MIT", rival: "Apache-2.0 (mem0ai/mem0); the Platform is a hosted service" },
    { aspect: "Hosted option", llmslim: "LLMSlim Orbit, opening with LLMSlim 1.0 (not available yet)", rival: "Mem0 Platform: a Free plan and Custom plans" },
  ],
  about: [
    {
      name: "Mem0 Platform",
      cite: "Mem0 docs: Platform overview, Platform vs open source",
      url: "https://docs.mem0.ai/platform/platform-vs-oss",
      body: "Mem0's managed service. When you add messages, an LLM pulls out the facts, decisions and preferences worth keeping, and new memories accumulate alongside the old. Search embeds the question and ranks memories by similarity, with optional reranking. Mem0 runs the LLM, embedder and vector store and provides a dashboard. Graph memory, memory decay, temporal reasoning and Dream, a background step that merges duplicates and supersedes outdated facts, are Platform features.",
    },
    {
      name: "Mem0 open source",
      cite: "mem0ai/mem0 on GitHub (Apache-2.0)",
      url: "https://github.com/mem0ai/mem0",
      body: "The mem0ai library, which you run yourself. Add and search work the same way, and you provision, configure and pay for the LLM, embedder and vector store. It has no dashboard, and the Platform-only features above are not in it. Round 3 benchmarked this library, version 2.2.1, with Claude Haiku 5.5 as its LLM and Qwen3-Embedding-0.6B, the embedder of Mem0's own published open-source runs.",
    },
  ],
  aboutNote: `From Mem0's documentation and its GitHub repository, read on ${PRICES_CHECKED}. Mem0's documentation also covers add with infer=False, which stores messages without extraction; Mem0's harness, and so round 3, used the default.`,
  differences: [
    { title: "Verbatim storage", body: "add stores each turn as it was said, with its time and scope. Nothing is summarized or extracted, so a stored turn can't become a wrong fact. When something changes, both turns stay, each under its date, and the model sees which is newer." },
    { title: "No LLM calls on write", body: "Storing makes no model call, so adding memory costs nothing per message and works offline. In round 3, building Mem0's memory on Claude Haiku 5.5 was $1.76 of its $2.66 per 1,000 LoCoMo questions, and about $0.22 a question on LongMemEval's 500-message histories." },
    { title: "Selection at question time, within a budget", body: "search ranks user turns and windows of replies against the question, and returns what fits the token budget you give, in date order. Relevance is lexical by default: no model, deterministic. relevance=\"semantic\" adds a 22M-parameter cross-encoder that runs on a CPU." },
    { title: "Self-hosted on SQLite, Postgres or MongoDB", body: "One pip install. Memory lives in a SQLite file by default, in Postgres for several processes or machines, or, from 1.0, in MongoDB. There is no vector database to run and no embedding service to host." },
    { title: "An MCP server and an HTTP API", body: "llmslim mcp gives Claude Code, Claude Desktop, Cursor and other MCP clients remember, recall, forget and fit_context tools. llmslim serve puts the same memory behind a JSON API, with a TypeScript client for the Vercel AI SDK and Mastra." },
    { title: "A Mem0-compatible facade", body: "from llmslim.memory.compat import Mem0Memory as Memory keeps Mem0 2.x method names, keyword arguments and return shapes, so most code changes one import. Where behaviour differs, it fails loudly: an unknown filter key raises instead of being ignored." },
  ],
  benchmarks: [
    {
      id: "round6",
      status: "latest",
      kicker: ROUND6_KICKER,
      heading: ["BEAM-1M, held out.", "On par with Mem0, at a fraction of the cost."],
      intro: `BEAM's 1M tier: ${F6.conversations.value} conversations of about 946,000 tokens each between a user and an assistant, and ${F6.questions.value} questions of 10 types about them. ${ROUND6_INTRO_COMMON}: the answer call, Mem0's memory-building calls, and each system's compute. Mem0 OSS 2.2.1 stored every exchange through its own pipeline, with extraction on; LLMSlim 0.12 ran with its reranker.`,
      tables: [
        {
          title: `BEAM-1M: ${F6.questions.value} held-out questions on ${F6.conversations.value} conversations of about 946,000 tokens`,
          scoreLabel: ROUND6_SCORE,
          rows: [
            row6("LLMSlim 0.12 + reranker", R6.all.llmslim2500, "llmslim", BUDGET_2500),
            row6("Mem0, top 50 memories", R6.all.mem0Top50, "rival", BUDGET_2500),
            row6("LLMSlim 0.12 + reranker", R6.all.llmslim10000, "llmslim", BUDGET_10000),
            row6("Mem0, top 200 memories", R6.all.mem0Top200, "rival", BUDGET_10000),
          ],
          note: `BEAM's rubric score out of 100, each question read three times and each read judged, with the 95% t interval over the ${F6.conversations.value} conversations. Mem0's top 50 and top 200 memories are its pairs for the two budgets; they came to ${tokens(R6.all.mem0Top50.tokens)} and ${tokens(R6.all.mem0Top200.tokens)} tokens on average, more than LLMSlim's. Per 1,000 questions at list prices, Mem0 costs ${ROUND6_COST_MULTIPLES.at2500} LLMSlim's total at 2,500 tokens and ${ROUND6_COST_MULTIPLES.at10000} at 10,000. Most of Mem0's cost is the extraction calls that build its memory (${usd(F6.mem0MemoryBuilding.value)} per 1,000 questions), which it pays once per stored exchange whatever is asked later. No history fits in the reader's 1M-token window, so there is no whole-history row.`,
        },
      ],
      pairedDiffs: [
        diff6(D6.M2500, "LLMSlim 0.12 + reranker vs Mem0, top 50 memories", `BEAM-1M, 2,500 tokens (${F6.questions.value})`),
        diff6(D6.M10000, "LLMSlim 0.12 + reranker vs Mem0, top 200 memories", `BEAM-1M, 10,000 tokens (${F6.questions.value})`),
      ],
      pairedNote: `Paired differences in points, LLMSlim 0.12 with its reranker minus Mem0 at the same budget, on the same questions, with the 95% t interval over the ${F6.conversations.value} conversations in brackets; the paired cluster bootstrap gives ${range(D6.M2500.bootstrapLow, D6.M2500.bootstrapHigh)} and ${range(D6.M10000.bootstrapLow, D6.M10000.bootstrapHigh)}. Both intervals include zero, so LLMSlim and Mem0 are on par at both budgets: neither difference is significant, and we do not claim to beat Mem0.`,
      weakSpots: {
        title: "Where LLMSlim trails Mem0, by question type",
        columns: ["Question type", "Budget (questions)"],
        rows: ROUND6_WEAK_SPOTS_VS_MEM0.map((diff) => diff6(diff, typeName(diff), `${budgetOf(diff.key)} (70)`)),
        note: `LLMSlim 0.12 minus Mem0 at the same budget, per question type on all ${F6.conversations.value} conversations, with 95% t intervals, which are descriptive and not adjusted for multiple comparisons. These are every type more than 3 points behind, as the round 6 report lists them: summarization at both budgets and multi-session reasoning at 10,000 tokens are behind; information extraction is behind within noise. No type is more than 10 points behind.`,
      },
      caveats: [
        ROUND6_CAVEATS.resultsOnly,
        { title: "Mem0's open-source library, set up as the report describes", body: "Mem0 OSS 2.2.1 with extraction on (infer=True, Mem0's default): every exchange added in order, with Claude Haiku 5.5 as its LLM, Qwen3-Embedding-0.6B as its embedder and embedded Qdrant with BM25. One search per question (top_k=200, Mem0's default threshold, no reranker); the reader got the top 50 or top 200 memories with their dates, in the format of Mem0's own BEAM harness. Its LLM calls went through one metering proxy that recorded every call. Mem0's hosted Platform was not benchmarked." },
        ROUND6_CAVEATS.oneReader,
        ROUND6_CAVEATS.reranker,
        { title: "The cost gap depends on questions per conversation", body: `The ratios assume BEAM's 20 questions per conversation. Mem0's cost is mostly the one-time extraction of each stored exchange, so with more questions per conversation the gap gets smaller: at 2,500 tokens, storing one conversation and asking 20 questions costs ${usd(F6.mem0PerConversation20.value, 3)} on Mem0 against ${usd(F6.llmslimPerConversation20.value, 3)} on LLMSlim, and asking 100 costs ${usd(F6.mem0PerConversation100.value, 3)} against ${usd(F6.llmslimPerConversation100.value, 3)}.` },
        { title: "Cost details that favour Mem0, and one that burdens it", body: `Mem0's extraction calls are priced as they ran, with the prompt cache the metering proxy put on its long system prompt; without that cache they cost more, so this favours Mem0. Compute is priced on the device each store was built on: Mem0's embedder ran on the benchmark laptop's GPU for some conversations and on its CPU for others, where they did not fit in the GPU's memory, and CPU embedding takes much longer, so part of Mem0's ${usd(F6.mem0Compute.value)} of compute per 1,000 questions comes from that. Its extraction calls (${usd(F6.mem0MemoryBuilding.value)}) are most of its cost either way.` },
        ROUND6_CAVEATS.commit,
        ROUND6_CAVEATS.oneBenchmark,
      ],
      links: ROUND6_LINKS,
      linksLabel: "Sources",
    },
    {
      id: "round3",
      status: "earlier",
      kicker: "Round 3 · LLMSlim Core 0.9.0 · 13–15 Oct 2026",
      context: "The earlier round, on different benchmarks: round 3 measured LLMSlim Core 0.9.0 against Mem0 on LoCoMo and LongMemEval-S. The latest results, round 6 on BEAM-1M, are above.",
      heading: ["Two memory benchmarks, one reader.", "Same questions, same budget."],
      intro: "Mem0's open-source library ran through Mem0's own benchmark harness on LoCoMo and LongMemEval-S, and LLMSlim selected from the same histories at the same token budgets. Claude Haiku 5.5 read every context with Mem0's own answer prompt; Mem0's judge scored LoCoMo and the official judge LongMemEval. Costs are per 1,000 questions end to end at list prices: the answer call, Mem0's memory-building calls, and each system's compute.",
      tables: [
        {
          title: "LoCoMo: 1,307 test questions on 8 long conversations",
          rows: [
            { budget: "About 1,000 tokens", system: "LLMSlim 0.9 + reranker", tokens: "994", score: "90.5 (88.9–92.0)", cost: "$0.70", kind: "llmslim" },
            { budget: "About 1,000 tokens", system: "Mem0, top 20 memories", tokens: "976", score: "88.7 (86.9–90.4)", cost: "$2.43", kind: "rival" },
            { budget: "About 1,000 tokens", system: "LLMSlim 0.9", tokens: "994", score: "87.5 (85.5–89.3)", cost: "$0.67", kind: "llmslim" },
            { budget: "About 2,500 tokens", system: "LLMSlim 0.9 + reranker", tokens: "2,495", score: "93.0 (91.5–94.3)", cost: "$0.95", kind: "llmslim" },
            { budget: "About 2,500 tokens", system: "LLMSlim 0.9", tokens: "2,492", score: "91.7 (90.3–93.3)", cost: "$0.89", kind: "llmslim" },
            { budget: "About 2,500 tokens", system: "Mem0, top 50 memories", tokens: "2,425", score: "91.0 (89.4–92.5)", cost: "$2.66", kind: "rival" },
            { budget: "About 2,500 tokens", system: "RAG over turns (Qwen3-Embedding-0.6B)", tokens: "2,430", score: "85.2 (83.2–87.0)", cost: "$0.90", kind: "other" },
            { budget: "About 10,000 tokens", system: "LLMSlim 0.9", tokens: "9,997", score: "94.3 (93.0–95.6)", cost: "$2.02", kind: "llmslim" },
            { budget: "About 10,000 tokens", system: "Mem0, top 200 memories", tokens: "9,628", score: "91.6 (90.1–93.0)", cost: "$3.74", kind: "rival" },
            { budget: "The whole history", system: "Full history, read from the prompt cache", tokens: "27,133", score: "95.1 (93.9–96.3)", cost: "$0.83", kind: "other" },
          ],
          note: "Three budgets, about 1,000, 2,500 and 10,000 tokens: Mem0 is its top 20, 50 and 200 memories, as in Mem0's harness. Accuracy by Mem0's judge, with the 95% bootstrap interval. The full history was read from the prompt cache because a conversation's questions were asked back to back; without the cache it costs $4.48 per 1,000 questions.",
        },
        {
          title: "LongMemEval-S: Mem0's 60-question sample, about 2,500 tokens",
          rows: [
            { system: "RAG over turns (Qwen3-Embedding-0.6B)", tokens: "2,473", score: "80.0 (70.0–90.0)", cost: "$3.36", kind: "other" },
            { system: "LLMSlim 0.9 + reranker", tokens: "2,501", score: "78.3 (68.3–88.3)", cost: "$1.04", kind: "llmslim" },
            { system: "Full history", tokens: "111,417", score: "78.3 (68.3–88.3)", cost: "$90.20", kind: "other" },
            { system: "Mem0, top 200 memories", tokens: "11,347", score: "76.7 (65.0–86.7)", cost: "$220.88", kind: "rival" },
            { system: "Mem0, top 50 memories", tokens: "2,848", score: "75.0 (63.3–85.0)", cost: "$219.50", kind: "rival" },
            { system: "LLMSlim 0.9", tokens: "2,501", score: "71.7 (60.0–81.7)", cost: "$0.96", kind: "llmslim" },
          ],
          note: "Each question has its own history of about 111k tokens and 500 messages, so Mem0 builds a new memory for each question: about $0.22 a question. Accuracy by the official judge. Dense retrieval over turns scored higher than both here, for $3.36 per 1,000 questions.",
        },
      ],
      pairedDiffs: [
        { comparison: "LLMSlim vs Mem0, top 20 memories", benchmark: "LoCoMo, about 1,000 tokens (1,307)", difference: "−1.2 (−3.1, +0.8)", reading: "Level" },
        { comparison: "LLMSlim vs Mem0, top 50 memories", benchmark: "LoCoMo, about 2,500 tokens (1,307)", difference: "+0.8 (−0.9, +2.5)", reading: "Level" },
        { comparison: "LLMSlim vs Mem0, top 50, token F1 (no judge)", benchmark: "LoCoMo, about 2,500 tokens (1,307)", difference: "+1.4 (−0.2, +2.8)", reading: "Level" },
        { comparison: "LLMSlim vs Mem0, top 200 memories", benchmark: "LoCoMo, about 10,000 tokens (1,307)", difference: "+2.7 (+1.2, +4.1)", reading: "Ahead" },
        { comparison: "LLMSlim vs Mem0, top 50 memories", benchmark: "LongMemEval-S, Mem0's sample (60)", difference: "−3.3 (−11.7, +5.0)", reading: "Level" },
        { comparison: "LLMSlim vs Mem0, top 200 memories", benchmark: "LongMemEval-S, Mem0's sample (60)", difference: "−5.0 (−16.7, +5.0)", reading: "Level" },
      ],
      pairedNote: "Paired differences in points, the default LLMSlim (no model) minus Mem0, on the same questions, with the paired bootstrap 95% interval in brackets, from the round 3 tables. Level means the interval includes zero, so the gap may be noise. The tables give no paired interval between LLMSlim with its reranker and Mem0, so none is shown here.",
      caveats: [
        { title: "Mem0's open-source library, not its Platform", body: "We ran mem0ai 2.2.1 through Mem0's own harness (mem0ai/memory-benchmarks), with Claude Haiku 5.5 for extraction and Qwen3-Embedding-0.6B for embeddings. The Platform has features the library lacks, such as graph memory and Dream, and may score differently." },
        { title: "One reader and one extraction model", body: "Every number uses Claude Haiku 5.5 at effort low, for reading and for Mem0's extraction. Another model may rank these systems differently. Third-party re-runs of Mem0 on LongMemEval-S with GPT-4o-mini report 53.6% to 66.4%, against 55.4% to 56.8% for full context (the MemOS and LightMem papers)." },
        { title: "Where the run differs from Mem0's harness", body: "Each difference is in Mem0's favour or forced by the benchmark's one-model rule. Mem0's open-source add rejects a timestamp, so its harness dates every memory at ingestion; here each memory got its session's date. On LongMemEval, Mem0's 2,000-token output cap cut off about 2% of extraction replies, so it was raised to 8,192. Mem0's embedding and database compute is not counted, which favours it." },
        { title: "Small samples on LongMemEval", body: "Mem0 ran on its pre-registered 60-question sample, because building a memory of each 500-message history costs about $0.22 a question. The 95% intervals are about ±10 points on 60 questions." },
        MEASURED_ON_09,
        { title: "A cached full history", body: "When a conversation's questions come back to back, the cached full history (95.1% for $0.83 per 1,000 questions) is cheaper than LLMSlim at 10,000 tokens and more accurate than any compressed context. LLMSlim is the cheaper choice when the context changes between questions, when questions arrive too far apart for the cache, or when a history is long enough to be billed at the long-prompt rate." },
      ],
      links: [
        { label: "Round 3 report and tables", url: ROUND3_REPORT },
        { label: "How the runs were kept honest", url: ROUND3 },
        { label: "Mem0 run scripts", url: `${ROUND3}/mem0_locomo.py` },
        { label: "Per-question results", url: `${ROUND3}/results` },
      ],
    },
  ],
  chooseThem: [
    { title: "Questions that join many sessions, in a small context", body: "At about 1,000 tokens, Mem0's extracted facts packed more evidence into the prompt: 88.7% against 80.3% for the default LLMSlim on LoCoMo's multi-hop questions, and 93.4% against 85.7% on temporal ones. If your prompts must stay that small and your questions span many sessions, extraction helps." },
    { title: "A managed service today", body: "Mem0's Platform is available now, with a free plan and custom plans that add SSO, audit logs, an SLA and on-prem deployment. LLMSlim's hosted edition, Orbit, opens with LLMSlim 1.0; until then LLMSlim is a library and servers you run yourself." },
    { title: "A profile of facts, not a transcript", body: "Mem0 keeps a list of short facts per user that you can read and edit, and the Platform can export them to a schema you define. LLMSlim keeps what was said; it has no step that turns a conversation into a profile." },
    { title: "Graph memory and consolidation", body: "Mem0's Platform links entities across memories and can merge duplicates and supersede outdated facts in the background. LLMSlim has no graph and never rewrites a stored turn: when a fact changes, both turns stay under their dates." },
    { title: "Questions worded unlike what was said", body: "LLMSlim's default relevance needs shared words. In our migration test, \"Where does Asha live now?\" did not find the memory \"Moved to Pune in September 2026\", while \"Where did Asha move to?\" did. Mem0 searches by embedding similarity. On LLMSlim, paraphrase is what the optional reranker (relevance=\"semantic\") is for; we did not run it in that test." },
    { title: "Text mostly not in English", body: "LLMSlim's default lexical scoring uses English stemming and stopwords, and we have no published results in other languages. Evaluate both on your own data before choosing." },
  ],
  chooseUs: [
    "You want what was said, not a model's summary of it: stored turns are exact, under their dates, and nothing is lost or reworded when you add them.",
    "Write cost and latency matter: storing a message makes no model call. In round 3, building Mem0's memory was $1.76 of its $2.66 per 1,000 LoCoMo questions.",
    "Long per-user histories: on Mem0's own LongMemEval questions, LLMSlim with its reranker answered 78.3% for $1.04 per 1,000 questions, against 76.7% for $220.88.",
    "Everything on your own machines in one package: SQLite, Postgres or, from 1.0, MongoDB, with no vector database or embedding service.",
    "Claude Code, Cursor and other MCP clients through llmslim mcp, and any language through llmslim serve.",
    "Code already written for Mem0: Mem0Memory keeps its method names, filters and result shapes.",
  ],
  pricing: {
    intro: `Mem0's plans as its pricing page listed them on ${PRICES_CHECKED}, next to LLMSlim's. The units differ (Mem0 counts adds and retrievals, Orbit counts stored turns and searches), so the plans don't map one to one.`,
    rival: {
      url: "https://mem0.ai/pricing",
      rows: [
        { plan: "Free", price: "Free", includes: "Unlimited end users. For the first 30 days, 10,000 adds and 1,000 retrievals a month, with model calls covered by Mem0; then, with your own LLM key, 50,000 adds and 10,000 retrievals a month. Use past the limits is billed by usage, up to a monthly cap you set. Community support." },
        { plan: "Custom", price: "Custom (contact Mem0)", includes: "Limits set to your volume, graph memory, user profiles, Dream, advanced analytics, private Slack support, SSO, audit logs and an SLA, on-prem deployment and custom integrations. Model call and overage terms are set in the agreement." },
        { plan: "Open source (mem0ai)", price: "Free, Apache-2.0", includes: "Self-hosted. You provision and pay for the LLM, embedder and vector store." },
      ],
    },
    notes: [
      "Mem0's pricing page lists no per-unit price for usage past the free limits.",
      "With extraction on, every add is an LLM call, and with your own key that call is on your provider's bill. In round 3, building Mem0's memory on Claude Haiku 5.5 added $1.76 per 1,000 LoCoMo questions, and about $0.22 per LongMemEval question.",
      "LLMSlim Core makes no model calls, so its only costs are your machine and database.",
      ORBIT_NOTE,
    ],
  },
  migration: {
    intro: "Three steps: export your memories with Mem0's get_all, import them, and point your code at LLMSlim. We ran the import and search below on a sample export in the shape get_all returns; the outputs are copied from that run. We have no Mem0 account, so the export script follows Mem0's SDK source but was not run against Mem0.",
    steps: [
      {
        title: "1. Export your memories from Mem0",
        body: "get_all lists a scope's memories: on the Platform 200 at a time, with a `next` link while more remain. Write each memory as one JSON line. The Platform's memory export writes JSON shaped by a schema you define, which `llmslim import mem0` doesn't read.",
        samples: [MEM0_EXPORT, MEM0_SAMPLE],
      },
      {
        title: "2. Import them",
        body: "`llmslim import mem0` comes with LLMSlim 1.0. Until then, install main from GitHub to use it; `pip install llmslim` (0.12.0) has the Mem0-compatible API but no importer. Each memory becomes one `user` turn under its own `user_id`, `agent_id` and `run_id`, at its original time.",
        samples: [INSTALL_MAIN, MEM0_IMPORT_COMMANDS, MEM0_IMPORT_OUTPUT],
        after: "On 0.12.0, a short loop does the same. Unlike the importer, it stores everything again if you run it twice.",
      },
      {
        title: "On 0.12.0: add them in a loop",
        body: "Run with `pip install \"llmslim[fast-tokens]\"`, the 0.12.0 release.",
        samples: [MEM0_ADD_LOOP, MEM0_ADD_LOOP_OUTPUT],
      },
      {
        title: "3. Switch one import and search",
        body: "Mem0Memory takes the calls your Mem0 code makes; Memory is LLMSlim's own API, with a token budget.",
        samples: [MEM0_CHECK, MEM0_CHECK_OUTPUT],
        after: "The last two lines show the limit of lexical relevance. Mem0's memories are short facts without their subject, so \"Where did Asha move to?\" shares the word \"move\" with \"Moved to Pune\" and finds it, while \"Where does Asha live now?\" shares no word with it, and the budget goes to the oldest memory instead. For questions worded unlike what was stored, use `relevance=\"semantic\"` (`pip install \"llmslim[semantic]\"`), or a budget that holds the whole history.",
      },
    ],
    notes: [
      "Mem0's memories are facts its model extracted (\"Is allergic to peanuts\"), not what was said, and they are stored as they are. From then on, what you add is stored word for word.",
      "Each turn keeps the memory's created_at as its time and its id as source_id in its metadata. Mem0's categories and metadata are not imported.",
      "Mem0Memory covers Mem0's open-source Memory class in its 2.x shape, not the hosted MemoryClient. Filters other than user_id, agent_id and run_id raise, and so do reset, expiration_date and reference_date.",
      "Re-run your own evaluation after switching. Our results cover two English benchmarks and one reader.",
    ],
    guide: { label: "The full migration guide", href: "/docs/migrate-from-mem0" },
  },
  faqs: [
    ["Is LLMSlim better than Mem0?", `Not across the board. In round 6, the latest results, LLMSlim 0.12 with its reranker was on par with Mem0 on BEAM-1M's conversations of about 946,000 tokens: ${signed(D6.M2500.mean)} points at 2,500 tokens and ${signed(D6.M10000.mean)} at 10,000, and both 95% intervals include zero, so we do not claim to beat Mem0. It cost ${usd(R6.all.llmslim2500.cost)} and ${usd(R6.all.llmslim10000.cost)} per 1,000 questions against ${usd(R6.all.mem0Top50.cost)} and ${usd(R6.all.mem0Top200.cost)}, and it trails Mem0 on summarization at both budgets and on multi-session reasoning at 10,000 tokens. ` + "In round 3, read by Claude Haiku 5.5, the default LLMSlim and Mem0 were level on LoCoMo at about 1,000 and 2,500 tokens, LLMSlim was ahead at 10,000 (+2.7 points, 95% CI +1.2 to +4.1), and they were level on Mem0's own LongMemEval sample. LLMSlim cost about a third as much on LoCoMo and 212 times less on Mem0's LongMemEval questions, because it makes no model calls to build memory. Mem0 was clearly better on multi-hop and temporal questions at about 1,000 tokens. The round-3 results are for LLMSlim Core 0.9.0; the 0.12 Memory API keeps less of the evidence on two-person conversations, a gap that is still open."],
    ["Can I keep my Mem0 code?", "Mostly. from llmslim.memory.compat import Mem0Memory as Memory keeps the method names, keyword arguments and return shapes of Mem0 2.x's open-source Memory class. The differences fail loudly: filters other than user_id, agent_id and run_id raise, reset raises, and infer, prompt and memory_type are accepted and ignored. It doesn't cover Mem0's hosted MemoryClient."],
    ["How do I move my existing Mem0 memories?", "Export them with get_all as JSON lines, then run llmslim import mem0 (LLMSlim 1.0, or main from GitHub today), or a short Memory.add loop on 0.12.0. Each memory becomes one user turn under its own user_id, agent_id and run_id, at its original time. The steps and their real output are above and in the migration guide."],
    ["Does LLMSlim call an LLM?", "No. Storing and searching run no LLM. By default no model runs at all; relevance=\"semantic\" adds a 22M-parameter cross-encoder that runs on your CPU."],
    ["Is LLMSlim affiliated with Mem0?", "No. LLMSlim is an independent MIT-licensed project from AMEYOR. We ran Mem0's open-source library ourselves, through Mem0's own benchmark harness in round 3 and in the format of its BEAM harness in round 6; Mem0 did not run, review or endorse the comparison."],
    ["Can I reproduce the numbers?", `Round 3's, yes. The splits, the scripts that ran Mem0 (mem0_locomo.py and mem0_lme.py) and every answer and judgement are in benchmarks/live/round3 in the public repository. All of round 3, every system and benchmark, cost $107.10 in Claude API calls. ${ROUND6_REPRODUCE}`],
  ],
  sources: [
    { label: `Mem0 pricing (read ${PRICES_CHECKED})`, url: "https://mem0.ai/pricing" },
    { label: "Mem0 docs: Platform overview", url: "https://docs.mem0.ai/overview" },
    { label: "Mem0 docs: Platform vs open source", url: "https://docs.mem0.ai/platform/platform-vs-oss" },
    { label: "Mem0 docs: add", url: "https://docs.mem0.ai/core-concepts/memory-operations/add" },
    { label: "Mem0 docs: search", url: "https://docs.mem0.ai/core-concepts/memory-operations/search" },
    { label: "Mem0 API: get all memories", url: "https://docs.mem0.ai/api-reference/memory/get-memories" },
    { label: "Mem0 docs: memory export", url: "https://docs.mem0.ai/platform/features/memory-export" },
    { label: "mem0ai/mem0 on GitHub (Apache-2.0)", url: "https://github.com/mem0ai/mem0" },
    { label: "Mem0's benchmark harness", url: "https://github.com/mem0ai/memory-benchmarks" },
    { label: "Third-party Mem0 re-run (MemOS paper)", url: "https://arxiv.org/abs/2507.03724" },
    ...ROUND6_LINKS,
    { label: "Round 3 report and tables", url: ROUND3_REPORT },
    { label: "How round 3 was run, and where Mem0's run differs", url: ROUND3 },
    { label: "Known memory quality issues (1.0 roadmap)", url: ROADMAP_ISSUES },
    { label: "Migration guide on GitHub", url: MIGRATION_GUIDE },
  ],
}

// ------------------------------------------------------------------ Zep

export const ZEP_COMPARISON: MemoryComparison = {
  slug: "zep",
  rival: "Zep",
  title: "Zep Alternative: LLMSlim vs Zep for Agent Memory",
  description: "LLMSlim vs Zep: verbatim turns with no LLM calls on write against a temporal context graph, LoCoMo and LongMemEval results with cost and 95% intervals, pricing, and a migration path.",
  kicker: "Comparison · Zep alternative",
  heading: ["LLMSlim vs Zep.", "An honest comparison."],
  lede: "Zep is a context layer for agents: an LLM turns the messages and data you send into a temporal graph of entities and facts, and agents retrieve from that graph. LLMSlim Core is an MIT-licensed Python library that stores every turn word for word and, when you search, returns the turns that answer the question within a token budget, with no LLM call on either side. Here is how they differ, what three public benchmarks show, what each costs, and how to bring your Zep threads across.",
  lastUpdated: "November 3, 2026",
  meta: ["Updated November 3, 2026", "Latest results: LLMSlim 0.12, round 6 (BEAM-1M)", "Earlier: LLMSlim Core 0.9, round 3", "Reader: Claude Haiku 5.5", `Prices checked ${PRICES_CHECKED}`],
  disclosure: "We build LLMSlim. We are not affiliated with Zep. Zep Cloud is a hosted service; we benchmarked Graphiti 0.30.2, the open-source framework Zep is built on, on Neo4j: through Zep's own benchmark harness in round 3, and in round 6 with Zep's LongMemEval context template. Zep did not run, review or endorse this comparison.",
  shortAnswer: [
    "Zep builds a temporal graph: an LLM extracts entities and facts from each message, dates them, and resolves them against what the graph already holds. LLMSlim keeps the messages and selects from them when you ask. Zep is a hosted service, with Graphiti as its open-source framework; LLMSlim Core is a library you run, and its hosted edition, Orbit, opens with LLMSlim 1.0.",
    `Ahead of Zep in round 6, the latest results: on BEAM-1M, on ${F6.zepConversations.value} of its ${F6.conversations.value} conversations of about 946,000 tokens each (${F6.zepQuestions.value} held-out questions), read by Claude Haiku 5.5, LLMSlim 0.12 with its reranker scored ${R6.zep.llmslim2500.score.toFixed(1)} out of 100 at 2,500 tokens and ${R6.zep.llmslim10000.score.toFixed(1)} at 10,000, against ${R6.zep.zep.score.toFixed(1)} for Graphiti 0.30.2 on Neo4j: ${signed(D6.Z2500.mean)} points (95% CI ${range(D6.Z2500.low, D6.Z2500.high)}) and ${signed(D6.Z10000.mean)} (${range(D6.Z10000.low, D6.Z10000.high)}). Zep ran on those ${F6.zepConversations.value} conversations to cap its cost, so the comparison is on them only.`,
    `${usd(R6.zep.llmslim2500.cost)} and ${usd(R6.zep.llmslim10000.cost)} per 1,000 of those questions at list prices, against ${usd(R6.zep.zep.cost)} for Zep, ${usd(F6.zepMemoryBuilding.value)} of it the LLM calls that build its graph. LLMSlim makes no LLM call when storing or searching.`,
    `Where LLMSlim loses in round 6: against Zep, no question type is more than 3 points behind; against Mem0, on all ${F6.conversations.value} conversations, ${ROUND6_LOSSES}.`,
    "In round 3, an earlier round on LoCoMo and LongMemEval-S: on LoCoMo at about 2,500 tokens, read by Claude Haiku 5.5, Graphiti on Neo4j answered 74.4%, against 91.7% for LLMSlim Core 0.9 with no model (+17.3 points, 95% CI +14.8 to +19.7) and 93.0% with its optional 22M-parameter reranker. Per 1,000 questions end to end, that cost $6.24 for Graphiti, against $0.89 and $0.95 for LLMSlim.",
    "In round 3, on the 24 LongMemEval questions pre-registered for Zep, Graphiti answered 58.3% for $697.56 per 1,000 questions, against 87.5% for $0.94 for LLMSlim (+29.2 points, 95% CI +12.5 to +45.8). Building a graph of each 500-message history costs about $0.70 a question. 24 questions is a small sample: the intervals are about ±17 points.",
    "Our round-3 Graphiti results are far below Zep's own published LongMemEval result (71.2% with GPT-4o, in the Zep paper), and in both rounds we ran Graphiti with Claude Haiku 5.5 rather than Zep Cloud. Read them as one setup, not a verdict on Zep Cloud.",
    "The round-3 results are for LLMSlim Core 0.9.0 selecting from whole sessions. The Memory API of 0.12 reads a history differently, and on two-person conversations it keeps less of the evidence than the version benchmarked in round 3; see what round 3 does not show.",
  ],
  glance: [
    { aspect: "What it stores", llmslim: "Every turn, word for word, under its date and scope", rival: "Each message as an episode, which stays retrievable, and the entities and facts an LLM extracts from it, in a temporal graph" },
    { aspect: "Model calls when you add", llmslim: "None", rival: "LLM calls for each episode: extracting entities and facts, dating facts, resolving them against the graph, and summarizing entities" },
    { aspect: "When a fact changes", llmslim: "Both turns stay, each under its date; since 0.12, search shows statements that may conflict side by side", rival: "A contradicting fact invalidates the older one, with valid_at and invalid_at times on each fact" },
    { aspect: "How search works", llmslim: "Ranks stored turns against the question by shared words, with no model, and returns them within a token budget; an optional 22M-parameter cross-encoder rescores", rival: "Retrieves a prompt-ready Context Block from the user's graph; Graphiti combines semantic, full-text and graph search" },
    { aspect: "What you run", llmslim: "One Python package. Memory in SQLite (built into Python), Postgres or, from 1.0, MongoDB", rival: "Zep Cloud is hosted; Enterprise can deploy in your VPC. Graphiti runs on Neo4j, FalkorDB or Amazon Neptune, with an LLM and an embedder you provide" },
    { aspect: "Interfaces", llmslim: "Python API, llmslim serve (HTTP), llmslim mcp (MCP server), a TypeScript client", rival: "Python, TypeScript and Go SDKs, a REST API, a Context MCP Server" },
    { aspect: "Scope", llmslim: "Per user, agent and session", rival: "User graphs, and shared Context Graphs across users, documents and business data, with access policies" },
    { aspect: "License", llmslim: "MIT", rival: "Zep Cloud: a commercial service. Graphiti: Apache-2.0. Zep Community Edition is deprecated" },
    { aspect: "Hosted option", llmslim: "LLMSlim Orbit, opening with LLMSlim 1.0 (not available yet)", rival: "Zep Cloud: Free, Flex, Flex Plus and Enterprise plans" },
  ],
  about: [
    {
      name: "Zep",
      cite: "Zep docs: overview, How graph creation works",
      url: "https://help.getzep.com/v4/how-graph-creation-works",
      body: "Zep calls itself \"the unified context layer for enterprise data\": it combines conversations, documents and business data into temporal Context Graphs that agents retrieve from. Chat messages go into threads. Each message is stored as an episode, and an LLM-driven pipeline extracts entities and facts from it, dates the facts, resolves them against the graph (a contradiction invalidates the older fact) and updates entity summaries. Agents retrieve a prompt-ready Context Block from a user's graph.",
    },
    {
      name: "Graphiti",
      cite: "getzep/graphiti on GitHub (Apache-2.0); Zep docs: Graphiti overview",
      url: "https://help.getzep.com/v4/graphiti/getting-started/overview",
      body: "Zep's open-source framework for temporal knowledge graphs, which Zep's FAQ describes as the framework that powers Zep Cloud. It runs on Neo4j, FalkorDB or Amazon Neptune, with an LLM and an embedder from providers such as OpenAI, Azure OpenAI, Gemini or Anthropic. Zep Community Edition, a self-hosted Zep, is deprecated and no longer supported. Round 3 benchmarked Graphiti 0.30.2 on Neo4j.",
    },
  ],
  aboutNote: `From Zep's documentation, its FAQ and the Graphiti repository, read on ${PRICES_CHECKED}.`,
  differences: [
    { title: "Verbatim storage, no graph to maintain", body: "add stores each turn as it was said, with its time and scope. There are no entities to resolve and no facts to extract, so nothing can be merged wrongly or extracted wrongly; what the model reads later is what was said." },
    { title: "No LLM calls on write", body: "Storing makes no model call, so adding memory costs nothing per message and works offline. In round 3, building Graphiti's graph on Claude Haiku 5.5 was $5.29 of its $6.24 per 1,000 LoCoMo questions, and about $0.70 a question on LongMemEval's 500-message histories." },
    { title: "Selection at question time, within a budget", body: "search ranks user turns and windows of replies against the question, and returns what fits the token budget you give, in date order. Relevance is lexical by default: no model, deterministic. relevance=\"semantic\" adds a 22M-parameter cross-encoder that runs on a CPU." },
    { title: "Self-hosted on SQLite, Postgres or MongoDB", body: "One pip install. Memory lives in a SQLite file by default, in Postgres for several processes or machines, or, from 1.0, in MongoDB. There is no graph database, embedding model or LLM to run." },
    { title: "An MCP server and an HTTP API", body: "llmslim mcp gives Claude Code, Claude Desktop, Cursor and other MCP clients remember, recall, forget and fit_context tools. llmslim serve puts the same memory behind a JSON API, with a TypeScript client for the Vercel AI SDK and Mastra." },
    { title: "Changes kept side by side", body: "Zep invalidates a fact when a newer one contradicts it. LLMSlim keeps both statements under their dates, and since 0.12 its search shows statements that may conflict side by side, so the model weighs which one holds." },
  ],
  benchmarks: [
    {
      id: "round6",
      status: "latest",
      kicker: ROUND6_KICKER,
      heading: ["BEAM-1M, held out.", "Ahead of Zep, on its 30 conversations."],
      intro: `BEAM's 1M tier: conversations of about 946,000 tokens each between a user and an assistant, with 20 questions of 10 types about each. To cap its cost, Zep ran on ${F6.zepConversations.value} of the ${F6.conversations.value} conversations, drawn with a fixed seed before any result, so every comparison here is on those ${F6.zepConversations.value} and their ${F6.zepQuestions.value} questions. ${ROUND6_INTRO_COMMON}: the answer call, Mem0's and Zep's memory-building calls, and each system's compute. Graphiti 0.30.2 on Neo4j stored every exchange through its own pipeline; LLMSlim 0.12 ran with its reranker.`,
      tables: [
        {
          title: `BEAM-1M on Zep's ${F6.zepConversations.value} conversations: ${F6.zepQuestions.value} held-out questions`,
          scoreLabel: ROUND6_SCORE,
          rows: [
            row6("LLMSlim 0.12 + reranker", R6.zep.llmslim2500, "llmslim", BUDGET_2500),
            row6("Mem0, top 50 memories", R6.zep.mem0Top50, "other", BUDGET_2500),
            row6("LLMSlim 0.12 + reranker", R6.zep.llmslim10000, "llmslim", BUDGET_10000),
            row6("Mem0, top 200 memories", R6.zep.mem0Top200, "other", BUDGET_10000),
            row6("Zep (Graphiti 0.30.2 on Neo4j)", R6.zep.zep, "rival", "Zep: 20 facts and 20 entities"),
          ],
          note: `BEAM's rubric score out of 100, each question read three times and each read judged, with the 95% t interval over Zep's ${F6.zepConversations.value} conversations. Zep's 20 facts and 20 entities, in Zep's LongMemEval context template, came to ${tokens(R6.zep.zep.tokens)} tokens on average. Most of Zep's cost is the LLM calls that build its graph: ${usd(F6.zepMemoryBuilding.value)} of its ${usd(R6.zep.zep.cost)} per 1,000 questions at list prices. On these ${F6.zepConversations.value} conversations LLMSlim at 10,000 tokens is level with Mem0's top 200 (${signed(F6.llmslimVsMem0OnZep10000.value)}); the on-par reading against Mem0 is on all ${F6.conversations.value} conversations.`,
        },
      ],
      pairedDiffs: [
        diff6(D6.Z2500, "LLMSlim 0.12 + reranker, 2,500 tokens, vs Zep", `BEAM-1M, Zep's ${F6.zepConversations.value} conversations (${F6.zepQuestions.value})`),
        diff6(D6.Z10000, "LLMSlim 0.12 + reranker, 10,000 tokens, vs Zep", `BEAM-1M, Zep's ${F6.zepConversations.value} conversations (${F6.zepQuestions.value})`),
      ],
      pairedNote: `Paired differences in points, LLMSlim 0.12 with its reranker minus Zep, on the same ${F6.zepQuestions.value} questions, with the 95% t interval over Zep's ${F6.zepConversations.value} conversations in brackets; the paired cluster bootstrap gives ${range(D6.Z2500.bootstrapLow, D6.Z2500.bootstrapHigh)} and ${range(D6.Z10000.bootstrapLow, D6.Z10000.bootstrapHigh)}. Both intervals are above zero, so LLMSlim is ahead of Zep at both budgets, on Zep's ${F6.zepConversations.value} conversations only.`,
      weakSpots: {
        title: "Where LLMSlim trails, by question type",
        columns: ["Question type, against", "Budget, conversations (questions)"],
        rows: [
          ...ROUND6_BELOW_ZEP.map((diff) => diff6(diff, `${typeName(diff)}, vs Zep`, `${budgetOf(diff.key)}, Zep's ${F6.zepConversations.value} (60)`)),
          ...ROUND6_WEAK_SPOTS_VS_MEM0.map((diff) => diff6(diff, `${typeName(diff)}, vs Mem0 ${diff.key === "M2500" ? "top 50" : "top 200"}`, `${budgetOf(diff.key)}, all ${F6.conversations.value} (70)`)),
        ],
        note: `LLMSlim 0.12 minus the other system per question type, with 95% t intervals, which are descriptive and not adjusted for multiple comparisons. Against Zep no type is more than 3 points behind at either budget; temporal reasoning at 2,500 tokens is the only type below Zep, within noise. The round's weak spots are against Mem0, on all ${F6.conversations.value} conversations: every type more than 3 points behind, as the round 6 report lists them. Summarization at both budgets and multi-session reasoning at 10,000 tokens are behind; information extraction is behind within noise.`,
      },
      caveats: [
        ROUND6_CAVEATS.resultsOnly,
        { title: "Graphiti, set up as the report describes", body: "Graphiti 0.30.2 on Neo4j, one exchange per episode, with Claude Haiku 5.5 as its LLM, Qwen3-Embedding-0.6B as its embedder and BAAI/bge-reranker-v2-m3. Search returned 20 facts and 20 entities in Zep's LongMemEval context template. Its LLM calls went through one metering proxy that recorded every call. Zep Cloud, the hosted service, was not benchmarked." },
        { title: "Zep on a seeded 30", body: `Zep ran on ${F6.zepConversations.value} of the ${F6.conversations.value} conversations, drawn with a fixed seed before any result, to cap its cost. Its comparisons are on those ${F6.zepConversations.value} only, and so is every number in the table above.` },
        ROUND6_CAVEATS.oneReader,
        ROUND6_CAVEATS.reranker,
        { title: "The cost gap depends on questions per conversation", body: `The cost figures assume BEAM's 20 questions per conversation. Most of Zep's cost is the one-time work of building its graph, so with more questions per conversation the gap gets smaller: at 2,500 tokens, storing one conversation and asking 20 questions costs ${usd(F6.zepPerConversation20.value, 3)} on Zep against ${usd(F6.llmslimOnZepPerConversation20.value, 3)} on LLMSlim, and asking 100 costs ${usd(F6.zepPerConversation100.value, 3)} against ${usd(F6.llmslimOnZepPerConversation100.value, 3)}.` },
        ROUND6_CAVEATS.commit,
        ROUND6_CAVEATS.oneBenchmark,
      ],
      links: ROUND6_LINKS,
      linksLabel: "Sources",
    },
    {
      id: "round3",
      status: "earlier",
      kicker: "Round 3 · LLMSlim Core 0.9.0 · 13–15 Oct 2026",
      context: "The earlier round, on different benchmarks: round 3 measured LLMSlim Core 0.9.0 against Graphiti on LoCoMo and LongMemEval-S. The latest results, round 6 on BEAM-1M, are above.",
      heading: ["Two memory benchmarks, one reader.", "Same questions, similar budgets."],
      intro: "Graphiti ran through Zep's own benchmark harness: each LoCoMo message an episode, each LongMemEval session an episode, and 20 facts and 20 entities in Zep's own context template. LLMSlim selected from the same histories at about the same number of tokens. Claude Haiku 5.5 read every context with Mem0's answer prompt; Mem0's judge scored LoCoMo and the official judge LongMemEval. Costs are per 1,000 questions end to end at list prices, including the calls that build Graphiti's graph.",
      tables: [
        {
          title: "LoCoMo: 1,307 test questions on 8 long conversations, about 2,500 tokens",
          rows: [
            { system: "Full history, read from the prompt cache", tokens: "27,133", score: "95.1 (93.9–96.3)", cost: "$0.83", kind: "other" },
            { system: "LLMSlim 0.9 + reranker", tokens: "2,495", score: "93.0 (91.5–94.3)", cost: "$0.95", kind: "llmslim" },
            { system: "LLMSlim 0.9", tokens: "2,492", score: "91.7 (90.3–93.3)", cost: "$0.89", kind: "llmslim" },
            { system: "Mem0, top 50 memories", tokens: "2,425", score: "91.0 (89.4–92.5)", cost: "$2.66", kind: "other" },
            { system: "RAG over turns (Qwen3-Embedding-0.6B)", tokens: "2,430", score: "85.2 (83.2–87.0)", cost: "$0.90", kind: "other" },
            { system: "Zep (Graphiti on Neo4j)", tokens: "2,738", score: "74.4 (72.0–76.7)", cost: "$6.24", kind: "rival" },
          ],
          note: "Accuracy by Mem0's judge, with the 95% bootstrap interval. Graphiti's context, in Zep's template, averaged 2,738 tokens. The full history was read from the prompt cache because a conversation's questions were asked back to back; without the cache it costs $4.48 per 1,000 questions.",
        },
        {
          title: "LongMemEval-S: Zep's 24-question sample, about 2,500 tokens",
          rows: [
            { system: "Full history", tokens: "111,243", score: "91.7 (79.2–100.0)", cost: "$90.22", kind: "other" },
            { system: "LLMSlim 0.9", tokens: "2,501", score: "87.5 (75.0–100.0)", cost: "$0.94", kind: "llmslim" },
            { system: "LLMSlim 0.9 + reranker", tokens: "2,498", score: "87.5 (70.8–100.0)", cost: "$1.01", kind: "llmslim" },
            { system: "Mem0, top 50 memories", tokens: "2,844", score: "87.5 (75.0–100.0)", cost: "$219.48", kind: "other" },
            { system: "RAG over turns (Qwen3-Embedding-0.6B)", tokens: "2,474", score: "83.3 (66.7–95.8)", cost: "$3.28", kind: "other" },
            { system: "Zep (Graphiti on Neo4j)", tokens: "2,053", score: "58.3 (37.5–79.2)", cost: "$697.56", kind: "rival" },
          ],
          note: "Each question has its own history of about 111k tokens and 500 messages, so Graphiti builds a new graph for each question: about $0.70 a question. Accuracy by the official judge.",
        },
      ],
      pairedDiffs: [
        { comparison: "LLMSlim vs Zep", benchmark: "LoCoMo, about 2,500 tokens (1,307)", difference: "+17.3 (+14.8, +19.7)", reading: "Ahead" },
        { comparison: "LLMSlim vs Zep, token F1 (no judge)", benchmark: "LoCoMo, about 2,500 tokens (1,307)", difference: "+10.5 (+8.9, +12.0)", reading: "Ahead" },
        { comparison: "LLMSlim vs Zep", benchmark: "LongMemEval-S, Zep's sample (24)", difference: "+29.2 (+12.5, +45.8)", reading: "Ahead" },
        { comparison: "LLMSlim vs Zep, Mem0's more lenient judge", benchmark: "LongMemEval-S, Zep's sample (24)", difference: "+20.8 (+0.0, +41.7)", reading: "Level" },
      ],
      pairedNote: "Paired differences in points, the default LLMSlim (no model) minus Zep, on the same questions, with the paired bootstrap 95% interval in brackets, from the round 3 tables. Level means the interval includes zero, so the gap may be noise.",
      caveats: [
        { title: "Graphiti, not Zep Cloud", body: "Zep Cloud is a hosted service with its own models and settings. We ran Graphiti 0.30.2, the open-source framework that powers it, on Neo4j (Graphiti's primary backend), through Zep's own harness (getzep/zep-papers), with Claude Haiku 5.5 for extraction, Qwen3-Embedding-0.6B for embeddings and Zep's BGE reranker. Zep Cloud may score differently." },
        { title: "Far below Zep's own published result", body: "Zep's paper reports 71.2% on LongMemEval-S with GPT-4o, against 60.2% for full context in its setup. Our 58.3% used Claude Haiku 5.5 for extraction and reading, on a 24-question sample, so the two are not comparable. Compare each system's gap to its own full-context baseline, not raw scores across readers." },
        { title: "Where the run differs from Zep's harness", body: "Each difference is in Zep's favour or forced by the benchmark's one-model rule. On LongMemEval, Zep's run added every message on its own; here each session is one episode, to keep the cost of Graphiti's several calls per episode within budget. Zep's LoCoMo script read a photo-caption key LoCoMo does not have; here every system sees the captions. Graphiti's embedding and database compute is not counted, which favours it." },
        { title: "A small sample on LongMemEval", body: "Zep ran on its pre-registered 24 questions, because building a graph of each 500-message history costs about $0.70 a question. The 95% intervals are about ±17 points on 24 questions; under Mem0's more lenient judge the gap's interval touches zero." },
        MEASURED_ON_09,
        { title: "A cached full history", body: "When a conversation's questions come back to back, the cached full history (95.1% for $0.83 per 1,000 questions) is cheaper than LLMSlim at 10,000 tokens and more accurate than any compressed context. LLMSlim is the cheaper choice when the context changes between questions, when questions arrive too far apart for the cache, or when a history is long enough to be billed at the long-prompt rate." },
      ],
      links: [
        { label: "Round 3 report and tables", url: ROUND3_REPORT },
        { label: "How the runs were kept honest", url: ROUND3 },
        { label: "Zep run scripts", url: `${ROUND3}/zep_locomo.py` },
        { label: "Per-question results", url: `${ROUND3}/results` },
      ],
    },
  ],
  chooseThem: [
    { title: "Shared, governed context across sources", body: "Zep combines business data, documents and conversations into Context Graphs shared across users and accounts, with access policies for agents and teams. LLMSlim scopes memory per user, agent and session, and has no graph that spans sources." },
    { title: "Compliance and a managed service today", body: "Zep's Enterprise plan includes SOC 2 Type II, a HIPAA BAA, an SLA and deployment in your own VPC. LLMSlim Core runs wherever you run it, and its hosted edition, Orbit, opens with LLMSlim 1.0." },
    { title: "Questions about entities and their history", body: "Zep's graph answers questions about people, accounts and how facts about them changed, with validity times on each fact. LLMSlim returns what was said; it has no entity graph." },
    { title: "Facts that should be invalidated", body: "When a fact changes, Zep invalidates the older one. LLMSlim keeps both under their dates and shows statements that may conflict side by side; if your agent must see only the current fact, Zep does that work for you." },
    { title: "Text mostly not in English", body: "LLMSlim's default lexical scoring uses English stemming and stopwords, and we have no published results in other languages. Evaluate both on your own data before choosing." },
  ],
  chooseUs: [
    "Conversation memory where the exact words matter, with no extraction model in between.",
    "No LLM bill for memory: storing a message costs nothing. In round 3, building Graphiti's graph was $5.29 of its $6.24 per 1,000 LoCoMo questions.",
    "Long conversations: on LoCoMo, 91.7% with no model and 93.0% with the reranker, against 74.4% for Graphiti, in round 3.",
    "One package on your own machines: SQLite, Postgres or, from 1.0, MongoDB, with no graph database to run.",
    "Claude Code, Cursor and other MCP clients through llmslim mcp, and any language through llmslim serve.",
  ],
  pricing: {
    intro: `Zep's plans as its pricing page listed them on ${PRICES_CHECKED}, next to LLMSlim's. The units differ (Zep counts credits for what you ingest, Orbit counts stored turns and searches), so the plans don't map one to one.`,
    rival: {
      url: "https://www.getzep.com/pricing",
      rows: [
        { plan: "Free", price: "Free", includes: "10,000 credits a month, for prototyping. Limits apply." },
        { plan: "Flex", price: "$125 a month, billed monthly", includes: "50,000 credits a month, then $25 per 10,000 credits. 600 requests a minute, 5 projects, 5 Context MCP Server seats, API logs kept 1 day." },
        { plan: "Flex Plus", price: "$375 a month, billed monthly", includes: "200,000 credits a month, then $75 per 40,000 credits. 1,000 requests a minute, 10 projects, 15 Context MCP Server seats, webhooks and analytics, API logs kept 7 days." },
        { plan: "Enterprise", price: "Custom (contact Zep)", includes: "Negotiated credits, guaranteed rate limits with an SLA, SOC 2 Type II and a HIPAA BAA, and deployment in Zep Cloud, with your own encryption keys, or in your VPC." },
        { plan: "Graphiti (open source)", price: "Free, Apache-2.0", includes: "Self-hosted framework. You run a graph database (Neo4j, FalkorDB or Amazon Neptune) and pay for its LLM and embedder." },
      ],
    },
    notes: [
      "A credit, per Zep's page: an episode (a chat message, a JSON payload or a block of text) up to 350 bytes uses 1 credit, plus 1 for each further 350 bytes or part of it. Retrieval, storage, threads and users use no credits. The page also offers annual billing, which it says saves 17%.",
      "Zep's extraction runs on Zep's side and is covered by credits. On Graphiti it is your LLM bill: in round 3, building Graphiti's graph on Claude Haiku 5.5 added $5.29 per 1,000 LoCoMo questions, and about $0.70 per LongMemEval question.",
      "LLMSlim Core makes no model calls, so its only costs are your machine and database.",
      ORBIT_NOTE,
    ],
  },
  migration: {
    intro: "LLMSlim has no Zep importer. The closest path is Zep's own message history: export each thread's messages as JSON lines in the shape `llmslim import jsonl` reads, and import those. We ran the conversion, the import and the search below on sample messages in the shape of Zep's v4 list-messages response; the outputs are copied from that run. We have no Zep account, so the export script follows Zep's SDK reference and source but was not run against Zep.",
    steps: [
      {
        title: "1. Export your threads from Zep",
        body: "With `pip install zep-cloud` and a Zep API key: list each user's threads, read their messages oldest first, and write one line per message. `to_llmslim` maps Zep's message fields to the JSONL fields LLMSlim reads.",
        samples: [ZEP_EXPORT, ZEP_SAMPLE],
      },
      {
        title: "2. Import the JSONL",
        body: "`llmslim import jsonl` comes with LLMSlim 1.0; until then, install main from GitHub to use it. Each thread becomes a session. System messages are left out, and function and tool messages too unless you pass `--include-tool-output`. Running it again stores only what is new.",
        samples: [INSTALL_MAIN, ZEP_IMPORT_COMMAND, ZEP_IMPORT_OUTPUT],
      },
      {
        title: "On 0.12.0: add them in a loop",
        body: "`pip install llmslim` (0.12.0) has no importer; this loop stores the same messages. Running it twice stores them twice.",
        samples: [ZEP_ADD_LOOP, ZEP_ADD_LOOP_OUTPUT],
      },
      {
        title: "3. Search",
        body: "Memory.search returns the turns that answer a question, within a token budget, ready to put in a prompt as data.",
        samples: [ZEP_CHECK, ZEP_CHECK_OUTPUT],
      },
    ],
    notes: [
      "Only messages come across. Zep's facts, entities, summaries and data added to a graph directly are not exported by this script; LLMSlim reads the messages themselves.",
      "Your user ids are yours to choose: the script maps each of your users to their Zep user UUID, and stores turns under your id.",
      "Re-run your own evaluation after switching. Our results cover two English benchmarks and one reader.",
    ],
    guide: { label: "Import your chat history (1.0 docs)", href: "/docs/1.0/import-history" },
  },
  faqs: [
    ["Is LLMSlim better than Zep?", `In the setups we ran, LLMSlim was ahead. In round 6, the latest results, on Zep's ${F6.zepConversations.value} BEAM-1M conversations, LLMSlim 0.12 with its reranker was ahead of Zep (Graphiti 0.30.2) by ${D6.Z2500.mean.toFixed(1)} points at 2,500 tokens (95% CI ${range(D6.Z2500.low, D6.Z2500.high)}) and ${D6.Z10000.mean.toFixed(1)} at 10,000 (${range(D6.Z10000.low, D6.Z10000.high)}). ` + "In round 3: on LoCoMo, 91.7% with no model against 74.4% for Graphiti (+17.3 points, 95% CI +14.8 to +19.7), and on Zep's 24 LongMemEval questions 87.5% against 58.3%. But we ran Graphiti, not Zep Cloud, with Claude Haiku 5.5 as every model, and Zep's own paper reports 71.2% on LongMemEval-S with GPT-4o. Zep also does things LLMSlim doesn't: graphs shared across users and sources, fact invalidation, and compliance options. The round-3 results are for LLMSlim Core 0.9.0; the 0.12 Memory API keeps less of the evidence on two-person conversations, a gap that is still open."],
    ["Can LLMSlim import my Zep data?", "Not directly: llmslim import has no Zep format. Export your threads' messages with Zep's SDK as JSON lines and import them with llmslim import jsonl (LLMSlim 1.0, or main from GitHub today), or with a Memory.add loop on 0.12.0. Facts and entities from Zep's graph don't come across; LLMSlim reads the messages themselves."],
    ["Can I self-host Zep instead?", "Zep's FAQ says Zep Community Edition is deprecated and no longer supported, and points to Zep Cloud, the open-source Graphiti framework, and BYOC deployments for enterprise customers. LLMSlim Core is self-hosted by default."],
    ["Does LLMSlim call an LLM?", "No. Storing and searching run no LLM. By default no model runs at all; relevance=\"semantic\" adds a 22M-parameter cross-encoder that runs on your CPU."],
    ["Is LLMSlim affiliated with Zep?", "No. LLMSlim is an independent MIT-licensed project from AMEYOR. We ran Graphiti, Zep's open-source framework, ourselves, through Zep's own benchmark harness in round 3 and with Zep's LongMemEval context template in round 6; Zep did not run, review or endorse the comparison."],
    ["Can I reproduce the numbers?", `Round 3's, yes. The splits, the scripts that ran Graphiti (zep_locomo.py and zep_lme.py) and every answer and judgement are in benchmarks/live/round3 in the public repository. All of round 3, every system and benchmark, cost $107.10 in Claude API calls. ${ROUND6_REPRODUCE}`],
  ],
  sources: [
    { label: `Zep pricing (read ${PRICES_CHECKED})`, url: "https://www.getzep.com/pricing" },
    { label: "Zep docs: overview", url: "https://help.getzep.com/v4/overview" },
    { label: "Zep docs: How graph creation works", url: "https://help.getzep.com/v4/how-graph-creation-works" },
    { label: "Zep docs: retrieving context", url: "https://help.getzep.com/v4/retrieving-context" },
    { label: "Zep docs: FAQ (self-hosting, Community Edition)", url: "https://help.getzep.com/v4/faq" },
    { label: "Zep docs: threads and messages", url: "https://help.getzep.com/v4/threads" },
    { label: "Zep API: list thread messages", url: "https://help.getzep.com/v4/sdk-reference/thread/list-messages" },
    { label: "Graphiti overview", url: "https://help.getzep.com/v4/graphiti/getting-started/overview" },
    { label: "getzep/graphiti on GitHub (Apache-2.0)", url: "https://github.com/getzep/graphiti" },
    { label: "Zep paper (arXiv:2501.13956)", url: "https://arxiv.org/abs/2501.13956" },
    { label: "Zep's benchmark harness", url: "https://github.com/getzep/zep-papers" },
    ...ROUND6_LINKS,
    { label: "Round 3 report and tables", url: ROUND3_REPORT },
    { label: "How round 3 was run, and where Zep's run differs", url: ROUND3 },
    { label: "Known memory quality issues (1.0 roadmap)", url: ROADMAP_ISSUES },
  ],
}

export const MEMORY_COMPARISONS: Record<string, MemoryComparison> = {
  [MEM0_COMPARISON.slug]: MEM0_COMPARISON,
  [ZEP_COMPARISON.slug]: ZEP_COMPARISON,
}
