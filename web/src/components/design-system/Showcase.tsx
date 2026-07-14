"use client";

import React, { useState } from "react";
import {
  AuroraBackground,
  GridBackground,
  NoiseOverlay,
  CursorGlow,
  AnimatedButton,
  Card,
  BentoCard,
  MetricCard,
  MetricsGrid,
  ComparisonCard,
  CodeWindow,
  CommandPalette,
  Pipeline,
  Timeline,
  FeatureCard,
  BenchmarkTable,
  Charts,
} from "./index";

import {
  Zap,
  Shield,
  Layers,
  Search,
  Terminal,
  Cpu,
  TrendingUp,
  DollarSign,
  Sparkles,
  ChevronRight,
  Command,
} from "lucide-react";

export function DesignSystemShowcase() {
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  return (
    <AuroraBackground className="min-h-screen py-12 px-4 sm:px-8 max-w-7xl mx-auto space-y-16">
      <NoiseOverlay opacity={0.03} />
      <CursorGlow color="emerald" size={400} />
      <CommandPalette isOpen={commandPaletteOpen} onClose={() => setCommandPaletteOpen(false)} />

      {/* Header Title Section */}
      <div className="text-center space-y-4 pt-8">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          <Sparkles className="w-3.5 h-3.5" />
          LLMSlim UI System — Dark Mode Only Architecture
        </div>
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white">
          The Design System for <span className="text-gradient-emerald">AI Infrastructure</span>
        </h1>
        <p className="text-slate-400 max-w-2xl mx-auto text-base sm:text-lg leading-relaxed">
          Production-grade Next.js, TypeScript, Tailwind CSS v4, and Framer Motion component specs designed for LLMSlim.
        </p>

        {/* Command Palette Trigger */}
        <div className="pt-2 flex justify-center">
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="inline-flex items-center gap-3 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/15 text-xs font-mono text-slate-300 transition-all cursor-pointer shadow-lg"
          >
            <Command className="w-4 h-4 text-emerald-400" />
            <span>Press <kbd className="px-1.5 py-0.5 rounded bg-white/10 border border-white/10 text-white font-bold">⌘K</kbd> to open Command Palette</span>
          </button>
        </div>
      </div>

      {/* 1. BUTTONS SYSTEM SECTION */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <Terminal className="w-5 h-5 text-emerald-400" /> 01 // Animated Buttons
          </h2>
          <span className="text-xs font-mono text-slate-500">Quantum Beam & Micro-Tactile Motion</span>
        </div>

        <div className="flex flex-wrap items-center gap-4 p-6 rounded-2xl bg-[#0D121C] border border-white/10">
          <AnimatedButton variant="quantum" size="lg" icon={<Zap className="w-4 h-4" />}>
            Get Started with LLMSlim
          </AnimatedButton>
          <AnimatedButton variant="glass" size="lg" icon={<ChevronRight className="w-4 h-4" />} iconPosition="right">
            Explore Documentation
          </AnimatedButton>
          <AnimatedButton variant="outline" size="md">
            View Benchmarks
          </AnimatedButton>
          <AnimatedButton variant="ghost" size="md">
            GitHub ⭐ 1.2k
          </AnimatedButton>
        </div>
      </section>

      {/* 2. LIVE COMPRESSION REACTOR SECTION */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <Cpu className="w-5 h-5 text-cyan-400" /> 02 // Live Interactive Compression Simulator
          </h2>
          <span className="text-xs font-mono text-slate-500">Side-by-Side Context Pruning</span>
        </div>

        <ComparisonCard />
      </section>

      {/* 3. METRIC CARDS GRID */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <TrendingUp className="w-5 h-5 text-emerald-400" /> 03 // Financial & Quality Telemetry
          </h2>
          <span className="text-xs font-mono text-slate-500">Tabular Numbers & Savings Indicators</span>
        </div>

        <MetricsGrid>
          <MetricCard
            label="Token Reduction"
            value="40–70%"
            change="+52.3% avg"
            changeType="positive"
            accentColor="emerald"
            icon={<Zap className="w-4 h-4" />}
            subValue="Surgically removes prompt filler with zero meaning loss"
          />
          <MetricCard
            label="Instruction Fidelity"
            value="100.0%"
            change="Guaranteed"
            changeType="positive"
            accentColor="cyan"
            icon={<Shield className="w-4 h-4" />}
            subValue="System prompts, directives, and code blocks retained completely"
          />
          <MetricCard
            label="Annual ROI Savings"
            value="$32,462"
            change="@ 50k reqs/day"
            changeType="positive"
            accentColor="emerald"
            icon={<DollarSign className="w-4 h-4" />}
            subValue="Calculated for flagship GPT-5 / Claude Sonnet model workloads"
          />
          <MetricCard
            label="Processing Overhead"
            value="28 ms"
            change="Sub-50ms"
            changeType="positive"
            accentColor="violet"
            icon={<Cpu className="w-4 h-4" />}
            subValue="Works offline out-of-the-box with TF-IDF fallback"
          />
        </MetricsGrid>
      </section>

      {/* 4. CODE WINDOW & QUICKSTART */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <Terminal className="w-5 h-5 text-cyan-400" /> 04 // Terminal & Code Blocks
          </h2>
          <span className="text-xs font-mono text-slate-500">Warp & Linear CLI Syntax Theme</span>
        </div>

        <CodeWindow
          tabs={[
            {
              id: "single-prompt",
              title: "compress_prompt.py",
              code: `from llmslim import compress\n\n# Compress massive prompt in 1 line\nresult = compress(your_prompt, target_ratio=0.5)\n\nprint(result.compressed_text)    # → 52.3% fewer tokens\nprint(result.tokens_saved)       # → 1,847 tokens saved\nprint(result.summary())          # → Full telemetry stats`,
            },
            {
              id: "chat-history",
              title: "compress_chat.py",
              code: `from llmslim import compress_chat_messages\n\n# Compress multi-turn chat history while preserving system prompt\ncompressed = compress_chat_messages(messages, target_ratio=0.5)\n\nresponse = client.chat.completions.create(model="gpt-5", messages=compressed)`,
            },
            {
              id: "rag-documents",
              title: "compress_rag.py",
              code: `from llmslim import compress_documents\n\n# Query-aware RAG compression: keeps sentences relevant to user query\nresults = compress_documents(retrieved_chunks, query="FastAPI authentication", target_ratio=0.4)`,
            },
          ]}
        />
      </section>

      {/* 5. BENTO GRID FEATURE CARDS */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <Layers className="w-5 h-5 text-violet-400" /> 05 // Bento Grid 2.0 Feature Cards
          </h2>
          <span className="text-xs font-mono text-slate-500">Spotlight Cursor Follow & Specular Lines</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <FeatureCard
            title="Semantic Topic Chunking"
            subtitle="Groups sentences by topic using embedding similarity. Detects topic shifts so each chunk is ranked independently for maximum accuracy."
            badge="Topic Drift Engine"
            glowColor="emerald"
            icon={<Layers className="w-5 h-5" />}
          />
          <FeatureCard
            title="100% Instruction Shield"
            subtitle="Automatically preserves imperative language, code fences, numbered steps, and directives. Your instructions never get dropped."
            badge="Instruction Protection"
            glowColor="cyan"
            icon={<Shield className="w-5 h-5" />}
          />
          <FeatureCard
            title="Query-Aware RAG Pipeline"
            subtitle="Pass a query parameter to favor sentences relevant to the user's question — perfect for compressing retrieved documents."
            badge="Relevance Signal"
            glowColor="violet"
            icon={<Search className="w-5 h-5" />}
          />
        </div>
      </section>

      {/* 6. PIPELINE ARCHITECTURE */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <Zap className="w-5 h-5 text-emerald-400" /> 06 // Execution Pipeline DAG
          </h2>
          <span className="text-xs font-mono text-slate-500">6-Stage Sentence Protection Walkthrough</span>
        </div>

        <Pipeline />
      </section>

      {/* 7. CHARTS TELEMETRY */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <TrendingUp className="w-5 h-5 text-cyan-400" /> 07 // Performance & Efficiency Charts
          </h2>
          <span className="text-xs font-mono text-slate-500">Visual Metrics & Latency Scales</span>
        </div>

        <Charts />
      </section>

      {/* 8. EMPIRICAL BENCHMARKS TABLE */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <Shield className="w-5 h-5 text-emerald-400" /> 08 // Benchmark Quality Matrix
          </h2>
          <span className="text-xs font-mono text-slate-500">Standardized Datasets Matrix</span>
        </div>

        <BenchmarkTable />
      </section>

      {/* 9. ROADMAP HORIZON TIMELINE */}
      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2 font-mono">
            <Sparkles className="w-5 h-5 text-violet-400" /> 09 // Engine Version Roadmap
          </h2>
          <span className="text-xs font-mono text-slate-500">v0.1 → v0.2 → v0.3 → v1.0 Progression</span>
        </div>

        <Timeline />
      </section>
    </AuroraBackground>
  );
}
