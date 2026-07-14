import React from "react";
import Link from "next/link";
import { constructMetadata } from "@/lib/seo";
import { ClientStudioWrapper } from "@/components/studio/ClientStudioWrapper";
import { Cpu, ShieldCheck, Zap, Sliders, ArrowRight, BookOpen, BarChart3 } from "lucide-react";
import { GithubIcon } from "@/components/icons/GithubIcon";
import { Card } from "@/components/design-system";

export const metadata = constructMetadata({
  title: "LLMSlim Studio | Interactive Prompt Compression Playground",
  description: "Compress prompts interactively in real-time. Test sentence centrality, JSON schema safety shields, and token savings across OpenAI, Claude, and local models.",
  canonicalUrl: "https://llmslim.app/playground",
});

export default function PlaygroundPage() {
  const softwareAppSchema = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "LLMSlim Studio Playground",
    operatingSystem: "Web",
    applicationCategory: "DeveloperApplication",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    description: "Interactive real-time prompt context compressor and token savings analyzer for OpenAI, Claude, Gemini, and local LLMs.",
    url: "https://llmslim.app/playground",
  };

  const breadcrumbSchema = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: "https://llmslim.app",
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Playground",
        item: "https://llmslim.app/playground",
      },
    ],
  };

  return (
    <div className="space-y-12 font-sans">
      {/* JSON-LD Structured Data Schema Insertion */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareAppSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbSchema) }}
      />

      {/* Header Banner */}
      <div className="space-y-4 max-w-4xl">
        <div className="inline-flex items-center gap-2.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          <Cpu className="w-3.5 h-3.5" />
          <span>Interactive Context Compression Sandbox</span>
          <span className="text-slate-500">|</span>
          <span className="text-slate-300 font-semibold flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            Priority Tier 4 Safeguards
          </span>
        </div>

        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          LLMSlim <span className="text-gradient-emerald">Studio Playground</span>
        </h1>

        <p className="text-slate-400 text-base leading-relaxed">
          Test sentence centrality scoring, live target ratios, and syntax safety shields in real-time. Input your raw prompt context, adjust parameters, and generate production-ready Python & TypeScript code wrappers.
        </p>
      </div>

      {/* Main Interactive Studio Engine Centerpiece */}
      <section id="studio-workspace" aria-label="Interactive Studio Workspace" className="space-y-3">
        <div className="flex items-center justify-between px-1 font-mono text-xs text-slate-400">
          <span className="text-emerald-400 font-bold flex items-center gap-2">
            <Sliders className="w-4 h-4" />
            3-Panel Compression Workbench
          </span>
          <span className="text-slate-500 hidden sm:inline">
            Sub-30ms Offline CPU Simulation
          </span>
        </div>

        <ClientStudioWrapper />
      </section>

      {/* Studio Usage Capabilities & Feature Cards */}
      <section id="capabilities" className="space-y-6 pt-4 border-t border-white/10">
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <Zap className="w-5 h-5 text-emerald-400" /> Key Playground Capabilities
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card glowColor="emerald" className="p-6 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-mono font-bold text-sm">
              01
            </div>
            <h3 className="text-lg font-bold text-white">Preset Scenarios</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Load realistic prompt benchmarks: Verbose Chat Messages, RAG Document Searches, Complex System Directives, or Code Generator prompts.
            </p>
          </Card>

          <Card glowColor="cyan" className="p-6 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 font-mono font-bold text-sm">
              02
            </div>
            <h3 className="text-lg font-bold text-white">Priority Tier Shielding</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Observe how LLMSlim automatically locks imperative rules (<code className="text-emerald-400">must</code>, <code className="text-emerald-400">never</code>) and code fences to guarantee zero instruction loss.
            </p>
          </Card>

          <Card glowColor="violet" className="p-6 space-y-3">
            <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400 font-mono font-bold text-sm">
              03
            </div>
            <h3 className="text-lg font-bold text-white">Code Generator</h3>
            <p className="text-slate-400 text-xs leading-relaxed">
              Instantly export copyable, production-ready Python SDK or TypeScript `@llmslim/core` integration snippets pre-configured with your active parameters.
            </p>
          </Card>
        </div>
      </section>

      {/* Navigation Links Back to Documentation and Benchmarks */}
      <section id="next-steps" className="p-8 rounded-2xl bg-[#0D121C] border border-white/10 space-y-6">
        <h2 className="text-xl font-bold text-white tracking-tight">
          Ready to deploy prompt compression to production?
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Link href="/docs/getting-started" className="group p-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all">
            <div className="flex items-center justify-between text-xs font-mono text-emerald-400 font-bold mb-1">
              <span className="flex items-center gap-1.5"><BookOpen className="w-3.5 h-3.5" /> Documentation</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
            <p className="text-slate-300 text-xs font-sans">Read integration guides & API references.</p>
          </Link>

          <Link href="/benchmarks" className="group p-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all">
            <div className="flex items-center justify-between text-xs font-mono text-cyan-400 font-bold mb-1">
              <span className="flex items-center gap-1.5"><BarChart3 className="w-3.5 h-3.5" /> Open Benchmarks</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
            <p className="text-slate-300 text-xs font-sans">Explore reproducible metric suites & data.</p>
          </Link>

          <a href="https://github.com/Thanatos9404/llmslim" target="_blank" rel="noopener noreferrer" className="group p-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all">
            <div className="flex items-center justify-between text-xs font-mono text-violet-400 font-bold mb-1">
              <span className="flex items-center gap-1.5"><GithubIcon className="w-3.5 h-3.5" /> Source Code</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
            <p className="text-slate-300 text-xs font-sans">View open-source repository on GitHub.</p>
          </a>
        </div>
      </section>
    </div>
  );
}
