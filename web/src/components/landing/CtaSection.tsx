"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { AnimatedButton, Card } from "@/components/design-system";
import { Terminal, Copy, Check, Sparkles, ArrowRight } from "lucide-react";
import { GithubIcon } from "@/components/icons/GithubIcon";

export function CtaSection() {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText("pip install llmslim");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="py-24 px-4 sm:px-8 max-w-5xl mx-auto text-center relative overflow-hidden">
      <Card glowColor="emerald" className="p-8 sm:p-14 space-y-8 relative z-10 overflow-hidden">
        <div className="space-y-4 max-w-2xl mx-auto">
          <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
            <Sparkles className="w-3.5 h-3.5" />
            Start Saving Tokens Today
          </span>
          <h2 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight leading-tight">
            Ready to Cut Your <span className="text-gradient-emerald">API Invoices?</span>
          </h2>
          <p className="text-slate-400 text-base sm:text-lg leading-relaxed font-normal">
            Install LLMSlim in 30 seconds and start compressing RAG contexts, prompt instructions, and chat histories with zero setup complexity.
          </p>
        </div>

        {/* Terminal Copy Box */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-2">
          <div className="flex items-center gap-3 px-5 py-3.5 rounded-2xl bg-[#070A0F] border border-white/15 font-mono text-sm text-slate-200 shadow-2xl">
            <Terminal className="w-4 h-4 text-emerald-400 shrink-0" />
            <span className="text-slate-500">$</span>
            <span className="font-bold text-white">pip install llmslim</span>
            <button
              onClick={handleCopy}
              className="ml-3 p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white transition-all cursor-pointer"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>

          <AnimatedButton
            variant="quantum"
            size="lg"
            icon={<GithubIcon className="w-4 h-4" />}
            onClick={() => window.open("https://github.com/Thanatos9404/llmslim", "_blank")}
          >
            Star Repository on GitHub
          </AnimatedButton>
        </div>
      </Card>
    </section>
  );
}
