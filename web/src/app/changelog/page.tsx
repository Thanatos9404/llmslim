import { CheckCircle2, ShieldCheck, Wrench } from "lucide-react";
import { Footer } from "@/components/landing/Footer";
import { Navbar } from "@/components/landing/Navbar";
import { constructMetadata } from "@/lib/seo";

type ReleaseItem = { label: string; icon: typeof CheckCircle2; title: string; body: string };
type Release = { version: string; date: string; theme: string; summary: string; metrics: string[]; tag: string; items: ReleaseItem[] };

const releases: Release[] = [
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
  description: "Verified LLMSlim Python package history for v0.1.0 through v0.4.0, including release themes, compatibility, and security changes.",
});

export default function ChangelogPage() {
  return <div className="site-shell"><Navbar /><main id="main-content" className="changelog-page"><header className="hub-header"><span className="hub-eyebrow">Release history</span><h1>Changes with <span>consequences.</span></h1><p>LLMSlim releases document what shipped, what changed, and where the boundary remains. Phase 2 is an engineering and benchmark milestone—not an invented package version.</p></header>{releases.map((release) => <section key={release.version} aria-label={`${release.version} release notes`}><section className="release-card"><div className="release-card__side"><span>Python release</span><strong>{release.version}</strong><small>{release.date}</small><i>Released</i></div><div className="release-card__content"><h2>{release.theme}</h2><p>{release.summary}</p><div className="release-card__metrics">{release.metrics.map((metric) => <span key={metric}>{metric}</span>)}</div><a href={release.tag} target="_blank" rel="noreferrer">View verified source ↗</a></div></section><section className="release-timeline" aria-label={`${release.version} changes`}>{release.items.map((item) => { const Icon = item.icon; return <article key={item.title}><div className="release-timeline__dot"><Icon size={17} /></div><div><span>{item.label}</span><h2>{item.title}</h2><p>{item.body}</p></div></article>; })}</section></section>)}<section className="changelog-note"><ShieldCheck size={18} /><p><b>Important:</b> LLMSlim mitigates compression-induced instruction elevation. It does not claim to solve prompt injection completely, authenticate caller-provided roles, or ship an npm, Rust, or WASM runtime.</p></section></main><Footer /></div>;
}
