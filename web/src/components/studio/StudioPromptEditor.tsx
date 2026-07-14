"use client";

import React from "react";
import Editor from "@monaco-editor/react";
import { FileCode } from "lucide-react";
import { cn } from "@/lib/utils";

export const SAMPLE_PROMPT_SINGLE = `You are an expert AI software engineer designed to help developers solve high-throughput coding tasks. You should be helpful, honest, and harmless. 

API KEY REQUIREMENT: Always use API_KEY_V2 header for authentication.

When answering coding questions:
1. Provide comprehensive explanations accompanied by working code snippets in Python or TypeScript.
2. Consider potential edge cases, hardware bounds, memory footprints, and exception handling.
3. If you are uncertain regarding a specific technical detail or API specification, explicitly acknowledge your uncertainty rather than inventing facts.
4. Format all technical outputs using clean GitHub-flavored markdown.
5. Include direct references and web links to official documentation when relevant.
6. Always execute unit tests locally prior to sharing production snippets.
7. Maintain detailed step-by-step reasoning for all algorithm implementations.

WARNING: Never log unencrypted secret credentials to stdout.
Ensure all database transactions use atomic rollbacks on failure.`;

export const SAMPLE_PROMPT_CHAT = `[
  {
    "role": "system",
    "content": "You are a senior PostgreSQL DBA consultant. Keep responses precise and prioritize query performance tuning."
  },
  {
    "role": "user",
    "content": "Our production database CPU spikes to 100% every midnight during analytics batch jobs. We run complex JOIN queries over a 50M row events table with unindexed JSONB metadata fields..."
  },
  {
    "role": "assistant",
    "content": "To resolve 100% CPU spikes during midnight batch processing, you must first inspect active queries using pg_stat_activity and create expression indexes on frequently queried JSONB paths..."
  }
]`;

export const SAMPLE_PROMPT_RAG = `USER QUERY: How do I handle authentication and JWT verification in FastAPI pipelines?

RETRIEVED DOCUMENT 1:
FastAPI supports security dependencies using OAuth2 with Password bearer and HTTP Basic auth out of the box. You can define security scopes using Depends(oauth2_scheme).

RETRIEVED DOCUMENT 2:
JSON Web Tokens (JWT) are decoded using python-jose or PyJWT libraries. Secret keys must be loaded securely from environment variables. Expiration timestamps (exp) must be validated on every API request.

RETRIEVED DOCUMENT 3:
For high-volume production deployments, cache decoded token claims inside Redis to prevent repetitive cryptographic signature verification latency overhead per HTTP request.`;

export interface StudioPromptEditorProps {
  value: string;
  onChange: (val: string) => void;
  mode: "prompt" | "chat" | "rag";
  onLoadPreset: (presetKey: "single" | "chat" | "rag") => void;
  tokenCount: number;
  activePreset?: "single" | "chat" | "rag";
}

export function StudioPromptEditor({
  value,
  onChange,
  mode,
  onLoadPreset,
  tokenCount,
  activePreset = "single",
}: StudioPromptEditorProps) {
  return (
    <div className="flex flex-col h-full bg-[#070A0F] border-r border-white/10 overflow-hidden font-mono text-xs">
      {/* Panel Top Bar */}
      <div className="px-4 py-3 bg-[#0D121C] border-b border-white/10 flex items-center justify-between select-none">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-emerald-400" />
          <span className="font-bold text-white uppercase text-[11px] tracking-wider font-mono">
            Input Prompt Editor
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Preset Buttons with Active State Indicators (Phase B) */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => onLoadPreset("single")}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer",
                activePreset === "single"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-bold"
                  : "bg-white/5 text-slate-400 hover:text-white border border-white/10"
              )}
            >
              System Prompt
            </button>
            <button
              onClick={() => onLoadPreset("chat")}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer",
                activePreset === "chat"
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 font-bold"
                  : "bg-white/5 text-slate-400 hover:text-white border border-white/10"
              )}
            >
              Chat Log
            </button>
            <button
              onClick={() => onLoadPreset("rag")}
              className={cn(
                "px-2 py-0.5 rounded text-[10px] font-mono transition-all cursor-pointer",
                activePreset === "rag"
                  ? "bg-violet-500/20 text-violet-400 border border-violet-500/30 font-bold"
                  : "bg-white/5 text-slate-400 hover:text-white border border-white/10"
              )}
            >
              RAG Docs
            </button>
          </div>

          <span className="px-2.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-300 text-[11px] font-mono font-bold font-tabular">
            {tokenCount.toLocaleString()} tokens
          </span>
        </div>
      </div>

      {/* Adaptive Height Flex Container (Phase B) */}
      <div className="flex-1 w-full relative min-h-[350px]">
        <Editor
          height="100%"
          language={mode === "chat" ? "json" : "markdown"}
          theme="vs-dark"
          value={value}
          onChange={(v) => onChange(v || "")}
          options={{
            minimap: { enabled: false },
            fontSize: 12,
            fontFamily: "'JetBrains Mono', 'Geist Mono', monospace",
            lineNumbers: "on",
            wordWrap: "on",
            scrollBeyondLastLine: false,
            padding: { top: 12, bottom: 12 },
            smoothScrolling: true,
            cursorBlinking: "smooth",
            renderLineHighlight: "all",
          }}
        />
      </div>
    </div>
  );
}
