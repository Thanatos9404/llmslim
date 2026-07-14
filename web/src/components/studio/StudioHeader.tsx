"use client";

import React from "react";
import { Sliders, Cpu, Sparkles, RefreshCw, Layers, ShieldCheck, DollarSign } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StudioModel {
  id: string;
  name: string;
  provider: string;
  pricePerM: number;
}

export const STUDIO_MODELS: StudioModel[] = [
  { id: "gpt-5", name: "GPT-5 Flagship", provider: "OpenAI", pricePerM: 1.25 },
  { id: "claude-opus", name: "Claude Opus 4.8", provider: "Anthropic", pricePerM: 5.0 },
  { id: "claude-sonnet", name: "Claude Sonnet 4.6", provider: "Anthropic", pricePerM: 3.0 },
  { id: "gpt-4o", name: "GPT-4o", provider: "OpenAI", pricePerM: 2.5 },
  { id: "gemini-2.5", name: "Gemini 2.5 Pro", provider: "Google", pricePerM: 1.25 },
  { id: "deepseek-v3", name: "DeepSeek-V3", provider: "DeepSeek", pricePerM: 0.14 },
];

export interface StudioHeaderProps {
  activeMode: "prompt" | "chat" | "rag";
  setActiveMode: (mode: "prompt" | "chat" | "rag") => void;
  selectedModel: StudioModel;
  setSelectedModel: (model: StudioModel) => void;
  targetRatio: number;
  setTargetRatio: (ratio: number) => void;
  isProcessing: boolean;
  onCompress: () => void;
  onReset: () => void;
}

export function StudioHeader({
  activeMode,
  setActiveMode,
  selectedModel,
  setSelectedModel,
  targetRatio,
  setTargetRatio,
  isProcessing,
  onCompress,
  onReset,
}: StudioHeaderProps) {
  return (
    <div className="bg-[#070A0F] border-b border-white/10 px-4 py-3 flex flex-wrap items-center justify-between gap-4 font-mono select-none">
      {/* Mode Switcher Tabs */}
      <div className="flex items-center gap-1 bg-white/[0.04] p-1 rounded-xl border border-white/10">
        <button
          onClick={() => setActiveMode("prompt")}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold",
            activeMode === "prompt"
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(0,245,155,0.2)]"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          Single Prompt
        </button>
        <button
          onClick={() => setActiveMode("chat")}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold",
            activeMode === "chat"
              ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 shadow-[0_0_15px_rgba(0,229,255,0.2)]"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          Chat History
        </button>
        <button
          onClick={() => setActiveMode("rag")}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold",
            activeMode === "rag"
              ? "bg-violet-500/15 text-violet-400 border border-violet-500/30 shadow-[0_0_15px_rgba(168,85,247,0.2)]"
              : "text-slate-400 hover:text-slate-200"
          )}
        >
          RAG Contexts
        </button>
      </div>

      {/* Model & Custom Premium Target Ratio Control */}
      <div className="flex items-center flex-wrap gap-4">
        {/* Target Model Selector */}
        <div className="flex items-center gap-2 bg-white/[0.04] px-3 py-1.5 rounded-xl border border-white/10">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[11px] text-slate-400">Model:</span>
          <select
            value={selectedModel.id}
            onChange={(e) => {
              const m = STUDIO_MODELS.find((x) => x.id === e.target.value);
              if (m) setSelectedModel(m);
            }}
            className="bg-transparent text-xs text-white font-bold cursor-pointer focus:outline-none"
          >
            {STUDIO_MODELS.map((m) => (
              <option key={m.id} value={m.id} className="bg-[#0D121C] text-slate-200">
                {m.name} (${m.pricePerM}/1M)
              </option>
            ))}
          </select>
        </div>

        {/* Custom Premium Slider (Phase B) */}
        <div className="flex items-center gap-3 bg-white/[0.04] px-3 py-1.5 rounded-xl border border-white/10">
          <Sliders className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[11px] text-slate-400">Target Retain:</span>
          <input
            type="range"
            min="0.2"
            max="0.8"
            step="0.05"
            value={targetRatio}
            onChange={(e) => setTargetRatio(parseFloat(e.target.value))}
            className="w-24 custom-slider cursor-pointer"
          />
          <span className="text-xs font-bold text-emerald-400 font-mono min-w-[32px]">
            {Math.round(targetRatio * 100)}%
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onReset}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white transition-colors cursor-pointer"
            title="Reset Input Template"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onCompress}
            disabled={isProcessing}
            className="px-4 py-1.5 rounded-xl bg-gradient-to-r from-emerald-400 to-cyan-400 text-[#030508] font-bold text-xs flex items-center gap-2 hover:shadow-[0_0_20px_rgba(0,245,155,0.4)] transition-all cursor-pointer disabled:opacity-50"
          >
            <Sparkles className={cn("w-3.5 h-3.5", isProcessing && "animate-spin")} />
            {isProcessing ? "Processing..." : "Compress Prompt"}
          </button>
        </div>
      </div>
    </div>
  );
}
