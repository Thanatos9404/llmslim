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
import { Building2, Code, Cpu, Database, Layers, Server } from "lucide-react";

export function IntegrationIcon({ iconKey, className = "w-8 h-8" }: { iconKey: string; className?: string }) {
  switch (iconKey) {
    case "sarvam":
      return <span role="img" aria-label="Sarvam" className={className} style={{ display: "inline-block", background: "currentColor", mask: "url('/sarvam-symbol.svg') center / contain no-repeat" }} />;
    case "zoho":
      return <Building2 className={`${className} text-red-400`} />;
    case "mongodb":
      return <Database className={`${className} text-emerald-500`} />;
    case "openai":
      return <OpenAI className={className} size={32} />;
    case "anthropic":
      return <Anthropic className={className} size={32} />;
    case "gemini":
      return <Gemini className={className} size={32} />;
    case "groq":
      return <Groq className={className} size={32} />;
    case "mistral":
      return <Mistral className={className} size={32} />;
    case "ollama":
      return <Ollama className={className} size={32} />;
    case "langchain":
      return <LangChain className={className} size={32} />;
    case "llamaindex":
      return <LlamaIndex className={className} size={32} />;
    case "vercel":
      return <Vercel className={className} size={32} />;
    case "fastapi":
      return <Server className={`${className} text-emerald-400`} />;
    case "crewai":
      return <Cpu className={`${className} text-cyan-400`} />;
    case "mastra":
      return <Layers className={`${className} text-emerald-400`} />;
    default:
      return <Code className={`${className} text-emerald-400`} />;
  }
}
