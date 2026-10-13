import Link from "next/link"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { BetaRequestForm } from "@/components/site/BetaRequestForm"
import { PlatformHero } from "@/components/platform/PlatformHero"
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
  { topic: "Long memory", value: "63.3", unit: "%", label: "accuracy at an 8k-token budget, on default settings", source: "LongMemEval, Platform 0.9.1",
    meter: { before: { name: "0.9.0", value: 18.9, display: "18.9%" }, after: { name: "0.9.1", value: 63.3, display: "63.3%" }, max: 100 } },
  { topic: "Agent turns", value: "0", label: "repeated tool calls in 1,054 agent turns with continue_turn", source: "InjecAgent",
    meter: { before: { name: "Before", value: 50, display: "50" }, after: { name: "continue_turn", value: 0, display: "0" }, max: 50 } },
  { topic: "Cost", value: "67", unit: "×", label: "lower cost per question than sending the whole history, at Haiku 5.5 list prices", source: "Per 1,000 questions; 15× fewer tokens",
    meter: { before: { name: "Whole history", value: 90.72, display: "$90.72" }, after: { name: "Platform", value: 1.36, display: "$1.36" }, max: 90.72 } },
  { topic: "Reliability", value: "0", label: "histories that fail to compile at default settings", source: "LongMemEval, 90 histories",
    meter: { before: { name: "0.9.0", value: 28, display: "28 of 90" }, after: { name: "0.9.1", value: 0, display: "0" }, max: 28 } },
]

const comparison = [
  ["License", "MIT, open source", "Proprietary"],
  ["Install", "pip install llmslim", "By invitation"],
  ["Runs", "In your Python process", "As a service in your environment"],
  ["Focus", "Compress and plan model-visible context", "Agent state, decision traces, learned context policies"],
] as const

export default function PlatformPage() {
  return <div className="slim-site platform-site"><PageView event="platform_page_view" /><SiteHeader /><main id="main-content" className="platform-page">
    <PlatformHero version={siteConfig.platformVersion} />

    <section className="site-width platform-features feature-rows" aria-labelledby="capabilities-title">
      <h2 id="capabilities-title" className="sr-only">Platform capabilities</h2>
      <FeatureRow kicker="Temporal state" title="Know what is still true." visual={<Showcase><TimelineVisual /></Showcase>}>
        <p>An append-only, tamper-evident timeline of conversation, retrieval, memory, and tool events. Corrections replace the facts they correct instead of sitting beside them.</p>
        <p>Long sessions resume from verified checkpoints.</p>
      </FeatureRow>
      <FeatureRow flip kicker="Context traces" title="See why context was chosen." visual={<Showcase><TraceVisual /></Showcase>}>
        <p>Every prepared request comes with a trace: what went in, what was left out and why, and where each token went.</p>
        <p>Traces replay deterministically, so a decision can be audited long after it was made.</p>
      </FeatureRow>
      <FeatureRow kicker="Outcome learning" title="Learn which context wins." visual={<Showcase><PolicyVisual /></Showcase>}>
        <p>Record whether a task succeeded and link it to the context behind it. Offline training proposes context policies.</p>
        <p>They run in shadow until an evaluation passes and an administrator promotes them. Rollback is instant.</p>
      </FeatureRow>
      <FeatureRow flip kicker="Guardrails" title="Keep the guardrails first." visual={<Showcase><GuardVisual /></Showcase>}>
        <p>Learned suggestions can only leave out optional context. Trust boundaries, mandatory instructions, tenant isolation, and dependencies always win.</p>
        <p>Tool output and retrieved text reach the model as data, never as instructions.</p>
      </FeatureRow>
    </section>

    <section className="site-width platform-evidence" aria-labelledby="evidence-title">
      <p className="p-kicker">Measured on public benchmarks</p>
      <h2 id="evidence-title">Remembers what matters from 500 turns ago. <span>At 1/67 of the cost.*</span></h2>
      <StatsBand stats={platformStats} />
      <p className="platform-evidence-note">* LongMemEval-S, 90 questions over histories of about 50 chat sessions (115k tokens), official judge prompts. Platform 0.9.1 at its default settings and an 8k-token budget. Agent turns: InjecAgent, 1,054 cases, with the user message, the agent&apos;s call and its result ingested in order and the next step compiled with <code>prepare(continue_turn=True)</code>. The 0.9.0 figures published earlier came from a synthetic offline suite with no model answering; these replace them. Every context was read by Claude Haiku 5.5. <Link href="/benchmarks#longmemeval">Full results</Link></p>
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
