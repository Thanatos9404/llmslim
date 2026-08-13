import React from "react";
import Link from "next/link";
import { constructMetadata } from "@/lib/seo";
import { ClientStudioWrapper } from "@/components/studio/ClientStudioWrapper";
import { Cpu, ShieldCheck, Zap, Sliders, ArrowRight, BookOpen, BarChart3 } from "lucide-react";
import { GithubIcon } from "@/components/icons/GithubIcon";
import { Card } from "@/components/design-system";

export const metadata = constructMetadata({ title: "LLMSlim Studio | Interactive Demonstration", description: "A client-side visual demonstration of context-compression concepts. Use the Python package for the production engine.", canonicalUrl: "https://llmslim.app/playground" });

export default function PlaygroundPage() {
  return <div className="space-y-12 font-sans">
    <div className="space-y-4 max-w-4xl">
      <div className="inline-flex items-center gap-2.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-mono"><Cpu className="w-3.5 h-3.5" /><span>Client-side visual demonstration — not the Python engine</span></div>
      <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">LLMSlim <span className="text-gradient-emerald">Studio Playground</span></h1>
      <p className="text-slate-400 text-base leading-relaxed">Explore the compression interface and concepts. Studio uses a local simulation; it does not execute the Python v0.3.1 engine or provide server-side compression results.</p>
    </div>
    <section id="studio-workspace" aria-label="Interactive Studio Workspace" className="space-y-3"><div className="flex items-center justify-between px-1 font-mono text-xs text-slate-400"><span className="text-emerald-400 font-bold flex items-center gap-2"><Sliders className="w-4 h-4" />3-panel demonstration</span><span className="text-amber-300 hidden sm:inline">Simulated output</span></div><ClientStudioWrapper /></section>
    <section className="space-y-6 pt-4 border-t border-white/10"><h2 className="text-xl font-bold text-white flex items-center gap-2"><Zap className="w-5 h-5 text-emerald-400" />How to use the released engine</h2><div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <Card glowColor="emerald" className="p-6 space-y-3"><ShieldCheck className="w-5 h-5 text-emerald-400" /><h3 className="text-lg font-bold text-white">Use ContextRole</h3><p className="text-slate-400 text-xs leading-relaxed">Use the Python API to label RAG, tool, and assistant context as untrusted. This prevents protected-priority elevation from wording.</p></Card>
      <Card glowColor="cyan" className="p-6 space-y-3"><BookOpen className="w-5 h-5 text-cyan-400" /><h3 className="text-lg font-bold text-white">Read the Python docs</h3><p className="text-slate-400 text-xs leading-relaxed">The released API supports extractive, rewrite, and hybrid strategies, with caller-supplied rewrite providers.</p></Card>
      <Card glowColor="violet" className="p-6 space-y-3"><BarChart3 className="w-5 h-5 text-violet-400" /><h3 className="text-lg font-bold text-white">Verify locally</h3><p className="text-slate-400 text-xs leading-relaxed">Run the repository test and benchmark commands for measurements that match your environment.</p></Card>
    </div></section>
    <section className="p-8 rounded-2xl bg-[#0D121C] border border-white/10"><div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <Link href="/docs/getting-started" className="group p-4 rounded-xl bg-white/5 border border-white/10"><div className="text-xs font-mono text-emerald-400 font-bold flex items-center gap-1">Documentation <ArrowRight className="w-3.5 h-3.5" /></div><p className="text-slate-300 text-xs mt-1">Read the released Python API.</p></Link>
      <Link href="/benchmarks" className="group p-4 rounded-xl bg-white/5 border border-white/10"><div className="text-xs font-mono text-cyan-400 font-bold flex items-center gap-1">Release verification <ArrowRight className="w-3.5 h-3.5" /></div><p className="text-slate-300 text-xs mt-1">See measured gate results.</p></Link>
      <a href="https://github.com/Thanatos9404/llmslim" className="group p-4 rounded-xl bg-white/5 border border-white/10"><div className="text-xs font-mono text-violet-400 font-bold flex items-center gap-1"><GithubIcon className="w-3.5 h-3.5" />Source code</div><p className="text-slate-300 text-xs mt-1">View the open-source repository.</p></a>
    </div></section>
  </div>;
}
