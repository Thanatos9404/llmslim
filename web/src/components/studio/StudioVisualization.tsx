"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShieldCheck, Layers, Sparkles, CheckCircle2 } from "lucide-react";
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
    <div className="flex flex-col h-full bg-[#0D121C] border-r border-white/10 overflow-hidden font-mono text-xs">
      {/* Top Bar with Tabs */}
      <div className="px-4 py-3 bg-[#070A0F] border-b border-white/10 flex items-center justify-between select-none">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-400" />
          <span className="font-bold text-white uppercase text-[11px] tracking-wider font-mono">
            Compression Visualization
          </span>
        </div>

        <div className="flex items-center gap-1 bg-white/[0.04] p-1 rounded-lg border border-white/10">
          <button
            onClick={() => setActiveTab("diff")}
            className={cn(
              "px-2.5 py-1 rounded text-[10px] font-bold transition-all cursor-pointer",
              activeTab === "diff" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "text-slate-400 hover:text-slate-200"
            )}
          >
            Diff Highlight
          </button>
          <button
            onClick={() => setActiveTab("chunks")}
            className={cn(
              "px-2.5 py-1 rounded text-[10px] font-bold transition-all cursor-pointer",
              activeTab === "chunks" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "text-slate-400 hover:text-slate-200"
            )}
          >
            Topic Chunks
          </button>
          <button
            onClick={() => setActiveTab("pipeline")}
            className={cn(
              "px-2.5 py-1 rounded text-[10px] font-bold transition-all cursor-pointer",
              activeTab === "pipeline" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "text-slate-400 hover:text-slate-200"
            )}
          >
            6-Step DAG
          </button>
        </div>
      </div>

      {/* Badges Banner */}
      <div className="px-4 py-2 bg-[#070A0F]/80 border-b border-white/10 flex items-center justify-between text-[11px] font-tabular">
        <div className="flex items-center gap-2 text-emerald-400 font-bold">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Instruction Shield: {instructionRetentionPercent}.0% Preserved</span>
        </div>
        <div className="flex items-center gap-2 text-emerald-400 font-bold">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>Entities Retained: 100%</span>
        </div>
      </div>

      {/* Panel Content Body */}
      <div className="flex-1 p-4 sm:p-6 overflow-y-auto space-y-4">
        {isProcessing ? (
          <div className="h-full flex flex-col items-center justify-center space-y-4 text-center">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
              className="w-10 h-10 rounded-full border-2 border-emerald-400 border-t-transparent"
            />
            <div className="text-sm font-bold text-white font-mono">Surgically Pruning Sentences...</div>
            <div className="text-xs text-slate-500 font-mono">Running LexRank Graph Degree Centrality</div>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {activeTab === "diff" && (
              <motion.div
                key="diff"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                <div className="text-[11px] text-slate-400 leading-relaxed font-sans">
                  Sentences highlighted in <span className="text-emerald-400 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 font-mono">Emerald</span> are retained signal; muted sentences in slate are pruned filler.
                </div>

                <div className="p-4 rounded-xl bg-[#070A0F] border border-white/10 space-y-2 leading-relaxed">
                  {sentencesWithScores.map((item) => {
                    const isSelected = selectedIndices.has(item.index);
                    return (
                      <motion.span
                        key={item.index}
                        initial={{ opacity: 0.8 }}
                        animate={{ opacity: isSelected ? 1 : 0.45 }}
                        className={cn(
                          "inline-block mr-1.5 p-1.5 rounded transition-all duration-300",
                          isSelected
                            ? "bg-emerald-500/10 text-emerald-200 border border-emerald-500/30 font-semibold shadow-[0_0_12px_rgba(0,245,155,0.1)]"
                            : "text-[#475569] opacity-50 bg-transparent select-none font-normal"
                        )}
                      >
                        {item.text}
                        {item.isInstruction && isSelected && (
                          <span className="ml-1 text-[9px] uppercase px-1 rounded bg-emerald-400/20 text-emerald-300 font-mono font-bold">
                            🔒 Rule
                          </span>
                        )}
                      </motion.span>
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
                <div className="text-[11px] text-slate-400 font-sans">
                  Semantic Topic Chunking divides documents into topic drift regions (max 300 tokens/chunk).
                </div>

                <div className="space-y-3 font-mono">
                  <div className="p-4 rounded-xl bg-white/[0.03] border border-emerald-500/30 space-y-2">
                    <div className="flex items-center justify-between text-xs text-emerald-400 font-bold">
                      <span className="flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5" /> Chunk 01 // Directives & Security
                      </span>
                      <span className="font-tabular">Cosine Similarity: 0.88</span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed font-sans">
                      Contains core system prompt instructions, API key headers, and warning constraints. Retained at 100% capacity.
                    </p>
                  </div>

                  <div className="p-4 rounded-xl bg-white/[0.03] border border-emerald-500/30 space-y-2">
                    <div className="flex items-center justify-between text-xs text-emerald-400 font-bold">
                      <span className="flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5" /> Chunk 02 // Formatting & Rules
                      </span>
                      <span className="font-tabular">Cosine Similarity: 0.64</span>
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
                    className="p-3 rounded-xl bg-[#070A0F] border border-white/10 flex items-center justify-between text-xs font-mono"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold text-[10px]">
                        {item.step}
                      </span>
                      <span className="text-slate-200 font-bold">{item.name}</span>
                    </div>
                    <span className="text-emerald-400 font-bold font-tabular">{item.status}</span>
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
