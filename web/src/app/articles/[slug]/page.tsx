import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowUpRight, Calendar, Clock3, Sigma, User } from "lucide-react";
import { constructMetadata } from "@/lib/seo";
import { ARTICLES_REGISTRY } from "@/data/articles";
import { siteConfig } from "@/config/site";
import { DocCodeBlock } from "@/components/docs/DocCodeBlock";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = ARTICLES_REGISTRY[slug];
  return article ? constructMetadata({ title: `${article.title} — LLMSlim Technical Papers`, description: `${article.subtitle}. ${article.abstract}` }) : constructMetadata({ title: "Article Not Found | LLMSlim Research", description: "Requested engineering article not found." });
}

export async function generateStaticParams() { return Object.keys(ARTICLES_REGISTRY).map((slug) => ({ slug })); }

export default async function ArticleSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = ARTICLES_REGISTRY[slug];
  if (!article) notFound();
  const jsonLd = { "@context": "https://schema.org", "@type": "TechArticle", headline: article.title, alternativeHeadline: article.subtitle, description: article.abstract, url: `${siteConfig.url}/articles/${article.slug}`, datePublished: "2026-07-15", dateModified: "2026-07-15", author: { "@type": "Person", name: article.author, jobTitle: article.authorRole }, publisher: { "@type": "Organization", name: "LLMSlim" } };
  return <article className="reading-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
    <Link href="/articles" className="reading-back"><ArrowLeft size={15} /> All engineering notes</Link>
    <header className="reading-header"><div className="reading-meta"><span>{article.category}</span><i><Clock3 size={14} /> {article.readingTime}</i><i><User size={14} /> {article.author}</i><i><Calendar size={14} /> {article.publishedDate}</i></div><h1>{article.title}</h1><p>{article.subtitle}</p></header>
    <section className="reading-summary"><div><Sigma size={18} /><span>Mathematical intuition</span></div><p>{article.mathIntuitionSummary}</p></section>
    <section className="reading-takeaways"><span className="section-label">Key takeaways</span><ol>{article.keyTakeaways.map((item, index) => <li key={item}><b>{String(index + 1).padStart(2, "0")}</b><span>{item}</span></li>)}</ol></section>
    <div className="reading-content">{article.sections.map((section) => <section id={section.id} key={section.id}><h2>{section.title}</h2><div className="reading-copy">{section.content}</div>{section.mathFormula && <Formula value={section.mathFormula} />}{section.codeSnippet && <DocCodeBlock language={section.codeSnippet.language} filename={section.codeSnippet.filename} code={section.codeSnippet.code} />}{section.tableData && <div className="reading-table"><table><thead><tr>{section.tableData.headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{section.tableData.rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>}</section>)}</div>
    {article.references.length > 0 && <section className="reading-references"><span className="section-label">References</span><ol>{article.references.map((ref) => <li key={ref.citationKey}><span>[{ref.citationKey}]</span><a href={ref.url} target="_blank" rel="noreferrer">{ref.title} <ArrowUpRight size={13} /></a></li>)}</ol></section>}
  </article>;
}

function Formula({ value }: { value: string }) {
  const readable = value.replace(/\\text\{([^{}]+)\}/g, "$1").replace(/\\mathbf\{([^{}]+)\}/g, "$1").replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1) / ($2)").replace(/\\cdot/g, "·").replace(/\\\|/g, "‖").replace(/_\{([^{}]+)\}/g, "_$1").replace(/\^\{([^{}]+)\}/g, "^$1");
  return <figure className="article-formula"><figcaption>Equation</figcaption><div aria-label={`Mathematical formula: ${readable}`}>{readable}</div></figure>;
}
