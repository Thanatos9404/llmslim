"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { CheckCircle2, Circle, Clock, Rocket } from "lucide-react";

export interface Milestone {
  version: string;
  title: string;
  status: "completed" | "current" | "in-progress" | "planned";
  features: string[];
}

export function Timeline({ className }: { className?: string }) {
  const milestones: Milestone[] = [
    {
      version: "v0.1.0",
      title: "Foundation Release",
      status: "completed",
      features: [
        "Core TF-IDF sentence centrality ranking",
        "Basic sentence boundary splitting",
        "Fast heuristic token counter",
      ],
    },
    {
      version: "v0.2.0",
      title: "Production Governance Engine",
      status: "current",
      features: [
        "100.0% Instruction Retention Engine",
        "Named Entity, Regex & Code Block Protection",
        "Semantic Chunking with soft token caps",
        "93%+ Test Coverage & Ruff/MyPy CI Matrix",
      ],
    },
    {
      version: "v0.3.0",
      title: "High-Throughput Streaming",
      status: "in-progress",
      features: [
        "Streaming token compression API (compress_stream)",
        "Native ONNX Embeddings for sub-5ms latency",
        "Async asyncio pipeline integration (acompress_batch)",
      ],
    },
    {
      version: "v1.0.0",
      title: "Ecosystem Maturity",
      status: "planned",
      features: [
        "WASM / Web Assembly Edge local execution",
        "Multi-Modal context compression (Text-Image)",
        "Rust/C-Extension core sentence tokenizer (<1ms overhead)",
      ],
    },
  ];

  return (
    <div className={cn("p-6 sm:p-8 rounded-2xl bg-[#0D121C] border border-white/10 backdrop-blur-xl space-y-6", className)}>
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <span className="text-xs font-mono uppercase tracking-widest text-violet-400">
            Roadmap Horizon
          </span>
          <h3 className="text-xl font-bold text-white tracking-tight mt-1">
            Engine Progression & Release Milestones
          </h3>
        </div>
        <Rocket className="w-5 h-5 text-violet-400" />
      </div>

      <div className="relative border-l-2 border-white/10 ml-4 pl-6 space-y-8">
        {milestones.map((item, idx) => (
          <motion.div
            key={item.version}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: idx * 0.1 }}
            className="relative"
          >
            {/* Status Node Circle */}
            <span className="absolute -left-[33px] top-1.5 p-1 rounded-full bg-[#0D121C] border border-white/20">
              {item.status === "completed" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
              {item.status === "current" && <Clock className="w-4 h-4 text-cyan-400 animate-spin" />}
              {item.status === "in-progress" && <Circle className="w-4 h-4 text-violet-400 fill-violet-400/20" />}
              {item.status === "planned" && <Circle className="w-4 h-4 text-slate-600" />}
            </span>

            <div className="flex items-center gap-3 mb-2">
              <span className={cn(
                "px-2.5 py-0.5 rounded text-xs font-mono font-bold border",
                item.status === "current" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" : "bg-white/5 text-slate-300 border-white/10"
              )}>
                {item.version}
              </span>
              <h4 className="text-base font-bold text-white">{item.title}</h4>
            </div>

            <ul className="space-y-1.5 pl-2">
              {item.features.map((f, i) => (
                <li key={i} className="text-xs text-slate-400 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400/60" />
                  {f}
                </li>
              ))}
            </ul>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
