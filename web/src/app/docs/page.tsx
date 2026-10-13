import Link from "next/link"
import { ArrowRight } from "lucide-react"
import { DocsHero } from "@/components/docs/DocsHero"
import { constructMetadata } from "@/lib/seo"
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs"
import { INTEGRATIONS_REGISTRY } from "@/data/integrations"

/** LangChain, LlamaIndex and Haystack adapters, listed with the guides because most readers arrive from a framework. */
const FRAMEWORKS = Object.values(INTEGRATIONS_REGISTRY).filter((item) => item.category === "Framework")

export const metadata = constructMetadata({ title: "Documentation | LLMSlim Prompt & Context Compression", description: "Install LLMSlim with pip and compress prompts, chat history, RAG passages and tool output in Python: getting started, the optional reranker, ContextRole, pipelines and the context planner.", path: "/docs", markdownPath: "/docs.md" })

const PATHS = [
  { slug: "getting-started", step: "Start here", title: "Your first compression", body: "Install, compress a long context, and focus it on the question your agent is answering." },
  { slug: "context-role", step: "Understand", title: "Provenance and trust", body: "Keep instructions protected and retrieved or tool text in its place, whatever it says." },
  { slug: "pipelines", step: "Build", title: "Retrieval and chat", body: "Share one budget across documents, and compress conversations with role-aware defaults." },
]

export default function DocsIndexPage() {
  const docs = Object.values(DOCS_REGISTRY)
  return <div className="docs-index">
    <DocsHero />
    <section className="docs-paths" aria-label="Where to start">
      {PATHS.map((path, i) => <Link key={path.slug} href={`/docs/${path.slug}`} className="docs-path">
        <span className="docs-path-step"><span>{String(i + 1).padStart(2, "0")}</span>{path.step}</span>
        <strong>{path.title}</strong>
        <span className="docs-path-body">{path.body}</span>
        <span className="docs-path-go">Read <ArrowRight size={14} /></span>
      </Link>)}
    </section>
    {DOC_CATEGORIES.map((category) => {
      const items = docs.filter((doc) => doc.category === category)
      return items.length ? <section key={category} className="docs-group" aria-labelledby={`group-${category}`}>
        <h2 id={`group-${category}`}>{category}</h2>
        <ul>{items.map((doc) => <li key={doc.slug}><Link href={`/docs/${doc.slug}`}>
          <span className="docs-row-title">{doc.title}</span>
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
        <span className="docs-row-time">{item.installation.command.match(/llmslim\[[a-z]+\]/)?.[0] ?? "Guide"}</span>
        <ArrowRight size={15} className="docs-row-arrow" aria-hidden="true" />
      </Link></li>)}</ul>
    </section>
  </div>
}
