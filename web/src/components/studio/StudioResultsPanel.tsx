"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { StudioModel } from "./StudioHeader";
import { CodeWindow } from "@/components/design-system";
import { DollarSign, Copy, Check, BarChart3, Code, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StudioResultsPanelProps {
  originalTokens: number;
  targetRatio: number;
  selectedModel: StudioModel;
  mode: "prompt" | "chat" | "rag";
}

export function StudioResultsPanel({
  originalTokens,
  targetRatio,
  selectedModel,
  mode,
}: StudioResultsPanelProps) {
  const [activeTab, setActiveTab] = useState<"stats" | "code" | "cli">("stats");
  const [copiedCli, setCopiedCli] = useState(false);

  const compressedTokens = Math.max(10, Math.round(originalTokens * targetRatio));
  const savedTokens = originalTokens - compressedTokens;
  const reductionPercent = Math.round((1 - targetRatio) * 100);

  // Financial calculations
  const dailyRequests = 50000;
  const dailySavingsUSD = (savedTokens * dailyRequests * (selectedModel.pricePerM / 1000000));
  const annualSavingsUSD = dailySavingsUSD * 365;

  const generatedPythonCode = `from llmslim import ${
    mode === "chat" ? "compress_chat_messages" : mode === "rag" ? "compress_documents" : "compress"
  }

# Model: ${selectedModel.name} | Target Ratio: ${targetRatio} (${reductionPercent}% reduction)
${
  mode === "chat"
    ? `compressed_messages = compress_chat_messages(conversation, target_ratio=${targetRatio})`
    : mode === "rag"
    ? `compressed_docs = compress_documents(retrieved_chunks, query="FastAPI auth", target_ratio=${targetRatio})`
    : `result = compress(prompt_text, target_ratio=${targetRatio})

print("Tokens Saved:", result.tokens_saved)    # → ${savedTokens.toLocaleString()} tokens
print("Reduction %:", result.reduction_percent)  # → ${reductionPercent}%
print(result.compressed_text)`
}`;

  const generatedCliCommand = `llmslim input_prompt.txt -r ${targetRatio} --cost ${selectedModel.id} --requests-per-day 50000`;

  const handleCopyCli = () => {
    navigator.clipboard.writeText(generatedCliCommand);
    setCopiedCli(true);
    setTimeout(() => setCopiedCli(false), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-[#070A0F] font-mono text-xs overflow-hidden">
      {/* Top Chrome Bar */}
      <div className="px-5 py-3.5 bg-[#0D121C] border-b border-white/10 flex items-center justify-between gap-2 select-none">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setActiveTab("stats")}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5",
              activeTab === "stats"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-white"
            )}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Telemetry</span>
          </button>
          <button
            onClick={() => setActiveTab("code")}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5",
              activeTab === "code"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-white"
            )}
          >
            <Code className="w-3.5 h-3.5" />
            <span>Python SDK</span>
          </button>
          <button
            onClick={() => setActiveTab("cli")}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5",
              activeTab === "cli"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "text-slate-400 hover:text-white"
            )}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>CLI</span>
          </button>
        </div>
      </div>

      {/* Structured Results Body */}
      <div className="flex-1 p-5 sm:p-6 overflow-y-auto space-y-6">
        {activeTab === "stats" && (
          <div className="space-y-6">
            {/* Section 1: Compression Metrics */}
            <div className="space-y-2">
              <div className="text-[10px] uppercase text-slate-500 font-mono tracking-wider font-bold">
                1. Token Compression Metrics
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3.5 rounded-xl bg-[#0D121C] border border-white/10">
                  <div className="text-[10px] text-slate-500 uppercase font-mono">Original Tokens</div>
                  <div className="text-xl font-bold text-white mt-1 font-tabular">{originalTokens.toLocaleString()}</div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#0D121C] border border-emerald-500/30">
                  <div className="text-[10px] text-emerald-400 uppercase font-mono">Compressed Tokens</div>
                  <div className="text-xl font-bold text-emerald-400 mt-1 font-tabular">{compressedTokens.toLocaleString()}</div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#0D121C] border border-emerald-500/30">
                  <div className="text-[10px] text-emerald-400 uppercase font-mono">Tokens Saved</div>
                  <div className="text-xl font-bold text-emerald-400 mt-1 font-tabular">{savedTokens.toLocaleString()}</div>
                </div>

                <div className="p-3.5 rounded-xl bg-[#0D121C] border border-emerald-500/30">
                  <div className="text-[10px] text-emerald-400 uppercase font-mono">Reduction %</div>
                  <div className="text-xl font-bold text-emerald-400 mt-1 font-tabular">{reductionPercent}%</div>
                </div>
              </div>
            </div>

            {/* Section 2: Financial ROI Savings */}
            <div className="space-y-2">
              <div className="text-[10px] uppercase text-slate-500 font-mono tracking-wider font-bold">
                2. Projected Financial Savings (50k reqs/day)
              </div>

              <div className="p-5 rounded-2xl bg-gradient-to-br from-[#0D121C] to-[#141B29] border border-emerald-500/30 space-y-3 shadow-[0_0_30px_rgba(0,245,155,0.08)]">
                <div className="flex items-center justify-between text-xs text-emerald-400 font-bold border-b border-white/10 pb-2">
                  <span className="flex items-center gap-1.5 font-mono">
                    <DollarSign className="w-4 h-4 text-emerald-400" /> API Invoice ROI
                  </span>
                  <span className="text-slate-400 text-[10px] font-mono font-tabular">{selectedModel.name}</span>
                </div>

                <div className="space-y-2 pt-1 font-mono">
                  <div className="flex justify-between text-xs text-slate-300 font-tabular">
                    <span>Daily Savings:</span>
                    <span className="font-bold text-emerald-400">${dailySavingsUSD.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-300 font-tabular">
                    <span>Monthly Savings:</span>
                    <span className="font-bold text-emerald-400">${(dailySavingsUSD * 30).toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between items-baseline text-base font-bold text-white pt-2 border-t border-white/10">
                    <span className="text-xs text-slate-400">Annual Savings:</span>
                    <AnimatePresence mode="wait">
                      <motion.span
                        key={annualSavingsUSD}
                        initial={{ opacity: 0.6, y: -2 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-emerald-400 font-mono text-xl font-extrabold font-tabular"
                      >
                        ${annualSavingsUSD.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                      </motion.span>
                    </AnimatePresence>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "code" && (
          <div className="space-y-4">
            <div className="text-xs text-slate-400 font-sans leading-relaxed">
              Copy auto-generated Python client code for immediate integration into your pipeline:
            </div>
            <CodeWindow singleCode={generatedPythonCode} title="llmslim_integration.py" />
          </div>
        )}

        {activeTab === "cli" && (
          <div className="space-y-4">
            <div className="text-xs text-slate-400 font-sans leading-relaxed">
              Execute token compression via terminal command line:
            </div>

            <div className="p-4 rounded-xl bg-[#0D121C] border border-white/15 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase text-slate-500 font-mono font-bold">CLI Command</span>
                <button
                  onClick={handleCopyCli}
                  className="flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 cursor-pointer font-bold"
                >
                  {copiedCli ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedCli ? "Copied" : "Copy CLI String"}</span>
                </button>
              </div>

              <div className="p-3 rounded-lg bg-[#070A0F] border border-white/10 text-emerald-300 select-all overflow-x-auto font-mono text-xs">
                {generatedCliCommand}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
