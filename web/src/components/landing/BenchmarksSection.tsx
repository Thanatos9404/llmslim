"use client";

import React from "react";

export function BenchmarksSection() {
  const releaseChecks = [
    { label: "Python test suite", value: "589 passed / 0 failed" },
    { label: "Branch coverage", value: "90.60%" },
    { label: "Static analysis", value: "Ruff + MyPy: pass" },
    { label: "Planner benchmark", value: "28 cases / 12 languages" },
  ];

  return (
    <section id="benchmarks" className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-emerald-400">
          Release verification
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Measured checks for <span className="text-gradient-emerald">v0.6.0 RC</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          The release gate combines Python quality checks with a frozen offline planner benchmark. Results and limitations ship in the repository.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {releaseChecks.map((check) => (
          <div key={check.label} className="rounded-xl bg-[#0D121C] border border-white/10 p-5 space-y-2">
            <p className="text-xs font-mono uppercase tracking-wide text-slate-500">{check.label}</p>
            <p className="text-lg font-bold text-emerald-300">{check.value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
