"use client";

import React from "react";
import { FeatureCard } from "@/components/design-system";
import { ShieldCheck, Sparkles, Search, DollarSign, Plug, MessageSquare } from "lucide-react";

export function FeatureGridSection() {
  return <section id="features" className="py-20 sm:py-28 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
    <div className="text-center space-y-4 max-w-3xl mx-auto"><span className="badge-scientific text-emerald-400 text-xs">v0.3.1 Python release</span><h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">Compression with <span className="text-gradient-emerald">clear trust boundaries</span></h2><p className="text-slate-400 text-base leading-relaxed">LLMSlim ranks sentences locally and makes provenance explicit where protected priority matters.</p></div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <FeatureCard title="Provenance-aware priority" subtitle="RAG, tool, and assistant content cannot become Tier 4 or must_keep merely from imperative wording. This mitigates compression-induced instruction elevation; it is not complete prompt-injection prevention." badge="v0.3.1 security" glowColor="emerald" icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />} />
      <FeatureCard title="Extractive, rewrite, and hybrid" subtitle="Use local extractive selection by default, or provide your own LLM provider for validated rewrite and hybrid flows." badge="Python API" glowColor="cyan" icon={<Sparkles className="w-5 h-5 text-cyan-400" />} />
      <FeatureCard title="Role-aware RAG" subtitle="compress_documents defaults to RAG provenance so retrieved imperative text does not consume the protected budget." badge="Pipeline default" glowColor="violet" icon={<Search className="w-5 h-5 text-violet-400" />} />
      <FeatureCard title="Measured verification" subtitle="v0.3.1 was verified with 432 passing tests, 92.57% branch coverage, Ruff, and an actual pytest benchmark collector." badge="Release gate" glowColor="emerald" icon={<DollarSign className="w-5 h-5 text-emerald-400" />} />
      <FeatureCard title="Provider flexibility" subtitle="Bring a BaseRewriteProvider or CallableProvider when using rewrite or hybrid strategies. The core package does not ship a provider SDK." badge="Caller supplied" glowColor="cyan" icon={<Plug className="w-5 h-5 text-cyan-400" />} />
      <FeatureCard title="Chat and token telemetry" subtitle="Chat roles retain distinct provenance and every result reports whether tiktoken or the heuristic token counter was active." badge="Operational clarity" glowColor="violet" icon={<MessageSquare className="w-5 h-5 text-violet-400" />} />
    </div>
  </section>;
}
