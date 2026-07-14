"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "./Card";

export function Charts({ className }: { className?: string }) {
  const chartData = [
    { label: "System Prompts", original: 100, compressed: 41, saved: 59 },
    { label: "Chat Dialogs", original: 100, compressed: 48, saved: 52 },
    { label: "RAG Contexts", original: 100, compressed: 51, saved: 49 },
    { label: "Tech Docs", original: 100, compressed: 47, saved: 53 },
  ];

  return (
    <div className={cn("grid grid-cols-1 md:grid-cols-2 gap-6", className)}>
      {/* Chart 1: Token Reduction Efficiency */}
      <Card glowColor="emerald" className="p-6 space-y-4 border-specular-emerald">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div>
            <span className="badge-scientific text-emerald-400 text-xs">Telemetry Chart 01</span>
            <h4 className="text-base font-bold text-white">Token Reduction Efficiency (%)</h4>
          </div>
          <span className="text-xs font-mono text-emerald-400 font-bold bg-emerald-500/10 px-2.5 py-1 rounded border border-emerald-500/20 font-tabular">
            Avg -52.4% Tokens
          </span>
        </div>

        <div className="space-y-4 pt-2">
          {chartData.map((item, idx) => (
            <div key={idx} className="space-y-1.5 font-mono text-xs">
              <div className="flex justify-between text-slate-300">
                <span>{item.label}</span>
                <span className="text-emerald-400 font-bold font-tabular">{item.saved}% Saved</span>
              </div>
              <div className="h-3 rounded-full bg-white/5 overflow-hidden flex p-0.5 border border-white/10 relative">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${item.saved}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: idx * 0.15 }}
                  className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-cyan-400 to-emerald-400 shadow-[0_0_15px_rgba(0,245,155,0.4)] relative flex items-center justify-end"
                >
                  {/* Leading Specular Highlight Tip Node (#19) */}
                  <span className="w-2 h-full rounded-r-full bg-white shadow-[0_0_10px_#ffffff] shrink-0" />
                </motion.div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Chart 2: Processing Latency Specs */}
      <Card glowColor="violet" className="p-6 space-y-4 border-specular-violet">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div>
            <span className="badge-scientific text-violet-400 text-xs">Telemetry Chart 02</span>
            <h4 className="text-base font-bold text-white">Processing Latency Overhead (ms)</h4>
          </div>
          <span className="text-xs font-mono text-violet-400 font-bold bg-violet-500/10 px-2.5 py-1 rounded border border-violet-500/20 font-tabular">
            Sub-50ms Average
          </span>
        </div>

        <div className="space-y-4 pt-2 font-mono text-xs">
          {[
            { corpus: "Small Prompt (<1K)", ms: 28, max: 400 },
            { corpus: "Medium Dialog (3K)", ms: 45, max: 400 },
            { corpus: "RAG Context (5K)", ms: 120, max: 400 },
            { corpus: "Long Doc (12K)", ms: 340, max: 400 },
          ].map((item, idx) => (
            <div key={idx} className="space-y-1.5">
              <div className="flex justify-between text-slate-300">
                <span>{item.corpus}</span>
                <span className="text-violet-400 font-bold font-tabular">{item.ms} ms</span>
              </div>
              <div className="h-3 rounded-full bg-white/5 overflow-hidden flex p-0.5 border border-white/10 relative">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${(item.ms / item.max) * 100}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: idx * 0.15 }}
                  className="h-full rounded-full bg-gradient-to-r from-violet-500 to-pink-500 shadow-[0_0_15px_rgba(168,85,247,0.4)] relative flex items-center justify-end"
                >
                  {/* Leading Specular Highlight Tip Node (#19) */}
                  <span className="w-2 h-full rounded-r-full bg-white shadow-[0_0_10px_#ffffff] shrink-0" />
                </motion.div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
