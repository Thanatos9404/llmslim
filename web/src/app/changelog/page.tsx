import { CheckCircle2, ShieldCheck, Wrench } from "lucide-react";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { constructMetadata } from "@/lib/seo";

type ReleaseItem = { label: string; icon: typeof CheckCircle2; title: string; body: string };
type Release = { version: string; date: string; theme: string; summary: string; metrics: string[]; tag: string; items: ReleaseItem[] };

const releases: Release[] = [
  {
    version: "v0.6.0",
    date: "19 Sep 2026",
    theme: "Plan the whole context, not just one string.",
    summary: "A deterministic, explainable Adaptive Context Planner with explicit hard constraints, provider-neutral model budgets, and optional Sarvam, Zoho, and MongoDB integrations.",
    metrics: ["28 frozen cases", "96.4% budget success", "100% hard-constraint retention"],
    tag: "https://github.com/Thanatos9404/llmslim/blob/main/docs/releases/v0.6.0.md",
    items: [
      { label: "Added", icon: CheckCircle2, title: "Adaptive Context Planner", body: "Multiple-choice constrained allocation selects safe representations for trusted instructions, chat, RAG, memory, tool results, and tool schemas, then explains each decision." },
      { label: "Boundary", icon: ShieldCheck, title: "Failure is explicit", body: "Required trusted content is never silently truncated. Impossible budgets produce an infeasible plan, provider candidates fail closed, and tool selection never grants execution authority." },
      { label: "Integrations", icon: Wrench, title: "Optional ecosystem adapters", body: "Official-SDK Sarvam rewriting, bounded read-only Zoho sources, and PyMongo async memory remain optional extras; the base planner stays local and provider-neutral." },
    ],
  },
  {
    version: "v0.5.0",
    date: "13 Sep 2026",
    theme: "MCP catalogs. Your host stays in control.",
    summary: "Optional MCP transports and an OpenAI Agents SDK bridge, with complete tool contracts and explicit execution ownership.",
    metrics: ["MCP + Agents extras", "Full catalog by default", "Python 3.10+ for integrations"],
    tag: "https://github.com/Thanatos9404/llmslim/releases/tag/v0.5.0",
    items: [
      { label: "Added", icon: CheckCircle2, title: "MCP catalog sources", body: "Streamable HTTP and literal-argv stdio support bounded pagination, scoped caching, contract fingerprints, and stale-plan detection." },
      { label: "Boundary", icon: ShieldCheck, title: "Execution belongs to the host", body: "The optional Agents SDK bridge requires a host callback. Full and measure-only plans retain every schema; selective exposure remains research-only." },
      { label: "Website", icon: Wrench, title: "A new home for LLMSlim", body: "A redesigned website with light and dark themes, and official Sarvam co-branding marking acceptance into the Sarvam Startup Program." },
    ],
  },
  {
    version: "v0.4.0",
    date: "21 Aug 2026",
    theme: "Contract-safe tool context.",
    summary: "This Python release adds stable, conservative tool-schema infrastructure while keeping retrieval and selective exposure research-only.",
    metrics: ["489 / 0 tests", "90.93% coverage", "375 schemas / 18 catalogs"],
    tag: "https://github.com/Thanatos9404/llmslim/releases/tag/v0.4.0",
    items: [
      { label: "Added", icon: CheckCircle2, title: "Stable tool-contract APIs", body: "The released tool surface supports copied schema normalization, deterministic canonical JSON, SHA-256 fingerprints, exact contract checks, and safe catalog optimization." },
      { label: "Boundary", icon: ShieldCheck, title: "Retrieval remains research-only", body: "Lexical, dense, hybrid retrieval, selective exposure, and lazy hydration are explicit experiments. They do not authorize or execute tools, and compress() keeps its established behavior." },
      { label: "Measured", icon: CheckCircle2, title: "Schema-tax evidence stays transparent", body: "The v0.4.0 release gate records 489 passing tests, 90.93% coverage, and 375 generated tool schemas in 18 catalogs. The compact baseline produced 0.00% lossless reduction." },
    ],
  },
  {
    version: "v0.3.1",
    date: "13 Aug 2026",
    theme: "Provenance and verification.",
    summary: "This security-focused Python release strengthens caller-declared trust boundaries and makes token-counter provenance visible in the public result.",
    metrics: ["432 / 0 tests", "92.57% coverage", "Ruff passed"],
    tag: "https://github.com/Thanatos9404/llmslim/blob/main/release_notes.md",
    items: [
      { label: "Security", icon: ShieldCheck, title: "Provenance-aware priority locking", body: "ContextRole distinguishes system, developer, user, assistant, tool, RAG, and general content. Untrusted RAG, tool, and assistant text cannot become hard-locked priority from imperative wording, safety patterns, or preserve patterns." },
      { label: "Security", icon: ShieldCheck, title: "Nonce-protected rewrite template fences", body: "User text containing a template-fence-like delimiter remains byte-for-byte unchanged while the template uses a content-preserving nonce fence, preventing fence breakout." },
      { label: "Added", icon: CheckCircle2, title: "Context roles and token-counter telemetry", body: "The public Python API exports ContextRole and records token_counter_used so callers can distinguish tiktoken from the documented heuristic fallback." },
      { label: "Fixed", icon: CheckCircle2, title: "Inline code and CJK sentence boundaries", body: "Inline backtick code spans no longer create false sentence boundaries, and the CJK ideographic stops 。, ！, and ？ are recognized by the sentence-splitting paths." },
      { label: "Changed", icon: Wrench, title: "Pipelines preserve provenance", body: "Document compression defaults retrieved context to RAG, while chat compression propagates supplied system, developer, user, assistant, and tool roles instead of flattening them." },
      { label: "Fixed", icon: CheckCircle2, title: "Benchmark collection reports real pytest results", body: "The release runner collects actual pass/fail reports rather than replaying stale tuples. The checked-in release record reports 432 passing tests, zero failures, 92.57% branch coverage, and Ruff passing." },
    ],
  },
  {
    version: "v0.3.0",
    date: "18 Jul 2026",
    theme: "Hybrid prompt optimization.",
    summary: "v0.3.0 expanded the package from its offline extractive default into an extensible rewrite and hybrid framework without bundling an LLM provider.",
    metrics: ["Extractive default", "Provider abstraction", "Validation pipeline"],
    tag: "https://github.com/Thanatos9404/llmslim/tree/v0.3.0",
    items: [
      { label: "Added", icon: CheckCircle2, title: "Rewrite and hybrid strategies", body: "compress() gained extractive, rewrite, and hybrid strategies. Rewrite-capable paths require a caller-supplied provider; the default extractive path remains offline and deterministic." },
      { label: "Added", icon: CheckCircle2, title: "Provider and validation contracts", body: "BaseRewriteProvider, CallableProvider, RewriteRequest, RewriteMetadata, versioned templates, and structural, instruction, entity, and similarity validation were added as public building blocks." },
      { label: "Changed", icon: Wrench, title: "Rewrite work moved into a focused sub-package", body: "Prompt construction, execution, and validation were separated into llmslim.rewrite modules, with strategy benchmarking and a CLI strategy flag added alongside them." },
    ],
  },
  {
    version: "v0.2.0",
    date: "13 Jul 2026",
    theme: "High-performance semantic compression.",
    summary: "v0.2.0 deepened the original extractive engine with instruction and entity protection, chunking improvements, cost tooling, and a fuller command-line and benchmark surface.",
    metrics: ["Instruction retention", "Entity preservation", "CLI + benchmarks"],
    tag: "https://github.com/Thanatos9404/llmslim/tree/v0.2.0",
    items: [
      { label: "Added", icon: CheckCircle2, title: "Instruction and entity retention", body: "The release added explicit instruction prioritization plus regex and heuristic preservation for names, dates, financial metrics, technical identifiers, and URLs." },
      { label: "Added", icon: CheckCircle2, title: "Chunking, embeddings, and cost tooling", body: "It introduced semantic and hybrid chunking, optional sentence-transformers support, model cost estimation, an interactive/file-based CLI, and comprehensive benchmark tooling." },
      { label: "Changed", icon: Wrench, title: "Richer ranking and result telemetry", body: "TF-IDF plus PageRank-style sentence centrality, optional tiktoken accounting, and a standardized CompressionResult with detailed telemetry became part of the release." },
    ],
  },
  {
    version: "v0.1.0",
    date: "16 Jun 2026",
    theme: "Initial public release.",
    summary: "The first LLMSlim release established the installable Python package and its simple offline compression entry point.",
    metrics: ["Python 3.8+", "TF-IDF ranking", "Public compress() API"],
    tag: "https://github.com/Thanatos9404/llmslim/tree/v0.1.0",
    items: [
      { label: "Added", icon: CheckCircle2, title: "Installable LLMSlim package", body: "v0.1.0 published the llmslim package for Python 3.8+ with the public compress(), ContextCompressor, CompressionResult, token, pipeline, and cost utility exports." },
      { label: "Added", icon: CheckCircle2, title: "Offline prompt compression foundation", body: "The initial engine provided ratio-driven prompt compression using TF-IDF sentence scoring and thresholding, with optional semantic, fast-token, and NLTK extras." },
    ],
  },
];

export const metadata = constructMetadata({
  title: "LLMSlim release history | Changelog",
  description: "Verified LLMSlim Python package history for v0.1.0 through v0.6.0, including release themes, compatibility, and security changes.",
});

export default function ChangelogPage() {
  return <div className="flex min-h-screen flex-col"><SiteHeader /><main id="main-content" className="mx-auto w-full max-w-5xl flex-1 space-y-8 px-4 py-10 sm:px-6 lg:px-8"><header><Badge variant="secondary">Release history</Badge><h1 className="mt-4 text-4xl font-semibold tracking-tight">Changes with consequences.</h1><p className="mt-3 max-w-3xl text-muted-foreground">LLMSlim releases document what shipped, what changed, and where the boundary remains.</p></header>{releases.map((release) => <Card key={release.version}><CardHeader><div className="flex flex-wrap items-center gap-2"><Badge>{release.version}</Badge><Badge variant="outline">{release.date}</Badge></div><CardTitle className="mt-2 text-2xl">{release.theme}</CardTitle><CardDescription>{release.summary}</CardDescription></CardHeader><CardContent className="space-y-5"><div className="flex flex-wrap gap-2">{release.metrics.map((metric) => <Badge key={metric} variant="secondary">{metric}</Badge>)}</div><div className="space-y-4">{release.items.map((item) => { const Icon = item.icon; return <div key={item.title} className="flex gap-3"><Icon className="mt-0.5 size-5 shrink-0" /><div><p className="text-sm font-medium">{item.title}</p><p className="mt-1 text-sm leading-6 text-muted-foreground">{item.body}</p></div></div> })}</div></CardContent><CardFooter><Button variant="outline" size="sm" render={<a href={release.tag} target="_blank" rel="noreferrer" />}>View verified source</Button></CardFooter></Card>)}</main><SiteFooter /></div>;
}
