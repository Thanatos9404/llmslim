"use client";

import React from "react";
import Link from "next/link";
import { Heart } from "lucide-react";
import { GithubIcon } from "@/components/icons/GithubIcon";

export function Footer() {
  return <footer className="border-t border-white/10 bg-[#070A0F] py-12 px-4 sm:px-8">
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex flex-col sm:flex-row items-start justify-between gap-6">
        <div className="space-y-2"><div className="font-bold text-white">LLMSlim <span className="ml-2 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono">v0.3.1</span></div><p className="text-xs text-slate-400 max-w-sm">Python context compression with provenance-aware priority handling for modern AI pipelines.</p></div>
        <div className="flex gap-5 text-xs font-mono"><Link href="/docs" className="text-slate-400 hover:text-emerald-400">Documentation</Link><Link href="/benchmarks" className="text-slate-400 hover:text-emerald-400">Verification</Link><a href="https://github.com/Thanatos9404/llmslim" className="text-slate-400 hover:text-emerald-400 flex items-center gap-1"><GithubIcon className="w-3.5 h-3.5" />GitHub</a></div>
      </div>
      <div className="pt-6 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs font-mono text-slate-500"><span>© {new Date().getFullYear()} LLMSlim Open Source Project.</span><span className="flex items-center gap-1">Built with <Heart className="w-3 h-3 text-rose-500 fill-rose-500" /> by Yashvardhan Thanvi</span></div>
    </div>
  </footer>;
}
