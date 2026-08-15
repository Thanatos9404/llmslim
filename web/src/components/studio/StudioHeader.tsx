"use client";

import React from "react";
import { Sliders, Cpu, Sparkles, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StudioModel {
  id: string;
  name: string;
  provider: string;
  pricePerM: number;
}

export const STUDIO_MODELS: StudioModel[] = [
  { id: "gpt-5.6-sol", name: "GPT-5.6 Sol", provider: "OpenAI", pricePerM: 5.0 },
  { id: "gpt-5.6-terra", name: "GPT-5.6 Terra", provider: "OpenAI", pricePerM: 2.0 },
  { id: "gpt-5.6-luna", name: "GPT-5.6 Luna", provider: "OpenAI", pricePerM: 0.2 },
  { id: "gpt-5.5", name: "GPT-5.5", provider: "OpenAI", pricePerM: 5.0 },
  { id: "gpt-5.4", name: "GPT-5.4", provider: "OpenAI", pricePerM: 2.5 },
  { id: "gpt-5", name: "GPT-5 Flagship", provider: "OpenAI", pricePerM: 1.25 },
  { id: "claude-fable-5", name: "Claude Fable 5", provider: "Anthropic", pricePerM: 10.0 },
  { id: "claude-opus-5", name: "Claude Opus 5", provider: "Anthropic", pricePerM: 5.0 },
  { id: "claude-opus-4.8", name: "Claude Opus 4.8", provider: "Anthropic", pricePerM: 5.0 },
  { id: "claude-sonnet-5", name: "Claude Sonnet 5", provider: "Anthropic", pricePerM: 2.0 },
  { id: "claude-sonnet-4.6", name: "Claude Sonnet 4.6", provider: "Anthropic", pricePerM: 3.0 },
  { id: "claude-haiku-4.5", name: "Claude Haiku 4.5", provider: "Anthropic", pricePerM: 1.0 },
  { id: "gemini-3.1-pro", name: "Gemini 3.1 Pro", provider: "Google", pricePerM: 2.0 },
  { id: "gemini-3.5-flash", name: "Gemini 3.5 Flash", provider: "Google", pricePerM: 1.5 },
  { id: "gemini-3-flash", name: "Gemini 3 Flash", provider: "Google", pricePerM: 0.5 },
  { id: "gemini-2.5-pro", name: "Gemini 2.5 Pro", provider: "Google", pricePerM: 1.25 },
  { id: "grok-4", name: "Grok-4", provider: "xAI", pricePerM: 3.0 },
  { id: "grok-4.20", name: "Grok-4.20", provider: "xAI", pricePerM: 2.0 },
  { id: "llama-4-maverick", name: "Llama 4 Maverick", provider: "Meta", pricePerM: 0.3 },
  { id: "qwen-max", name: "Qwen Max", provider: "Alibaba", pricePerM: 1.6 },
  { id: "glm-5.2", name: "GLM-5.2", provider: "Z.ai", pricePerM: 0.6 },
  { id: "kimi-k3", name: "Kimi K3", provider: "Moonshot AI", pricePerM: 0.8 },
  { id: "deepseek-v4-pro", name: "DeepSeek-V4 Pro", provider: "DeepSeek", pricePerM: 0.435 },
  { id: "deepseek-v3", name: "DeepSeek-V3", provider: "DeepSeek", pricePerM: 0.14 },
  { id: "deepseek-r1.5", name: "DeepSeek-R1.5", provider: "DeepSeek", pricePerM: 0.55 },
  { id: "mistral-large-3", name: "Mistral Large 3", provider: "Mistral", pricePerM: 0.5 },
  { id: "nova-premier", name: "Nova Premier", provider: "Amazon", pricePerM: 2.5 },
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
            <h2 className="text-lg font-bold text-white tracking-tight font-sans">
              LLMSlim Studio Playground
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono font-bold">
              live Python engine
            </span>
          </div>
          <p className="text-xs text-slate-400 font-sans mt-1">
            Live extractive compression executes through the same-origin LLMSlim Python function.
          </p>
        </div>

        {/* Primary CTA Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={onReset}
            aria-label="Reset input prompt template"
            className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white transition-colors cursor-pointer text-xs font-mono flex items-center gap-1.5 min-h-[40px] focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            title="Reset Active Preset"
          >
            <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
            <span>Reset</span>
          </button>

          <button
            onClick={onCompress}
            disabled={isProcessing}
            aria-label="Run prompt compression engine"
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-400 via-cyan-400 to-emerald-400 text-[#030508] font-bold text-xs flex items-center gap-2 hover:shadow-[0_0_25px_rgba(0,245,155,0.45)] transition-all cursor-pointer disabled:opacity-50 min-h-[40px] focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
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
          <span className="text-[11px] text-slate-400 px-2 font-mono font-bold">Presets:</span>
          <button
            onClick={() => setActiveMode("prompt")}
            aria-label="Switch to System Prompt mode"
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400",
              activeMode === "prompt"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(0,245,155,0.2)]"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            System Prompt
          </button>
          <button
            onClick={() => setActiveMode("chat")}
            aria-label="Switch to Chat History mode"
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400",
              activeMode === "chat"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(0,245,155,0.2)]"
                : "text-slate-400 hover:text-slate-200"
            )}
          >
            Chat History
          </button>
          <button
            onClick={() => setActiveMode("rag")}
            aria-label="Switch to RAG Contexts mode"
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer font-bold focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400",
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
            <label htmlFor="target-model-select" className="text-[11px] text-slate-400 cursor-pointer">
              Target Model:
            </label>
            <select
              id="target-model-select"
              aria-label="Target LLM Model Selection"
              value={selectedModel.id}
              onChange={(e) => {
                const m = STUDIO_MODELS.find((x) => x.id === e.target.value);
                if (m) setSelectedModel(m);
              }}
              className="bg-transparent text-xs text-white font-bold cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 rounded"
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
            <label htmlFor="target-retain-slider" className="text-[11px] text-slate-400 cursor-pointer">
              Retain Target:
            </label>
            <input
              id="target-retain-slider"
              aria-label="Target Compression Retain Percentage Slider"
              type="range"
              min="0.2"
              max="0.8"
              step="0.05"
              value={targetRatio}
              onChange={(e) => setTargetRatio(parseFloat(e.target.value))}
              className="w-28 custom-slider cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
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
