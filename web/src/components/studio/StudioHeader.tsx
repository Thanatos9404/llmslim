"use client";

import React from "react";
import { Sliders, Cpu, Sparkles, RefreshCw, Layers } from "lucide-react";
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
    <div className="bg-[#070A0F] border-b border-white/10 p-5 sm:p-6 space-y-4 font-mono select-none">
      {/* Row 1: Studio Title + Description Subtitle + Primary Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <h3 className="text-lg font-bold text-white tracking-tight font-sans">
              LLMSlim Studio Playground
            </h3>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono font-bold">
              v0.2.0 Engine
            </span>
          </div>
          <p className="text-xs text-slate-400 font-sans mt-1">
            Interactive IDE playground for testing context compression, priority tier retention, and token ROI.
          </p>
        </div>

        {/* Primary CTA Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={onReset}
            className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white transition-colors cursor-pointer text-xs font-mono flex items-center gap-1.5 min-h-[40px]"
            title="Reset Active Preset"
          >
            <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
            <span>Reset</span>
          </button>

          <button
            onClick={onCompress}
            disabled={isProcessing}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-400 via-cyan-400 to-emerald-400 text-[#030508] font-bold text-xs flex items-center gap-2 hover:shadow-[0_0_25px_rgba(0,245,155,0.45)] transition-all cursor-pointer disabled:opacity-50 min-h-[40px]"
          >
            <Sparkles className={cn("w-4 h-4", isProcessing && "animate-spin")} />
            <span>{isProcessing ? "Executing Compression..." : "Run Compression"}</span>
          </button>
        </div>
      </div>

      {/* Row 2: Preset Selector Tabs + Model Selector + Ratio Slider */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-white/5 text-xs">
        {/* Prompt Presets */}
        <div className="flex items-center gap-1.5 bg-white/[0.03] p-1.5 rounded-xl border border-white/10">
          <span className="text-[11px] text-slate-500 px-2 font-mono font-bold">Presets:</span>
          <button
            onClick={() => setActiveMode("prompt")}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold",
              activeMode === "prompt"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(0,245,155,0.2)]"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            System Prompt
          </button>
          <button
            onClick={() => setActiveMode("chat")}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold",
              activeMode === "chat"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(0,245,155,0.2)]"
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
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(0,245,155,0.2)]"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            RAG Contexts
          </button>
        </div>

        {/* Model Selector & Compression Ratio Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Target Model Selector */}
          <div className="flex items-center gap-2 bg-white/[0.03] px-3.5 py-2 rounded-xl border border-white/10 min-h-[40px]">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span className="text-[11px] text-slate-400">Target Model:</span>
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
                  {m.name} (${m.pricePerM}/1M tokens)
                </option>
              ))}
            </select>
          </div>

          {/* Custom Retain Target Slider */}
          <div className="flex items-center gap-3 bg-white/[0.03] px-3.5 py-2 rounded-xl border border-white/10 min-h-[40px]">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <span className="text-[11px] text-slate-400">Retain Target:</span>
            <input
              type="range"
              min="0.2"
              max="0.8"
              step="0.05"
              value={targetRatio}
              onChange={(e) => setTargetRatio(parseFloat(e.target.value))}
              className="w-28 custom-slider cursor-pointer"
            />
            <span className="text-xs font-bold text-emerald-400 font-tabular min-w-[36px]">
              {Math.round(targetRatio * 100)}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
