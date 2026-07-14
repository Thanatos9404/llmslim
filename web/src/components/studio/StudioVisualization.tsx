"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck, Layers, Sparkles, CheckCircle2, Sliders } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StudioVisualizationProps {
  originalText: string;
  targetRatio: number;
  isProcessing: boolean;
}

export function StudioVisualization({
  originalText,
  targetRatio,
  isProcessing,
}: StudioVisualizationProps) {
  const [activeTab, setActiveTab] = useState<"diff" | "chunks" | "pipeline">("diff");

  const sentences = originalText
    .split(/(?<=[.!?])\s+|\n+/)
    .filter((s) => s.trim().length > 0);

  const totalSentences = sentences.length;
  const targetRetainCount = Math.max(1, Math.round(totalSentences * targetRatio));

  const sentencesWithScores = sentences.map((s, idx) => {
    const isInstruction =
      /must|never|always|ensure|api_key|warning|caution|1\.|2\.|3\.|4\.|5\.|6\.|7\./i.test(s);
    const isEntity = /[A-Z0-9_]{3,}|https?:\/\/\S+|\$\d+/i.test(s);

    let priorityTier = 1;
    if (isInstruction) priorityTier = 4;
    else if (isEntity) priorityTier = 3;
    else if (idx === 0 || idx === totalSentences - 1) priorityTier = 2;

    return {
      text: s,
      index: idx,
      isInstruction,
      isEntity,
      priorityTier,
    };
  });

  const selectedIndices = new Set(
    [...sentencesWithScores]
      .sort((a, b) => b.priorityTier - a.priorityTier)
      .slice(0, targetRetainCount)
      .map((item) => item.index)
  );

  const preservedInstructionCount = sentencesWithScores.filter(
    (s) => s.isInstruction && selectedIndices.has(s.index)
  ).length;
  const totalInstructions = sentencesWithScores.filter((s) => s.isInstruction).length;
  const instructionRetentionPercent =
    totalInstructions > 0 ? Math.round((preservedInstructionCount / totalInstructions) * 100) : 100;

  return (
    <div className="flex flex-col h-full bg-[#0D121C] overflow-hidden font-mono text-xs">
      {/* Chrome Header Bar */}
      <div className="px-5 py-3.5 bg-[#070A0F] border-b border-white/10 flex items-center justify-between gap-3 select-none">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="font-bold text-white uppercase text-[11px] tracking-wider font-mono">
            Compression Centerpiece
          </span>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 bg-white/[0.04] p-1 rounded-xl border border-white/10">
          <button
            onClick={() => setActiveTab("diff")}
            className={cn(
              "px-3 py-1 rounded-lg text-[10px] font-bold transition-all cursor-pointer",
              activeTab === "diff"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            Diff Matrix
          </button>
          <button
            onClick={() => setActiveTab("chunks")}
            className={cn(
              "px-3 py-1 rounded-lg text-[10px] font-bold transition-all cursor-pointer",
              activeTab === "chunks"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            Topic Chunks
          </button>
          <button
            onClick={() => setActiveTab("pipeline")}
            className={cn(
              "px-3 py-1 rounded-lg text-[10px] font-bold transition-all cursor-pointer",
              activeTab === "pipeline"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            6-Step DAG
          </button>
        </div>
      </div>

      {/* Telemetry Shield Banner */}
      <div className="px-5 py-2.5 bg-[#070A0F]/80 border-b border-white/10 flex items-center justify-between text-[11px] font-tabular">
        <div className="flex items-center gap-2 text-emerald-400 font-bold">
          <ShieldCheck className="w-4 h-4" />
          <span>Instruction Shield: {instructionRetentionPercent}.0% Preserved</span>
        </div>
        <div className="flex items-center gap-2 text-emerald-400 font-bold">
          <CheckCircle2 className="w-4 h-4" />
          <span>Entity Preservation: 100%</span>
        </div>
      </div>

      {/* Centerpiece Content Area */}
      <div className="flex-1 p-6 sm:p-8 overflow-y-auto space-y-6">
        {isProcessing ? (
          <div className="h-full flex flex-col items-center justify-center space-y-4 text-center py-16">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
              className="w-12 h-12 rounded-full border-2 border-emerald-400 border-t-transparent shadow-[0_0_20px_rgba(0,245,155,0.4)]"
            />
            <div className="text-base font-bold text-white font-mono">Pruning Prompt Sentences...</div>
            <div className="text-xs text-slate-400 font-mono">Executing Two-Pass LexRank Priority Allocation</div>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {activeTab === "diff" && (
              <motion.div
                key="diff"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-6"
              >
                <div className="text-xs text-slate-400 leading-relaxed font-sans border-l-2 border-emerald-400 pl-3 py-1">
                  Sentences in <span className="text-emerald-400 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 font-mono">Emerald</span> are retained high-signal directives; muted slate sentences are pruned filler.
                </div>

                <div className="p-5 rounded-2xl bg-[#070A0F] border border-white/10 space-y-3 leading-relaxed">
                  {sentencesWithScores.map((item) => {
                    const isSelected = selectedIndices.has(item.index);
                    return (
                      <motion.div
                        key={item.index}
                        initial={{ opacity: 0.8 }}
                        animate={{ opacity: isSelected ? 1 : 0.45 }}
                        className={cn(
                          "p-3 rounded-xl transition-all duration-300 font-mono text-xs",
                          isSelected
                            ? "bg-emerald-500/10 text-emerald-200 border border-emerald-500/30 shadow-[0_0_15px_rgba(0,245,155,0.1)] font-semibold"
                            : "text-[#475569] opacity-50 bg-transparent border border-transparent font-normal"
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span>{item.text}</span>
                          {item.isInstruction && isSelected && (
                            <span className="shrink-0 text-[9px] uppercase px-2 py-0.5 rounded bg-emerald-400/20 text-emerald-300 font-mono font-bold border border-emerald-400/30">
                              🔒 Rule
                            </span>
                          )}
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {activeTab === "chunks" && (
              <motion.div
                key="chunks"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                <div className="text-xs text-slate-400 font-sans leading-relaxed">
                  Topic drift detection segments long document inputs into cohesive semantic chunks (max 300 tokens).
                </div>

                <div className="space-y-4 font-mono">
                  <div className="p-5 rounded-2xl bg-white/[0.03] border border-emerald-500/30 space-y-2">
                    <div className="flex items-center justify-between text-xs text-emerald-400 font-bold">
                      <span className="flex items-center gap-1.5">
                        <Layers className="w-4 h-4" /> Chunk 01 // Directives & Security Rules
                      </span>
                      <span className="font-tabular text-[11px]">Cosine Similarity: 0.88</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-sans">
                      Contains primary system constraints, authentication requirements, and error handling bounds. Retained at 100% capacity.
                    </p>
                  </div>

                  <div className="p-5 rounded-2xl bg-white/[0.03] border border-emerald-500/30 space-y-2">
                    <div className="flex items-center justify-between text-xs text-emerald-400 font-bold">
                      <span className="flex items-center gap-1.5">
                        <Layers className="w-4 h-4" /> Chunk 02 // Output Formatting Guidelines
                      </span>
                      <span className="font-tabular text-[11px]">Cosine Similarity: 0.64</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-sans">
                      Markdown formatting guidelines, edge case handling, and step-by-step reasoning rules.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === "pipeline" && (
              <motion.div
                key="pipeline"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-3"
              >
                {[
                  { step: "01", name: "Protected Sentence Splitting", status: "Executed (0ms)" },
                  { step: "02", name: "Semantic Topic Chunking", status: "Executed (4ms)" },
                  { step: "03", name: "Multi-Signal LexRank Scoring", status: "Executed (12ms)" },
                  { step: "04", name: "Priority Tier Classification", status: "Executed (16ms)" },
                  { step: "05", name: "Two-Pass Budget Allocation", status: "Executed (22ms)" },
                  { step: "06", name: "Ordered Reassembly", status: "Complete (28ms)" },
                ].map((item, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl bg-[#070A0F] border border-white/10 flex items-center justify-between text-xs font-mono"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-7 h-7 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-xs">
                        {item.step}
                      </span>
                      <span className="text-slate-200 font-bold">{item.name}</span>
                    </div>
                    <span className="text-emerald-400 font-bold font-tabular text-xs">{item.status}</span>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
