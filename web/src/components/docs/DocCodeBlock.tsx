"use client";

import React, { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";

export function DocCodeBlock({
  language = "bash",
  filename,
  code,
}: {
  language?: string;
  filename?: string;
  code: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-6 rounded-2xl bg-[#0D121C] border border-white/15 border-specular-emerald overflow-hidden shadow-2xl font-mono text-xs select-text">
      {/* Code Header Bar */}
      <div className="px-4 py-2.5 bg-[#070A0F] border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-emerald-400" />
          {filename && <span className="font-bold text-slate-300">{filename}</span>}
          {!filename && <span className="text-slate-500 uppercase tracking-widest text-[10px]">{language}</span>}
        </div>
        <button
          onClick={handleCopy}
          aria-label="Copy code block snippet"
          title="Copy code to clipboard"
          className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-400 hover:text-white transition-all cursor-pointer min-h-[32px] min-w-[32px] flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Code Area */}
      <div className="p-4 sm:p-5 overflow-x-auto text-slate-200 leading-relaxed font-mono">
        <pre>
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
}
