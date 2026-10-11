import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { TrackedLink } from "@/components/site/TrackedLink"
import { BetaRequestForm } from "@/components/site/BetaRequestForm"
import { FeatureRow, GuardVisual, PolicyVisual, Showcase, StatsBand, TimelineVisual, TraceVisual, type Stat } from "@/components/landing/Visuals"
import { PageView } from "@/components/site/Telemetry"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "LLMSlim Platform: Context intelligence beta",
  description: "LLMSlim Platform builds on the open-source Core: a verifiable timeline of agent state, explainable and replayable context decisions, and outcome-driven context policies that start in shadow mode. Private beta.",
  canonicalUrl: `${siteConfig.url}/platform`,
})

// Claude Haiku 5.5 on LongMemEval-S (90 questions); see /benchmarks for every arm and the weak spots.
const platformStats: Stat[] = [
  { value: "63.3", unit: "%", label: "accuracy at an 8k-token budget, default settings", note: "Platform 0.9.1 · 0.9.0 scored 18.9%" },
  { value: "86.7", unit: "%", label: "on knowledge-update questions", note: "Full 115k-token history: 80.0%" },
  { value: "67", unit: "×", label: "lower cost per question than sending the whole history", note: "$1.36 vs $90.72 per 1,000 questions" },
  { value: "0", label: "histories that fail to compile at default settings", note: "0.9.0 failed 28 of 90" },
]

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

    <section className="site-width platform-features feature-rows" aria-label="Platform capabilities">
      <FeatureRow kicker="Temporal state" title="Know what is still true." visual={<Showcase tone="teal"><TimelineVisual /></Showcase>}>
        <p>An append-only, tamper-evident timeline of conversation, retrieval, memory, and tool events. Corrections replace the facts they correct instead of sitting beside them.</p>
        <p>Long sessions resume from verified checkpoints.</p>
      </FeatureRow>
      <FeatureRow flip kicker="Context traces" title="See why context was chosen." visual={<Showcase tone="violet"><TraceVisual /></Showcase>}>
        <p>Every prepared request comes with a trace: what went in, what was left out and why, and where each token went.</p>
        <p>Traces replay deterministically, so a decision can be audited long after it was made.</p>
      </FeatureRow>
      <FeatureRow kicker="Outcome learning" title="Learn which context wins." visual={<Showcase tone="amber"><PolicyVisual /></Showcase>}>
        <p>Record whether a task succeeded and link it to the context behind it. Offline training proposes context policies.</p>
        <p>They run in shadow until an evaluation passes and an administrator promotes them. Rollback is instant.</p>
      </FeatureRow>
      <FeatureRow flip kicker="Guardrails" title="Keep the guardrails first." visual={<Showcase tone="rose"><GuardVisual /></Showcase>}>
        <p>Learned suggestions can only leave out optional context. Trust boundaries, mandatory instructions, tenant isolation, and dependencies always win.</p>
        <p>Tool output and retrieved text reach the model as data, never as instructions.</p>
      </FeatureRow>
    </section>

    <section className="site-width platform-evidence" aria-labelledby="evidence-title">
      <p className="p-kicker">Measured on Claude Haiku 5.5</p>
      <h2 id="evidence-title">Remembers what matters from 500 turns ago. <span>At 1/67 of the cost.</span></h2>
      <StatsBand stats={platformStats} />
      <p className="platform-evidence-note">LongMemEval-S, 90 questions over histories of about 50 chat sessions (115k tokens), official judge prompts. Platform 0.9.1 at its default settings and an 8k-token budget. The 0.9.0 figures published earlier came from a synthetic offline suite with no model answering; these replace them. <Link href="/benchmarks#longmemeval">Full results and weak spots</Link></p>
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
      <p>We are working with a small number of design partners who run agents in production. Tell us about your agent, your workload, and where context goes wrong today, and the founder will reply personally. Evaluations start with sanitized or test workloads.</p>
      <BetaRequestForm />
    </section>
  </main><SiteFooter /></div>
}
