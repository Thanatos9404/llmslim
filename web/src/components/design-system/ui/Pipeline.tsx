"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Scissors, Layers, Signal, ShieldCheck, PieChart, CheckCircle, ArrowRight } from "lucide-react";

export interface PipelineStep {
  step: number;
  title: string;
  subtitle: string;
  tech: string;
  icon: React.ReactNode;
  accent: string;
}

export function Pipeline({ className }: { className?: string }) {
  const steps: PipelineStep[] = [
    {
      step: 1,
      title: "Protected Sentence Split",
      subtitle: "Splits text at sentence boundaries while keeping code blocks & markdown titles intact.",
      tech: "Regex & placeholder substitution preserving code fences & URLs",
      icon: <Scissors className="w-5 h-5" />,
      accent: "text-cyan-400 border-cyan-500/30 bg-cyan-500/10",
    },
    {
      step: 2,
      title: "Semantic Topic Chunking",
      subtitle: "Groups sentences into semantic topic chunks using cosine similarity thresholding.",
      tech: "similarity_threshold (0.10 TF-IDF / 0.35 Transformers) & max_chunk_tokens=300",
      icon: <Layers className="w-5 h-5" />,
      accent: "text-violet-400 border-violet-500/30 bg-violet-500/10",
    },
    {
      step: 3,
      title: "Multi-Signal Scoring",
      subtitle: "Scores sentences combining degree centrality, entity density, and position bias.",
      tech: "LexRank centrality + position bias + entity patterns + query similarity",
      icon: <Signal className="w-5 h-5" />,
      accent: "text-pink-400 border-pink-500/30 bg-pink-500/10",
    },
    {
      step: 4,
      title: "Priority Tier Classification",
      subtitle: "Classifies sentences into Priority 4 (Critical/Safety), Priority 3, Priority 2, Priority 1.",
      tech: "Rule-based regex heuristics guaranteeing 100.0% high-value sentence retention",
      icon: <ShieldCheck className="w-5 h-5" />,
      accent: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    },
    {
      step: 5,
      title: "Two-Pass Budget Allocation",
      subtitle: "Pass 1 selects sentences locally per chunk; Pass 2 rebalances tokens globally.",
      tech: "Two-pass priority-aware selection algorithm hitting exact target ratio",
      icon: <PieChart className="w-5 h-5" />,
      accent: "text-cyan-400 border-cyan-500/30 bg-cyan-500/10",
    },
    {
      step: 6,
      title: "Ordered Reassembly",
      subtitle: "Re-joins selected sentences in original document order, maintaining structure.",
      tech: "Natural text flow reassembly with optimal context window utilization",
      icon: <CheckCircle className="w-5 h-5" />,
      accent: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    },
  ];

  const [activeStep, setActiveStep] = useState(1);

  return (
    <div className={cn("space-y-8 p-6 sm:p-8 rounded-2xl bg-[#0D121C] border border-white/10 backdrop-blur-xl border-specular-emerald", className)}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="badge-scientific text-emerald-400 text-xs">
            Internal Pipeline Architecture
          </span>
          <h2 className="text-2xl font-bold text-white tracking-tight mt-1">
            The 6-Step Compression Engine
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-mono text-slate-400">Deterministic & Reproducible Execution</span>
        </div>
      </div>

      {/* Interactive Step Timeline Cards with Flow Connectors (Phase E) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 relative">
        {steps.map((s, idx) => (
          <motion.div
            key={s.step}
            onClick={() => setActiveStep(s.step)}
            whileHover={{ scale: 1.02, y: -2 }}
            className={cn(
              "p-5 rounded-xl border transition-all cursor-pointer relative overflow-hidden flex flex-col justify-between group",
              activeStep === s.step
                ? "bg-white/[0.08] border-emerald-500/40 shadow-[0_0_25px_rgba(0,245,155,0.15)]"
                : "bg-white/[0.03] border-white/10 hover:border-white/20"
            )}
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className={cn("p-2 rounded-lg border transition-transform group-hover:scale-110", s.accent)}>
                  {s.icon}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-mono text-slate-500 font-bold">STEP 0{s.step}</span>
                  {idx < steps.length - 1 && (
                    <ArrowRight className="w-3.5 h-3.5 text-slate-600 hidden lg:inline" />
                  )}
                </div>
              </div>
              <h4 className="text-base font-bold text-white mb-1.5 group-hover:text-emerald-300 transition-colors">
                {s.title}
              </h4>
              <p className="text-xs text-slate-400 leading-relaxed">{s.subtitle}</p>
            </div>

            <div className="mt-4 pt-3 border-t border-white/5 text-[11px] font-mono text-slate-500 flex items-center justify-between font-tabular">
              <span>{s.tech.split(" ")[0]} engine</span>
              <span className="text-emerald-400 font-bold">{activeStep === s.step ? "Active" : "Inspect"}</span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
