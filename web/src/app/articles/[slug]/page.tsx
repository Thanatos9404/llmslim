import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { constructMetadata } from "@/lib/seo";
import { ARTICLES_REGISTRY } from "@/data/articles";
import { DocCodeBlock } from "@/components/docs/DocCodeBlock";
import { ArrowLeft, Clock, Sigma, CheckCircle2, ExternalLink, Calendar, User } from "lucide-react";
import { Card } from "@/components/design-system";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = ARTICLES_REGISTRY[slug];

  if (!article) {
    return constructMetadata({
      title: "Article Not Found | LLMSlim Research",
      description: "Requested engineering article not found.",
    });
  }

  return constructMetadata({
    title: `${article.title} — LLMSlim Technical Papers`,
    description: `${article.subtitle}. ${article.abstract}`,
  });
}

export async function generateStaticParams() {
  return Object.keys(ARTICLES_REGISTRY).map((slug) => ({ slug }));
}

export default async function ArticleSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = ARTICLES_REGISTRY[slug];

  if (!article) {
    notFound();
  }

  // Build JSON-LD TechArticle & BlogPosting Schema Graph
  const techArticleJsonLd = {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    headline: article.title,
    alternativeHeadline: article.subtitle,
    description: article.abstract,
    url: `https://llmslim.app/articles/${article.slug}`,
    datePublished: "2026-07-15",
    dateModified: "2026-07-15",
    author: {
      "@type": "Person",
      name: article.author,
      jobTitle: article.authorRole,
      url: "https://github.com/Thanatos9404",
    },
    publisher: {
      "@type": "Organization",
      name: "LLMSlim",
      logo: {
        "@type": "ImageObject",
        url: "https://llmslim.app/llmslim_logo.png",
      },
    },
  };

  return (
    <article className="max-w-4xl mx-auto space-y-10 font-sans">
      {/* JSON-LD TechArticle Schema Script */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(techArticleJsonLd) }}
      />

      {/* Top Navigation Back Link */}
      <Link href="/articles" className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-emerald-400 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Technical Papers Index
      </Link>

      {/* Article Header & Rigorous Metadata */}
      <div className="space-y-5 border-b border-white/10 pb-8">
        <div className="flex flex-wrap items-center gap-3 font-mono text-xs text-slate-400">
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold">
            {article.category}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {article.readingTime}
          </span>
          <span>•</span>
          <span className="flex items-center gap-1 text-slate-300">
            <User className="w-3.5 h-3.5 text-emerald-400" />
            <strong>{article.author}</strong> ({article.authorRole})
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Calendar className="w-3.5 h-3.5" />
            Published: {article.publishedDate} (Updated: {article.lastUpdated})
          </span>
        </div>

        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          {article.title}
        </h1>

        <p className="text-base sm:text-xl text-slate-300 font-normal leading-relaxed">
          {article.subtitle}
        </p>
      </div>

      {/* Mathematical Intuition Summary Callout */}
      <div className="p-5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 font-sans text-sm space-y-2">
        <div className="flex items-center gap-2 font-mono text-xs font-bold text-emerald-400 uppercase tracking-widest">
          <Sigma className="w-4 h-4" />
          Mathematical Intuition & Formal Derivation
        </div>
        <p className="pl-6 font-mono text-xs leading-relaxed text-emerald-200">
          {article.mathIntuitionSummary}
        </p>
      </div>

      {/* Key Architectural Takeaways Card */}
      <Card glowColor="emerald" className="p-6 space-y-4">
        <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-400 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" /> Key Takeaways
        </h2>
        <ul className="space-y-2 text-xs font-sans text-slate-300">
          {article.keyTakeaways.map((takeaway, idx) => (
            <li key={idx} className="flex items-start gap-2">
              <span className="text-emerald-400 font-mono font-bold">0{idx + 1}.</span>
              <span>{takeaway}</span>
            </li>
          ))}
        </ul>
      </Card>

      {/* Article Sections Flow */}
      <div className="space-y-12">
        {article.sections.map((section) => (
          <section key={section.id} id={section.id} className="space-y-5 scroll-mt-32">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight border-b border-white/5 pb-3">
              {section.title}
            </h2>

            <div className="text-slate-300 text-sm leading-relaxed whitespace-pre-line space-y-4 font-sans">
              {section.content}
            </div>

            {/* LaTeX Math Formula Block */}
            {section.mathFormula && (
              <div className="my-6 p-4.5 rounded-2xl bg-[#0D121C] border border-white/10 font-mono text-xs text-center text-cyan-300 overflow-x-auto shadow-xl">
                <span className="text-[10px] uppercase tracking-widest text-slate-500 block mb-1">Mathematical Formula</span>
                <code>{section.mathFormula}</code>
              </div>
            )}

            {/* Runnable Code Snippet */}
            {section.codeSnippet && (
              <DocCodeBlock
                language={section.codeSnippet.language}
                filename={section.codeSnippet.filename}
                code={section.codeSnippet.code}
              />
            )}

            {/* Data Table */}
            {section.tableData && (
              <div className="my-6 overflow-x-auto rounded-2xl border border-white/10 bg-[#0D121C] font-mono text-xs">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/10 bg-[#070A0F] text-emerald-400">
                      {section.tableData.headers.map((header, idx) => (
                        <th key={idx} className="px-4 py-3 font-bold uppercase tracking-wider">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-slate-200">
                    {section.tableData.rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-white/[0.02] transition-colors font-tabular">
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} className="px-4 py-3">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ))}
      </div>

      {/* Peer-Reviewed References & Citations */}
      {article.references.length > 0 && (
        <div className="pt-10 border-t border-white/10 space-y-4">
          <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">
            Academic Literature & Peer-Reviewed References
          </h3>
          <ul className="space-y-2 font-mono text-xs">
            {article.references.map((ref, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-slate-500">[{ref.citationKey}]</span>
                <a
                  href={ref.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-emerald-400 hover:underline inline-flex items-center gap-1"
                >
                  {ref.title} <ExternalLink className="w-3 h-3" />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
