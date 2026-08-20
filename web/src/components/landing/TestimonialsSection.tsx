"use client";

import React from "react";
import { Card } from "@/components/design-system";
import { Quote } from "lucide-react";

export function TestimonialsSection() {
  return <section className="py-20 sm:py-28 px-4 sm:px-8 max-w-7xl mx-auto space-y-8">
    <div className="text-center space-y-4 max-w-3xl mx-auto"><span className="badge-scientific text-emerald-400 text-xs">Open-source project</span><h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">Evaluate with your own workload</h2><p className="text-slate-400 text-base leading-relaxed">LLMSlim publishes reproducible release checks rather than unverified customer claims.</p></div>
    <Card glowColor="emerald" className="p-8 max-w-3xl mx-auto"><Quote className="w-6 h-6 text-emerald-400 mb-4" /><p className="text-slate-300 leading-relaxed">The v0.4.0 release gate records 489 passing tests, 90.93% coverage, Ruff success, and measured schema-tax results across 375 schemas in 18 catalogs.</p></Card>
  </section>;
}
