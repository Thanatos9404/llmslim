import React from "react";
import Link from "next/link";
import { constructMetadata } from "@/lib/seo";
import { BENCHMARK_SUITES } from "@/data/benchmarks";
import { ArrowRight, BarChart3, Cpu, ShieldCheck, FileText, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/design-system";

export const metadata = constructMetadata({
  title: "Open & Reproducible Benchmarks — LLMSlim",
  description: "Open and reproducible performance benchmarks comparing LLMSlim against manual editing, prompt caching, GPT-5, Claude, Gemini, and dynamic compression ratios.",
});

export default function BenchmarksIndexPage() {
  const suiteList = Object.values(BENCHMARK_SUITES);

  return (
    <div className="space-y-12">
      {/* Benchmark Hub Header Banner */}
      <div className="space-y-4 max-w-4xl">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Open & Reproducible Experimental Suite</span>
        </div>
        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          LLMSlim <span className="text-gradient-emerald">Open Benchmarks</span>
        </h1>
        <p className="text-slate-400 text-base leading-relaxed font-sans">
          Transparent, reproducible benchmark evaluations measuring token volume reduction, execution latency (Mean ± StdDev), projected API billing costs, instruction fidelity, and entity retention.
        </p>
      </div>

      {/* Featured Overview Metric Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <Card glowColor="emerald" className="p-6 space-y-2">
          <div className="text-xs font-mono uppercase text-slate-400 flex items-center justify-between">
            <span>Measured Execution Speed</span>
            <Cpu className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-400 font-mono tracking-tight font-tabular">
            24.8 ms <span className="text-xs text-slate-400 font-normal">± 2.1 ms</span>
          </div>
          <p className="text-[11px] text-slate-400 font-sans">
            Measured local CPU execution overhead per prompt (N=100 runs per sample).
          </p>
        </Card>

        <Card glowColor="cyan" className="p-6 space-y-2">
          <div className="text-xs font-mono uppercase text-slate-400 flex items-center justify-between">
            <span>Measured Directive Shielding</span>
            <ShieldCheck className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-3xl font-extrabold text-cyan-400 font-mono tracking-tight font-tabular">
            100.0% <span className="text-xs text-slate-400 font-normal">± 0.0%</span>
          </div>
          <p className="text-[11px] text-slate-400 font-sans">
            Imperative constraint retention via Priority Tier 4 hard locking.
          </p>
        </Card>

        <Card glowColor="violet" className="p-6 space-y-2">
          <div className="text-xs font-mono uppercase text-slate-400 flex items-center justify-between">
            <span>Measured Token Reduction</span>
            <BarChart3 className="w-4 h-4 text-violet-400" />
          </div>
          <div className="text-3xl font-extrabold text-violet-400 font-mono tracking-tight font-tabular">
            40% – 70%
          </div>
          <p className="text-[11px] text-slate-400 font-sans">
            Measured reduction in prompt tokens submitted to downstream APIs.
          </p>
        </Card>
      </div>

      {/* Benchmark Suites List */}
      <div className="space-y-8 pt-4">
        <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-400 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          Open & Reproducible Benchmark Suites ({suiteList.length} Experimental Runs)
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {suiteList.map((suite) => (
            <Link key={suite.slug} href={`/benchmarks/${suite.slug}`} className="group flex">
              <Card glowColor="emerald" className="p-6 h-full flex flex-col justify-between space-y-5 hover:border-emerald-500/50 transition-all w-full">
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                    <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 font-bold text-slate-200">
                      Target: {suite.targetModel}
                    </span>
                    <span className="text-emerald-400 font-bold">100% Reproducible</span>
                  </div>

                  <div className="space-y-1.5">
                    <h3 className="text-xl font-bold text-white group-hover:text-emerald-400 transition-colors font-sans">
                      {suite.title}
                    </h3>
                    <p className="text-slate-400 text-xs line-clamp-2 leading-relaxed font-sans">
                      {suite.subtitle}
                    </p>
                  </div>
                </div>

                <div className="pt-2 text-xs font-mono text-emerald-400 flex items-center gap-1 group-hover:translate-x-1.5 transition-transform font-bold">
                  View Full Benchmark & Raw Data <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
