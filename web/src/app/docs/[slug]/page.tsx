import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowUpRight, Clock3 } from "lucide-react";
import { constructMetadata } from "@/lib/seo";
import { DOCS_REGISTRY } from "@/data/docs";
import { siteConfig } from "@/config/site";
import { DocCallout } from "@/components/docs/DocCallout";
import { DocCodeBlock } from "@/components/docs/DocCodeBlock";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = DOCS_REGISTRY[slug];
  return doc ? constructMetadata({ title: `${doc.title} — LLMSlim Documentation`, description: doc.description }) : constructMetadata({ title: "Page Not Found | LLMSlim Docs", description: "Requested documentation guide not found." });
}

export async function generateStaticParams() { return Object.keys(DOCS_REGISTRY).map((slug) => ({ slug })); }

export default async function DocSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = DOCS_REGISTRY[slug];
  if (!doc) notFound();
  const jsonLd = { "@context": "https://schema.org", "@type": "TechArticle", headline: doc.title, description: doc.description, url: `${siteConfig.url}/docs/${doc.slug}`, dateModified: "2026-07-15", publisher: { "@type": "Organization", name: "LLMSlim" } };
  return <article className="reading-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
    <Link href="/docs" className="reading-back"><ArrowLeft size={15} /> All documentation</Link>
    <header className="reading-header"><div className="reading-meta"><span>{doc.category}</span><i><Clock3 size={14} /> {doc.readingTime}</i><i>Updated {doc.lastUpdated}</i></div><h1>{doc.title}</h1><p>{doc.subtitle}</p></header>
    <div className="reading-content">{doc.sections.map((section) => <section id={section.id} key={section.id}><h2>{section.title}</h2><div className="reading-copy">{section.content}</div>{section.callout && <DocCallout callout={section.callout} />}{section.codeSnippet && <DocCodeBlock language={section.codeSnippet.language} filename={section.codeSnippet.filename} code={section.codeSnippet.code} />}</section>)}</div>
    {doc.faqs.length > 0 && <section className="reading-faq"><span className="section-label">Frequently asked questions</span>{doc.faqs.map((faq) => <details key={faq.question}><summary>{faq.question}</summary><p>{faq.answer}</p></details>)}</section>}
    {doc.relatedPages.length > 0 && <section className="reading-references"><span className="section-label">Continue reading</span><div className="reading-related">{doc.relatedPages.map((item) => <Link href={`/docs/${item.slug}`} key={item.slug}>{item.title}<ArrowUpRight size={16} /></Link>)}</div></section>}
  </article>;
}
