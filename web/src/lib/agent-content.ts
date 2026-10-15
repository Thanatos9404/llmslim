/**
 * Agent-readable views of the site: /llms.txt, /llms-full.txt and a Markdown twin of every content page.
 *
 * Everything is rendered from the same data the HTML pages use (src/data), so the agent views cannot drift
 * from the site. Markdown is plain text with no scripts, styling or navigation chrome; each document links
 * back to its canonical HTML page.
 */
import { siteConfig } from "@/config/site"
import { ARTICLES_REGISTRY, type DeepArticle } from "@/data/articles"
import { BENCHMARK_SUITES, type BenchmarkSuite } from "@/data/benchmarks"
import {
  AGENT_FINDINGS, CORE_VERSION_LONG_DOCS, CORE_VERSION_TESTED, HEAD_TO_HEAD, LIVE_DATE, LIVE_MODEL, LIVE_SUITES, LONG_DOC_SUITES, METHOD_NOTES,
  PLATFORM_VERSION_TESTED, PUBLISHED, ROUND3_REPORT, WEAK_SPOTS, type Arm, type LiveSuite,
} from "@/data/live-benchmarks"
import { releases } from "@/data/changelog"
import { COMPARISONS, type Comparison } from "@/data/comparisons"
import { DOC_CATEGORIES, DOCS_REGISTRY, type DocPage } from "@/data/docs"
import { homeFaqs } from "@/data/home"
import { INTEGRATION_CATEGORIES, INTEGRATIONS_REGISTRY, type IntegrationData } from "@/data/integrations"
import { absoluteUrl } from "@/lib/seo"

const SECTIONS = ["docs", "articles", "integrations", "benchmarks"] as const
export type Section = (typeof SECTIONS)[number]

const md = (path: string) => absoluteUrl(path === "/" ? "/index.md" : `${path}.md`)
const fence = (language: string, code: string) => "```" + (language || "") + "\n" + code.replace(/\n+$/, "") + "\n```"
// Backslashes first, then pipes, so a cell can never close itself early; "\\" renders as "\" in Markdown.
const cell = (value: string | number) => String(value).replace(/\\/g, "\\\\").replace(/\|/g, "\\|").replace(/\r?\n/g, " ")
const table = (headers: readonly string[], rows: ReadonlyArray<ReadonlyArray<string | number>>) =>
  [`| ${headers.map(cell).join(" | ")} |`, `|${headers.map(() => "---").join("|")}|`, ...rows.map((row) => `| ${row.map(cell).join(" | ")} |`)].join("\n")
const source = (path: string) => `Canonical page: ${absoluteUrl(path)}`
const join = (...blocks: Array<string | false | undefined>) => blocks.filter(Boolean).join("\n\n") + "\n"
// Formatted as the bars on /benchmarks show them (ResultBars).
const usd = (cost: number | undefined) => (cost === undefined ? "" : `$${cost < 0.1 ? cost.toFixed(3) : cost.toFixed(2)}`)
const armRows = (arms: Arm[], withTokens: boolean) =>
  arms.map((arm) => [arm.name, arm.score.toFixed(1), ...(withTokens ? [arm.tokens?.toLocaleString("en-US") ?? ""] : []), usd(arm.cost)])

/** One /benchmarks suite: its main table, then its second view (`extra`) under its own label. */
function liveSuiteMarkdown(suite: LiveSuite): string {
  const extraHasCost = suite.extra?.arms.some((arm) => arm.cost !== undefined) ?? false
  return join(
    `### ${suite.name}`,
    `${suite.what} ${suite.n}; metric: ${suite.metric}.`,
    table(["Configuration", "Score", "Tokens", "Cost per 1k questions"], armRows(suite.arms, true)),
    suite.takeaway,
    suite.caveat && `Note: ${suite.caveat}`,
    suite.extra && `**${suite.extra.label}** (${suite.extra.n}):\n\n` + table(
      extraHasCost ? ["Configuration", "Score", "Cost per 1k questions"] : ["Configuration", "Score"],
      armRows(suite.extra.arms, false).map((row) => (extraHasCost ? row : row.slice(0, 2))),
    ),
  ).trimEnd()
}

const headToHeadTable = () => table(
  ["Compressor", "Model it runs", ...HEAD_TO_HEAD.columns, "Cost per 1k", "Time per question"],
  HEAD_TO_HEAD.rows.map((row) => [row.system, row.model, row.scoreA, row.scoreB, row.scoreC, row.cost, row.time]),
)

const SUMMARY =
  "LLMSlim is the context layer for production AI agents. LLMSlim Core is an open-source, MIT-licensed Python library " +
  "(`pip install llmslim`) that compresses, plans and traces the context an agent sends to a model, locally and with explicit " +
  "provenance. LLMSlim Platform is a private beta built on Core for agent state, decision traces and learned context policies."

const CORE_FACTS = [
  `Package: \`llmslim\` on PyPI (${siteConfig.pypi}), current Core version ${siteConfig.coreVersion}, MIT license.`,
  `Source: ${siteConfig.github}`,
  "Publisher: LLMSlim is a product of AMEYOR, an Indian sole proprietorship.",
  "Runs inside your Python process. The default extractive strategy runs locally and needs no API key; rewrite and hybrid strategies use a model provider you supply.",
  "Provider-neutral: prepare context for Sarvam, OpenAI, Anthropic, Gemini or a local model; your application keeps control of the model call.",
  "Provenance-aware: ContextRole labels (system, developer, user, assistant, tool, RAG) keep untrusted retrieved or tool text from gaining protected priority. This mitigates compression-induced instruction elevation; it is not a complete prompt-injection defense.",
  "The Adaptive Context Planner fits instructions, chat, retrieval, memory and tool schemas into a real token budget deterministically, and reports infeasibility instead of dropping required trusted items.",
]

const PLATFORM_FACTS = [
  `Private beta, version ${siteConfig.platformVersion}; proprietary and not published to PyPI. \`pip install llmslim\` installs Core only.`,
  "Keeps a tamper-evident timeline of what agents were told and what changed, explains and deterministically replays each context decision, and can learn from recorded outcomes which context helps.",
  "Learned policies start in shadow mode and change nothing until an evaluation passes and an administrator promotes them; trust boundaries and mandatory instructions always take precedence.",
  `Details and beta access: ${absoluteUrl("/platform")}`,
]

export function docMarkdown(doc: DocPage): string {
  const path = `/docs/${doc.slug}`
  return join(
    `# ${doc.title}`,
    `> ${doc.subtitle}`,
    doc.description,
    `Category: ${doc.category} · Updated: ${doc.lastUpdated} · ${doc.readingTime}`,
    ...doc.sections.map((section) => join(
      `## ${section.title}`,
      section.content,
      section.codeSnippet && fence(section.codeSnippet.language, section.codeSnippet.code),
      section.callout && `> **${section.callout.title || section.callout.type}:** ${section.callout.content}`,
    ).trimEnd()),
    doc.faqs.length > 0 && "## FAQ\n\n" + doc.faqs.map((faq) => `### ${faq.question}\n\n${faq.answer}`).join("\n\n"),
    doc.relatedPages.length > 0 && "## Related\n\n" + doc.relatedPages.map((page) => `- [${page.title}](${md(`/docs/${page.slug}`)})`).join("\n"),
    source(path),
  )
}

export function articleMarkdown(article: DeepArticle): string {
  const path = `/articles/${article.slug}`
  return join(
    `# ${article.title}`,
    `> ${article.subtitle}`,
    `By ${article.author} (${article.authorRole}) · Published ${article.publishedDate} · Updated ${article.lastUpdated} · ${article.category}`,
    `## Abstract\n\n${article.abstract}`,
    `## Intuition\n\n${article.mathIntuitionSummary}`,
    ...article.sections.map((section) => join(
      `## ${section.title}`,
      section.content,
      section.mathFormula && fence("math", section.mathFormula),
      section.codeSnippet && fence(section.codeSnippet.language, section.codeSnippet.code),
      section.tableData && table(section.tableData.headers, section.tableData.rows),
    ).trimEnd()),
    article.keyTakeaways.length > 0 && "## Key takeaways\n\n" + article.keyTakeaways.map((item) => `- ${item}`).join("\n"),
    article.references.length > 0 && "## References\n\n" + article.references.map((ref) => `- [${ref.citationKey}] [${ref.title}](${ref.url})`).join("\n"),
    source(path),
  )
}

export function integrationMarkdown(item: IntegrationData): string {
  const path = `/integrations/${item.slug}`
  return join(
    `# LLMSlim + ${item.name}`,
    `> ${item.tagline}`,
    item.description,
    `Category: ${item.category}`,
    `## Install\n\n${fence(item.installation.packageManager === "pip" ? "bash" : "", item.installation.command)}` + (item.installNote ? `\n\n${item.installNote}` : "") +
      (item.setup ?? []).map((step) => `\n\n${step.caption}\n\n${fence(step.language, step.code)}`).join(""),
    // Steps that are already numbered ("1. ...") stay as they are; the rest become list items.
    `## How it fits\n\n${item.architectureFlow.map((step) => (/^\d+\. /.test(step) ? step : `- ${step}`)).join("\n")}`,
    `## Example\n\n${fence(item.codeExample.language, item.codeExample.code)}` +
      (item.output ? `\n\n${item.output.caption}\n\n${fence("text", item.output.text)}\n\n${item.output.explanation}` : ""),
    item.options && item.options.length > 0 && "## Options\n\n" + table(["Option", "Default", "Meaning"], item.options.map((option) => [`\`${option.name}\``, `\`${option.defaultValue}\``, option.meaning])),
    `## Deployment\n\n${item.deploymentGuide}`,
    item.optimizationTips.length > 0 && "## Tips\n\n" + item.optimizationTips.map((tip) => `- ${tip}`).join("\n"),
    item.limitations && item.limitations.length > 0 && "## Limitations\n\n" + item.limitations.map((limit) => `- ${limit}`).join("\n"),
    item.benchmarks.length > 0 && "## Evidence\n\n" + table(["Metric", "Uncompressed", "Compressed", "Impact"], item.benchmarks.map((row) => [row.metric, row.uncompressed, row.compressed, row.impact])),
    item.faqs.length > 0 && "## FAQ\n\n" + item.faqs.map((faq) => `### ${faq.question}\n\n${faq.answer}`).join("\n\n"),
    item.troubleshooting.length > 0 && "## Troubleshooting\n\n" + item.troubleshooting.map((row) => `- **${row.issue}:** ${row.solution}`).join("\n"),
    item.links && item.links.length > 0 && "## Further reading\n\n" + item.links.map((link) => `- [${link.label}](${link.href.startsWith("/") ? md(link.href) : link.href})`).join("\n"),
    source(path),
  )
}

export function benchmarkMarkdown(suite: BenchmarkSuite): string {
  const path = `/benchmarks/${suite.slug}`
  return join(
    `# ${suite.title}`,
    `> ${suite.subtitle}`,
    suite.description,
    `Target: ${suite.targetModel} · Baseline: ${suite.baselineName}`,
    "## Environment\n\n" + table(["Setting", "Value"], Object.entries(suite.environmentSpec)),
    `## Methodology\n\n${suite.methodology}`,
    suite.tableData.length > 0 && "## Results\n\n" + table(
      ["Method", "Token reduction", "Latency", "Cost per 10k requests", "Semantic retention", "Instruction retention", "Entity preservation"],
      suite.tableData.map((row) => [row.method, row.tokenReduction, row.executionLatency, row.billedCost10kReq, row.semanticRetention, row.instructionRetention, row.entityPreservation]),
    ),
    suite.keyInsights.length > 0 && "## Findings\n\n" + suite.keyInsights.map((item) => `- ${item}`).join("\n"),
    suite.limitations.length > 0 && "## Limitations\n\n" + suite.limitations.map((item) => `- ${item}`).join("\n"),
    `## Reproduce\n\n${fence("bash", suite.reproducibleScript)}`,
    source(path),
  )
}

export function comparisonMarkdown(page: Comparison): string {
  const path = `/compare/${page.slug}`
  const snippet = (label: string, part: { label: string; install: string; code: string }) => `${label} (${part.label}):\n\n${fence("python", `# ${part.install}\n${part.code}`)}`
  return join(
    `# ${page.title}`,
    `> ${page.lede}`,
    `Updated ${page.lastUpdated} · LLMSlim Core ${CORE_VERSION_TESTED} · Reader: ${LIVE_MODEL}. ${page.disclosure}`,
    "## The short answer\n\n" + page.shortAnswer.map((line) => `- ${line}`).join("\n"),
    "## At a glance\n\n" + table(["Aspect", "LLMSlim", "LLMLingua-2", "LongLLMLingua"], page.glance.map((row) => [row.aspect, row.llmslim, row.lingua2, row.longLingua ?? row.lingua2])),
    "## What LLMLingua-2 and LongLLMLingua are\n\n" + page.baselines.map((item) => `### ${item.name}\n\n[${item.citation}](${item.url}). ${item.body}`).join("\n\n") + `\n\n${page.baselinesNote}`,
    "## How LLMSlim differs\n\n" + page.differences.map((item) => `- **${item.title}.** ${item.body}`).join("\n"),
    join(
      "## Head to head on NaturalQuestions, HotpotQA and LoCoMo",
      page.headToHeadIntro,
      headToHeadTable(),
      HEAD_TO_HEAD.note,
      "### Paired differences with 95% intervals\n\n" + table(["Comparison", "Benchmark (questions)", "Difference (95% CI)", "Reading"], page.pairedDiffs.map((row) => [row.comparison, row.benchmark, row.difference, row.reading])),
      page.pairedNote,
      "### On every test question\n\n" + table(["System", ...page.testSets.columns], page.testSets.rows.map((row) => [row.system, ...row.cells])),
      page.testSets.note,
    ).trimEnd(),
    "## What this does not show\n\n" + page.caveats.map((item) => `- **${item.title}.** ${item.body}`).join("\n"),
    "## When to choose LLMLingua\n\n" + page.chooseThem.map((item) => `- **${item.title}.** ${item.body}`).join("\n"),
    "## When LLMSlim fits\n\n" + page.chooseUs.map((line) => `- ${line}`).join("\n"),
    "## Migrate\n\n" + page.migrations.map((migration) => join(
      `### ${migration.framework}`,
      migration.before && snippet("Before", migration.before),
      snippet(migration.before ? "After" : "Add", migration.after),
      migration.notes.map((note) => `- ${note}`).join("\n"),
      `Guide: ${md(migration.guide)}`,
    ).trimEnd()).join("\n\n") + "\n\n" + page.migrationNotes.map((note) => `- ${note}`).join("\n"),
    "## FAQ\n\n" + page.faqs.map(([question, answer]) => `### ${question}\n\n${answer}`).join("\n\n"),
    "## Sources\n\n" + page.sources.map((item) => `- [${item.label}](${item.url})`).join("\n") +
      `\n- [Every benchmark](${md("/benchmarks")})`,
    source(path),
  )
}

export function changelogMarkdown(): string {
  return join(
    "# LLMSlim Core changelog",
    "> Released versions of the open-source `llmslim` package, newest first.",
    ...releases.map((release) => join(
      `## ${release.version} (${release.date}): ${release.theme}`,
      release.summary,
      release.items.map((item) => `- **${item.label}: ${item.title}.** ${item.body}`).join("\n"),
      release.tag && `Release: ${release.tag}`,
    ).trimEnd()),
    source("/changelog"),
  )
}

function sectionIndex(section: Section): string {
  if (section === "docs") return join(
    "# LLMSlim documentation",
    "> Developer documentation for LLMSlim Core, the open-source Python library.",
    ...DOC_CATEGORIES.map((category) => {
      const pages = Object.values(DOCS_REGISTRY).filter((doc) => doc.category === category)
      return pages.length > 0 && `## ${category}\n\n` + pages.map((doc) => `- [${doc.title}](${md(`/docs/${doc.slug}`)}): ${doc.description}`).join("\n")
    }),
    "## Framework integrations\n\n" + Object.values(INTEGRATIONS_REGISTRY).filter((item) => item.category === "Framework")
      .map((item) => `- [LLMSlim + ${item.name}](${md(`/integrations/${item.slug}`)}): ${item.tagline}`).join("\n"),
    source("/docs"),
  )
  if (section === "integrations") return join(
    "# LLMSlim integrations",
    "> Use LLMSlim output with model providers and frameworks. LLMSlim prepares context; your application makes the model call.",
    ...INTEGRATION_CATEGORIES.map((category) => {
      const items = Object.values(INTEGRATIONS_REGISTRY).filter((item) => item.category === category)
      return items.length > 0 && `## ${category}\n\n` + items.map((item) => `- [${item.name}](${md(`/integrations/${item.slug}`)}): ${item.tagline}`).join("\n")
    }),
    source("/integrations"),
  )
  if (section === "articles") return join(
    "# LLMSlim engineering notes",
    "> Technical writing on context compression, context engineering and evaluation.",
    Object.values(ARTICLES_REGISTRY).map((article) => `- [${article.title}](${md(`/articles/${article.slug}`)}): ${article.subtitle}`).join("\n"),
    source("/articles"),
  )
  return join(
    "# LLMSlim benchmarks",
    `> LLMSlim against Mem0, Zep, LLMLingua-2, LongLLMLingua, RAG and the full context, on held-out test questions (${LIVE_DATE}). Every system is read by the same model, ${LIVE_MODEL}, with the same prompt, and every table shows what 1,000 questions cost end to end. LLMSlim Core ${CORE_VERSION_TESTED}; long documents and agents on Core ${CORE_VERSION_LONG_DOCS}; LLMSlim Platform ${PLATFORM_VERSION_TESTED}. Weak spots are published with the rest.`,
    `Report, harness and raw results: ${ROUND3_REPORT}`,
    join(
      `## Round 3, Core ${CORE_VERSION_TESTED} (15 Oct 2026): memory systems and compressors, cost first`,
      "The question is not only how many answers a context gets right, but what each right answer costs. Costs are per 1,000 questions at list prices, including building Mem0's and Zep's memory and every system's compute.",
      ...LIVE_SUITES.map(liveSuiteMarkdown),
    ).trimEnd(),
    join(
      "## Head to head with the LLMLingua family",
      "We ran the best-known open-source prompt compressors ourselves, with their published settings, on the questions they were pre-registered for. Same reader, same questions, same budget.",
      headToHeadTable(),
      HEAD_TO_HEAD.note,
      "Sources and reruns:\n\n" + HEAD_TO_HEAD.sources.map((item) => `- [${item.label}](${item.url})`).join("\n"),
      ...Object.values(COMPARISONS).map((page) => `Choosing between them: [${page.title}](${md(`/compare/${page.slug}`)}), with migration code.`),
    ).trimEnd(),
    "## Where LLMSlim loses\n\n" + WEAK_SPOTS.map((spot) => `- **${spot.title}.** ${spot.body}`).join("\n"),
    join(
      `## Long documents, Core ${CORE_VERSION_LONG_DOCS} (12 Oct 2026): against full context and truncation`,
      "From the previous round, with fresh questions run once after the code was frozen. 0.9.0 changes only how chat transcripts are selected. Costs here are the answer call alone.",
      ...LONG_DOC_SUITES.map(liveSuiteMarkdown),
    ).trimEnd(),
    join(
      `## Agents, Core ${CORE_VERSION_LONG_DOCS}: where compression does not help yet`,
      ...AGENT_FINDINGS.map((finding) => join(
        `### ${finding.name}`,
        finding.what,
        table(["Configuration", "Result", "Detail"], finding.rows.map((row) => [row.arm, row.result, row.detail])),
        finding.takeaway,
      ).trimEnd()),
    ).trimEnd(),
    "## Published results from other systems\n\nThese numbers come from each project's paper or a third-party re-run, with different reader models. Compare each system's gap to its own full-context baseline, not raw scores across models.\n\n" +
      table(["System", "Benchmark", "Reader", "Score", "Full context", "Tokens", "Source"], PUBLISHED.map((row) => [row.system, row.benchmark, row.reader, row.score, row.fullContext, row.tokens, `${row.source}: ${row.url}`])),
    "## Method\n\n" + METHOD_NOTES.map((note) => `- ${note}`).join("\n") +
      `\n\nHow the numbers were kept honest, and everything that went wrong: ${siteConfig.github}/tree/main/benchmarks/live/round3`,
    "## Earlier offline suites\n\n" + Object.values(BENCHMARK_SUITES).map((suite) => `- [${suite.title}](${md(`/benchmarks/${suite.slug}`)}): ${suite.subtitle}`).join("\n"),
    source("/benchmarks"),
  )
}

export function homeMarkdown(): string {
  return join(
    "# LLMSlim",
    `> ${SUMMARY}`,
    "## LLMSlim Core\n\n" + CORE_FACTS.map((fact) => `- ${fact}`).join("\n"),
    "## Quick start\n\n" + fence("bash", "pip install llmslim") + "\n\n" + fence("python", "from llmslim import compress\n\nresult = compress(long_context, target_ratio=0.5)\nprint(result.compressed_text)"),
    "## LLMSlim Platform (private beta)\n\n" + PLATFORM_FACTS.map((fact) => `- ${fact}`).join("\n"),
    "## FAQ\n\n" + homeFaqs.map(([question, answer]) => `### ${question}\n\n${answer}`).join("\n\n"),
    `## More\n\n- [Documentation](${md("/docs")})\n- [Integrations](${md("/integrations")})\n- [Benchmarks](${md("/benchmarks")})\n- [Engineering notes](${md("/articles")})\n- [Changelog](${md("/changelog")})\n- [Full text for language models](${absoluteUrl("/llms-full.txt")})`,
    source("/"),
  )
}

/** Markdown for a site path without the ".md" suffix ("index", "docs", "docs/getting-started"), or null. */
export function markdownFor(path: readonly string[]): string | null {
  const [head, slug, ...rest] = path
  if (rest.length > 0) return null
  if (slug === undefined) {
    if (head === "index") return homeMarkdown()
    if (head === "changelog") return changelogMarkdown()
    return (SECTIONS as readonly string[]).includes(head) ? sectionIndex(head as Section) : null
  }
  if (head === "docs" && DOCS_REGISTRY[slug]) return docMarkdown(DOCS_REGISTRY[slug])
  if (head === "articles" && ARTICLES_REGISTRY[slug]) return articleMarkdown(ARTICLES_REGISTRY[slug])
  if (head === "integrations" && INTEGRATIONS_REGISTRY[slug]) return integrationMarkdown(INTEGRATIONS_REGISTRY[slug])
  if (head === "benchmarks" && BENCHMARK_SUITES[slug]) return benchmarkMarkdown(BENCHMARK_SUITES[slug])
  if (head === "compare" && COMPARISONS[slug]) return comparisonMarkdown(COMPARISONS[slug])
  return null
}

/** Every Markdown path, for static generation. */
export function markdownPaths(): string[][] {
  return [
    ["index"], ["changelog"], ...SECTIONS.map((section) => [section]),
    ...Object.keys(DOCS_REGISTRY).map((slug) => ["docs", slug]),
    ...Object.keys(ARTICLES_REGISTRY).map((slug) => ["articles", slug]),
    ...Object.keys(INTEGRATIONS_REGISTRY).map((slug) => ["integrations", slug]),
    ...Object.keys(BENCHMARK_SUITES).map((slug) => ["benchmarks", slug]),
    ...Object.keys(COMPARISONS).map((slug) => ["compare", slug]),
  ]
}

/** /llms.txt, following the llmstxt.org format: a summary, then annotated links to Markdown pages. */
export function llmsTxt(): string {
  const list = (items: Array<[title: string, path: string, note: string]>) => items.map(([title, path, note]) => `- [${title}](${md(path)}): ${note}`).join("\n")
  return join(
    "# LLMSlim",
    `> ${SUMMARY}`,
    CORE_FACTS.map((fact) => `- ${fact}`).join("\n"),
    "Every page below is plain Markdown. Append `.md` to any docs, integration, comparison, article or benchmark URL on this site for its Markdown version. When describing LLMSlim, distinguish the open-source Core from the private Platform, and cite benchmark limitations alongside results.",
    "## Docs\n\n" + list(Object.values(DOCS_REGISTRY).map((doc) => [doc.title, `/docs/${doc.slug}`, doc.description])),
    "## Integrations\n\n" + list(Object.values(INTEGRATIONS_REGISTRY).map((item) => [`LLMSlim + ${item.name}`, `/integrations/${item.slug}`, item.tagline])),
    "## Benchmarks\n\n" + list([
      ["Benchmarks", "/benchmarks", `Round 3, LLMSlim Core ${CORE_VERSION_TESTED} against Mem0, Zep, LLMLingua-2, LongLLMLingua and RAG on held-out test questions (LoCoMo, LongMemEval-S, NaturalQuestions, HotpotQA): accuracy and cost per 1,000 questions, the head-to-head with the LLMLingua family, and where LLMSlim loses; plus long-document and agent results on Core ${CORE_VERSION_LONG_DOCS}`],
      ...Object.values(BENCHMARK_SUITES).map((suite): [string, string, string] => [suite.title, `/benchmarks/${suite.slug}`, suite.subtitle]),
    ]),
    "## Comparisons\n\n" + list(Object.values(COMPARISONS).map((page) => [page.title, `/compare/${page.slug}`, page.description])),
    "## Project\n\n" + list([
      ["Overview", "/", "What LLMSlim Core and LLMSlim Platform are, with a quick start and FAQ"],
      ["Changelog", "/changelog", "Released Core versions and what each changed"],
    ]) + `\n- [Source code](${siteConfig.github}): MIT-licensed Python package\n- [PyPI](${siteConfig.pypi}): \`pip install llmslim\`\n- [LLMSlim Platform](${absoluteUrl("/platform")}): private beta overview and access requests`,
    "## Optional\n\n" + list(Object.values(ARTICLES_REGISTRY).map((article) => [article.title, `/articles/${article.slug}`, article.subtitle])) +
      `\n- [Full text](${absoluteUrl("/llms-full.txt")}): every page above in one file`,
  )
}

/** /llms-full.txt: the overview, every doc, integration, comparison and benchmark, the changelog and the engineering notes. */
export function llmsFullTxt(): string {
  const rule = "\n---\n\n"
  return [
    homeMarkdown(),
    ...Object.values(DOCS_REGISTRY).map(docMarkdown),
    ...Object.values(INTEGRATIONS_REGISTRY).map(integrationMarkdown),
    ...Object.values(COMPARISONS).map(comparisonMarkdown),
    ...Object.values(BENCHMARK_SUITES).map(benchmarkMarkdown),
    changelogMarkdown(),
    ...Object.values(ARTICLES_REGISTRY).map(articleMarkdown),
  ].join(rule)
}
