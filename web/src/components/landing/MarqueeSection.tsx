"use client";

import React from "react";
import { motion } from "framer-motion";

export function MarqueeSection() {
  const providers = [
    { name: "OpenAI GPT-5", price: "$1.25 / 1M tokens", status: "Compatible" },
    { name: "Anthropic Claude Opus 4.8", price: "$5.00 / 1M tokens", status: "Compatible" },
    { name: "Google Gemini 2.5 Pro", price: "$1.25 / 1M tokens", status: "Compatible" },
    { name: "DeepSeek-V3", price: "$0.14 / 1M tokens", status: "Compatible" },
    { name: "Mistral Large 3", price: "$1.00 / 1M tokens", status: "Compatible" },
    { name: "Meta Llama 3.3 70B", price: "Local / Open Source", status: "Compatible" },
  ];

  return (
    <section className="py-14 border-y border-white/10 bg-[#070A0F]/60 overflow-hidden select-none">
      <div className="max-w-7xl mx-auto px-4 text-center mb-6">
        <span className="badge-scientific text-slate-400 text-xs">
          Model Agnostic — Compresses Text Before Any LLM API Call
        </span>
      </div>

      <div className="flex overflow-hidden [mask-image:linear-gradient(90deg,transparent_0%,black_15%,black_85%,transparent_100%)]">
        <motion.div
          animate={{ x: ["0%", "-50%"] }}
          transition={{ duration: 28, repeat: Infinity, ease: "linear" }}
          className="flex shrink-0 gap-6 items-center pr-6"
        >
          {[...providers, ...providers].map((p, idx) => (
            <div
              key={idx}
              className="flex items-center gap-3 px-5 py-2.5 rounded-xl bg-white/[0.03] border border-white/10 text-xs font-mono shrink-0 hover:border-emerald-500/30 transition-all duration-300 group"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-400 group-hover:scale-125 transition-transform" />
              <span className="font-bold text-white font-mono">{p.name}</span>
              <span className="text-slate-500">|</span>
              <span className="text-slate-400 font-tabular">{p.price}</span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px] font-bold">
                {p.status}
              </span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
