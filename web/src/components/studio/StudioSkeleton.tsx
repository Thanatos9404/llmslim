"use client";

import React from "react";
import { Cpu, Sparkles } from "lucide-react";

export function StudioSkeleton() {
  return (
    <div className="w-full rounded-2xl bg-[#0D121C] border border-white/10 p-6 animate-pulse space-y-6 min-h-[500px] flex flex-col justify-between">
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-24 h-6 rounded-lg bg-white/10" />
          <div className="w-24 h-6 rounded-lg bg-white/10" />
          <div className="w-24 h-6 rounded-lg bg-white/10" />
        </div>
        <div className="w-32 h-8 rounded-xl bg-emerald-500/20" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        <div className="rounded-xl bg-[#070A0F] border border-white/5 p-4 space-y-3 min-h-[250px]" />
        <div className="rounded-xl bg-[#070A0F] border border-white/5 p-4 space-y-3 min-h-[250px]" />
        <div className="rounded-xl bg-[#070A0F] border border-white/5 p-4 space-y-3 min-h-[250px]" />
      </div>

      <div className="flex items-center justify-between text-xs font-mono text-slate-500 pt-2 border-t border-white/5">
        <span className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-emerald-400 animate-spin" />
          Initializing LLMSlim Studio Engine...
        </span>
        <span>Sub-50ms Latency Benchmark</span>
      </div>
    </div>
  );
}
