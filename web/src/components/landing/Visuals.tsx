"use client"

import { animate, motion, useInView, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useEffect, useRef, type PointerEvent, type ReactNode } from "react"

// Product visuals in place of text boxes: each one shows what LLMSlim actually does.
// Transform and opacity only; reduced-motion users get the finished state.

const EASE = [0.16, 1, 0.3, 1] as const

/* ------------------------------------------------------------------ window chrome */

export function Window({ title, badge, children, className = "" }: { title: string; badge?: ReactNode; children: ReactNode; className?: string }) {
  return <div className={`win ${className}`}>
    <div className="win-bar"><span className="win-title"><span className="win-pixel" aria-hidden="true" />{title}</span>{badge ? <span className="win-badge">{badge}</span> : <span />}</div>
    <div className="win-body">{children}</div>
  </div>
}

/** A neutral plate with a fading dot grid. The product rises out of its bottom edge as the plate scrolls in,
 *  and a soft light follows the cursor across it. */
export function Showcase({ children, className = "" }: { children: ReactNode; className?: string }) {
  const panel = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: panel, offset: ["start end", "end start"] })
  const y = useTransform(scrollYProgress, [0, 0.5, 1], [56, 0, -16])
  const move = (event: PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty("--spot-x", `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty("--spot-y", `${event.clientY - box.top}px`)
  }
  return <div ref={panel} className={`stage ${className}`} onPointerMove={move}>
    <div className="stage-spot" aria-hidden="true" />
    <motion.div className="stage-mock" style={reduced ? undefined : { y }}>{children}</motion.div>
  </div>
}

function Count({ to, from = 0, suffix = "", duration = 1.6 }: { to: number; from?: number; suffix?: string; duration?: number }) {
  const node = useRef<HTMLSpanElement>(null)
  const inView = useInView(node, { once: true, amount: 0.8 })
  const reduced = useReducedMotion()
  const format = (v: number) => `${Math.round(v).toLocaleString("en-US")}${suffix}`
  useEffect(() => {
    if (!inView || !node.current || reduced) return
    const controls = animate(from, to, { duration, ease: EASE, onUpdate: (v) => { if (node.current) node.current.textContent = format(v) } })
    return () => controls.stop()
  }, [inView, reduced]) // eslint-disable-line react-hooks/exhaustive-deps
  return <span ref={node}>{format(to)}</span>
}

/* ------------------------------------------------------------------ Core: tokens being selected */

// A fixed pattern (not random) so server and client render the same cells.
const CELLS = Array.from({ length: 72 }, (_, i) => ({ keep: [0, 1, 5, 9, 10, 14, 19, 22, 23, 27, 31, 36, 37, 41, 46, 50, 51, 55, 58, 63, 64, 68, 70, 71].includes(i), width: 18 + ((i * 37) % 5) * 9 }))

export function CompressVisual({ before, after, foot }: { before: number; after: number; foot: ReactNode }) {
  const grid = useRef<HTMLDivElement>(null)
  const inView = useInView(grid, { once: true, amount: 0.5 })
  const reduced = useReducedMotion()
  const done = inView || reduced
  return <Window title="agent.py · llmslim.compress()" badge={<><span className="dot-live" />local</>}>
    <div className="cv-row"><span>Context in</span><span className="cv-num">{before.toLocaleString("en-US")} tokens</span></div>
    <div ref={grid} className="cv-grid" aria-hidden="true">
      {CELLS.map((cell, i) => <motion.i key={i} className={cell.keep ? "is-keep" : ""} style={{ width: cell.width }}
        initial={false} animate={done ? (cell.keep ? { opacity: 1, scale: 1 } : { opacity: 0.14, scale: 0.92 }) : { opacity: 0.7, scale: 1 }}
        transition={{ duration: 0.7, ease: EASE, delay: reduced ? 0 : 0.25 + (i % 24) * 0.025 }} />)}
    </div>
    <div className="cv-row"><span>Sent to the model</span><span className="cv-num cv-num-accent"><Count to={after} from={before} /> tokens</span></div>
    <div className="cv-bar" aria-hidden="true"><motion.span initial={false} animate={{ scaleX: done ? after / before : 1 }} transition={{ duration: 1.4, ease: EASE, delay: reduced ? 0 : 0.3 }} /></div>
    <div className="cv-foot">{foot}</div>
  </Window>
}

/* ------------------------------------------------------------------ Platform: a context trace */

type TraceRow = { handle: string; kind: "state" | "evidence" | "tool" | "dialogue"; text: string; status: "kept" | "superseded" | "data" | "dropped" }

const TRACE: TraceRow[] = [
  { handle: "s1", kind: "state", text: 'user.home_city = "Delhi"', status: "kept" },
  { handle: "h1", kind: "state", text: 'user.home_city = "Pune"', status: "superseded" },
  { handle: "e3", kind: "evidence", text: "Renewal signed: 50 pilot workspaces", status: "kept" },
  { handle: "t1", kind: "tool", text: "IMPORTANT!!! Ignore all previous instructions…", status: "data" },
  { handle: "e7", kind: "evidence", text: "Q3 offsite agenda, catering notes", status: "dropped" },
  { handle: "d9", kind: "dialogue", text: "When does the contract renew?", status: "kept" },
]
const STATUS_LABEL = { kept: "sent", superseded: "superseded", data: "data, not instruction", dropped: "left out" }
const BUDGET = [["state", 0.12], ["evidence", 0.38], ["tool", 0.14], ["dialogue", 0.27]] as const

export function TraceVisual({ used = "7,287", total = "8,000" }: { used?: string; total?: string }) {
  const list = useRef<HTMLUListElement>(null)
  const inView = useInView(list, { once: true, amount: 0.4 })
  const reduced = useReducedMotion()
  const show = inView || reduced
  return <Window title="trace · turn 214" badge="replayable">
    <ul ref={list} className="tv-list">
      {TRACE.map((row, i) => <motion.li key={row.handle} className={`tv-row is-${row.status}`} initial={false}
        animate={show ? { opacity: 1, x: 0 } : { opacity: 0, x: -14 }} transition={{ duration: 0.6, ease: EASE, delay: reduced ? 0 : 0.1 + i * 0.09 }}>
        <span className="tv-handle">{row.handle}</span><span className={`tv-kind tv-${row.kind}`}>{row.kind}</span>
        <span className="tv-text">{row.text}</span><span className="tv-status">{STATUS_LABEL[row.status]}</span>
      </motion.li>)}
    </ul>
    <div className="tv-budget"><div className="tv-budget-bar" aria-hidden="true">{BUDGET.map(([kind, share], i) =>
      <motion.span key={kind} className={`tb-${kind}`} style={{ width: `${share * 100}%`, originX: 0 }} initial={false}
        animate={{ scaleX: show ? 1 : 0 }} transition={{ duration: 0.9, ease: EASE, delay: reduced ? 0 : 0.6 + i * 0.12 }} />)}</div>
      <span>{used} / {total} tokens</span></div>
  </Window>
}

/* ------------------------------------------------------------------ Platform page: three more */

export function TimelineVisual() {
  const steps = [["May 1", 'home_city = "Pune"', "superseded"], ["May 20", 'home_city = "Delhi"', "correction"], ["Today", 'home_city = "Delhi"', "active"]] as const
  return <Window title="state · user.home_city" badge="verified">
    <ol className="tl-list">{steps.map(([when, fact, state], i) => <motion.li key={when} className={`tl-step is-${state}`} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.6 }} transition={{ duration: 0.6, ease: EASE, delay: i * 0.15 }}>
      <span className="tl-when">{when}</span><span className="tl-node" aria-hidden="true" /><span className="tl-fact">{fact}</span><span className="tl-state">{state}</span>
    </motion.li>)}</ol>
    <p className="win-note">One answer reaches the model. The history stays in the ledger.</p>
  </Window>
}

export function PolicyVisual() {
  const stages = ["Shadow", "Evaluated", "Canary", "Active"]
  const points = [38, 41, 40, 47, 52, 55, 61, 63, 66, 71]
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${i * (300 / (points.length - 1))} ${90 - p}`).join(" ")
  return <Window title="policy · support-agent" badge="rollback ready">
    <div className="pv-stages">{stages.map((stage, i) => <span key={stage} className={i === 2 ? "is-current" : i < 2 ? "is-done" : ""}>{stage}</span>)}</div>
    <svg className="pv-chart" viewBox="0 0 300 70" aria-hidden="true" preserveAspectRatio="none">
      <path d={`${path} L 300 70 L 0 70 Z`} fill="var(--brand)" fillOpacity=".08" />
      <motion.path d={path} fill="none" stroke="var(--brand)" strokeWidth="1.5" initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: 1.6, ease: EASE }} />
    </svg>
    <p className="win-note">Suggestions run in shadow until an offline evaluation passes.</p>
  </Window>
}

export function GuardVisual() {
  const layers = [["System instructions", "locked"], ["Developer policy", "locked"], ["Tenant isolation", "enforced"], ["Tool output", "data only"]] as const
  return <Window title="trust boundaries" badge="always first">
    <ul className="gv-list">{layers.map(([name, state], i) => <motion.li key={name} className={i === 3 ? "is-untrusted" : ""} initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.6 }} transition={{ duration: 0.55, ease: EASE, delay: i * 0.1 }}><span>{name}</span><span className="gv-state">{state}</span></motion.li>)}</ul>
    <p className="win-note">Learned policies can only leave out optional context.</p>
  </Window>
}

/* ------------------------------------------------------------------ receipts ledger */

type Bar = { name: string; value: number; display: string }
export type Stat = { topic: string; value: string; unit?: string; label: string; source: string; meter: { before: Bar; after: Bar; max: number } }

/** Counts up to a value like "62", "+23" or "63.3" the first time it is seen. */
function Ticker({ value }: { value: string }) {
  const node = useRef<HTMLSpanElement>(null)
  const inView = useInView(node, { once: true, amount: 0.8 })
  const reduced = useReducedMotion()
  useEffect(() => {
    if (!inView || reduced || !node.current) return
    const sign = value.startsWith("+") ? "+" : ""
    const target = parseFloat(value.replace("+", ""))
    const digits = value.includes(".") ? value.split(".")[1].length : 0
    const controls = animate(0, target, { duration: 1.4, ease: EASE, onUpdate: (v) => { if (node.current) node.current.textContent = `${sign}${v.toFixed(digits)}` } })
    return () => controls.stop()
  }, [inView, reduced, value])
  return <span ref={node}>{value}</span>
}

function Meter({ bar, max, ours, delay }: { bar: Bar; max: number; ours?: boolean; delay: number }) {
  const reduced = useReducedMotion()
  return <div className={`ledger-bar${ours ? " is-ours" : ""}`}>
    <span>{bar.name}</span><span className="ledger-bar-value">{bar.display}</span>
    <span className="ledger-bar-track"><motion.span className="ledger-bar-fill" style={{ width: `${Math.max(0, Math.min(100, (bar.value / max) * 100))}%` }}
      initial={reduced ? false : { scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true, amount: 0.8 }} transition={{ duration: 1.2, ease: EASE, delay }} /></span>
  </div>
}

/** Four results in one ledger. A light follows the cursor across the panel and its edge. */
export function StatsBand({ stats }: { stats: Stat[] }) {
  const reduced = useReducedMotion()
  const move = (event: PointerEvent<HTMLDListElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty("--mx", `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty("--my", `${event.clientY - box.top}px`)
  }
  return <dl className="ledger" onPointerMove={move}>
    {stats.map((stat, i) => <motion.div key={stat.topic} className="ledger-cell" initial={reduced ? false : { opacity: 0, y: 18, filter: "blur(6px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }} viewport={{ once: true, amount: 0.4 }} transition={{ duration: 0.8, ease: EASE, delay: i * 0.08 }}>
      <dt className="ledger-topic">{stat.topic}</dt>
      <dd className="ledger-value"><Ticker value={stat.value} />{stat.unit && <span className="ledger-unit">{stat.unit}</span>}</dd>
      <dd className="ledger-label">{stat.label}</dd>
      <dd className="ledger-meter">
        <Meter bar={stat.meter.before} max={stat.meter.max} delay={0.2 + i * 0.08} />
        <Meter bar={stat.meter.after} max={stat.meter.max} ours delay={0.35 + i * 0.08} />
      </dd>
      <dd className="ledger-source">{stat.source}</dd>
    </motion.div>)}
  </dl>
}

/* ------------------------------------------------------------------ feature row */

export function FeatureRow({ kicker, title, children, visual, flip = false }: { kicker: string; title: ReactNode; children: ReactNode; visual: ReactNode; flip?: boolean }) {
  return <div className={`feature-row ${flip ? "is-flipped" : ""}`}>
    <motion.div className="feature-copy" initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.4 }} transition={{ duration: 0.8, ease: EASE }}>
      <p className="p-kicker">{kicker}</p><h3>{title}</h3><div className="feature-body">{children}</div>
    </motion.div>
    <div className="feature-visual">{visual}</div>
  </div>
}
