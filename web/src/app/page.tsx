import Image from "next/image"
import Link from "next/link"
import { ArrowRight, ArrowUpRight, Check } from "lucide-react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { CopyCommand, HomeEffects, CodeExample, ContextPreview, HeroArtwork } from "@/components/landing/RedesignInteractions"
import { StartupBrands, StartupMarquee, startupProgramCount, startupProgramNames } from "@/components/landing/StartupPrograms"
import { TrackedLink } from "@/components/site/TrackedLink"
import { PageView } from "@/components/site/Telemetry"
import { siteConfig } from "@/config/site"
import { homeFaqs } from "@/data/home"
import { constructMetadata, faqJsonLd, jsonLdScript } from "@/lib/seo"

export const metadata = constructMetadata({ path: "/", markdownPath: "/index.md" })

const faqs: ReadonlyArray<readonly [string, string]> = [
  ...homeFaqs,
  ["What do the startup program announcements mean?", `LLMSlim is part of ${startupProgramCount} startup programs: ${startupProgramNames}. These programs offer credits, tools, or guidance. They are not investments and do not imply endorsement. Our Sarvam integration guide shows how to combine local context compression with the official Sarvam Python SDK.`],
]

export default function Home() {
  return <div className="slim-site"><HomeEffects /><PageView event="homepage_view" /><SiteHeader /><main id="main-content">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(faqJsonLd(faqs)) }} />
    <section className="cinema-hero" aria-labelledby="hero-title">
      <HeroArtwork />
      <div className="cinema-copy">
        <StartupMarquee />
        <h1 id="hero-title">The context layer for{" "}<br /><span>production AI agents.</span></h1>
        <p>LLMSlim controls what your agents know, remembers what changed, and learns which context improves their decisions.</p>
        <div className="hero-actions"><TrackedLink className="button" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "hero" }}>Explore LLMSlim Core <ArrowRight size={16} /></TrackedLink><TrackedLink className="button button-outline" href="/platform#beta" event="platform_beta_clicked" properties={{ location: "hero" }}>Request Platform Beta Access <ArrowUpRight size={16} /></TrackedLink></div>
        <CopyCommand />
      </div>
      <div className="hero-base"><span>LOCAL BY DEFAULT</span><span>OPEN-SOURCE CORE · PRIVATE PLATFORM</span><a href="#features">A closer look <span>↓</span></a></div>
    </section>

    <section className="layers-section site-width" id="layers" aria-labelledby="layers-title">
      <div className="focus-heading" data-reveal><p className="section-kicker">Open-source core. Private platform.</p><h2 id="layers-title">Start with the library.<br /> <span>Add memory and judgment when you need them.</span></h2></div>
      <div className="layer-cards">
        <article className="layer-card" data-reveal><span className="eyebrow">LLMSLIM CORE · v{siteConfig.coreVersion} · MIT</span><h3>Shape what reaches the model.</h3><p>A Python library you can install today. It compresses context locally, keeps track of where each piece came from, and plans what fits your token budget.</p><ul><li><Check size={14} /> Local extractive compression</li><li><Check size={14} /> Provenance-aware roles</li><li><Check size={14} /> Adaptive context planning</li></ul><TrackedLink className="text-link" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "layers" }}>Explore LLMSlim Core <ArrowUpRight size={15} /></TrackedLink></article>
        <article className="layer-card" data-reveal><span className="eyebrow">LLMSLIM PLATFORM · v{siteConfig.platformVersion} BETA · PRIVATE</span><h3>Give agents a memory you can audit.</h3><p>A private service built on Core. It keeps a timeline of what your agents were told and what changed, explains every context decision, and learns from outcomes under rules you control.</p><ul><li><Check size={14} /> State that knows what is current</li><li><Check size={14} /> Decision traces you can replay</li><li><Check size={14} /> Learned policies, shadow by default</li></ul><TrackedLink className="text-link" href="/platform" event="platform_beta_clicked" properties={{ location: "layers" }}>About the Platform beta <ArrowUpRight size={15} /></TrackedLink></article>
      </div>
    </section>

    <section className="focus-section site-width" id="features">
      <div className="focus-heading" data-reveal><p className="section-kicker">A little less goes a long way.</p><h2>Good context gives your model direction.<br /> <span>The rest just takes up space.</span></h2></div>
      <ContextPreview />
      <div className="focus-notes" data-reveal><div><h3>Keep it relevant.</h3><p>Rank and select content around your question, before it reaches the model.</p></div><div><h3>Keep its origins.</h3><p>Treat instructions, retrieved documents, and tool responses according to their roles.</p></div><div><h3>Keep control.</h3><p>Choose your retention target. Inspect the output. Evaluate it on your own workload.</p></div></div>
      <Link className="text-link" href="/benchmarks" id="benchmarks">Read the evaluations and their limitations <ArrowUpRight size={15} /></Link>
    </section>

    <section className="sarvam-story" id="sarvam"><div className="sarvam-halo" aria-hidden="true" data-parallax="0.08" /><div className="site-width sarvam-content">
      <div className="partnership-logos startup-partnership" data-reveal><StartupBrands /><span className="partnership-cross">×</span><span className="partnership-slim"><span className="brand-symbol" aria-hidden="true" />LLM<span>Slim</span></span></div>
      <p className="section-kicker" data-reveal>Part of {startupProgramCount} startup programs</p><h2 data-reveal>A shared beginning.<br /><span>Built from India.</span></h2><p className="sarvam-description" data-reveal>We’re building LLMSlim with support from {startupProgramCount} startup programs. They offer credits, tools, and guidance; none is an investor or an endorsement. Start with local context compression, then bring Sarvam’s models into your application.</p><Link className="button" href="/integrations/sarvam">Explore the integration <ArrowRight size={16} /></Link>
    </div></section>

    <section className="build-section site-width" id="pipeline"><div className="build-copy" data-reveal><p className="section-kicker">Small library. Familiar workflow.</p><h2>A few lines.<br /><span>Then back to building.</span></h2><p>Add LLMSlim before your model call. Run extraction locally, or bring a provider for rewrite and hybrid strategies.</p><div className="build-points"><span><Check size={15} /> Python-native</span><span><Check size={15} /> Provider-agnostic</span><span><Check size={15} /> MIT licensed</span></div><Link className="text-link" href="/docs/getting-started">Open the documentation <ArrowUpRight size={15} /></Link></div><CodeExample /></section>

    <section className="questions-section site-width" id="faq"><div data-reveal><p className="section-kicker">Before you start.</p><h2>A few good<br /> <span>questions.</span></h2></div><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus">+</span></summary><p>{answer}</p></details>)}</div></section>

    <section className="end-section"><div className="end-ribbon" aria-hidden="true" data-parallax="-0.07"><Image src="/compression-ribbon-dark.webp" alt="" width={1536} height={1024} className="art-dark" /><Image src="/compression-ribbon-light.webp" alt="" width={1536} height={1024} className="art-light" /></div><div className="end-copy"><span className="brand-symbol" aria-hidden="true" /><h2>Make a little room.</h2><p>Your next model call is a good place to start.</p><div className="hero-actions"><Link className="button" href="/docs/getting-started">Get started <ArrowRight size={16} /></Link><a className="text-link" href={siteConfig.github} target="_blank" rel="noreferrer">View on GitHub <ArrowUpRight size={16} /></a></div></div></section>
  </main><SiteFooter /></div>
}
