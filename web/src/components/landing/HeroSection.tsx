"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import { Sparkles, Terminal, Copy, Check, ShieldCheck, Zap, ArrowRight, Cpu } from "lucide-react";
import { AnimatedButton } from "@/components/design-system";
import { StudioSkeleton } from "@/components/studio/StudioSkeleton";

// Dynamic lazy load for heavy Monaco Studio bundle
const DynamicLLMSlimStudio = dynamic(
  () => import("@/components/studio/LLMSlimStudio").then((mod) => mod.LLMSlimStudio),
  {
    ssr: false,
    loading: () => <StudioSkeleton />,
  }
);

export function HeroSection() {
  const [copied, setCopied] = useState(false);

  const handleCopyInstall = () => {
    navigator.clipboard.writeText("pip install llmslim");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="relative pt-32 sm:pt-40 pb-20 sm:pb-28 px-4 sm:px-8 max-w-7xl mx-auto flex flex-col items-center text-center space-y-12 sm:space-y-14">
      {/* Top Release Pill Badge */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono shadow-[0_0_20px_rgba(0,245,155,0.15)] mb-2"
      >
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>LLMSlim Studio & Engine v0.2.0</span>
        <span className="text-slate-500 hidden sm:inline">|</span>
        <span className="text-slate-300 font-semibold hidden sm:flex items-center gap-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          100.0% Instruction Retention
        </span>
      </motion.div>

      {/* Hero Headline — Refined Silver Sheen & Cybermatic Emerald Telemetry Accent */}
      <div className="space-y-6 max-w-4xl">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-6xl md:text-7xl font-extrabold tracking-tight text-white leading-[1.04]"
        >
          <span className="text-gradient-silver">Cut Your LLM Token Costs by</span>{" "}
          <span className="text-gradient-emerald">50% in 1 Line</span>{" "}
          <span className="text-gradient-silver">of Code.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-base sm:text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed font-normal"
        >
          Semantic context compression built for enterprise LLM pipelines. Surgically eliminates prompt filler, RAG noise, and conversation redundancy while preserving guaranteed instruction fidelity.
        </motion.p>
      </div>

      {/* Hero CTA & Terminal Quick Box */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
        className="flex flex-col sm:flex-row items-center gap-4 w-full justify-center"
      >
        {/* Terminal Specular Frame Copy Box */}
        <div className="flex items-center justify-between gap-3 px-4 py-3 rounded-2xl bg-[#0D121C] border border-white/15 border-specular-emerald shadow-2xl font-mono text-xs text-slate-200 w-full sm:w-auto">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-slate-400">$</span>
            <span className="font-bold text-white">pip install llmslim</span>
          </div>
          <button
            onClick={handleCopyInstall}
            aria-label="Copy install command"
            className="ml-2 p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white transition-all cursor-pointer min-h-[36px] min-w-[36px] flex items-center justify-center"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>

        <AnimatedButton
          variant="quantum"
          size="lg"
          icon={<ArrowRight className="w-4 h-4" />}
          iconPosition="right"
          onClick={() => {
            const el = document.getElementById("studio-playground");
            if (el) el.scrollIntoView({ behavior: "smooth" });
          }}
        >
          Launch Interactive Studio
        </AnimatedButton>
      </motion.div>

      {/* Interactive Studio Playground Centerpiece */}
      <motion.div
        id="studio-playground"
        initial={{ opacity: 0, y: 30, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.8, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full pt-6 sm:pt-8 text-left"
      >
        <div className="flex items-center justify-between mb-3 px-1 font-mono text-xs">
          <span className="text-emerald-400 font-bold flex items-center gap-2">
            <Cpu className="w-4 h-4" />
            LLMSlim Studio Playground (OpenAI x Vercel AI Style)
          </span>
          <span className="text-slate-500 hidden sm:inline">
            Interactive 3-Panel Compression Sandbox
          </span>
        </div>
        <DynamicLLMSlimStudio />
      </motion.div>
    </section>
  );
}
