import Image from "next/image"
import Link from "next/link"
import { ArrowRight, ArrowUpRight, ChevronRight, Check } from "lucide-react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { CopyCommand, HomeEffects, CodeExample, ContextPreview, HeroArtwork } from "@/components/landing/RedesignInteractions"
import { siteConfig } from "@/config/site"

const faqs = [
  ["Does it need an API key?", "Not for local extraction. LLMSlim’s default extractive strategy runs in your Python application. Rewrite and hybrid strategies use a provider you supply."],
  ["Does it work with my model?", "LLMSlim prepares text before your model call. Use the output with Sarvam, OpenAI, Anthropic, Gemini, or a local model. Your application keeps control of the request."],
  ["How much should I compress?", "Start with a conservative target ratio and evaluate the answers your application produces. The right setting depends on the documents, question, and model. Compression can remove useful information; there is no universal quality guarantee."],
  ["What do the startup program announcements mean?", "LLMSlim is part of both the Sarvam Startup Program and Zoho for Startups. Our Sarvam integration guide shows how to combine local context compression with the official Sarvam Python SDK."],
]

export default function Home() {
  return <div className="slim-site"><HomeEffects /><SiteHeader /><main id="main-content">
    <section className="cinema-hero" aria-labelledby="hero-title">
      <HeroArtwork />
      <div className="cinema-copy">
        <div className="startup-announcements"><Link className="news-pill" href="/integrations/sarvam"><span className="news-flower" aria-hidden="true" />Now part of the Sarvam Startup Program<ChevronRight size={14} /></Link><a className="news-pill" href="https://www.zoho.com/startups/" target="_blank" rel="noreferrer"><span className="news-zoho" aria-hidden="true"><Image src="/zoho-logo-light.png" alt="" width={860} height={409} className="art-light" /><Image src="/zoho-logo-dark.png" alt="" width={860} height={378} className="art-dark" /></span>Now part of Zoho for Startups<ChevronRight size={14} /></a></div>
        <h1 id="hero-title">Your context.<br /><span>Only what matters.</span></h1>
        <p>Less noise between your ideas and your AI.<br />An open-source Python library for thoughtful context compression.</p>
        <div className="hero-actions"><Link className="button" href="/docs/getting-started">Start building <ArrowRight size={16} /></Link><Link className="button button-outline" href="/playground" prefetch={false}>Try it in Studio <ArrowUpRight size={16} /></Link></div>
        <CopyCommand />
      </div>
      <div className="hero-base"><span>LOCAL BY DEFAULT</span><span>OPEN SOURCE, ALWAYS</span><a href="#features">A closer look <span>↓</span></a></div>
    </section>

    <section className="focus-section site-width" id="features">
      <div className="focus-heading" data-reveal><p className="section-kicker">A little less goes a long way.</p><h2>Good context gives your model direction.<br /> <span>The rest just takes up space.</span></h2></div>
      <ContextPreview />
      <div className="focus-notes" data-reveal><div><h3>Keep it relevant.</h3><p>Rank and select content around your question, before it reaches the model.</p></div><div><h3>Keep its origins.</h3><p>Treat instructions, retrieved documents, and tool responses according to their roles.</p></div><div><h3>Keep control.</h3><p>Choose your retention target. Inspect the output. Evaluate it on your own workload.</p></div></div>
      <Link className="text-link" href="/benchmarks" id="benchmarks">Read the evaluations and their limitations <ArrowUpRight size={15} /></Link>
    </section>

    <section className="sarvam-story" id="sarvam"><div className="sarvam-halo" aria-hidden="true" data-parallax="0.08" /><div className="site-width sarvam-content">
      <div className="partnership-logos startup-partnership" data-reveal><div className="startup-program-brands"><div className="startup-program-brand"><span className="sarvam-brand" role="img" aria-label="Sarvam"><span className="sarvam-symbol" /><span className="sarvam-wordmark" /></span><span className="startup-program-name">Sarvam Startup Program</span></div><div className="startup-program-brand"><span className="zoho-brand"><Image src="/zoho-logo-light.png" alt="Zoho" width={860} height={409} sizes="200px" className="art-light" /><Image src="/zoho-logo-dark.png" alt="Zoho" width={860} height={378} sizes="200px" className="art-dark" /></span><span className="startup-program-name">Zoho for Startups</span></div></div><span className="partnership-cross">×</span><span className="partnership-slim"><span className="brand-symbol" aria-hidden="true" />LLM<span>Slim</span></span></div>
      <p className="section-kicker" data-reveal>Part of the Sarvam Startup Program &amp; Zoho for Startups</p><h2 data-reveal>A shared beginning.<br /><span>Built from India.</span></h2><p className="sarvam-description" data-reveal>We’re building LLMSlim with support from the Sarvam Startup Program and Zoho for Startups. Start with local context compression, then bring Sarvam’s models into your application.</p><Link className="button" href="/integrations/sarvam">Explore the integration <ArrowRight size={16} /></Link><div className="startup-program-links"><a className="program-link" href="https://www.sarvam.ai/startup-program" target="_blank" rel="noreferrer">About Sarvam’s program <ArrowUpRight size={13} /></a><a className="program-link" href="https://www.zoho.com/startups/" target="_blank" rel="noreferrer">About Zoho for Startups <ArrowUpRight size={13} /></a></div>
    </div></section>

    <section className="build-section site-width" id="pipeline"><div className="build-copy" data-reveal><p className="section-kicker">Small library. Familiar workflow.</p><h2>A few lines.<br /><span>Then back to building.</span></h2><p>Add LLMSlim before your model call. Run extraction locally, or bring a provider for rewrite and hybrid strategies.</p><div className="build-points"><span><Check size={15} /> Python-native</span><span><Check size={15} /> Provider-agnostic</span><span><Check size={15} /> MIT licensed</span></div><Link className="text-link" href="/docs/getting-started">Open the documentation <ArrowUpRight size={15} /></Link></div><CodeExample /></section>

    <section className="questions-section site-width" id="faq"><div data-reveal><p className="section-kicker">Before you start.</p><h2>A few good<br /> <span>questions.</span></h2></div><div className="faq-list">{faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus">+</span></summary><p>{answer}</p></details>)}</div></section>

    <section className="end-section"><div className="end-ribbon" aria-hidden="true" data-parallax="-0.07"><Image src="/compression-ribbon-dark.webp" alt="" width={1536} height={1024} className="art-dark" /><Image src="/compression-ribbon-light.webp" alt="" width={1536} height={1024} className="art-light" /></div><div className="end-copy"><span className="brand-symbol" aria-hidden="true" /><h2>Make a little room.</h2><p>Your next model call is a good place to start.</p><div className="hero-actions"><Link className="button" href="/docs/getting-started">Get started <ArrowRight size={16} /></Link><a className="text-link" href={siteConfig.github} target="_blank" rel="noreferrer">View on GitHub <ArrowUpRight size={16} /></a></div></div></section>
  </main><SiteFooter /></div>
}
