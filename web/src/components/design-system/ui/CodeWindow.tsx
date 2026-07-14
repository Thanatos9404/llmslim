"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Copy, Check, Terminal } from "lucide-react";

export interface CodeTab {
  id: string;
  title: string;
  code: string;
  language?: string;
}

export interface CodeWindowProps {
  tabs?: CodeTab[];
  singleCode?: string;
  title?: string;
  showLineNumbers?: boolean;
  className?: string;
}

export function CodeWindow({
  tabs,
  singleCode,
  title = "llmslim_quickstart.py",
  showLineNumbers = true,
  className,
}: CodeWindowProps) {
  const activeTabList = tabs || [
    {
      id: "python",
      title: title,
      code: singleCode || `from llmslim import compress\n\n# Compress massive prompt in 1 line\nresult = compress(your_prompt, target_ratio=0.5)\n\nprint(result.compressed_text)    # → 52.3% fewer tokens\nprint(result.tokens_saved)       # → 1,847 tokens saved\nprint(result.summary())          # → Full telemetry stats`,
    },
  ];

  const [activeTabId, setActiveTabId] = useState(activeTabList[0].id);
  const [copied, setCopied] = useState(false);

  const activeTab = activeTabList.find((t) => t.id === activeTabId) || activeTabList[0];

  const handleCopy = () => {
    navigator.clipboard.writeText(activeTab.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = activeTab.code.split("\n");

  return (
    <div
      className={cn(
        "rounded-2xl bg-[#0D121C] border border-white/10 overflow-hidden shadow-2xl backdrop-blur-xl font-mono text-xs text-slate-200 select-text",
        "before:block before:h-[1px] before:w-full before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent",
        className
      )}
    >
      {/* Top Bar with Window Dots & Tabs */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#070A0F] border-b border-white/10 select-none">
        <div className="flex items-center gap-3">
          {/* macOS Controls */}
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-[#FF5F56] inline-block" />
            <span className="w-3 h-3 rounded-full bg-[#FFBD2E] inline-block" />
            <span className="w-3 h-3 rounded-full bg-[#27C93F] inline-block" />
          </div>

          {/* Tab Buttons */}
          <div className="flex items-center gap-1 ml-3 overflow-x-auto">
            {activeTabList.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTabId(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono transition-colors cursor-pointer",
                  activeTabId === tab.id
                    ? "bg-white/10 text-emerald-400 border border-white/10"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                )}
              >
                <Terminal className="w-3 h-3 text-slate-500" />
                {tab.title}
              </button>
            ))}
          </div>
        </div>

        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white transition-all cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-bold">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5 text-slate-400" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code Editor Body */}
      <div className="p-4 sm:p-6 overflow-x-auto bg-[#070A0F]/60">
        <pre className="flex flex-col gap-1.5">
          {lines.map((line, idx) => (
            <div key={idx} className="table-row">
              {showLineNumbers && (
                <span className="table-cell select-none text-right pr-4 text-slate-600 font-mono w-8">
                  {idx + 1}
                </span>
              )}
              <span className="table-cell font-mono leading-relaxed">
                {formatCodeLine(line)}
              </span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}

// Custom syntax color formatter matching LLMSlim Palette
function formatCodeLine(line: string) {
  if (line.trim().startsWith("#")) {
    return <span className="text-slate-500 italic">{line}</span>;
  }

  // Token syntax replaces for standard Python statements
  const tokens = line.split(/(\s+)/);

  return tokens.map((token, i) => {
    if (["from", "import", "def", "class", "return", "if", "for", "in", "as"].includes(token)) {
      return (
        <span key={i} className="text-violet-400 font-semibold">
          {token}
        </span>
      );
    }
    if (["compress", "compress_chat_messages", "compress_documents", "print"].includes(token)) {
      return (
        <span key={i} className="text-cyan-400 font-bold">
          {token}
        </span>
      );
    }
    if (token.startsWith('"') || token.startsWith("'")) {
      return (
        <span key={i} className="text-emerald-300">
          {token}
        </span>
      );
    }
    if (!isNaN(Number(token))) {
      return (
        <span key={i} className="text-pink-400 font-mono">
          {token}
        </span>
      );
    }
    return <span key={i}>{token}</span>;
  });
}
