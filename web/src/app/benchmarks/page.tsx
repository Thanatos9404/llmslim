import Link from "next/link";
import { ArrowRight, BarChart3, ShieldCheck, TestTube2 } from "lucide-react";
import { BENCHMARK_SUITES } from "@/data/benchmarks";
import { Card } from "@/components/design-system";
import { constructMetadata } from "@/lib/seo";

export const metadata = constructMetadata({ title: "Benchmarks | LLMSlim v0.3.1", description: "Measured v0.3.1 release verification and benchmark methodology.", canonicalUrl: "https://llmslim.app/benchmarks" });

export default function BenchmarksPage() {
  const suites = Object.values(BENCHMARK_SUITES);
  return <div className="space-y-12">
    <div className="space-y-4 max-w-3xl"><div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono"><TestTube2 className="w-3.5 h-3.5" />Measured release verification</div><h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">LLMSlim <span className="text-gradient-emerald">Benchmarks</span></h1><p className="text-slate-400 text-base leading-relaxed">v0.3.1 reports only checked-in, reproducible measurements. Use the repository scripts and your workload for performance measurements.</p></div>
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
      <Card glowColor="emerald" className="p-6"><div className="text-xs font-mono uppercase text-slate-400">Tests</div><div className="text-3xl font-extrabold text-emerald-400 font-mono">432 / 0</div><p className="text-[11px] text-slate-400">Passed / failed</p></Card>
      <Card glowColor="cyan" className="p-6"><div className="text-xs font-mono uppercase text-slate-400">Branch coverage</div><div className="text-3xl font-extrabold text-cyan-400 font-mono">92.57%</div><p className="text-[11px] text-slate-400">90% gate passed</p></Card>
      <Card glowColor="violet" className="p-6"><div className="text-xs font-mono uppercase text-slate-400">Runner reliability</div><div className="text-3xl font-extrabold text-violet-400 font-mono">100 / 100</div><p className="text-[11px] text-slate-400">Actual pytest report collection</p></Card>
    </div>
    <div className="space-y-5"><h2 className="text-xl font-bold text-white">Methodology and release gate</h2>{suites.map((suite) => <Link key={suite.slug} href={"/benchmarks/" + suite.slug} className="group block"><Card glowColor="emerald" className="p-6"><div className="flex items-center justify-between gap-4"><div><h3 className="text-xl font-bold text-white group-hover:text-emerald-400">{suite.title}</h3><p className="text-slate-400 text-sm mt-2">{suite.description}</p></div><ArrowRight className="w-5 h-5 text-emerald-400" /></div></Card></Link>)}</div>
    <p className="text-xs text-slate-500 flex items-center gap-2"><ShieldCheck className="w-4 h-4" />LLMSlim mitigates compression-induced instruction elevation; it does not provide complete prompt-injection prevention.</p>
  </div>;
}
