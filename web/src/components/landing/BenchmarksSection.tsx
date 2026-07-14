"use client";

import React from "react";
import { BenchmarkTable, Charts } from "@/components/design-system";

export function BenchmarksSection() {
  return (
    <section id="benchmarks" className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-emerald-400">
          Empirical Data Verification
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Rigorously Benchmarked on <span className="text-gradient-emerald">Multi-Domain Datasets</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          Evaluated across standardized scientific paper corpora, multi-turn dialogs, and technical documentations.
        </p>
      </div>

      <div className="space-y-10">
        <Charts />
        <BenchmarkTable />
      </div>
    </section>
  );
}
