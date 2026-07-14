"use client";

import React, { useState } from "react";
import { StudioModel } from "./StudioHeader";
import { CodeWindow } from "@/components/design-system";
import { DollarSign, Zap, Copy, Check, Terminal, Shield, BarChart3, Cpu, Code2 } from "lucide-react";
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
  const [activeTab, setActiveTab] = useState<"stats" | "code" | "cli" | "benchmarks">("stats");
  const [copiedCli, setCopiedCli] = useState(false);

  const compressedTokens = Math.max(10, Math.round(originalTokens * targetRatio));
  const savedTokens = originalTokens - compressedTokens;
  const reductionPercent = Math.round((1 - targetRatio) * 100);

  // Financial calculations
  const dailyRequests = 50000;
  const dailySavingsUSD = (savedTokens * dailyRequests * (selectedModel.pricePerM / 1000000));
  const annualSavingsUSD = dailySavingsUSD * 365;

  // Auto-generate Python snippet based on current state
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
      {/* Top Navigation Tabs */}
      <div className="px-4 py-3 bg-[#0D121C] border-b border-white/10 flex items-center justify-between select-none">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab("stats")}
            className={cn(
              "px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer",
              activeTab === "stats" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" : "text-slate-400 hover:text-white"
            )}
          >
            Telemetry
          </button>
          <button
            onClick={() => setActiveTab("code")}
            className={cn(
              "px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer",
              activeTab === "code" ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30" : "text-slate-400 hover:text-white"
            )}
          >
            Python Generator
          </button>
          <button
            onClick={() => setActiveTab("cli")}
            className={cn(
              "px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer",
              activeTab === "cli" ? "bg-violet-500/20 text-violet-400 border border-violet-500/30" : "text-slate-400 hover:text-white"
            )}
          >
            CLI Builder
          </button>
        </div>

        <span className="text-[10px] text-slate-500 font-bold uppercase">LLMSlim Studio v0.2.0</span>
      </div>

      {/* Main Body */}
      <div className="flex-1 p-4 sm:p-6 overflow-y-auto space-y-6">
        {activeTab === "stats" && (
          <div className="space-y-6">
            {/* Stat Badges Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-[#0D121C] border border-white/10">
                <div className="text-[10px] text-slate-500 uppercase font-mono">Original Tokens</div>
                <div className="text-xl font-bold text-white mt-1">{originalTokens.toLocaleString()}</div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#0D121C] border border-emerald-500/30">
                <div className="text-[10px] text-emerald-400 uppercase font-mono">Compressed Tokens</div>
                <div className="text-xl font-bold text-emerald-400 mt-1">{compressedTokens.toLocaleString()}</div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#0D121C] border border-cyan-500/30">
                <div className="text-[10px] text-cyan-400 uppercase font-mono">Tokens Saved</div>
                <div className="text-xl font-bold text-cyan-400 mt-1">{savedTokens.toLocaleString()}</div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#0D121C] border border-violet-500/30">
                <div className="text-[10px] text-violet-400 uppercase font-mono">Reduction %</div>
                <div className="text-xl font-bold text-violet-400 mt-1">{reductionPercent}%</div>
              </div>
            </div>

            {/* Financial Telemetry Banner */}
            <div className="p-5 rounded-xl bg-gradient-to-br from-[#0D121C] to-[#141B29] border border-emerald-500/30 space-y-3">
              <div className="flex items-center justify-between text-xs text-emerald-400 font-bold border-b border-white/10 pb-2">
                <span className="flex items-center gap-1.5">
                  <DollarSign className="w-4 h-4" /> Projected ROI ({selectedModel.name})
                </span>
                <span>@ 50k reqs/day</span>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-xs text-slate-300">
                  <span>Daily Savings:</span>
                  <span className="font-bold text-emerald-400">${dailySavingsUSD.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-xs text-slate-300">
                  <span>Monthly Savings:</span>
                  <span className="font-bold text-cyan-400">${(dailySavingsUSD * 30).toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between text-base font-bold text-white pt-2 border-t border-white/10">
                  <span>Annual Dollar Savings:</span>
                  <span className="text-emerald-400 font-mono text-lg">${annualSavingsUSD.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "code" && (
          <div className="space-y-3">
            <div className="text-xs text-slate-400 font-sans leading-relaxed">
              Auto-generated Python client snippet based on your interactive studio parameters:
            </div>
            <CodeWindow singleCode={generatedPythonCode} title="llmslim_studio_export.py" />
          </div>
        )}

        {activeTab === "cli" && (
          <div className="space-y-4">
            <div className="text-xs text-slate-400 font-sans leading-relaxed">
              Run prompt compression directly from terminal stdin/stdout:
            </div>

            <div className="p-4 rounded-xl bg-[#0D121C] border border-white/15 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase text-slate-500">CLI Execution Command</span>
                <button
                  onClick={handleCopyCli}
                  className="flex items-center gap-1 text-[11px] text-emerald-400 hover:text-emerald-300 cursor-pointer"
                >
                  {copiedCli ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedCli ? "Copied" : "Copy CLI"}</span>
                </button>
              </div>

              <div className="p-3 rounded-lg bg-[#070A0F] border border-white/10 text-emerald-300 select-all overflow-x-auto">
                {generatedCliCommand}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
