import React from "react";
import Link from "next/link";
import { constructMetadata } from "@/lib/seo";
import { ARTICLES_REGISTRY, ARTICLE_CATEGORIES } from "@/data/articles";
import { ArrowRight, BookOpen, Clock, Cpu, FileText, Sparkles, Sigma } from "lucide-react";
import { Card } from "@/components/design-system";

export const metadata = constructMetadata({
  title: "Engineering Articles & Research Papers — LLMSlim",
  description: "20 deep engineering articles on natural language prompt compression, LexRank graph centrality, attention economics, and enterprise AI architecture.",
});

export default function ArticlesIndexPage() {
  const articleList = Object.values(ARTICLES_REGISTRY);

  return (
    <div className="space-y-12">
      {/* Engineering Hub Header Banner */}
      <div className="space-y-4 max-w-4xl">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          <FileText className="w-3.5 h-3.5" />
          <span>Deep Technical Research & Systems Architecture Papers</span>
        </div>
        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          LLMSlim <span className="text-gradient-emerald">Engineering Papers</span>
        </h1>
        <p className="text-slate-400 text-base leading-relaxed font-sans">
          Deep technical explorations into graph centrality, token economics, attention saliency, and sub-30ms prompt compression gateways written for senior AI engineers.
        </p>
      </div>

      {/* Featured Headline Research Paper Card */}
      <Link href={`/articles/${articleList[0].slug}`} className="block group">
        <Card glowColor="emerald" className="p-8 space-y-6 hover:border-emerald-500/50 transition-all">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-slate-400">
            <span className="px-3 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-bold">
              Featured Research Paper
            </span>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> {articleList[0].readingTime}</span>
              <span>Published {articleList[0].publishedDate}</span>
            </div>
          </div>

          <div className="space-y-3">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-white group-hover:text-emerald-400 transition-colors tracking-tight font-sans">
              {articleList[0].title}
            </h2>
            <p className="text-slate-300 text-sm leading-relaxed font-sans max-w-3xl">
              {articleList[0].subtitle} — {articleList[0].abstract}
            </p>
          </div>

          <div className="p-4 rounded-xl bg-[#070A0F] border border-white/10 font-mono text-xs text-emerald-300 flex items-center gap-3">
            <Sigma className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Mathematical Intuition: {articleList[0].mathIntuitionSummary}</span>
          </div>

          <div className="text-xs font-mono text-emerald-400 flex items-center gap-1.5 font-bold group-hover:translate-x-1.5 transition-transform">
            Read Full Engineering Paper <ArrowRight className="w-4 h-4" />
          </div>
        </Card>
      </Link>

      {/* Categorized Articles Grid */}
      <div className="space-y-12 pt-6">
        {ARTICLE_CATEGORIES.map((category) => {
          const categoryArticles = articleList.filter((a) => a.category === category);
          if (categoryArticles.length === 0) return null;

          return (
            <div key={category} className="space-y-6 border-t border-white/10 pt-8">
              <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-400 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                {category} Track ({categoryArticles.length} Papers)
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {categoryArticles.map((article) => (
                  <Link key={article.slug} href={`/articles/${article.slug}`} className="group flex">
                    <div className="p-6 rounded-2xl bg-[#0D121C] border border-white/10 hover:border-emerald-500/40 transition-all space-y-4 flex flex-col justify-between w-full">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                          <span className="text-emerald-400 font-bold">{article.author}</span>
                          <span>{article.readingTime}</span>
                        </div>
                        <h3 className="text-lg font-bold text-white group-hover:text-emerald-400 transition-colors font-sans leading-snug">
                          {article.title}
                        </h3>
                        <p className="text-slate-400 text-xs line-clamp-2 leading-relaxed font-sans">
                          {article.subtitle}
                        </p>
                      </div>

                      <div className="pt-2 text-xs font-mono text-emerald-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform font-bold">
                        Read Article <ArrowRight className="w-3.5 h-3.5" />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
