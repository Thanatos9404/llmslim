"use client";

import Link from "next/link";
import { ArrowUpRight, Check, Copy, Database, Layers3, ShieldCheck, Terminal, TestTube2 } from "lucide-react";
import { useState } from "react";
import { Footer } from "@/components/landing/Footer";
import { Navbar } from "@/components/landing/Navbar";
import { MagneticLink } from "@/components/landing/MagneticLink";
import { FeatureMosaic } from "@/components/landing/FeatureMosaic";
import { GithubIcon } from "@/components/icons/GithubIcon";
import { siteConfig } from "@/config/site";

const phaseMetrics = [
  ["442", "tests passing", "Phase 2 release gate"],
  ["22", "evaluation categories", "24 disclosed samples"],
  ["375", "generated schemas", "18 measured catalogs"],
  ["0", "boundary violations", "security regression suite"],
] as const;

export default function Home() {
  const [copied, setCopied] = useState(false);
  const copyInstall = async () => { await navigator.clipboard.writeText("pip install llmslim"); setCopied(true); window.setTimeout(() => setCopied(false), 1600); };

  return <div className="site-shell"><Navbar /><main id="main-content" className="home-main home-main--rich">
    <section className="hero hero--product hero--atmospheric">
      <div className="hero-atmosphere" aria-hidden="true"><i /><i /><i /><i /></div>
      <div className="hero__copy reveal"><span className="eyebrow">Open source · Python · local-first</span><h1>Ship less context.<br /><span>Keep more signal.</span></h1><p>LLMSlim makes long prompts, documents, retrieval, and chat history easier to reason about—with local extractive compression, provider-aware strategies, and provenance-aware priorities.</p>
        <div className="hero__actions"><MagneticLink className="button--primary button--command" href="/playground"><Terminal size={16} /> Open Studio <kbd>⌘ K</kbd></MagneticLink><Link className="button" href="/docs/getting-started">Read docs <ArrowUpRight size={15} /></Link><a className="hero__github" href={siteConfig.github} target="_blank" rel="noreferrer"><GithubIcon className="h-4 w-4" /> GitHub</a></div>
        <div className="install-control install-control--hero"><span>$ pip install llmslim</span><button type="button" aria-label="Copy installation command" onClick={copyInstall}>{copied ? <Check size={17} /> : <Copy size={17} />}</button></div>
        <div className="hero__meta"><span><GithubIcon className="h-4 w-4" /> MIT licensed</span><span><ShieldCheck size={16} /> Provenance-aware</span><span><Layers3 size={16} /> Provider optional</span></div>
      </div>
    </section>

    <section className="phase-strip" aria-labelledby="phase-strip-title"><div className="phase-strip__heading"><span className="section-label">Phase 2 evaluation system</span><h2 id="phase-strip-title">A benchmark is more than a single corpus size.</h2><p>24 curated samples stay visible in the methodology; the release story also includes categories, languages, schema contracts, security regression, and machine-readable artifacts.</p><Link href="/benchmarks">Explore the evidence <ArrowUpRight size={15} /></Link></div><div className="phase-strip__metrics">{phaseMetrics.map(([value, label, detail]) => <div key={label}><strong>{value}</strong><span>{label}</span><small>{detail}</small></div>)}</div></section>

    <FeatureMosaic />

    <section className="schema-preview"><div className="schema-preview__copy"><span className="section-label">Schema tax · research track</span><h2>Tool definitions consume context too.</h2><p>Phase 2 measured 18 synthetic tool catalogs across simple, medium, and complex schema classes. At the measured extremes, one simple tool contained 62 tokens; 64 complex tools contained 12,739.</p><p>This is not a shipped schema optimizer. The real work now is finding out when contracts can be safely minimized or selectively loaded.</p><Link href="/benchmarks" className="button">Open the interactive explorer <ArrowUpRight size={15} /></Link></div><div className="schema-preview__visual" aria-label="Schema tax range, from 62 to 12,739 measured schema tokens"><div><span>1 simple tool</span><strong>62</strong><small>measured tokens</small></div><i /><div><span>64 complex tools</span><strong>12,739</strong><small>measured tokens</small></div><p>Derived 32-turn totals are labelled separately in the explorer.</p></div></section>

    <section className="story-grid"><article><TestTube2 size={20} /><span className="section-label">Measure honestly</span><h2>Classify every claim.</h2><p>Measured results, derived session totals, and unavailable provider-dependent findings are never flattened into one number.</p><Link href="/benchmarks">Benchmark methodology <ArrowUpRight size={14} /></Link></article><article><ShieldCheck size={20} /><span className="section-label">Protect the boundary</span><h2>Priority follows provenance.</h2><p>Untrusted RAG, tool, and assistant text cannot gain protected priority just because it sounds authoritative.</p><Link href="/docs/context-role">Read the ContextRole guide <ArrowUpRight size={14} /></Link></article><article><Database size={20} /><span className="section-label">Use what ships</span><h2>Local by default.</h2><p>Extractive compression works without a provider. Rewrite and hybrid flows require one you supply and should be measured in your environment.</p><Link href="/docs/getting-started">Install LLMSlim <ArrowUpRight size={14} /></Link></article></section>

    <section className="product-section product-section--install" id="install"><div><span className="section-label">Start in one command</span><h2>A shorter context is only useful when it stays explainable.</h2></div><div><div className="install-control"><span>$ pip install llmslim</span><button type="button" aria-label="Copy installation command" onClick={copyInstall}>{copied ? <Check size={18} /> : <Copy size={18} />}</button></div><p>Run a local extractive path first. Add a caller-supplied provider only when a rewrite or hybrid workflow makes the trade-off explicit.</p><div className="product-section__actions"><Link className="button button--primary" href="/playground">Try the Studio <ArrowUpRight size={15} /></Link><a className="button" href={siteConfig.pypi} target="_blank" rel="noreferrer">View on PyPI <ArrowUpRight size={15} /></a></div></div></section>
  </main><Footer /></div>;
}
