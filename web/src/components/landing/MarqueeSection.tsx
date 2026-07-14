"use client";

import React from "react";
import {
  OpenAI,
  Anthropic,
  Gemini,
  Groq,
  Mistral,
  Ollama,
  LangChain,
  LlamaIndex,
  Vercel,
} from "@lobehub/icons";
import { Cpu, Server, Layers } from "lucide-react";

export function MarqueeSection() {
  const providers = [
    {
      name: "OpenAI",
      icon: <OpenAI size={26} className="h-6.5 w-auto" aria-hidden="true" />,
    },
    {
      name: "Anthropic",
      icon: <Anthropic size={24} className="h-6 w-auto" aria-hidden="true" />,
    },
    {
      name: "Gemini",
      icon: <Gemini size={26} className="h-6.5 w-auto" aria-hidden="true" />,
    },
    {
      name: "Groq",
      icon: <Groq size={26} className="h-6.5 w-auto" aria-hidden="true" />,
    },
    {
      name: "Mistral",
      icon: <Mistral size={24} className="h-6 w-auto" aria-hidden="true" />,
    },
    {
      name: "Ollama",
      icon: <Ollama size={26} className="h-6.5 w-auto" aria-hidden="true" />,
    },
    {
      name: "LangChain",
      icon: <LangChain size={26} className="h-6.5 w-auto" aria-hidden="true" />,
    },
    {
      name: "LlamaIndex",
      icon: <LlamaIndex size={26} className="h-6.5 w-auto" aria-hidden="true" />,
    },
    {
      name: "CrewAI",
      icon: <Cpu className="h-6 w-6 text-cyan-400" aria-hidden="true" />,
    },
    {
      name: "Vercel AI SDK",
      icon: <Vercel size={24} className="h-6 w-auto" aria-hidden="true" />,
    },
    {
      name: "Mastra",
      icon: <Layers className="h-6 w-6 text-emerald-400" aria-hidden="true" />,
    },
    {
      name: "FastAPI",
      icon: <Server className="h-6 w-6 text-emerald-400" aria-hidden="true" />,
    },
  ];

  return (
    <section aria-label="Ecosystem Compatibility Marquee" className="py-14 border-y border-white/10 bg-[#070A0F]/80 overflow-hidden select-none">
      {/* Section Subtitle Heading */}
      <div className="max-w-7xl mx-auto px-4 text-center mb-8">
        <h2 className="badge-scientific text-slate-400 text-xs tracking-widest uppercase font-mono">
          Works with every major LLM ecosystem
        </h2>
      </div>

      {/* Infinite Seamless Marquee with CSS Mask Feathering & Hover Pause */}
      <div className="relative flex overflow-hidden [mask-image:linear-gradient(90deg,transparent_0%,black_15%,black_85%,transparent_100%)]">
        <div className="flex shrink-0 gap-16 sm:gap-24 items-center animate-marquee hover:[animation-play-state:paused] py-2">
          {[...providers, ...providers].map((item, idx) => (
            <div
              key={idx}
              title={`${item.name} Integration`}
              aria-label={`${item.name} ecosystem integration`}
              className="flex items-center gap-3 text-slate-400 opacity-70 hover:opacity-100 hover:text-white transition-all duration-300 cursor-pointer hover:drop-shadow-[0_0_14px_rgba(0,245,155,0.45)] shrink-0 group"
            >
              <div className="text-slate-300 group-hover:text-emerald-400 transition-colors flex items-center justify-center">
                {item.icon}
              </div>
              <span className="font-sans font-bold text-sm tracking-tight text-slate-200 group-hover:text-white transition-colors">
                {item.name}
              </span>
            </div>
          ))}
        </div>

        {/* Second Duplicate Infinite Loop for Zero Gap Seamless Scroll */}
        <div
          aria-hidden="true"
          className="flex shrink-0 gap-16 sm:gap-24 items-center animate-marquee hover:[animation-play-state:paused] py-2 ml-16 sm:ml-24"
        >
          {[...providers, ...providers].map((item, idx) => (
            <div
              key={`dup-${idx}`}
              title={`${item.name} Integration`}
              aria-label={`${item.name} ecosystem integration`}
              className="flex items-center gap-3 text-slate-400 opacity-70 hover:opacity-100 hover:text-white transition-all duration-300 cursor-pointer hover:drop-shadow-[0_0_14px_rgba(0,245,155,0.45)] shrink-0 group"
            >
              <div className="text-slate-300 group-hover:text-emerald-400 transition-colors flex items-center justify-center">
                {item.icon}
              </div>
              <span className="font-sans font-bold text-sm tracking-tight text-slate-200 group-hover:text-white transition-colors">
                {item.name}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
