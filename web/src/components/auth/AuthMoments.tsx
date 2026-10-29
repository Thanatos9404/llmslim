import type { CSSProperties } from "react"
import { LogoMark } from "@/components/brand/LogoMark"
import { MarkImage } from "@/components/landing/home/MarkImage"
import { DEMO_VERSION, PLAN_RECALL } from "@/data/landing-demo"
import { contextBlocks } from "@/lib/landing-context"

// The quiet product moments beside the sign-in and sign-up cards (desktop only, decorative: aria-hidden). Server
// markup animated with CSS; reduced motion shows the final frame. The window shows real llmslim 0.12.0 output, the
// same as the home page's hero.

type Vars = CSSProperties & Record<`--${string}`, string | number>

/** Strands entering from the left and converging on one point at the right edge: the logo's idea, quietly. */
function Converge({ count, kept, className }: { count: number; kept: number; className: string }) {
  const H = 320
  const lines = Array.from({ length: count }, (_, index) => {
    const y0 = 16 + (index * (H - 32)) / (count - 1)
    const keep = index % Math.round(count / kept) === 1
    const y1 = H / 2 + (keep ? (index - count / 2) * 2.5 : (y0 - H / 2) * 0.35)
    return { d: keep ? `M0 ${y0} C120 ${y0} 120 ${y1} 240 ${y1}` : `M0 ${y0} C90 ${y0} 110 ${y1} 170 ${y1}`, keep, index }
  })
  return <svg className={className} viewBox={`0 0 240 ${H}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id={`${className}-kept`} x1="0" y1="0" x2="240" y2="0" gradientUnits="userSpaceOnUse">
        <stop offset="0" className="lp-stop-violet" /><stop offset=".55" className="lp-stop-blue" /><stop offset="1" className="lp-stop-green" />
      </linearGradient>
      <linearGradient id={`${className}-faint`} x1="0" y1="0" x2="170" y2="0" gradientUnits="userSpaceOnUse">
        <stop offset="0" className="lp-stop-ink" /><stop offset="1" className="lp-stop-ink" stopOpacity="0" />
      </linearGradient>
    </defs>
    {lines.map((line) => <path key={line.index} d={line.d} pathLength={1} className={line.keep ? "auth-strand is-kept" : "auth-strand"}
      stroke={`url(#${className}-${line.keep ? "kept" : "faint"})`} style={{ "--i": line.index } as Vars} />)}
  </svg>
}

/** Sign in: a glass memory.search window recalling what this user asked for, as LLMSlim really returned it. */
export function RecallMoment() {
  const sections = contextBlocks(PLAN_RECALL.text).filter((block) => block.kind === "section")
  let line = 0
  return <div className="auth-moment" aria-hidden="true">
    <p className="auth-moment-eyebrow">Welcome back</p>
    <p className="auth-moment-title">Your agents remember what was asked. So does your account.</p>
    <div className="auth-moment-stage">
      <Converge count={12} kept={4} className="auth-converge" />
      <div className="auth-window lp-glass">
        <div className="auth-window-bar">
          <MarkImage size={12} />
          <span className="lp-mono">memory.search</span>
          <span className="auth-window-tag lp-mono">llmslim {DEMO_VERSION}</span>
        </div>
        <div className="auth-window-body">
          <p className="auth-window-question">{PLAN_RECALL.question}</p>
          {sections.map((block) => <div key={block.title} className="auth-window-section" data-section={block.title.startsWith("Requests") ? "requests" : "preferences"} style={{ "--i": line++ } as Vars}>
            <p className="auth-window-section-title">{block.title}</p>
            {block.lines.map((item) => <p key={item.stamp} className="auth-window-line"><span className="lp-mono">[{item.stamp}]</span> {item.text}</p>)}
          </div>)}
          <div className="auth-window-meter" style={{ "--fill": PLAN_RECALL.tokens / PLAN_RECALL.budget } as Vars}>
            <span><b className="lp-num">{PLAN_RECALL.tokens}</b> / {PLAN_RECALL.budget} tokens</span>
            <span className="auth-window-track"><i /></span>
            <span className="auth-window-zero">No LLM call</span>
          </div>
        </div>
      </div>
    </div>
    <p className="auth-moment-note">Real output from llmslim {DEMO_VERSION}: the standing request and the preference come back on their own.</p>
  </div>
}

/** Sign up: the mark's five strands drawing in, fed by many faint ones, and what Core is. */
export function StrandsMoment() {
  return <div className="auth-moment" aria-hidden="true">
    <div className="auth-moment-stage is-mark">
      <Converge count={14} kept={5} className="auth-converge" />
      <div className="auth-mark-orb"><LogoMark size={88} className="auth-mark" /></div>
    </div>
    <p className="auth-moment-title">Memory for AI agents that no LLM rewrites.</p>
    <ul className="auth-moment-facts">
      <li>Every turn kept word for word, in SQLite or Postgres</li>
      <li>No LLM call to store or recall</li>
      <li>Works with any MCP client</li>
      <li>Core is free and MIT licensed</li>
    </ul>
  </div>
}
