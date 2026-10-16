import type { Arm } from "@/data/live-benchmarks"

const LABEL: Record<Arm["kind"], string> = { full: "full context", llmslim: "LLMSlim", previous: "earlier LLMSlim", baseline: "baseline", competitor: "other system" }

function formatTokens(value: number) {
  return value >= 10_000 ? `${(value / 1000).toFixed(0)}k` : value.toLocaleString("en-US")
}

/** One suite's arms as horizontal bars, scaled to the best score, with tokens and cost beside each.
 *  `compact` draws thinner bars without the token and cost line (a second view of the suite).
 *  A server component: the bars grow with a CSS scroll-driven animation (globals.css, .rb-bar), so a page with dozens
 *  of them ships no script for them and hydrates nothing. */
export function ResultBars({ arms, metric, compact = false }: { arms: Arm[]; metric: string; compact?: boolean }) {
  const top = Math.max(...arms.map((arm) => arm.score))
  return <figure className={compact ? "rb is-compact" : "rb"}>
    <figcaption className="sr-only">{metric} by configuration</figcaption>
    <ul className="rb-list">{arms.map((arm) => <li key={arm.name} className={`rb-row is-${arm.kind}`}>
      <div className="rb-head">
        <span className="rb-name">{arm.name}<span className="sr-only"> ({LABEL[arm.kind]})</span></span>
        <span className="rb-score">{arm.score.toFixed(1)}</span>
      </div>
      <div className="rb-track" aria-hidden="true">
        <span className="rb-bar" style={{ width: `${(arm.score / top) * 100}%` }} />
      </div>
      {!compact && (arm.tokens !== undefined || arm.cost !== undefined) && <div className="rb-meta">
        {arm.tokens !== undefined && <span>{formatTokens(arm.tokens)} tokens</span>}
        {arm.cost !== undefined && <span>${arm.cost < 0.1 ? arm.cost.toFixed(3) : arm.cost.toFixed(2)} per 1k questions</span>}
      </div>}
    </li>)}</ul>
  </figure>
}
