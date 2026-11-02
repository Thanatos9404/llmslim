import Link from "next/link"
import { ArrowRight } from "lucide-react"
import { DocsHero } from "@/components/docs/DocsHero"
import { DocsVersionNotice } from "@/components/docs/DocsVersionNotice"
import { DOC_CATEGORIES, DOCS_BY_VERSION, docsInOrder, isNewIn } from "@/data/docs"
import { docHref, versionStatus, type DocsVersion } from "@/data/docs-versions"
import { COMPARISONS } from "@/data/comparisons"
import { INTEGRATIONS_REGISTRY } from "@/data/integrations"
import { MEMORY_COMPARISONS } from "@/data/memory-comparisons"
import { constructMetadata } from "@/lib/seo"

/** LangChain, LlamaIndex and Haystack adapters and the gptme, Hermes Agent and Pydantic AI history adapters, listed with the guides because most readers arrive from a framework. */
const FRAMEWORKS = Object.values(INTEGRATIONS_REGISTRY).filter((item) => item.category === "Framework")

/** The comparison pages (/compare/<slug>), for readers coming from Mem0, Zep or LLMLingua. */
const COMPARISON_PAGES = [...Object.values(MEMORY_COMPARISONS), ...Object.values(COMPARISONS)].map((page) => ({
  slug: page.slug, name: page.heading[0].replace(/\.$/, ""), description: page.description,
}))

/** The four ways in, one per interface. */
const PATHS = [
  { slug: "quickstart-python", step: "Python", title: "Memory in a few lines", body: "Store turns word for word and get back what answers a question, within a token budget." },
  { slug: "quickstart-mcp", step: "MCP", title: "Claude Code, Cursor and more", body: "Give any MCP client long-term memory with one command." },
  { slug: "quickstart-http", step: "HTTP", title: "llmslim serve", body: "The same memory behind a small JSON API, for apps in any language." },
  { slug: "quickstart-typescript", step: "TypeScript", title: "AI SDK and Mastra", body: "The npm client, with memory tools that never touch your prompt." },
]

const groupId = (category: string) => `group-${category.toLowerCase().replace(/\W+/g, "-")}`

export function docsIndexMetadata(version: DocsVersion) {
  const status = versionStatus(version)
  const path = status === "current" ? "/docs" : `/docs/${version}`
  const title = status === "current" ? "Documentation | LLMSlim Agent Memory & Context Compression" : status === "preview" ? `LLMSlim ${version} Documentation (Preview)` : `LLMSlim ${version} Documentation`
  const description = status === "preview"
    ? `Preview of the LLMSlim Core ${version} docs, for the unreleased main branch: getting started with Python, MCP, HTTP and TypeScript, import, explain, storage backends and the upgrade guide.`
    : "Install LLMSlim and give agents memory with no LLM in the loop, from Python, MCP, HTTP or TypeScript, and compress prompts, chat history, RAG passages and tool output into a real token budget."
  // Only the version pip installs is indexed: a preview describes unreleased code, and an old version is superseded.
  return constructMetadata({ title, description, path, markdownPath: `${path}.md`, noIndex: status !== "current" })
}

/** The docs home of one version: the hero, the four quickstarts, every guide by category, and the framework adapters. */
export function DocsIndex({ version }: { version: DocsVersion }) {
  const docs = docsInOrder(version)
  const status = versionStatus(version)
  const pages = DOCS_BY_VERSION[version]
  return <div className="docs-index">
    <DocsVersionNotice version={version} />
    <DocsHero kicker={status === "current" ? "Documentation" : status === "preview" ? `Documentation · ${version} preview` : `Documentation · ${version}`} />
    <section className="docs-paths" aria-label="Where to start">
      {PATHS.filter((path) => pages[path.slug]).map((path, i) => <Link key={path.slug} href={docHref(version, path.slug)} className="docs-path">
        <span className="docs-path-step"><span>{String(i + 1).padStart(2, "0")}</span>{path.step}</span>
        <strong>{path.title}</strong>
        <span className="docs-path-body">{path.body}</span>
        <span className="docs-path-go">Read <ArrowRight size={14} /></span>
      </Link>)}
    </section>
    {DOC_CATEGORIES.map((category) => {
      const items = docs.filter((doc) => doc.category === category)
      return items.length ? <section key={category} className="docs-group" aria-labelledby={groupId(category)}>
        <h2 id={groupId(category)}>{category}</h2>
        <ul>{items.map((doc) => <li key={doc.slug}><Link href={docHref(version, doc.slug)}>
          <span className="docs-row-title">{doc.title}{doc.experimental ? <span className="docs-nav-badge is-experimental">Experimental</span> : isNewIn(version, doc.slug) ? <span className="docs-nav-badge is-new">New</span> : null}</span>
          <span className="docs-row-body">{doc.description}</span>
          <span className="docs-row-time">{doc.readingTime}</span>
          <ArrowRight size={15} className="docs-row-arrow" aria-hidden="true" />
        </Link></li>)}</ul>
      </section> : null
    })}
    <section className="docs-group" aria-labelledby="group-frameworks">
      <h2 id="group-frameworks">Framework integrations</h2>
      <ul>{FRAMEWORKS.map((item) => <li key={item.slug}><Link href={`/integrations/${item.slug}`}>
        <span className="docs-row-title">{item.name}</span>
        <span className="docs-row-body">{item.tagline}</span>
        <span className="docs-row-time">{item.installation.command.match(/llmslim\[[a-z-]+\]/)?.[0] ?? "Guide"}</span>
        <ArrowRight size={15} className="docs-row-arrow" aria-hidden="true" />
      </Link></li>)}</ul>
    </section>
    <section className="docs-group" aria-labelledby="group-comparisons">
      <h2 id="group-comparisons">Comparisons</h2>
      <ul>{COMPARISON_PAGES.map((page) => <li key={page.slug}><Link href={`/compare/${page.slug}`}>
        <span className="docs-row-title">{page.name}</span>
        <span className="docs-row-body">{page.description}</span>
        <span className="docs-row-time">Comparison</span>
        <ArrowRight size={15} className="docs-row-arrow" aria-hidden="true" />
      </Link></li>)}</ul>
    </section>
  </div>
}
