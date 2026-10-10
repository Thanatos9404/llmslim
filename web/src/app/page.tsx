import Image from "next/image"
import Link from "next/link"
import { ArrowRight, ArrowUpRight, Check } from "lucide-react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { CopyCommand, HomeEffects, CodeExample, ContextPreview, HeroArtwork } from "@/components/landing/RedesignInteractions"
import { DecodeText, PixelProgramWall, Receipts, TiltCard, type Receipt } from "@/components/landing/HypeEffects"
import { startupProgramCount, startupProgramNames } from "@/components/landing/StartupPrograms"
import { TrackedLink } from "@/components/site/TrackedLink"
import { PageView } from "@/components/site/Telemetry"
import { siteConfig } from "@/config/site"
import { homeFaqs } from "@/data/home"
import { constructMetadata, faqJsonLd, jsonLdScript } from "@/lib/seo"

export const metadata = constructMetadata({ path: "/", markdownPath: "/index.md" })

const faqs: ReadonlyArray<readonly [string, string]> = [
  ...homeFaqs,
  ["What do the startup programs give LLMSlim?", `LLMSlim is part of ${startupProgramCount} startup programs: ${startupProgramNames}. They provide credits, tools, and guidance. Our Sarvam integration guide shows how to pair local context compression with the official Sarvam Python SDK.`],
]

// Every figure is measured and published: the Platform benchmark (180 cases, 18 categories, en/hi/Hinglish)
// and the Core Phase 2 evaluation. See /platform and /benchmarks.
const receipts: Receipt[] = [
  { value: 2, suffix: "×", label: "the task success of raw history", note: "Platform 0.9, 180-case benchmark" },
  { value: 84, suffix: "%", label: "fewer context tokens than v0.8", note: "Platform, 1,000-turn sessions" },
  { value: 0, suffix: "", label: "injected prompts promoted to trusted instructions", note: "Across all 180 benchmark cases" },
  { value: 0.026, decimals: 3, suffix: " ms", label: "median planning time per sample", note: "Core, Phase 2 evaluation" },
]

export default function Home() {
  return <div className="slim-site"><HomeEffects /><PageView event="homepage_view" /><SiteHeader /><main id="main-content">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(faqJsonLd(faqs)) }} />
    <section className="cinema-hero" aria-labelledby="hero-title">
      <HeroArtwork />
      <div className="hero-grid" aria-hidden="true" />
      <div className="cinema-copy">
        <span className="hero-badge"><span className="hero-badge-dot" aria-hidden="true" />Core v{siteConfig.coreVersion} is live · Platform v{siteConfig.platformVersion} beta</span>
        <h1 id="hero-title">The context layer for{" "}<br /><DecodeText text="production AI agents." className="hero-accent" /></h1>
        <p>Your agents are only as smart as what they know. LLMSlim decides what reaches the model, remembers what changed, and learns which context wins.</p>
        <div className="hero-actions"><TrackedLink className="button button-glow" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "hero" }}>Start with Core <ArrowRight size={16} /></TrackedLink><TrackedLink className="button button-outline" href="/platform#beta" event="platform_beta_clicked" properties={{ location: "hero" }}>Get Platform beta access <ArrowUpRight size={16} /></TrackedLink></div>
        <CopyCommand />
      </div>
      <div className="hero-base"><span>RUNS LOCALLY · NO API KEY</span><span>OPEN-SOURCE CORE · PRIVATE PLATFORM</span><a href="#receipts">The receipts <span>↓</span></a></div>
    </section>

    <section className="receipts-section site-width" id="receipts" aria-labelledby="receipts-title">
      <div className="focus-heading" data-reveal><p className="section-kicker">The receipts.</p><h2 id="receipts-title">Less context.<br /> <span>Sharper agents.</span></h2></div>
      <Receipts items={receipts} />
      <p className="receipts-foot" data-reveal>678 tests · 90% branch coverage · MIT licensed · <Link className="text-link" href="/benchmarks">Read the full benchmarks <ArrowUpRight size={14} /></Link></p>
    </section>

    <section className="layers-section site-width" id="layers" aria-labelledby="layers-title">
      <div className="focus-heading" data-reveal><p className="section-kicker">Open-source core. Private platform.</p><h2 id="layers-title">Start in one line.<br /> <span>Scale to agents that remember and learn.</span></h2></div>
      <div className="layer-cards">
        <TiltCard as="article" className="layer-card" depth={7}><span className="eyebrow">LLMSLIM CORE · v{siteConfig.coreVersion} · MIT</span><h3>Control exactly what reaches the model.</h3><p>Install it in seconds. Core compresses context in your own process, tracks where every piece came from, and fits it all into your token budget, deterministically.</p><ul><li><Check size={14} /> Local extractive compression, no API key</li><li><Check size={14} /> Provenance-aware roles that keep untrusted text untrusted</li><li><Check size={14} /> Adaptive context planning to the token</li></ul><TrackedLink className="text-link" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "layers" }}>Start with Core <ArrowUpRight size={15} /></TrackedLink></TiltCard>
        <TiltCard as="article" className="layer-card layer-card-accent" depth={7}><span className="eyebrow">LLMSLIM PLATFORM · v{siteConfig.platformVersion} BETA · PRIVATE</span><h3>Give your agents a memory you can audit.</h3><p>A private service built on Core. It keeps a tamper-evident timeline of everything your agents were told, explains every context decision, and learns from real outcomes which context wins.</p><ul><li><Check size={14} /> State that always knows what is current</li><li><Check size={14} /> Every decision traced and replayable</li><li><Check size={14} /> Learned policies with instant rollback</li></ul><TrackedLink className="text-link" href="/platform" event="platform_beta_clicked" properties={{ location: "layers" }}>Explore the Platform <ArrowUpRight size={15} /></TrackedLink></TiltCard>
      </div>
    </section>

    <section className="focus-section site-width" id="features">
      <div className="focus-heading" data-reveal><p className="section-kicker">Signal in. Noise out.</p><h2>Great context makes great agents.<br /> <span>Everything else is a tax.</span></h2></div>
      <ContextPreview />
      <div className="focus-notes" data-reveal><TiltCard depth={5} className="focus-note"><h3>Keep what matters.</h3><p>Rank and select content around the question before a single token reaches the model.</p></TiltCard><TiltCard depth={5} className="focus-note"><h3>Know where it came from.</h3><p>Instructions, retrieved documents, and tool output each keep their role, so untrusted text never gets promoted.</p></TiltCard><TiltCard depth={5} className="focus-note"><h3>Stay in control.</h3><p>Pick your budget, inspect every decision, and tune it against your own workload.</p></TiltCard></div>
      <Link className="text-link" href="/benchmarks" id="benchmarks">See the benchmarks <ArrowUpRight size={15} /></Link>
    </section>

    <section className="programs-section" id="programs" aria-labelledby="programs-title">
      <div className="programs-halo" aria-hidden="true" data-parallax="0.08" />
      <div className="site-width programs-head">
        <p className="section-kicker" data-reveal>Supported by {startupProgramCount} startup programs</p>
        <h2 id="programs-title" data-reveal>Built in India.<br /><span>Fuelled by {startupProgramCount} startup programs.</span></h2>
        <p className="programs-description" data-reveal>Credits, tools, and guidance from {startupProgramCount} startup programs, from Sarvam and MongoDB to Anthropic, OpenAI, and Sentry. Move your cursor across the wall.</p>
      </div>
      <PixelProgramWall />
      <div className="site-width programs-foot" data-reveal><Link className="button" href="/integrations/sarvam">Explore the Sarvam integration <ArrowRight size={16} /></Link></div>
    </section>

    <section className="build-section site-width" id="pipeline"><div className="build-copy" data-reveal><p className="section-kicker">Tiny library. Massive leverage.</p><h2>Three lines.<br /><span>Then back to shipping.</span></h2><p>Drop LLMSlim in front of your model call. Extraction runs locally and instantly, or bring any provider for rewrite and hybrid strategies.</p><div className="build-points"><span><Check size={15} /> Python-native</span><span><Check size={15} /> Any model provider</span><span><Check size={15} /> MIT licensed</span></div><Link className="text-link" href="/docs/getting-started">Open the documentation <ArrowUpRight size={15} /></Link></div><CodeExample /></section>

    <section className="questions-section site-width" id="faq"><div data-reveal><p className="section-kicker">Before you start.</p><h2>A few good<br /> <span>questions.</span></h2></div><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus">+</span></summary><p>{answer}</p></details>)}</div></section>

    <section className="end-section"><div className="end-ribbon" aria-hidden="true" data-parallax="-0.07"><Image src="/compression-ribbon-dark.webp" alt="" width={1536} height={1024} className="art-dark" /><Image src="/compression-ribbon-light.webp" alt="" width={1536} height={1024} className="art-light" /></div><div className="end-copy"><span className="brand-symbol" aria-hidden="true" /><h2>Ship agents that know exactly enough.</h2><p>One install. Your next model call gets sharper.</p><div className="hero-actions"><Link className="button button-glow" href="/docs/getting-started">Get started <ArrowRight size={16} /></Link><a className="text-link" href={siteConfig.github} target="_blank" rel="noreferrer">Star it on GitHub <ArrowUpRight size={16} /></a></div></div></section>
  </main><SiteFooter /></div>
}
