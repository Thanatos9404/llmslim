import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { constructMetadata } from "@/lib/seo";
import { BENCHMARK_SUITES } from "@/data/benchmarks";
import { DocCodeBlock } from "@/components/docs/DocCodeBlock";
import { ArrowLeft, BarChart3, CheckCircle2, Cpu, FileCode, AlertTriangle, ShieldCheck, Database, Server, Info } from "lucide-react";
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
    title: `${suite.title} — Open & Reproducible Benchmark`,
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

      {/* Hardware & System Environment Specification Box */}
      <section id="environment-spec" className="space-y-4 scroll-mt-32">
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <Server className="w-5 h-5 text-emerald-400" /> System Environment & Rig Specification
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-5 rounded-2xl bg-[#0D121C] border border-white/10 font-mono text-xs text-slate-300">
          <div><span className="text-slate-500 uppercase">CPU:</span> <span className="text-emerald-400 font-bold">{suite.environmentSpec.cpu}</span></div>
          <div><span className="text-slate-500 uppercase">RAM:</span> <span className="text-slate-200">{suite.environmentSpec.ram}</span></div>
          <div><span className="text-slate-500 uppercase">OS:</span> <span className="text-slate-200">{suite.environmentSpec.os}</span></div>
          <div><span className="text-slate-500 uppercase">Runtime:</span> <span className="text-slate-200">{suite.environmentSpec.pythonVersion}</span></div>
          <div><span className="text-slate-500 uppercase">Package:</span> <span className="text-emerald-400 font-bold">{suite.environmentSpec.packageVersion}</span></div>
          <div><span className="text-slate-500 uppercase">Tokenizer:</span> <span className="text-slate-200">{suite.environmentSpec.tokenizerVersion}</span></div>
          <div><span className="text-slate-500 uppercase">Dataset Size:</span> <span className="text-slate-200">{suite.environmentSpec.sampleSize}</span></div>
          <div><span className="text-slate-500 uppercase">Iterations:</span> <span className="text-slate-200">{suite.environmentSpec.iterationsPerSample}</span></div>
        </div>
      </section>

      {/* Step 1: Benchmark Data Table */}
      <section id="results-table" className="space-y-4 scroll-mt-32">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
            <BarChart3 className="w-5 h-5 text-emerald-400" /> Empirical Benchmark Matrix
          </h2>
          <span className="text-[11px] font-mono text-slate-400">
            *Costs are projected estimates; latencies and ratios are measured empirical values.
          </span>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#0D121C] font-mono text-xs">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-[#070A0F] text-emerald-400">
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Method Variant</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Token Reduction (Measured)</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Execution Latency (Measured)</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Billed Cost (Projected)</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Semantic Retention (Measured)</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Instruction Retention (Measured)</th>
                <th className="px-4 py-3 font-bold uppercase tracking-wider">Entity Preservation (Measured)</th>
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

      {/* Honest Limitations & Non-Recommended Workloads Section */}
      <section id="limitations" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <AlertTriangle className="w-5 h-5 text-amber-400" /> Limitations & Non-Recommended Workloads
        </h2>
        <div className="p-6 rounded-2xl bg-amber-500/10 border border-amber-500/25 space-y-3 font-sans text-xs text-amber-200/90 leading-relaxed">
          <div className="font-mono font-bold text-amber-300 uppercase tracking-widest flex items-center gap-1.5">
            <Info className="w-4 h-4" /> Honest Engineering Trade-Offs
          </div>
          <ul className="space-y-2 pl-4 border-l border-amber-500/30">
            {suite.limitations.map((limit, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-amber-400 font-mono font-bold">•</span>
                <span>{limit}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Step 3: Experimental Methodology */}
      <section id="methodology" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <Cpu className="w-5 h-5 text-emerald-400" /> Experimental Protocol & Methodology
        </h2>
        <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10 text-slate-300 text-sm leading-relaxed font-sans">
          {suite.methodology}
        </div>
      </section>

      {/* Raw Downloadable Evaluation Dataset JSON */}
      <section id="raw-dataset" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <Database className="w-5 h-5 text-emerald-400" /> Raw Evaluation Dataset Sample (JSON)
        </h2>
        <p className="text-xs font-mono text-slate-400">
          Raw evaluation prompt payload sample format used during experimental benchmark runs:
        </p>
        <DocCodeBlock
          language="json"
          filename="raw_dataset_sample.json"
          code={suite.rawDatasetJson}
        />
      </section>

      {/* Step 4: Reproducible Python Script */}
      <section id="reproducible-script" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <FileCode className="w-5 h-5 text-emerald-400" /> Reproducible Python Script
        </h2>
        <p className="text-xs font-mono text-slate-400">
          Run this exact script on your hardware to reproduce token reduction and execution latency:
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
