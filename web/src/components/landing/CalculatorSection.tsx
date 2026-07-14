"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/design-system";
import { DollarSign, Sparkles, Sliders } from "lucide-react";

export function CalculatorSection() {
  const models = [
    { name: "Claude Opus 4.8", pricePerM: 5.0 },
    { name: "Claude Sonnet 4.6", pricePerM: 3.0 },
    { name: "GPT-4o", pricePerM: 2.5 },
    { name: "GPT-5 (Flagship)", pricePerM: 1.25 },
    { name: "Gemini 2.5 Pro", pricePerM: 1.25 },
    { name: "Claude Haiku 4.5", pricePerM: 1.0 },
    { name: "DeepSeek-V3", pricePerM: 0.14 },
  ];

  const [selectedModel, setSelectedModel] = useState(models[3]); // Default GPT-5
  const [requestsPerDay, setRequestsPerDay] = useState(50000);
  const [promptTokens, setPromptTokens] = useState(1500);
  const [targetRatio, setTargetRatio] = useState(0.5);

  const savedTokensPerReq = Math.round(promptTokens * (1 - targetRatio));
  const dailySavedTokens = savedTokensPerReq * requestsPerDay;
  const dailySavingsUSD = (dailySavedTokens / 1000000) * selectedModel.pricePerM;
  const monthlySavingsUSD = dailySavingsUSD * 30;
  const annualSavingsUSD = dailySavingsUSD * 365;

  return (
    <section id="calculator" aria-label="Enterprise Token Savings Calculator" className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="badge-scientific text-emerald-400 text-xs">
          Enterprise ROI Calculator
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          How Much Will Your System <span className="text-gradient-emerald">Save?</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          Input your daily LLM request telemetry and observe instant projected savings across flagship models.
        </p>
      </div>

      <Card glowColor="emerald" className="p-6 sm:p-10 space-y-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left Sliders & Controls */}
          <div className="space-y-6">
            {/* Model Select */}
            <div className="space-y-2">
              <label htmlFor="calc-model-select" className="text-xs font-mono uppercase text-slate-300 flex items-center gap-2 cursor-pointer">
                <Sliders className="w-3.5 h-3.5 text-emerald-400" />
                Select LLM Model Provider
              </label>
              <select
                id="calc-model-select"
                aria-label="Select LLM Model Provider for Cost Calculation"
                value={selectedModel.name}
                onChange={(e) => {
                  const m = models.find((x) => x.name === e.target.value);
                  if (m) setSelectedModel(m);
                }}
                className="w-full bg-[#070A0F] border border-white/15 rounded-xl px-4 py-3 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-emerald-400 cursor-pointer"
              >
                {models.map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.name} (${m.pricePerM.toFixed(2)} / 1M input tokens)
                  </option>
                ))}
              </select>
            </div>

            {/* Requests Per Day Slider */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <label htmlFor="requests-per-day-slider" className="text-slate-400 cursor-pointer">Daily API Request Volume:</label>
                <span className="text-emerald-400 font-bold font-tabular">
                  {requestsPerDay.toLocaleString()} requests/day
                </span>
              </div>
              <input
                id="requests-per-day-slider"
                aria-label="Daily API Request Volume Slider"
                type="range"
                min="1000"
                max="200000"
                step="1000"
                value={requestsPerDay}
                onChange={(e) => setRequestsPerDay(parseInt(e.target.value))}
                className="w-full custom-slider cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-400"
              />
            </div>

            {/* Prompt Tokens Slider */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <label htmlFor="prompt-length-slider" className="text-slate-400 cursor-pointer">Average Prompt Length:</label>
                <span className="text-cyan-400 font-bold font-tabular">
                  {promptTokens.toLocaleString()} tokens
                </span>
              </div>
              <input
                id="prompt-length-slider"
                aria-label="Average Prompt Token Length Slider"
                type="range"
                min="300"
                max="8000"
                step="100"
                value={promptTokens}
                onChange={(e) => setPromptTokens(parseInt(e.target.value))}
                className="w-full custom-slider cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-400"
              />
            </div>

            {/* Target Retain Ratio */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <label htmlFor="calc-target-ratio-slider" className="text-slate-400 cursor-pointer">Compression Target Ratio:</label>
                <span className="text-violet-400 font-bold font-tabular">
                  {Math.round((1 - targetRatio) * 100)}% token reduction ({Math.round(targetRatio * 100)}% retained)
                </span>
              </div>
              <input
                id="calc-target-ratio-slider"
                aria-label="Compression Target Retain Ratio Slider"
                type="range"
                min="0.2"
                max="0.8"
                step="0.05"
                value={targetRatio}
                onChange={(e) => setTargetRatio(parseFloat(e.target.value))}
                className="w-full custom-slider cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-400"
              />
            </div>
          </div>

          {/* Right Live ROI Breakdown Card */}
          <div className="rounded-xl bg-[#070A0F] border border-emerald-500/30 p-6 flex flex-col justify-between space-y-6 shadow-[0_0_40px_rgba(0,245,155,0.08)]">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <span className="text-xs font-mono uppercase text-emerald-400 flex items-center gap-1.5 font-bold">
                <Sparkles className="w-4 h-4" />
                Live Telemetry Calculations
              </span>
              <span className="text-xs font-mono text-slate-500 font-tabular">{selectedModel.name}</span>
            </div>

            <div className="space-y-4 font-mono">
              <div className="flex justify-between items-center text-xs border-b border-white/5 pb-2 font-tabular">
                <span className="text-slate-400">Tokens Saved / Request:</span>
                <span className="text-slate-200 font-bold">{savedTokensPerReq.toLocaleString()} tokens</span>
              </div>
              <div className="flex justify-between items-center text-xs border-b border-white/5 pb-2 font-tabular">
                <span className="text-slate-400">Daily Savings:</span>
                <span className="text-emerald-400 font-bold">
                  ${dailySavingsUSD.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex justify-between items-center text-xs border-b border-white/5 pb-2 font-tabular">
                <span className="text-slate-400">Monthly Savings:</span>
                <span className="text-cyan-400 font-bold">
                  ${monthlySavingsUSD.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

              {/* Big Annual ROI Card */}
              <div className="pt-2">
                <div className="text-[11px] uppercase text-slate-400 mb-1 badge-scientific">Total Projected Annual Savings</div>
                <motion.div
                  key={annualSavingsUSD}
                  initial={{ scale: 0.95 }}
                  animate={{ scale: 1 }}
                  className="text-4xl sm:text-5xl font-extrabold text-emerald-400 font-mono tracking-tight font-tabular"
                >
                  ${annualSavingsUSD.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                </motion.div>
                <div className="text-[11px] text-slate-500 mt-2 font-mono font-tabular">
                  *Based on official pricing models as of July 2026.
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </section>
  );
}
