"use client";

import React from "react";
import { Terminal, Heart, ArrowUpRight } from "lucide-react";
import { GithubIcon } from "@/components/icons/GithubIcon";

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#030508] pt-16 pb-12 px-4 sm:px-8">
      <div className="max-w-7xl mx-auto space-y-12">
        {/* Top Sitemap Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 font-sans">
          {/* Col 1: Brand & Logomark */}
          <div className="space-y-4 md:col-span-1">
            <a href="#" className="flex items-center gap-2.5 group">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-400 to-cyan-400 p-[1px] shadow-[0_0_15px_rgba(0,245,155,0.3)] overflow-hidden flex items-center justify-center bg-[#070A0F]">
                <img
                  src="/llmslim_logo.png"
                  alt="LLMSlim Logo"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                />
              </div>
              <span className="font-bold text-base text-white tracking-tight flex items-center gap-2 font-sans">
                LLMSlim
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono badge-scientific">
                  v0.3.0
                </span>
              </span>
            </a>
            <p className="text-xs text-slate-400 leading-relaxed max-w-xs font-sans">
              The surgical context compressor for modern AI pipelines. Cut LLM token costs by 40–70% with guaranteed 100% instruction fidelity.
            </p>
          </div>

          {/* Col 2: Product & Engine */}
          <div className="space-y-3 font-mono text-xs">
            <div className="text-slate-200 font-bold uppercase text-[11px] tracking-wider badge-scientific">Product Engine</div>
            <ul className="space-y-2 text-slate-400">
              <li><a href="#features" className="hover:text-emerald-400 transition-colors">Instruction Shield</a></li>
              <li><a href="#pipeline" className="hover:text-emerald-400 transition-colors">6-Step Compression DAG</a></li>
              <li><a href="#benchmarks" className="hover:text-emerald-400 transition-colors">Empirical Datasets</a></li>
              <li><a href="#calculator" className="hover:text-emerald-400 transition-colors">Enterprise ROI Calculator</a></li>
            </ul>
          </div>

          {/* Col 3: Integrations & API */}
          <div className="space-y-3 font-mono text-xs">
            <div className="text-slate-200 font-bold uppercase text-[11px] tracking-wider badge-scientific">SDK & API</div>
            <ul className="space-y-2 text-slate-400">
              <li><a href="#code" className="hover:text-cyan-400 transition-colors flex items-center gap-1">PyPI Package <ArrowUpRight className="w-3 h-3 opacity-60" /></a></li>
              <li><a href="#code" className="hover:text-cyan-400 transition-colors">OpenAI Integration</a></li>
              <li><a href="#code" className="hover:text-cyan-400 transition-colors">Multi-turn Chat Helper</a></li>
              <li><a href="#code" className="hover:text-cyan-400 transition-colors">RAG Document Pipeline</a></li>
            </ul>
          </div>

          {/* Col 4: Community & Legal */}
          <div className="space-y-3 font-mono text-xs">
            <div className="text-slate-200 font-bold uppercase text-[11px] tracking-wider badge-scientific">Open Source</div>
            <ul className="space-y-2 text-slate-400">
              <li>
                <a
                  href="https://github.com/Thanatos9404/llmslim"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-emerald-400 transition-colors flex items-center gap-1.5"
                >
                  <GithubIcon className="w-3.5 h-3.5" />
                  GitHub Repository
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/Thanatos9404/llmslim/blob/main/LICENSE"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-emerald-400 transition-colors"
                >
                  MIT License
                </a>
              </li>
              <li>
                <a href="#faq" className="hover:text-emerald-400 transition-colors">
                  FAQ & Telemetry
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Metadata Bar */}
        <div className="pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-mono text-slate-500">
          <div>© {new Date().getFullYear()} LLMSlim Open Source Project. All rights reserved.</div>
          <div className="flex items-center gap-1">
            Built with <Heart className="w-3 h-3 text-rose-500 fill-rose-500" /> by{" "}
            <a
              href="https://github.com/Thanatos9404"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-300 hover:text-emerald-400 font-bold underline transition-colors ml-1"
            >
              Yashvardhan Thanvi
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
