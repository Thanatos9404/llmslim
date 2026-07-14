import React from "react";
import Link from "next/link";
import { constructMetadata } from "@/lib/seo";
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs";
import { ArrowRight, BookOpen, Sparkles, Terminal, Code, Cpu, ShieldCheck } from "lucide-react";
import { Card } from "@/components/design-system";

export const metadata = constructMetadata({
  title: "Documentation — LLMSlim Prompt & Context Compression",
  description: "Comprehensive developer guides, API references, CLI manuals, and prompt engineering strategies for LLMSlim.",
});

export default function DocsIndexPage() {
  const docList = Object.values(DOCS_REGISTRY);

  return (
    <div className="space-y-12">
      {/* Documentation Hub Banner */}
      <div className="space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          <BookOpen className="w-3.5 h-3.5" />
          <span>Official OpenAI-Grade Developer Documentation</span>
        </div>
        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          LLMSlim <span className="text-gradient-emerald">Documentation</span>
        </h1>
        <p className="text-slate-400 text-base max-w-2xl leading-relaxed">
          Master enterprise prompt compression, Priority Tier protection, offline TF-IDF centrality ranking, and API integration.
        </p>
      </div>

      {/* Featured Quick Start Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link href="/docs/getting-started" className="group">
          <Card glowColor="emerald" className="p-6 h-full flex flex-col justify-between space-y-4 hover:border-emerald-500/50 transition-colors">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-emerald-400 font-mono text-xs font-bold">
                <span className="flex items-center gap-1.5"><Sparkles className="w-4 h-4" /> Getting Started</span>
                <span>2 min read</span>
              </div>
              <h2 className="text-lg font-bold text-white group-hover:text-emerald-400 transition-colors">
                Overview & Philosophy
              </h2>
              <p className="text-slate-400 text-xs leading-relaxed">
                Learn how LLMSlim cuts LLM token costs by 40-70% with guaranteed 100% instruction fidelity.
              </p>
            </div>
            <div className="text-xs font-mono text-emerald-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
              Start Guide <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </Card>
        </Link>

        <Link href="/docs/quickstart" className="group">
          <Card glowColor="cyan" className="p-6 h-full flex flex-col justify-between space-y-4 hover:border-cyan-500/50 transition-colors">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-cyan-400 font-mono text-xs font-bold">
                <span className="flex items-center gap-1.5"><Code className="w-4 h-4" /> Quick Start</span>
                <span>5 min read</span>
              </div>
              <h2 className="text-lg font-bold text-white group-hover:text-cyan-400 transition-colors">
                Python SDK Integration
              </h2>
              <p className="text-slate-400 text-xs leading-relaxed">
                Integrate compress() into OpenAI, Claude, LangChain, and FastAPI pipelines in 1 line of code.
              </p>
            </div>
            <div className="text-xs font-mono text-cyan-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
              View Quickstart <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </Card>
        </Link>
      </div>

      {/* Categorized Documentation List */}
      <div className="space-y-10 pt-4">
        {DOC_CATEGORIES.map((category) => {
          const docs = docList.filter((d) => d.category === category);
          if (docs.length === 0) return null;

          return (
            <div key={category} className="space-y-4 border-t border-white/10 pt-8">
              <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-400 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                {category}
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {docs.map((doc) => (
                  <Link key={doc.slug} href={`/docs/${doc.slug}`} className="group">
                    <div className="p-5 rounded-2xl bg-[#0D121C] border border-white/10 hover:border-emerald-500/30 transition-all space-y-2 h-full flex flex-col justify-between">
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                          <span className="font-bold text-slate-300">{doc.title}</span>
                          <span>{doc.readingTime}</span>
                        </div>
                        <p className="text-slate-400 text-xs line-clamp-2 leading-relaxed">
                          {doc.description}
                        </p>
                      </div>
                      <div className="pt-2 text-[11px] font-mono text-emerald-400 flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                        Read Guide <ArrowRight className="w-3 h-3" />
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
