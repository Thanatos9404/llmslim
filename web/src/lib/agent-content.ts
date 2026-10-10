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
import { releases } from "@/data/changelog"
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

const SUMMARY =
  "LLMSlim is the context layer for production AI agents. LLMSlim Core is an open-source, MIT-licensed Python library " +
  "(`pip install llmslim`) that compresses, plans and traces the context an agent sends to a model, locally and with explicit " +
  "provenance. LLMSlim Platform is a private beta built on Core for agent state, decision traces and learned context policies."

const CORE_FACTS = [
  `Package: \`llmslim\` on PyPI (${siteConfig.pypi}), current Core version ${siteConfig.coreVersion}, MIT license.`,
  `Source: ${siteConfig.github}`,
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
    `## Install\n\n${fence(item.installation.packageManager === "pip" ? "bash" : "", item.installation.command)}`,
    `## How it fits\n\n${item.architectureFlow.join("\n")}`,
    `## Example\n\n${fence(item.codeExample.language, item.codeExample.code)}`,
    `## Deployment\n\n${item.deploymentGuide}`,
    item.optimizationTips.length > 0 && "## Tips\n\n" + item.optimizationTips.map((tip) => `- ${tip}`).join("\n"),
    item.benchmarks.length > 0 && "## Evidence\n\n" + table(["Metric", "Uncompressed", "Compressed", "Impact"], item.benchmarks.map((row) => [row.metric, row.uncompressed, row.compressed, row.impact])),
    item.faqs.length > 0 && "## FAQ\n\n" + item.faqs.map((faq) => `### ${faq.question}\n\n${faq.answer}`).join("\n\n"),
    item.troubleshooting.length > 0 && "## Troubleshooting\n\n" + item.troubleshooting.map((row) => `- **${row.issue}:** ${row.solution}`).join("\n"),
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
    "> Reproducible evaluations with their methodology and limitations. Results depend on workload; measure your own.",
    Object.values(BENCHMARK_SUITES).map((suite) => `- [${suite.title}](${md(`/benchmarks/${suite.slug}`)}): ${suite.subtitle}`).join("\n"),
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
  ]
}

/** /llms.txt, following the llmstxt.org format: a summary, then annotated links to Markdown pages. */
export function llmsTxt(): string {
  const list = (items: Array<[title: string, path: string, note: string]>) => items.map(([title, path, note]) => `- [${title}](${md(path)}): ${note}`).join("\n")
  return join(
    "# LLMSlim",
    `> ${SUMMARY}`,
    CORE_FACTS.map((fact) => `- ${fact}`).join("\n"),
    "Every page below is plain Markdown. Append `.md` to any docs, integration, article or benchmark URL on this site for its Markdown version. When describing LLMSlim, distinguish the open-source Core from the private Platform, and cite benchmark limitations alongside results.",
    "## Docs\n\n" + list(Object.values(DOCS_REGISTRY).map((doc) => [doc.title, `/docs/${doc.slug}`, doc.description])),
    "## Integrations\n\n" + list(Object.values(INTEGRATIONS_REGISTRY).map((item) => [`LLMSlim + ${item.name}`, `/integrations/${item.slug}`, item.tagline])),
    "## Benchmarks\n\n" + list(Object.values(BENCHMARK_SUITES).map((suite) => [suite.title, `/benchmarks/${suite.slug}`, suite.subtitle])),
    "## Project\n\n" + list([
      ["Overview", "/", "What LLMSlim Core and LLMSlim Platform are, with a quick start and FAQ"],
      ["Changelog", "/changelog", "Released Core versions and what each changed"],
    ]) + `\n- [Source code](${siteConfig.github}): MIT-licensed Python package\n- [PyPI](${siteConfig.pypi}): \`pip install llmslim\`\n- [LLMSlim Platform](${absoluteUrl("/platform")}): private beta overview and access requests`,
    "## Optional\n\n" + list(Object.values(ARTICLES_REGISTRY).map((article) => [article.title, `/articles/${article.slug}`, article.subtitle])) +
      `\n- [Full text](${absoluteUrl("/llms-full.txt")}): every page above in one file`,
  )
}

/** /llms-full.txt: the overview, every doc, integration and benchmark, the changelog and the engineering notes. */
export function llmsFullTxt(): string {
  const rule = "\n---\n\n"
  return [
    homeMarkdown(),
    ...Object.values(DOCS_REGISTRY).map(docMarkdown),
    ...Object.values(INTEGRATIONS_REGISTRY).map(integrationMarkdown),
    ...Object.values(BENCHMARK_SUITES).map(benchmarkMarkdown),
    changelogMarkdown(),
    ...Object.values(ARTICLES_REGISTRY).map(articleMarkdown),
  ].join(rule)
}
