import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { CopyCommand, HomeEffects, CodeExample, ContextPreview } from "@/components/landing/RedesignInteractions"
import { LogoCloud, PhotoSection, PremiumHero, Reveal, RevealWords } from "@/components/landing/Premium"
import { CompressVisual, Showcase, StatsBand, TraceVisual, type Stat } from "@/components/landing/Visuals"
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

// Real-model results only (Claude Haiku 5.5, public benchmarks, paired against full context and truncation).
// The full report, weak spots included, is on /benchmarks.
const stats: Stat[] = [
  { value: "62", unit: "×", label: "lower cost per question over long chat histories", note: "LongMemEval · 70% vs 82% with full history" },
  { value: "72", unit: "%", label: "fewer tokens on long documents and codebases", note: "LongBench v2 · 53% vs 60% accuracy" },
  { value: "+7.7", label: "points over truncation at the same token budget", note: "LongBench v1 · 95% CI +2.7 to +12.9" },
  { value: "45", unit: "%", label: "lower cost on multi-hop retrieval QA", note: "HotpotQA · F1 68.0 vs 74.9" },
]

export default function Home() {
  return <div className="slim-site premium"><HomeEffects /><PageView event="homepage_view" /><SiteHeader /><main id="main-content">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(faqJsonLd(faqs)) }} />

    <PremiumHero>
      <Link className="p-announce" href="/changelog"><span className="p-announce-dot" aria-hidden="true" />Core v{siteConfig.coreVersion} is out<span className="p-announce-sep" aria-hidden="true" />Platform v{siteConfig.platformVersion} in beta<ArrowRight size={14} aria-hidden="true" /></Link>
      <h1 id="hero-title"><RevealWords text="The context layer" /><br /><RevealWords className="p-hero-dim" text="for production AI agents." delay={0.25} /></h1>
      <Reveal delay={0.55}><p className="p-hero-lede">Your agents are only as smart as what they know. LLMSlim decides what reaches the model, remembers what changed, and learns which context wins.</p></Reveal>
      <Reveal delay={0.7} className="p-hero-actions">
        <TrackedLink className="button" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "hero" }}>Get started <ArrowRight size={16} /></TrackedLink>
        <TrackedLink className="button button-outline" href="/platform#beta" event="platform_beta_clicked" properties={{ location: "hero" }}>Request Platform beta</TrackedLink>
      </Reveal>
      <Reveal delay={0.85}><CopyCommand /></Reveal>
    </PremiumHero>

    <section className="p-section site-width" id="receipts" aria-labelledby="receipts-title">
      <Reveal className="p-head"><p className="p-kicker">The receipts</p><h2 id="receipts-title">Less context. <span>Sharper agents.</span></h2></Reveal>
      <StatsBand stats={stats} />
      <Reveal className="p-foot"><span>Claude Haiku 5.5 · public benchmarks · weak spots published</span><Link className="text-link" href="/benchmarks">Read the benchmarks <ArrowUpRight size={14} /></Link></Reveal>
    </section>

    <section className="p-section site-width" id="layers" aria-labelledby="layers-title">
      <Reveal className="p-head"><p className="p-kicker">Open-source core · private platform</p><h2 id="layers-title">Start in one line. <span>Scale to agents that remember.</span></h2></Reveal>
      <div className="duo">
        <div>
          <Showcase tone="teal"><CompressVisual before={114006} after={7985} foot={<><span><b>62× cheaper</b> per question</span><span>LongMemEval · Claude Haiku 5.5</span></>} /></Showcase>
          <Reveal className="duo-copy"><p className="sheet-eyebrow">LLMSlim Core · v{siteConfig.coreVersion} · MIT</p><h3>Control exactly what reaches the model.</h3><p>Compress context in your own process, keep provenance on every piece, and fit it all into your token budget. No API key, no network call.</p><TrackedLink className="text-link" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "layers" }}>Start with Core <ArrowUpRight size={15} /></TrackedLink></Reveal>
        </div>
        <div>
          <Showcase tone="violet"><TraceVisual /></Showcase>
          <Reveal className="duo-copy" delay={0.08}><p className="sheet-eyebrow">LLMSlim Platform · v{siteConfig.platformVersion} beta · private</p><h3>Give your agents a memory you can audit.</h3><p>A tamper-evident timeline of what your agents were told, a trace for every context decision, and policies that learn from real outcomes.</p><TrackedLink className="text-link" href="/platform" event="platform_beta_clicked" properties={{ location: "layers" }}>Explore the Platform <ArrowUpRight size={15} /></TrackedLink></Reveal>
        </div>
      </div>
    </section>

    <section className="p-section site-width" id="features" aria-labelledby="features-title">
      <Reveal className="p-head p-head-center"><p className="p-kicker">Signal in · noise out</p><h2 id="features-title">Great context makes great agents. <span>Everything else is a tax.</span></h2></Reveal>
      <ContextPreview />
      <ol className="p-notes">
        <Reveal as="li"><span className="p-note-index">01</span><h3>Keep what matters</h3><p>Rank and select content around the question before a single token reaches the model.</p></Reveal>
        <Reveal as="li" delay={0.08}><span className="p-note-index">02</span><h3>Know where it came from</h3><p>Instructions, retrieved documents, and tool output keep their roles, so untrusted text never gets promoted.</p></Reveal>
        <Reveal as="li" delay={0.16}><span className="p-note-index">03</span><h3>Stay in control</h3><p>Pick your budget, inspect every decision, and tune it against your own workload.</p></Reveal>
      </ol>
    </section>

    <PhotoSection src="/media/india-night.webp" id="programs" labelledBy="programs-title" className="p-programs" position="60% 40%">
      <div className="site-width">
        <Reveal className="p-head p-head-center"><p className="p-kicker">Supported by {startupProgramCount} startup programs</p><h2 id="programs-title">Built in India. <span>Fuelled by {startupProgramCount} startup programs.</span></h2></Reveal>
        <LogoCloud />
        <Reveal className="p-programs-foot"><Link className="text-link" href="/integrations/sarvam">Explore the Sarvam integration <ArrowUpRight size={15} /></Link></Reveal>
      </div>
    </PhotoSection>

    <section className="p-section build-section site-width" id="pipeline"><div className="build-copy" data-reveal><p className="p-kicker">Tiny library · massive leverage</p><h2>Three lines. <span>Then back to shipping.</span></h2><p className="p-body">Drop LLMSlim in front of your model call. Extraction runs locally and instantly, or bring any provider for rewrite and hybrid strategies.</p><Link className="text-link" href="/docs/getting-started">Open the documentation <ArrowUpRight size={15} /></Link></div><CodeExample /></section>

    <section className="p-section questions-section site-width" id="faq"><Reveal><p className="p-kicker">Before you start</p><h2>A few good <span>questions.</span></h2></Reveal><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus" aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>

    <PhotoSection src="/media/earth-limb.webp" className="p-final" labelledBy="final-title" position="30% 50%">
      <div className="site-width p-final-copy">
        <Reveal><h2 id="final-title">Ship agents that know <span>exactly enough.</span></h2></Reveal>
        <Reveal delay={0.1}><p className="p-hero-lede">One install. Your next model call gets sharper.</p></Reveal>
        <Reveal delay={0.2} className="p-hero-actions"><Link className="button" href="/docs/getting-started">Get started <ArrowRight size={16} /></Link><a className="button button-outline" href={siteConfig.github} target="_blank" rel="noreferrer">Star on GitHub <ArrowUpRight size={16} /></a></Reveal>
      </div>
    </PhotoSection>
  </main><SiteFooter /></div>
}
