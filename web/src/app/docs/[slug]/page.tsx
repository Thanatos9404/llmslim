import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowLeft, ArrowRight, Link2, Plus } from "lucide-react"
import { DocCallout } from "@/components/docs/DocCallout"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { DocToc, ReadingProgress } from "@/components/docs/DocToc"
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs"
import { breadcrumbJsonLd, constructMetadata, faqJsonLd, isoDate, jsonLdScript, techArticleJsonLd } from "@/lib/seo"

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) { const { slug } = await params; const doc = DOCS_REGISTRY[slug]; return doc ? constructMetadata({ title: `${doc.title} | LLMSlim Documentation`, description: doc.description, path: `/docs/${doc.slug}`, markdownPath: `/docs/${doc.slug}.md`, type: "article" }) : constructMetadata({ title: "Page Not Found | LLMSlim Docs", description: "Requested documentation guide not found." }) }
export async function generateStaticParams() { return Object.keys(DOCS_REGISTRY).map((slug) => ({ slug })) }

/** Guides in reading order: by category, then as listed. */
const ORDER = DOC_CATEGORIES.flatMap((category) => Object.values(DOCS_REGISTRY).filter((doc) => doc.category === category))

export default async function DocSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const doc = DOCS_REGISTRY[slug]; if (!doc) notFound()
  const path = `/docs/${doc.slug}`
  const jsonLd = [
    techArticleJsonLd({ path, headline: doc.title, description: doc.description, section: doc.category, dateModified: isoDate(doc.lastUpdated) }),
    breadcrumbJsonLd([["Home", "/"], ["Documentation", "/docs"], [doc.title, path]]),
    ...(doc.faqs.length > 0 ? [faqJsonLd(doc.faqs.map((faq) => [faq.question, faq.answer] as const), path)] : []),
  ]
  const index = ORDER.findIndex((item) => item.slug === doc.slug)
  const previous = index > 0 ? ORDER[index - 1] : null
  const next = index >= 0 && index < ORDER.length - 1 ? ORDER[index + 1] : null
  return <div className="doc-layout">
    <ReadingProgress />
    <article className="doc">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />
      <nav className="doc-crumbs" aria-label="Breadcrumb"><Link href="/docs">Docs</Link><span aria-hidden="true">/</span><span>{doc.category}</span></nav>
      <header className="doc-head">
        <h1>{doc.title}</h1>
        <p className="doc-subtitle">{doc.subtitle}</p>
        <p className="doc-meta"><span>{doc.readingTime}</span><span>Updated {doc.lastUpdated}</span></p>
      </header>
      {doc.sections.map((section) => <section id={section.id} key={section.id} className="doc-section">
        <h2><a href={`#${section.id}`} className="doc-anchor" aria-label={`Link to ${section.title}`}><Link2 size={15} /></a>{section.title}</h2>
        <p>{section.content}</p>
        {section.callout && <DocCallout callout={section.callout} />}
        {section.codeSnippet && <DocCodeBlock language={section.codeSnippet.language} filename={section.codeSnippet.filename} code={section.codeSnippet.code} />}
      </section>)}
      {doc.faqs.length > 0 && <section className="doc-faq" aria-labelledby="faq-title">
        <h2 id="faq-title">Questions</h2>
        {doc.faqs.map((faq) => <details key={faq.question}><summary>{faq.question}<Plus size={16} aria-hidden="true" /></summary><p>{faq.answer}</p></details>)}
      </section>}
      {doc.relatedPages.length > 0 && <p className="doc-related">Related: {doc.relatedPages.map((item, i) => <span key={item.slug}>{i > 0 && ", "}<Link href={`/docs/${item.slug}`}>{item.title}</Link></span>)}</p>}
      <nav className="doc-pager" aria-label="More guides">
        {previous ? <Link href={`/docs/${previous.slug}`} className="doc-pager-link"><span><ArrowLeft size={14} /> Previous</span><strong>{previous.title}</strong></Link> : <span />}
        {next ? <Link href={`/docs/${next.slug}`} className="doc-pager-link is-next"><span>Next <ArrowRight size={14} /></span><strong>{next.title}</strong></Link> : <span />}
      </nav>
    </article>
    <DocToc sections={doc.sections.map(({ id, title }) => ({ id, title }))} />
  </div>
}
