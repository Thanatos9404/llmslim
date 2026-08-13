"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Terminal, Copy, Check, ShieldCheck, ArrowRight } from "lucide-react";
import { AnimatedButton } from "@/components/design-system";

export function HeroSection() {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText("pip install llmslim");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <section id="hero" aria-label="Hero Section" className="relative pt-32 sm:pt-40 pb-16 sm:pb-20 px-4 sm:px-8 max-w-7xl mx-auto flex flex-col items-center text-center space-y-12 sm:space-y-14">
      <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>LLMSlim v0.3.1</span>
        <span className="text-slate-500 hidden sm:inline">|</span>
        <span className="text-slate-300 font-semibold hidden sm:flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />Provenance-aware priority handling</span>
      </div>
      <div className="space-y-6 max-w-4xl">
        <h1 className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white leading-[1.04]"><span className="text-gradient-silver">Compress LLM context with</span> <span className="text-gradient-emerald">trust-aware priorities.</span></h1>
        <p className="text-base sm:text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">Python context compression for extractive, rewrite, and hybrid workflows. Untrusted RAG, tool, and assistant text cannot gain protected priority solely from imperative wording.</p>
      </div>
      <div className="flex flex-col sm:flex-row items-center gap-4 w-full justify-center">
        <div className="flex items-center justify-between gap-3 px-4 py-3 rounded-2xl bg-[#0D121C] border border-white/15 font-mono text-xs text-slate-200 w-full sm:w-auto"><div className="flex items-center gap-2"><Terminal className="w-4 h-4 text-emerald-400" /><span className="text-slate-400">$</span><span className="font-bold text-white">pip install llmslim</span></div><button onClick={copy} aria-label="Copy install command" className="ml-2 p-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-400 hover:text-white"><>{copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}</></button></div>
        <Link href="/playground"><AnimatedButton variant="quantum" size="lg" aria-label="Open interactive LLMSlim Studio playground" icon={<ArrowRight className="w-4 h-4" />} iconPosition="right">Explore the Playground</AnimatedButton></Link>
      </div>
    </section>
  );
}
