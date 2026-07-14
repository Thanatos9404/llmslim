import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { constructMetadata } from "@/lib/seo";
import { BENCHMARK_SUITES } from "@/data/benchmarks";
import { DocCodeBlock } from "@/components/docs/DocCodeBlock";
import { ArrowLeft, BarChart3, CheckCircle2, Cpu, FileCode, ShieldCheck, Sparkles, Terminal } from "lucide-react";
import { Card } from "@/components/design-system";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const suite = BENCHMARK_SUITES[slug];

  if (!suite) {
    return constructMetadata({
      title: "Benchmark Not Found | LLMSlim",
      description: "Requested benchmark suite not found.",
    });
  }

  return constructMetadata({
    title: `${suite.title} — Reproducible Benchmark Suite`,
    description: `${suite.subtitle}. ${suite.description}`,
  });
}

export async function generateStaticParams() {
  return Object.keys(BENCHMARK_SUITES).map((slug) => ({ slug }));
}

export default async function BenchmarkSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const suite = BENCHMARK_SUITES[slug];

  if (!suite) {
    notFound();
  }

  // Build JSON-LD TechArticle & Dataset Schema Graph
  const datasetJsonLd = {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    headline: suite.title,
    alternativeHeadline: suite.subtitle,
    description: suite.description,
    url: `https://llmslim.app/benchmarks/${suite.slug}`,
    datePublished: "2026-07-15",
    dateModified: "2026-07-15",
    author: {
      "@type": "Person",
      name: "Yashvardhan Thanvi",
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
    <div className="max-w-4xl mx-auto space-y-10 font-sans">
      {/* JSON-LD Structured Data Schema Insertion */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(datasetJsonLd) }}
      />

      {/* Top Back Link */}
      <Link href="/benchmarks" className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-emerald-400 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Benchmarks Directory
      </Link>

      {/* Header Banner */}
      <div className="space-y-4 border-b border-white/10 pb-8">
        <div className="flex flex-wrap items-center gap-3 font-mono text-xs text-slate-400">
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold">
            Target: {suite.targetModel}
          </span>
          <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 font-bold">
            Baseline: {suite.baselineName}
          </span>
        </div>

        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          {suite.title}
        </h1>

        <p className="text-base sm:text-lg text-slate-300 font-normal leading-relaxed">
          {suite.subtitle}
        </p>

        <p className="text-sm text-slate-400 leading-relaxed font-sans">
          {suite.description}
        </p>
      </div>

      {/* Step 1: Benchmark Data Table */}
      <section id="results-table" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <BarChart3 className="w-5 h-5 text-emerald-400" /> Empirical Benchmark Matrix
        </h2>

        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#0D121C] font-mono text-xs">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-[#070A0F] text-emerald-400">
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Method Variant</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Token Reduction</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Execution Latency</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Billed Cost (10k Req)</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Semantic Retention</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Instruction Retention</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Entity Preservation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-slate-200">
              {suite.tableData.map((row, idx) => (
                <tr key={idx} className="hover:bg-white/[0.02] transition-colors font-tabular">
                  <td className="px-4 py-3 font-bold text-slate-100">{row.method}</td>
                  <td className="px-4 py-3 text-emerald-400 font-bold">{row.tokenReduction}</td>
                  <td className="px-4 py-3 text-cyan-400">{row.executionLatency}</td>
                  <td className="px-4 py-3 text-violet-400 font-bold">{row.billedCost10kReq}</td>
                  <td className="px-4 py-3 text-slate-300">{row.semanticRetention}</td>
                  <td className="px-4 py-3 text-emerald-400 font-bold">{row.instructionRetention}</td>
                  <td className="px-4 py-3 text-slate-300">{row.entityPreservation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Step 2: Key Architectural Insights */}
      <section id="insights" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" /> Key Insights & Analysis
        </h2>
        <Card glowColor="emerald" className="p-6">
          <ul className="space-y-2.5 font-sans text-xs text-slate-300">
            {suite.keyInsights.map((insight, idx) => (
              <li key={idx} className="flex items-start gap-2.5">
                <span className="text-emerald-400 font-mono font-bold">0{idx + 1}.</span>
                <span>{insight}</span>
              </li>
            ))}
          </ul>
        </Card>
      </section>

      {/* Step 3: Experimental Methodology */}
      <section id="methodology" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <Cpu className="w-5 h-5 text-emerald-400" /> Experimental Methodology
        </h2>
        <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10 text-slate-300 text-sm leading-relaxed font-sans">
          {suite.methodology}
        </div>
      </section>

      {/* Step 4: Reproducible Python Script */}
      <section id="reproducible-script" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <FileCode className="w-5 h-5 text-emerald-400" /> Reproducible Python Verification Script
        </h2>
        <p className="text-xs font-mono text-slate-400">
          Run this exact script locally to verify token compression ratio and execution latency:
        </p>
        <DocCodeBlock
          language="python"
          filename="benchmark_reproducible.py"
          code={suite.reproducibleScript}
        />
      </section>
    </div>
  );
}
