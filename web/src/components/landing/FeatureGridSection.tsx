"use client";

import React from "react";
import { FeatureCard } from "@/components/design-system";
import { ShieldCheck, Layers, Search, DollarSign, Plug, MessageSquare } from "lucide-react";

export function FeatureGridSection() {
  return (
    <section id="features" className="py-20 sm:py-28 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="badge-scientific text-emerald-400 text-xs">
          Engine Capability Specifications
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Engineered for <span className="text-gradient-emerald">Zero Accuracy Loss</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          LLMSlim combines graph centrality, topic drift detection, and rule-based priority heuristics to guarantee prompt intent preservation.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <FeatureCard
          title="Instruction Retention Shield"
          subtitle="Automatically detects and locks imperative directives, code blocks, numbered sequences, and role markers. System instructions are preserved at 100.0% accuracy across all compression ratios."
          badge="Guaranteed Preservation"
          glowColor="emerald"
          icon={<ShieldCheck className="w-5 h-5 text-emerald-400" />}
        />

        <FeatureCard
          title="Semantic Topic Chunking"
          subtitle="Groups sentences into cohesive topic blocks using cosine similarity thresholding. Automatically adjusts sentence ranking per chunk to avoid topic bias."
          badge="Topic Drift Engine"
          glowColor="cyan"
          icon={<Layers className="w-5 h-5 text-cyan-400" />}
        />

        <FeatureCard
          title="Query-Aware RAG Pipeline"
          subtitle="Pass a query parameter to rank retrieved vector documents by relevance to the user's specific question — cutting noise from large RAG contexts."
          badge="Relevance Vector Search"
          glowColor="violet"
          icon={<Search className="w-5 h-5 text-violet-400" />}
        />

        <FeatureCard
          title="Instant Cost Savings Telemetry"
          subtitle="Built-in cost estimator support for GPT-5, Claude Opus, Claude Sonnet, Gemini, and DeepSeek. Get exact dollar retention metrics per request."
          badge="Financial ROI Calculator"
          glowColor="emerald"
          icon={<DollarSign className="w-5 h-5 text-emerald-400" />}
        />

        <FeatureCard
          title="Pluggable Embeddings Engine"
          subtitle="Runs offline with local TF-IDF zero-dependency fallback out of the box. Upgrade to sentence-transformers for deep semantic vector ranking."
          badge="Zero Friction Fallback"
          glowColor="cyan"
          icon={<Plug className="w-5 h-5 text-cyan-400" />}
        />

        <FeatureCard
          title="Chat History & Batch Helpers"
          subtitle="Dedicated APIs for multi-turn chat message compression and async batch document pipeline processing that drop straight into existing OpenAI or Anthropic SDK code."
          badge="Pipeline Integration"
          glowColor="violet"
          icon={<MessageSquare className="w-5 h-5 text-violet-400" />}
        />
      </div>
    </section>
  );
}
