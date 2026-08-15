import Link from "next/link";
import { ArrowUpRight, Clock3, FileText, Sigma } from "lucide-react";
import { constructMetadata } from "@/lib/seo";
import { ARTICLES_REGISTRY, ARTICLE_CATEGORIES } from "@/data/articles";

export const metadata = constructMetadata({ title: "Engineering Articles & Research Papers — LLMSlim", description: "Technical writing about prompt compression, context safety, and evaluation." });

export default function ArticlesIndexPage() {
  const articles = Object.values(ARTICLES_REGISTRY);
  const featured = articles[0];
  return <div className="hub-page">
    <header className="hub-header"><span className="hub-eyebrow"><FileText size={14} /> Engineering notes & research</span><h1>Context, examined <span>in public.</span></h1><p>Technical explorations of graph centrality, token economics, attention saliency, and provenance-aware compression.</p></header>
    <Link className="article-feature" href={`/articles/${featured.slug}`}><div><span className="hub-kicker">Featured paper · {featured.readingTime}</span><h2>{featured.title}</h2><p>{featured.subtitle} — {featured.abstract}</p><span className="article-feature__math"><Sigma size={16} /> {featured.mathIntuitionSummary}</span></div><ArrowUpRight size={22} /></Link>
    <div className="hub-catalog">{ARTICLE_CATEGORIES.map((category) => { const items = articles.filter((article) => article.category === category); if (!items.length) return null; return <section className="hub-section" key={category}><div className="hub-section__heading"><span>{category}</span><small>{items.length} papers</small></div><div className="hub-list">{items.map((article, index) => <Link className="hub-row" href={`/articles/${article.slug}`} key={article.slug}><span className="hub-row__number">{String(index + 1).padStart(2, "0")}</span><div><h2>{article.title}</h2><p>{article.subtitle}</p></div><span className="hub-row__meta"><Clock3 size={14} /> {article.readingTime}<ArrowUpRight size={16} /></span></Link>)}</div></section>; })}</div>
  </div>;
}
