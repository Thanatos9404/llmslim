import Link from "next/link";
import { ArrowUpRight, BookOpen, Code2, Sparkles } from "lucide-react";
import { constructMetadata } from "@/lib/seo";
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs";

export const metadata = constructMetadata({
  title: "Documentation — LLMSlim Prompt & Context Compression",
  description: "Released developer documentation for LLMSlim.",
});

export default function DocsIndexPage() {
  const docs = Object.values(DOCS_REGISTRY);
  return <div className="hub-page">
    <header className="hub-header"><span className="hub-eyebrow"><BookOpen size={14} /> Released Python documentation</span><h1>Build with the <span>released engine.</span></h1><p>Concise guides for context roles, pipelines, token accounting, and the safety boundaries that ship in LLMSlim.</p></header>
    <section className="hub-feature-grid" aria-label="Featured documentation">
      <Link className="hub-feature" href="/docs/getting-started"><span className="hub-feature__icon"><Sparkles size={18} /></span><div><span className="hub-kicker">Start here · 2 min</span><h2>Overview & philosophy</h2><p>Understand what runs locally, what needs a provider, and where the trust boundary sits.</p></div><ArrowUpRight size={18} /></Link>
      <Link className="hub-feature" href="/docs/getting-started"><span className="hub-feature__icon"><Code2 size={18} /></span><div><span className="hub-kicker">Quick start · 5 min</span><h2>Python SDK integration</h2><p>Make one real extraction call, then choose the correct role and counter for your workflow.</p></div><ArrowUpRight size={18} /></Link>
    </section>
    <div className="hub-catalog">
      {DOC_CATEGORIES.map((category) => { const items = docs.filter((doc) => doc.category === category); if (!items.length) return null; return <section className="hub-section" key={category}><div className="hub-section__heading"><span>{category}</span><small>{items.length} guides</small></div><div className="hub-list">{items.map((doc, index) => <Link className="hub-row" href={`/docs/${doc.slug}`} key={doc.slug}><span className="hub-row__number">{String(index + 1).padStart(2, "0")}</span><div><h2>{doc.title}</h2><p>{doc.description}</p></div><span className="hub-row__meta">{doc.readingTime}<ArrowUpRight size={16} /></span></Link>)}</div></section>; })}
    </div>
  </div>;
}
