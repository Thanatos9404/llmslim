"use client";

import React from "react";
import { Pipeline } from "@/components/design-system";

export function PipelineSection() {
  return (
    <section id="pipeline" className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-emerald-400">
          Mechanical Transparency
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          How LLMSlim <span className="text-gradient-emerald">Surgically Prunes</span> Text
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          Explore the 6-stage pipeline engine that evaluates centrality, named entities, and imperative directives before budget allocation.
        </p>
      </div>

      <Pipeline />
    </section>
  );
}
