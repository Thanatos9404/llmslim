"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { CheckCircle2 } from "lucide-react";

export interface BenchmarkRow {
  category: string;
  targetRatio: string;
  achievedReduction: string;
  entityRetention: string;
  instructionRetention: string;
  latency: string;
  memoryPeak: string;
}

export function BenchmarkTable({ className }: { className?: string }) {
  const data: BenchmarkRow[] = [
    {
      category: "System Prompts",
      targetRatio: "40.0%",
      achievedReduction: "38.9%",
      entityRetention: "98.4%",
      instructionRetention: "100.0%",
      latency: "28 ms",
      memoryPeak: "12.1 MB",
    },
    {
      category: "Chat Conversations",
      targetRatio: "50.0%",
      achievedReduction: "52.3%",
      entityRetention: "96.1%",
      instructionRetention: "100.0%",
      latency: "45 ms",
      memoryPeak: "14.5 MB",
    },
    {
      category: "RAG Context (5 Docs)",
      targetRatio: "50.0%",
      achievedReduction: "48.7%",
      entityRetention: "94.2%",
      instructionRetention: "100.0%",
      latency: "120 ms",
      memoryPeak: "16.8 MB",
    },
    {
      category: "Technical Documentation",
      targetRatio: "50.0%",
      achievedReduction: "53.2%",
      entityRetention: "91.5%",
      instructionRetention: "100.0%",
      latency: "185 ms",
      memoryPeak: "18.2 MB",
    },
    {
      category: "Long Document (12K tokens)",
      targetRatio: "50.0%",
      achievedReduction: "51.1%",
      entityRetention: "92.0%",
      instructionRetention: "100.0%",
      latency: "340 ms",
      memoryPeak: "22.4 MB",
    },
  ];

  return (
    <div className={cn("rounded-2xl bg-[#0D121C] border border-white/10 overflow-hidden shadow-2xl backdrop-blur-xl border-specular-emerald", className)}>
      <div className="px-6 py-4 bg-[#070A0F] border-b border-white/10 flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="badge-scientific text-emerald-400 text-xs">
            Empirical Quality Matrix
          </span>
          <h3 className="text-lg font-bold text-white tracking-tight mt-0.5">
            Standardized Benchmark Evaluation
          </h3>
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-mono font-tabular bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          Evaluated on Python 3.12 / x86_64
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-white/[0.02] text-slate-400 border-b border-white/10 uppercase tracking-widest text-[10px]">
            <tr>
              <th className="py-3.5 px-6 font-semibold">Corpus Category</th>
              <th className="py-3.5 px-4 font-semibold text-center">Target Ratio</th>
              <th className="py-3.5 px-4 font-semibold text-center">Achieved Red.</th>
              <th className="py-3.5 px-4 font-semibold text-center">Entity Ret.</th>
              <th className="py-3.5 px-4 font-semibold text-center">Instruction Ret.</th>
              <th className="py-3.5 px-4 font-semibold text-center">Latency</th>
              <th className="py-3.5 px-6 font-semibold text-right">Memory Peak</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-slate-300 font-tabular">
            {data.map((row, idx) => (
              <tr
                key={idx}
                className="hover:bg-gradient-to-r hover:from-emerald-500/10 hover:via-white/[0.04] hover:to-transparent transition-all duration-200 group cursor-pointer"
              >
                <td className="py-4 px-6 font-bold text-white group-hover:text-emerald-300 transition-colors">
                  {row.category}
                </td>
                <td className="py-4 px-4 text-center text-slate-400">{row.targetRatio}</td>
                <td className="py-4 px-4 text-center font-bold text-cyan-400">{row.achievedReduction}</td>
                <td className="py-4 px-4 text-center text-slate-300">{row.entityRetention}</td>
                <td className="py-4 px-4 text-center">
                  <span className="inline-flex items-center gap-1 text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                    <CheckCircle2 className="w-3 h-3" />
                    {row.instructionRetention}
                  </span>
                </td>
                <td className="py-4 px-4 text-center text-violet-400 font-bold">{row.latency}</td>
                <td className="py-4 px-6 text-right text-slate-400">{row.memoryPeak}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
