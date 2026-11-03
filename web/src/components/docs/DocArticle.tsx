import Link from "next/link"
import { preload } from "react-dom"
import { ArrowLeft, ArrowRight, Link2, Plus } from "lucide-react"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { Inline, plainText } from "@/components/docs/DocInline"
import { DocSectionBody } from "@/components/docs/DocProse"
import { DocToc, ReadingProgress } from "@/components/docs/DocToc"
import { DocsVersionNotice } from "@/components/docs/DocsVersionNotice"
import { docsInOrder, isNewIn, type DocPage } from "@/data/docs"
import { docHref, docsHome, versionStatus, type DocsVersion } from "@/data/docs-versions"
import { breadcrumbJsonLd, faqJsonLd, isoDate, jsonLdScript, techArticleJsonLd } from "@/lib/seo"

/** One guide in one version: notice, header, sections, questions, related guides and the pager. */
export function DocArticle({ doc, version }: { doc: DocPage; version: DocsVersion }) {
  // The title's and subtitle's faces, requested with the stylesheet instead of after it: a late swap re-wrapped the
  // header and moved the first section on phones (CLS 0.029, already on main before this pass).
  preload("/fonts/geist-latin.woff2", { as: "font", type: "font/woff2", crossOrigin: "anonymous" })
  preload("/fonts/InstrumentSerif-Italic.woff2", { as: "font", type: "font/woff2", crossOrigin: "anonymous" })
  const path = docHref(version, doc.slug)
  const home = docsHome(version)
  const status = versionStatus(version)
  const jsonLd = [
    techArticleJsonLd({ path, headline: doc.title, description: doc.description, section: doc.category, dateModified: isoDate(doc.lastUpdated) }),
    breadcrumbJsonLd([["Home", "/"], [status === "current" ? "Documentation" : `Documentation ${version}`, home], [doc.title, path]]),
    ...(doc.faqs.length > 0 ? [faqJsonLd(doc.faqs.map((faq) => [faq.question, plainText(faq.answer)] as const), path)] : []),
  ]
  const order = docsInOrder(version)
  const index = order.findIndex((item) => item.slug === doc.slug)
  const previous = index > 0 ? order[index - 1] : null
  const next = index >= 0 && index < order.length - 1 ? order[index + 1] : null
  return <div className="doc-layout">
    <ReadingProgress />
    <article className="doc">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />
      <nav className="doc-crumbs" aria-label="Breadcrumb"><MemoryGlyph size={12} className="doc-crumbs-glyph" /><Link href={home}>{status === "current" ? "Docs" : `Docs ${version}`}</Link><span aria-hidden="true">/</span><span>{doc.category}</span></nav>
      <DocsVersionNotice version={version} slug={doc.slug} />
      <header className="doc-head">
        <h1>{doc.title}</h1>
        <p className="doc-subtitle">{doc.subtitle}</p>
        <p className="doc-meta">
          <span>{doc.readingTime}</span><span>Updated {doc.lastUpdated}</span>
          {doc.experimental && <span className="doc-badge is-experimental" title="A minor release may change this API">Experimental</span>}
          {!doc.experimental && isNewIn(version, doc.slug) && <span className="doc-badge is-new">New in {version}</span>}
        </p>
      </header>
      {doc.sections.map((section) => <section id={section.id} key={section.id} className="doc-section">
        <h2><a href={`#${section.id}`} className="doc-anchor" aria-label={`Link to ${section.title}`}><Link2 size={15} /></a>{section.title}</h2>
        <DocSectionBody section={section} version={version} />
      </section>)}
      {doc.faqs.length > 0 && <section className="doc-faq" aria-labelledby="faq-title">
        <h2 id="faq-title">Questions</h2>
        {doc.faqs.map((faq) => <details key={faq.question}><summary>{faq.question}<Plus size={16} aria-hidden="true" /></summary><p><Inline text={faq.answer} version={version} /></p></details>)}
      </section>}
      {doc.relatedPages.length > 0 && <p className="doc-related">Related: {doc.relatedPages.map((item, i) => <span key={item.slug}>{i > 0 && ", "}<Link href={docHref(version, item.slug)}>{item.title}</Link></span>)}</p>}
      <nav className="doc-pager" aria-label="More guides">
        {previous ? <Link href={docHref(version, previous.slug)} className="doc-pager-link"><span><ArrowLeft size={14} /> Previous</span><strong>{previous.title}</strong></Link> : <span />}
        {next ? <Link href={docHref(version, next.slug)} className="doc-pager-link is-next"><span>Next <ArrowRight size={14} /></span><strong>{next.title}</strong></Link> : <span />}
      </nav>
    </article>
    <DocToc sections={doc.sections.map(({ id, title }) => ({ id, title }))} />
  </div>
}
