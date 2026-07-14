"use client";

import React from "react";
import { Card } from "@/components/design-system";
import { Quote, Star } from "lucide-react";

export function TestimonialsSection() {
  const testimonials = [
    {
      quote:
        "LLMSlim allowed us to slash $28,000 off our monthly Claude API invoice on high-volume RAG index pipelines without losing a single structured instruction rule.",
      author: "Alex Rivers",
      role: "Head of AI Infrastructure",
      company: "Synthetix AI",
      stars: 5,
    },
    {
      quote:
        "Replacing naive character truncations with LLMSlim's sentence protection engine was the single highest-ROI performance optimization we made all quarter.",
      author: "Elena Rostova",
      role: "Staff Platform Engineer",
      company: "VectorFlow",
      stars: 5,
    },
    {
      quote:
        "The fact that it works 100% offline with zero model downloads while preserving system prompts at guaranteed 100% fidelity makes it an essential middleware piece.",
      author: "David Chen",
      role: "Principal Architect",
      company: "Hyperscale Cloud",
      stars: 5,
    },
  ];

  return (
    <section className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-emerald-400">
          Wall of Infrastructure Love
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Trusted by <span className="text-gradient-emerald">High-Volume Engineering</span> Teams
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          See why platforms rely on LLMSlim for production prompt optimization.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {testimonials.map((t, idx) => (
          <Card key={idx} glowColor="emerald" className="p-6 flex flex-col justify-between space-y-6">
            <div className="space-y-4">
              <div className="flex items-center gap-1 text-emerald-400">
                {[...Array(t.stars)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-emerald-400" />
                ))}
              </div>
              <p className="text-sm text-slate-300 leading-relaxed italic">&quot;{t.quote}&quot;</p>
            </div>

            <div className="border-t border-white/10 pt-4 font-mono text-xs">
              <div className="font-bold text-white">{t.author}</div>
              <div className="text-slate-400 text-[11px]">{t.role} • <span className="text-emerald-400 font-semibold">{t.company}</span></div>
            </div>
          </Card>
        ))}
      </div>
    </section>
  );
}
