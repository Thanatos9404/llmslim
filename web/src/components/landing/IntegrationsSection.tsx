"use client";

import React from "react";
import { Card } from "@/components/design-system";
import { Plug } from "lucide-react";

export function IntegrationsSection() {
  const integrations = [
    { name: "OpenAI SDK", tag: "Drop-in Wrapper", status: "Native Support" },
    { name: "Anthropic Claude SDK", tag: "Chat Messages Helper", status: "Native Support" },
    { name: "LangChain", tag: "Document Transformer", status: "Integration Ready" },
    { name: "LlamaIndex", tag: "Node Post-processor", status: "Integration Ready" },
    { name: "LiteLLM Proxy", tag: "Middleware Pipeline", status: "Integration Ready" },
    { name: "vLLM / Local Inference", tag: "Text Pre-processor", status: "Native Support" },
    { name: "Outlines & Instructor", tag: "Structured Output", status: "Guaranteed Compatibility" },
    { name: "FastAPI / Async Pipelines", tag: "Native Async Engine", status: "Native Support" },
  ];

  return (
    <section id="integrations" className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-emerald-400">
          Seamless Ecosystem Synergy
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Works With Your <span className="text-gradient-emerald">Existing Stack</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          LLMSlim operates purely on raw text strings and message dictionaries — standardizing cleanly across any Python AI framework.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {integrations.map((item, idx) => (
          <div
            key={idx}
            className="p-5 rounded-xl bg-[#0D121C] border border-white/10 hover:border-emerald-500/30 transition-all space-y-2 group"
          >
            <div className="flex items-center justify-between">
              <span className="p-2 rounded-lg bg-white/5 border border-white/10 text-emerald-400 group-hover:scale-110 transition-transform">
                <Plug className="w-4 h-4" />
              </span>
              <span className="text-[10px] font-mono text-slate-500 uppercase">{item.status}</span>
            </div>
            <h4 className="text-base font-bold text-white group-hover:text-emerald-300 transition-colors">
              {item.name}
            </h4>
            <p className="text-xs font-mono text-slate-400">{item.tag}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
