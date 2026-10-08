import { ArrowRight, ArrowUpRight, Check } from "lucide-react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { TrackedLink } from "@/components/site/TrackedLink"
import { PageView } from "@/components/site/Telemetry"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "LLMSlim Platform — Context intelligence beta",
  description: "LLMSlim Platform builds on the open-source Core: a verifiable timeline of agent state, explainable and replayable context decisions, and outcome-driven context policies that start in shadow mode. Private beta.",
  canonicalUrl: `${siteConfig.url}/platform`,
})

const capabilities = [
  ["Know what is still true.", "An append-only, tamper-evident timeline of conversation, retrieval, memory, and tool events. Corrections replace the facts they correct instead of sitting beside them, and long sessions resume from verified checkpoints."],
  ["See why context was chosen.", "Every prepared context comes with a trace: what was included, what was left out and why, and where each token went. Traces replay deterministically, so a decision can be audited long after it was made."],
  ["Learn from outcomes.", "Record whether a task succeeded and connect it to the context behind it. Offline training proposes context policies. They run in shadow mode until an evaluation passes and an administrator promotes them, and rollback is instant."],
  ["Keep the guardrails first.", "Learned suggestions can only leave out optional context. Trust boundaries, mandatory instructions, tenant isolation, and dependencies always take precedence."],
] as const

const comparison = [
  ["License", "MIT, open source", "Proprietary"],
  ["Install", "pip install llmslim", "By invitation"],
  ["Runs", "In your Python process", "As a service in your environment"],
  ["Focus", "Compress and plan model-visible context", "Agent state, decision traces, learned context policies"],
] as const

export default function PlatformPage() {
  return <div className="slim-site"><PageView event="platform_page_view" /><SiteHeader /><main id="main-content" className="platform-page">
    <section className="platform-hero site-width" aria-labelledby="platform-title">
      <span className="eyebrow">LLMSLIM PLATFORM · v{siteConfig.platformVersion} BETA · PRIVATE</span>
      <h1 id="platform-title">Context intelligence<br /><span>for agents in production.</span></h1>
      <p>LLMSlim Platform builds on the open-source Core. It records what your agents were told, works out what is still true, explains every context decision, and learns from outcomes which context helps, without handing safety decisions to a model.</p>
      <div className="hero-actions"><TrackedLink className="button" href="#beta" event="platform_beta_clicked" properties={{ location: "platform_hero" }}>Request Platform Beta Access <ArrowRight size={16} /></TrackedLink><TrackedLink className="button button-outline" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "platform_hero" }}>Explore LLMSlim Core <ArrowUpRight size={16} /></TrackedLink></div>
    </section>

    <section className="site-width platform-capabilities" aria-label="Platform capabilities">
      {capabilities.map(([title, body]) => <article className="layer-card" key={title}><h2>{title}</h2><p>{body}</p></article>)}
    </section>

    <section className="site-width platform-evidence" aria-labelledby="evidence-title">
      <p className="section-kicker">What we have measured, and what we have not.</p>
      <h2 id="evidence-title">Less context. <span>No loss of task success.</span></h2>
      <p>On a 180-case synthetic benchmark across 18 task categories in English, Hindi, and Hinglish, v0.9 sent 63% fewer context tokens to the model than v0.8 and solved 88.9% of tasks, compared with 83.3%. None of the benchmark’s prompt-injection probes reached the model as trusted instructions.</p>
      <ul className="platform-caveats">
        <li><Check size={14} /> Synthetic workloads only. Results on your workload will differ.</li>
        <li><Check size={14} /> Learned policies have not yet been validated on real customer outcomes, so they ship in shadow mode.</li>
        <li><Check size={14} /> Live provider cache savings have not been measured for this release.</li>
      </ul>
    </section>

    <section className="site-width platform-compare" aria-labelledby="compare-title">
      <h2 id="compare-title">Core and Platform</h2>
      <div className="platform-table" role="table" aria-label="LLMSlim Core compared with LLMSlim Platform">
        <div role="row" className="platform-row platform-row-head"><span role="columnheader"><span className="sr-only">Attribute</span></span><span role="columnheader">LLMSlim Core v{siteConfig.coreVersion}</span><span role="columnheader">LLMSlim Platform v{siteConfig.platformVersion}</span></div>
        {comparison.map(([label, core, platform]) => <div role="row" className="platform-row" key={label}><span role="rowheader">{label}</span><span role="cell">{core}</span><span role="cell">{platform}</span></div>)}
      </div>
      <p className="platform-note">LLMSlim Platform is not published to PyPI. <code>pip install llmslim</code> installs the open-source Core.</p>
    </section>

    <section className="site-width platform-beta" id="beta" aria-labelledby="beta-title">
      <h2 id="beta-title">Join the beta.</h2>
      <p>We are working with a small number of design partners who run agents in production. Tell us about your agent, your workload, and where context goes wrong today, and we will reply personally.</p>
      <div className="hero-actions"><TrackedLink className="button" href={siteConfig.linkedin} event="platform_beta_clicked" properties={{ location: "platform_beta" }} target="_blank" rel="noreferrer">Message the founder on LinkedIn <ArrowUpRight size={16} /></TrackedLink></div>
    </section>
  </main><SiteFooter /></div>
}
