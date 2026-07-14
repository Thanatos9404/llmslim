"use client";

import React from "react";
import { Card } from "@/components/design-system";
import { Cpu, ShieldCheck, Zap, Layers, GitMerge } from "lucide-react";

export function ArchitectureSection() {
  return (
    <section className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-violet-400">
          Core Scoring Mechanics
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Multi-Signal <span className="text-gradient-violet">Ranking Engine</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          Every sentence is evaluated against 5 weighted signals before two-pass budget rebalancing across semantic topic chunks.
        </p>
      </div>

      <Card glowColor="violet" className="p-8 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="p-5 rounded-xl bg-white/[0.03] border border-white/10 space-y-3 font-mono">
            <div className="text-xs text-violet-400 uppercase font-bold flex items-center gap-2">
              <Zap className="w-4 h-4" />
              1. Centrality (0.20)
            </div>
            <div className="text-sm font-bold text-white">LexRank Degree Graph</div>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Calculates eigenvector centrality across sentence similarity graphs to isolate core document topics.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-white/[0.03] border border-white/10 space-y-3 font-mono">
            <div className="text-xs text-cyan-400 uppercase font-bold flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" />
              2. Entity Density (0.40)
            </div>
            <div className="text-sm font-bold text-white">Named Entity Protection</div>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Detects proper nouns, dates, URLs, acronyms, and numeric parameters to prevent factual hallucinations.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-white/[0.03] border border-white/10 space-y-3 font-mono">
            <div className="text-xs text-emerald-400 uppercase font-bold flex items-center gap-2">
              <Cpu className="w-4 h-4" />
              3. Instruction Shield (0.40)
            </div>
            <div className="text-sm font-bold text-white">Imperative Directive Lock</div>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Heuristic regex engine classifying directives (&quot;must&quot;, &quot;never&quot;, code blocks) as Priority 4 Critical.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-white/[0.03] border border-white/10 space-y-3 font-mono">
            <div className="text-xs text-pink-400 uppercase font-bold flex items-center gap-2">
              <GitMerge className="w-4 h-4" />
              4. 2-Pass Budget Allocation
            </div>
            <div className="text-sm font-bold text-white">Global Token Rebalance</div>
            <p className="text-xs text-slate-400 leading-relaxed font-sans">
              Pass 1 selects locally per chunk; Pass 2 rebalances global margin to hit exact target retention ratios.
            </p>
          </div>
        </div>
      </Card>
    </section>
  );
}
