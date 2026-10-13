import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { GitHubMark, SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { CopyCommand, HomeEffects, CodeExample, ContextPreview } from "@/components/landing/RedesignInteractions"
import { LogoCloud, PhotoSection, PremiumHero, Reveal } from "@/components/landing/Premium"
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
// The full report is on /benchmarks.
const stats: Stat[] = [
  { topic: "Chat memory", value: "62", unit: "×", label: "lower cost per question over long chat histories, at Haiku 5.5 list prices", source: "LongMemEval, 76.7% vs 82.2% with the whole history; 14× fewer tokens",
    meter: { before: { name: "Whole history", value: 90.72, display: "$90.72" }, after: { name: "LLMSlim", value: 1.45, display: "$1.45" }, max: 90.72 } },
  { topic: "Long documents", value: "3", unit: "×", label: "fewer tokens on long documents, for the same score", source: "LongBench v1, 54.9 vs 54.9 with full context",
    meter: { before: { name: "Full document", value: 15532, display: "15.5k tokens" }, after: { name: "LLMSlim", value: 5232, display: "5.2k" }, max: 15532 } },
  { topic: "Retrieval", value: "+23", label: "points over truncation at the same token budget", source: "NaturalQuestions, 20 passages, 25% budget",
    meter: { before: { name: "Cut to fit", value: 52, display: "52.0" }, after: { name: "LLMSlim", value: 75, display: "75.0" }, max: 100 } },
  { topic: "Agent turns", value: "0", label: "repeated tool calls across 1,054 agent turns", source: "InjecAgent, Platform agent turns",
    meter: { before: { name: "Before", value: 50, display: "50" }, after: { name: "Agent turn", value: 0, display: "0" }, max: 50 } },
]

export default function Home() {
  return <div className="slim-site premium"><HomeEffects /><PageView event="homepage_view" /><SiteHeader /><main id="main-content">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(faqJsonLd(faqs)) }} />

    <PremiumHero>
      <Link className="p-announce" href="/changelog"><span className="p-announce-dot" aria-hidden="true" /><span className="p-announce-item">Core v{siteConfig.coreVersion} is out</span><span className="p-announce-sep" aria-hidden="true" /><span className="p-announce-item">Platform v{siteConfig.platformVersion} in beta<ArrowRight size={14} aria-hidden="true" /></span></Link>
      {/* No reveal on the headline and only transform motion below it, so the copy is painted on first load (LCP).
          The space before the <br> keeps "layer for" apart on phones, where the <br> is hidden. */}
      <h1 id="hero-title">The context layer{" "}<br /><span className="p-hero-dim">for production AI agents.</span></h1>
      <Reveal fade={false} delay={0.1}><p className="p-hero-sub">Open-source context compression for RAG and agents. <Link className="p-hero-proof" href="/benchmarks">Level with LongLLMLingua on NaturalQuestions at about 100× the speed, with a 22M reranker instead of a 7B model.<ArrowRight size={15} aria-hidden="true" /></Link></p></Reveal>
      <Reveal fade={false} delay={0.2}><p className="p-hero-lede">Your agents are only as smart as what they know. LLMSlim decides what reaches the model, remembers what changed, and learns which context wins.</p></Reveal>
      <Reveal fade={false} delay={0.3} className="p-hero-actions">
        <TrackedLink className="button" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "hero" }}>Get started <ArrowRight size={16} /></TrackedLink>
        <a className="button button-outline" href={siteConfig.github} target="_blank" rel="noreferrer"><GitHubMark /> View on GitHub</a>
        <TrackedLink className="button button-outline" href="/platform#beta" event="platform_beta_clicked" properties={{ location: "hero" }}>Request Platform beta</TrackedLink>
      </Reveal>
      <Reveal fade={false} delay={0.4}><CopyCommand /></Reveal>
    </PremiumHero>

    <section className="p-section site-width" id="receipts" aria-labelledby="receipts-title">
      <Reveal className="p-head"><p className="p-kicker">The receipts</p><h2 id="receipts-title">Less context. <span>Sharper agents.</span></h2></Reveal>
      <StatsBand stats={stats} />
      <Reveal className="p-foot"><span>Public benchmarks. One reader and one prompt for every run; only the context changes.*</span><Link className="text-link" href="/results">See the results, chapter by chapter <ArrowUpRight size={14} /></Link></Reveal>
      <p className="p-fineprint">* Every context was read by Claude Haiku 5.5.</p>
    </section>

    <section className="p-section site-width" id="layers" aria-labelledby="layers-title">
      <Reveal className="p-head"><p className="p-kicker">Open-source core · private platform</p><h2 id="layers-title">Start in one line. <span>Scale to agents that remember.</span></h2></Reveal>
      <div className="duo">
        <div>
          <Showcase><CompressVisual before={114006} after={7985} foot={<><span><b>62× cheaper</b> per question</span><span>LongMemEval at Haiku 5.5 list prices; 14× fewer tokens</span></>} /></Showcase>
          <Reveal className="duo-copy"><p className="sheet-eyebrow">LLMSlim Core · v{siteConfig.coreVersion} · MIT</p><h3>Control exactly what reaches the model.</h3><p>Compress context in your own process, keep provenance on every piece, and fit it all into your token budget. No API key, no network call.</p><TrackedLink className="text-link" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "layers" }}>Start with Core <ArrowUpRight size={15} /></TrackedLink></Reveal>
        </div>
        <div>
          <Showcase><TraceVisual /></Showcase>
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

    <PhotoSection src="/media/india-night.webp" lightSrc="/media/india-day.webp" lightPosition="50% 60%" id="programs" labelledBy="programs-title" className="p-programs" position="60% 40%">
      <div className="site-width">
        <Reveal className="p-head p-head-center"><p className="p-kicker">Supported by {startupProgramCount} startup programs</p><h2 id="programs-title">Built in India. <span>Fuelled by {startupProgramCount} startup programs.</span></h2></Reveal>
        <LogoCloud />
        <Reveal className="p-programs-foot"><Link className="text-link" href="/integrations/sarvam">Explore the Sarvam integration <ArrowUpRight size={15} /></Link></Reveal>
      </div>
    </PhotoSection>

    <section className="p-section build-section site-width" id="pipeline"><div className="build-copy" data-reveal><p className="p-kicker">Tiny library · massive leverage</p><h2>Three lines. <span>Then back to shipping.</span></h2><p className="p-body">Drop LLMSlim in front of your model call, or into the LangChain, LlamaIndex or Haystack pipeline you already run. Extraction runs locally and instantly, or bring any provider for rewrite and hybrid strategies.</p><p className="build-links"><Link className="text-link" href="/docs/getting-started">Open the documentation <ArrowUpRight size={15} /></Link><Link className="text-link" href="/integrations">LangChain, LlamaIndex and Haystack <ArrowUpRight size={15} /></Link></p></div><CodeExample /></section>

    <section className="p-section questions-section site-width" id="faq"><Reveal><p className="p-kicker">Before you start</p><h2>A few good <span>questions.</span></h2></Reveal><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus" aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>

    <PhotoSection src="/media/earth-limb.webp" lightSrc="/media/dusk-light.webp" lightPosition="50% 40%" className="p-final" labelledBy="final-title" position="30% 50%">
      <div className="site-width p-final-copy">
        <Reveal><h2 id="final-title">Ship agents that know <span>exactly enough.</span></h2></Reveal>
        <Reveal delay={0.1}><p className="p-hero-lede">One install. Your next model call gets sharper.</p></Reveal>
        <Reveal delay={0.2} className="p-hero-actions"><Link className="button" href="/docs/getting-started">Get started <ArrowRight size={16} /></Link><a className="button button-outline" href={siteConfig.github} target="_blank" rel="noreferrer">Star on GitHub <ArrowUpRight size={16} /></a></Reveal>
      </div>
    </PhotoSection>
  </main><SiteFooter /></div>
}
