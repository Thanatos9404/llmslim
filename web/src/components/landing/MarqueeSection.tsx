"use client";

import React from "react";
import { motion } from "framer-motion";

export function MarqueeSection() {
  const logos = [
    {
      name: "OpenAI",
      svg: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-6 w-auto">
          <path d="M12 2a10 10 0 0 0-7.3 3.2m14.6 0A10 10 0 0 0 12 2M2.5 9.5a10 10 0 0 0 1.2 7.8m16.6-7.8a10 10 0 0 1 1.2 7.8M6.2 20.3A10 10 0 0 0 12 22m5.8-1.7a10 10 0 0 0 0-16.6" />
          <path d="M12 6v12m-5.2-9 10.4 6m0-6L6.8 15" />
        </svg>
      ),
    },
    {
      name: "Anthropic",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-auto">
          <path d="M14.2 3.5h3.6L24 20.5h-3.6l-1.6-3.8h-5.6l-1.6 3.8H8l6.2-17zm3.1 10.3l-2-4.9-2 4.9h4zM0 20.5l6.2-17h3.6L3.6 20.5H0z" />
        </svg>
      ),
    },
    {
      name: "Google Gemini",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-6 w-auto">
          <path d="M12 0C12 6.627 6.627 12 0 12c6.627 0 12 5.373 12 12 0-6.627 5.373-12 12-12C17.373 12 12 6.627 12 0z" />
        </svg>
      ),
    },
    {
      name: "DeepSeek",
      svg: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-6 w-auto">
          <circle cx="12" cy="12" r="9" />
          <ellipse cx="12" cy="12" rx="9" ry="4" transform="rotate(-30 12 12)" />
          <circle cx="12" cy="12" r="3" fill="currentColor" />
        </svg>
      ),
    },
    {
      name: "Meta Llama",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-auto">
          <path d="M17.5 3c-2.4 0-4.6 1.4-5.5 3.4C11.1 4.4 8.9 3 6.5 3 2.9 3 0 5.9 0 9.5c0 4.9 6.2 10.4 11.4 11.4h1.2C17.8 19.9 24 14.4 24 9.5 24 5.9 21.1 3 17.5 3zm-11 11c-2.2 0-4-1.8-4-4s1.8-4 4-4 4 1.8 4 4-1.8 4-4 4zm11 0c-2.2 0-4-1.8-4-4s1.8-4 4-4 4 1.8 4 4-1.8 4-4 4z" />
        </svg>
      ),
    },
    {
      name: "Mistral AI",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-auto">
          <path d="M2 3h4v4H2V3zm14 0h4v4h-4V3zm-7 7h4v4H9v-4zM2 17h4v4H2v-4zm14 0h4v4h-4v-4zM2 10h4v4H2v-4zm14 0h4v4h-4v-4zM9 3h4v4H9V3z" />
        </svg>
      ),
    },
    {
      name: "Cohere",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-6 w-auto">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14.5v-9l7 4.5-7 4.5z" />
        </svg>
      ),
    },
    {
      name: "xAI",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-auto">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      ),
    },
    {
      name: "Qwen",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-6 w-auto">
          <path d="M12 2L2 12l10 10 10-10L12 2zm0 4.5L17.5 12 12 17.5 6.5 12 12 6.5z" />
        </svg>
      ),
    },
    {
      name: "Microsoft Azure AI",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-auto">
          <path d="M0 0h11v11H0V0zm13 0h11v11H13V0zM0 13h11v11H0V13zm13 0h11v11H13V13z" />
        </svg>
      ),
    },
    {
      name: "LangChain",
      svg: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-6 w-auto">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
      ),
    },
    {
      name: "LlamaIndex",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-6 w-auto">
          <path d="M4 2h16v4H4V2zm0 7h16v4H4V9zm0 7h10v4H4v-4z" />
        </svg>
      ),
    },
    {
      name: "CrewAI",
      svg: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-6 w-auto">
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="6" r="3" />
          <circle cx="18" cy="18" r="3" />
          <path d="M8.7 10.7l6.6-3.4M8.7 13.3l6.6 3.4" />
        </svg>
      ),
    },
    {
      name: "Haystack",
      svg: (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-6 w-auto">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
      ),
    },
    {
      name: "DSPy",
      svg: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-6 w-auto">
          <rect x="3" y="3" width="18" height="18" rx="4" />
          <path d="M7 8h10M7 12h7M7 16h4" />
        </svg>
      ),
    },
  ];

  return (
    <section className="py-14 border-y border-white/10 bg-[#070A0F]/80 overflow-hidden select-none">
      {/* Subtle Section Subtitle Heading */}
      <div className="max-w-7xl mx-auto px-4 text-center mb-8">
        <span className="badge-scientific text-slate-400 text-xs tracking-widest uppercase">
          Works with every major LLM ecosystem
        </span>
      </div>

      {/* Infinite Seamless Marquee with CSS Mask Feathering & Hover Pause */}
      <div className="relative flex overflow-hidden [mask-image:linear-gradient(90deg,transparent_0%,black_15%,black_85%,transparent_100%)]">
        <div className="flex shrink-0 gap-16 sm:gap-24 items-center animate-marquee hover:[animation-play-state:paused] py-2">
          {[...logos, ...logos].map((logo, idx) => (
            <div
              key={idx}
              className="flex items-center gap-3 text-slate-400 opacity-70 hover:opacity-100 hover:text-white transition-all duration-300 cursor-pointer hover:drop-shadow-[0_0_14px_rgba(0,245,155,0.45)] shrink-0 group"
            >
              <div className="text-slate-300 group-hover:text-emerald-400 transition-colors">
                {logo.svg}
              </div>
              <span className="font-sans font-bold text-sm tracking-tight text-slate-200 group-hover:text-white transition-colors">
                {logo.name}
              </span>
            </div>
          ))}
        </div>

        {/* Second Duplicate Infinite Loop for Zero Gap Seamless Scroll */}
        <div
          aria-hidden="true"
          className="flex shrink-0 gap-16 sm:gap-24 items-center animate-marquee hover:[animation-play-state:paused] py-2 ml-16 sm:ml-24"
        >
          {[...logos, ...logos].map((logo, idx) => (
            <div
              key={`dup-${idx}`}
              className="flex items-center gap-3 text-slate-400 opacity-70 hover:opacity-100 hover:text-white transition-all duration-300 cursor-pointer hover:drop-shadow-[0_0_14px_rgba(0,245,155,0.45)] shrink-0 group"
            >
              <div className="text-slate-300 group-hover:text-emerald-400 transition-colors">
                {logo.svg}
              </div>
              <span className="font-sans font-bold text-sm tracking-tight text-slate-200 group-hover:text-white transition-colors">
                {logo.name}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
