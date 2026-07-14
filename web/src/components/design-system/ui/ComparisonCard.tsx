"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "./Card";
import { Scissors, CheckCircle2, DollarSign, Zap } from "lucide-react";

export interface ComparisonCardProps {
  originalText?: string;
  compressedText?: string;
  originalTokens?: number;
  compressedTokens?: number;
  className?: string;
}

const DEFAULT_ORIGINAL = `You are an AI assistant that helps users with their coding questions. You should be helpful, harmless, and honest. When answering questions, you should provide detailed explanations with code examples where appropriate. Make sure to consider edge cases and provide best practices. If you're not sure about something, say so rather than making things up. Please format your responses using markdown for better readability. Include relevant links to documentation when possible. Always test your code before sharing it. Remember to handle errors gracefully and explain your reasoning step by step...`;

const DEFAULT_COMPRESSED = `You are an AI assistant for coding questions. Be helpful, harmless, honest. Provide detailed explanations with code examples. Consider edge cases and best practices. If unsure, say so. Format responses in markdown. Include documentation links. Always test code before sharing. Handle errors gracefully, explain reasoning step by step.`;

export function ComparisonCard({
  originalText = DEFAULT_ORIGINAL,
  compressedText = DEFAULT_COMPRESSED,
  originalTokens = 2847,
  compressedTokens = 1138,
  className,
}: ComparisonCardProps) {
  const [ratio, setRatio] = useState(0.4);

  const currentCompressedTokens = Math.round(originalTokens * ratio);
  const savedTokens = originalTokens - currentCompressedTokens;
  const reductionPercent = Math.round((1 - ratio) * 100);
  const estimatedSavingsUSD = (savedTokens * 0.0000025 * 50000 * 365).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

  return (
    <Card glowColor="emerald" className={cn("p-6 sm:p-8 space-y-6", className)}>
      {/* Top Controls Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Scissors className="w-4 h-4" />
            </span>
            <h3 className="text-lg font-bold text-white">Semantic Prompt Compressor Reactor</h3>
          </div>
          <p className="text-xs text-slate-400">
            Drag the ratio slider to simulate real-time sentence pruning & token reduction
          </p>
        </div>

        {/* Retain Target Ratio Slider */}
        <div className="flex items-center gap-3 bg-white/[0.04] p-3 rounded-xl border border-white/10">
          <span className="text-xs font-mono text-slate-400">Target Retain:</span>
          <input
            type="range"
            min="0.2"
            max="0.8"
            step="0.05"
            value={ratio}
            onChange={(e) => setRatio(parseFloat(e.target.value))}
            className="w-28 sm:w-36 accent-emerald-400 cursor-pointer"
          />
          <span className="text-xs font-mono font-bold text-emerald-400 min-w-[36px]">
            {Math.round(ratio * 100)}%
          </span>
        </div>
      </div>

      {/* Side-by-Side Comparison Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Before Box */}
        <div className="rounded-xl bg-[#070A0F] border border-white/10 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-slate-400 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              Before Compression
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
              {originalTokens.toLocaleString()} tokens
            </span>
          </div>

          <p className="text-xs text-slate-400 font-mono leading-relaxed select-none opacity-80 line-clamp-6">
            {originalText}
          </p>

          <div className="pt-2 text-[11px] font-mono text-slate-500 flex items-center gap-2">
            <span>🔴 40-60% Redundant Filler</span>
          </div>
        </div>

        {/* After Box */}
        <div className="rounded-xl bg-[#070A0F] border border-emerald-500/30 p-5 space-y-3 relative overflow-hidden shadow-[0_0_30px_rgba(0,245,155,0.08)]">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase text-emerald-400 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              After LLMSlim ({reductionPercent}% Reduced)
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
              {currentCompressedTokens.toLocaleString()} tokens
            </span>
          </div>

          <AnimatePresence mode="wait">
            <motion.p
              key={ratio}
              initial={{ opacity: 0.6 }}
              animate={{ opacity: 1 }}
              className="text-xs font-mono text-emerald-100/90 leading-relaxed line-clamp-6"
            >
              {compressedText}
            </motion.p>
          </AnimatePresence>

          <div className="pt-2 text-[11px] font-mono text-emerald-400/90 flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>100.0% Instruction Fidelity Preserved</span>
          </div>
        </div>
      </div>

      {/* Telemetry Footer */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-white/10 text-center font-mono">
        <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
          <div className="text-[10px] uppercase text-slate-500">Tokens Saved</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">{savedTokens.toLocaleString()}</div>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
          <div className="text-[10px] uppercase text-slate-500">Reduction %</div>
          <div className="text-lg font-bold text-cyan-400 mt-0.5">{reductionPercent}%</div>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
          <div className="text-[10px] uppercase text-slate-500">Annual Savings @ 50K/day</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">{estimatedSavingsUSD}</div>
        </div>
        <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5">
          <div className="text-[10px] uppercase text-slate-500">Processing Latency</div>
          <div className="text-lg font-bold text-violet-400 mt-0.5">28 ms</div>
        </div>
      </div>
    </Card>
  );
}
