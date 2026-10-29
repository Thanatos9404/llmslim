import type { CSSProperties } from "react"
import { DEMO_VERSION, PLAN_RECALL, STORED_TURNS } from "@/data/landing-demo"
import { contextBlocks, returnedTurns } from "@/lib/landing-context"
import { HeroStage } from "./HeroStage"
import { MarkImage } from "./MarkImage"

// Geometry shared by the turn rail and the strands, in CSS pixels. The strands' viewBox uses the same units
// vertically; horizontally its 200 units stretch to the gap between the rail and the window (about 150 to 250px).
const ROW = 28
const RAIL_HEAD = 48
const RAIL_HEIGHT = RAIL_HEAD + STORED_TURNS.length * ROW + 8
const INLET = RAIL_HEAD + (STORED_TURNS.length * ROW) / 2
const BUNDLE_GAP = 7
const SPAN = 200

type Vars = CSSProperties & Record<`--${string}`, string | number>

const kept = returnedTurns(STORED_TURNS, PLAN_RECALL)
const keptOrder = [...kept].sort((a, b) => a - b)
const blocks = contextBlocks(PLAN_RECALL.text)

/** "2026-09-02T10:14" as "09-02 10:14", for the compact rail. */
const short = (at: string) => `${at.slice(5, 10)} ${at.slice(11, 16)}`

function strandPath(index: number) {
  const y0 = RAIL_HEAD + index * ROW + ROW / 2
  const slot = keptOrder.indexOf(index)
  if (slot >= 0) {
    const y1 = INLET + (slot - (keptOrder.length - 1) / 2) * BUNDLE_GAP
    return { kept: true, d: `M0 ${y0} H24 C104 ${y0} 88 ${y1} 168 ${y1} H${SPAN}` }
  }
  const mid = y0 + (INLET - y0) * 0.5
  return { kept: false, d: `M0 ${y0} H24 C88 ${y0} 92 ${mid} 132 ${mid}` }
}

/**
 * The hero visual: the 16 stored turns on the left, their strands converging (the logo's idea) into the few that
 * answer, and a glass window with what `Memory.search` really returned for the deploy question, filling its token
 * meter to 284 of 300. Server-rendered and animated with CSS from the first paint; HeroStage adds the replay button,
 * the tilt on scroll and the pause when it is off screen.
 */
export function HeroDemo() {
  const strands = STORED_TURNS.map((_, index) => ({ index, ...strandPath(index) }))
  let line = 0
  const next = () => line++
  return <HeroStage>
    <div className="lp-stage" style={{ "--row": `${ROW}px`, "--rail-head": `${RAIL_HEAD}px`, "--rail-h": `${RAIL_HEIGHT}px`, "--inlet": `${INLET}px` } as Vars}>
      <div className="lp-rail lp-glass" aria-hidden="true">
        <div className="lp-rail-head"><span>Stored turns</span><span className="lp-num">{STORED_TURNS.length}</span></div>
        <ol>
          {STORED_TURNS.map((turn, index) => <li key={index} data-kept={kept.has(index) ? "" : undefined} data-role={turn.role} style={{ "--i": index } as Vars}>
            <span className="lp-rail-time">{short(turn.at)}</span>
            <span className="lp-rail-dot" />
            <span className="lp-rail-text">{turn.text}</span>
          </li>)}
        </ol>
      </div>

      <svg className="lp-strands" viewBox={`0 0 ${SPAN} ${RAIL_HEIGHT}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="lp-strand-kept" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={SPAN} y2="0">
            <stop offset="0" className="lp-stop-violet" /><stop offset=".5" className="lp-stop-blue" /><stop offset="1" className="lp-stop-green" />
          </linearGradient>
          <linearGradient id="lp-strand-dropped" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="132" y2="0">
            <stop offset="0" className="lp-stop-ink" /><stop offset="1" className="lp-stop-ink" stopOpacity="0" />
          </linearGradient>
        </defs>
        <g className="lp-strands-glow">{strands.filter((s) => s.kept).map((s) => <path key={s.index} d={s.d} pathLength={1} style={{ "--i": s.index } as Vars} />)}</g>
        <g>{strands.map((s) => <path key={s.index} d={s.d} pathLength={1} className={s.kept ? "lp-strand is-kept" : "lp-strand"} style={{ "--i": s.index } as Vars} />)}</g>
        <g className="lp-pulses">{strands.filter((s) => s.kept).map((s, k) => <path key={s.index} d={s.d} pathLength={1} style={{ "--k": k } as Vars} />)}</g>
      </svg>

      <figure className="lp-window lp-glass">
        <span className="lp-window-port" aria-hidden="true" />
        <div className="lp-window-bar">
          <MarkImage size={14} />
          <span className="lp-mono">memory.search</span>
          <span className="lp-window-tag lp-mono">llmslim {DEMO_VERSION}</span>
        </div>
        <div className="lp-window-ask">
          <span className="lp-window-label">Question</span>
          <p className="lp-window-question">{PLAN_RECALL.question}<span className="lp-caret" aria-hidden="true" /></p>
          <span className="lp-window-budget lp-mono">budget={PLAN_RECALL.budget}</span>
        </div>
        <div className="lp-strip" aria-hidden="true">
          {STORED_TURNS.map((_, index) => <i key={index} data-kept={kept.has(index) ? "" : undefined} style={{ "--i": index } as Vars} />)}
        </div>
        <div className="lp-window-body">
          <span className="lp-window-label">Returned context</span>
          <div className="lp-ctx">
            {blocks.map((block, b) => block.kind === "section"
              ? <div key={b} className="lp-ctx-section" data-section={block.title.startsWith("Requests") ? "requests" : "preferences"}>
                <p className="lp-ctx-title" style={{ "--i": next() } as Vars}>{block.title}</p>
                {block.lines.map((item, n) => <p key={n} className="lp-ctx-line" style={{ "--i": next() } as Vars}>
                  <span className="lp-ctx-bullet">- </span><span className="lp-stamp">[{item.stamp}]</span> {item.text}
                </p>)}
              </div>
              : <div key={b} className="lp-ctx-session">
                {block.lines.map((item, n) => <p key={n} className="lp-ctx-line" style={{ "--i": next() } as Vars}>
                  <span className="lp-stamp">[{item.stamp}]</span> <span className="lp-role" data-role={item.role}>{item.role}:</span> {item.text}
                </p>)}
              </div>)}
          </div>
        </div>
        <div className="lp-meter" style={{ "--fill": PLAN_RECALL.tokens / PLAN_RECALL.budget, "--tokens": PLAN_RECALL.tokens } as Vars}>
          <div className="lp-meter-head">
            <span>Tokens returned</span>
            <span className="lp-num"><span className="lp-count" aria-hidden="true" /><span className="lp-sr">{PLAN_RECALL.tokens}</span> / {PLAN_RECALL.budget}</span>
          </div>
          <div className="lp-meter-track"><span className="lp-meter-fill" /></div>
          <div className="lp-meter-foot">
            <span>{kept.size} of {STORED_TURNS.length} turns returned, from {PLAN_RECALL.historyTokens} stored tokens</span>
            <span className="lp-meter-zero">No LLM call</span>
          </div>
        </div>
        <figcaption className="lp-sr">
          Real output of llmslim {DEMO_VERSION}: asked “{PLAN_RECALL.question}” with a budget of {PLAN_RECALL.budget} tokens,
          Memory.search returned {kept.size} of {STORED_TURNS.length} stored turns in {PLAN_RECALL.tokens} tokens, including the
          standing request and the stated preference in their own sections, with no LLM call.
        </figcaption>
      </figure>
    </div>
  </HeroStage>
}
