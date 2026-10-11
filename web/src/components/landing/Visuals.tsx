"use client"

import { animate, motion, useInView, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useEffect, useRef, type ReactNode } from "react"

// Product visuals in place of text boxes: each one shows what LLMSlim actually does.
// Transform and opacity only; reduced-motion users get the finished state.

const EASE = [0.16, 1, 0.3, 1] as const

/* ------------------------------------------------------------------ window chrome */

export function Window({ title, badge, children, className = "" }: { title: string; badge?: ReactNode; children: ReactNode; className?: string }) {
  return <div className={`win ${className}`}>
    <div className="win-bar"><span className="win-dots" aria-hidden="true"><i /><i /><i /></span><span className="win-title">{title}</span>{badge ? <span className="win-badge">{badge}</span> : <span />}</div>
    <div className="win-body">{children}</div>
  </div>
}

/** A gradient art panel with a window floating on it. The window settles as the panel scrolls into view. */
export function Showcase({ tone, children, className = "" }: { tone: "teal" | "violet" | "amber" | "rose"; children: ReactNode; className?: string }) {
  const panel = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: panel, offset: ["start end", "start 0.45"] })
  const y = useTransform(scrollYProgress, [0, 1], [56, 0])
  const rotateX = useTransform(scrollYProgress, [0, 1], [10, 0])
  return <div ref={panel} className={`showcase showcase-${tone} ${className}`}>
    <div className="showcase-art" aria-hidden="true" />
    <motion.div className="showcase-stage" style={reduced ? undefined : { y, rotateX, transformPerspective: 1400 }}>{children}</motion.div>
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
      <defs><linearGradient id="pv-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--viz-a)" stopOpacity=".35" /><stop offset="1" stopColor="var(--viz-a)" stopOpacity="0" /></linearGradient></defs>
      <path d={`${path} L 300 70 L 0 70 Z`} fill="url(#pv-fill)" />
      <motion.path d={path} fill="none" stroke="var(--viz-a)" strokeWidth="2" initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: 1.6, ease: EASE }} />
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

/* ------------------------------------------------------------------ stats over converging rays */

export type Stat = { value: string; unit?: string; label: string; note: string }

export function StatsBand({ stats }: { stats: Stat[] }) {
  return <div className="stats-band">
    <dl className="stats-row">{stats.map((stat, i) => <motion.div key={stat.label} className="stat" initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.5 }} transition={{ duration: 0.8, ease: EASE, delay: i * 0.08 }}>
      <dt className="stat-label">{stat.label}</dt><dd><span className="stat-value">{stat.value}{stat.unit && <span className="stat-unit">{stat.unit}</span>}</span><span className="stat-note">{stat.note}</span></dd>
    </motion.div>)}</dl>
    <Rays />
  </div>
}

function Rays() {
  // Many lines in from the left converge into one beam: long context in, focused context out.
  // The flow animation runs only while the band is on screen.
  const band = useRef<HTMLDivElement>(null)
  const live = useInView(band, { amount: 0.1 })
  const lines = Array.from({ length: 34 }, (_, i) => {
    const y0 = 8 + i * (224 / 33)
    return `M 0 ${y0.toFixed(1)} C 360 ${y0.toFixed(1)}, 520 ${(120 + (y0 - 120) * 0.25).toFixed(1)}, 760 120`
  })
  return <div ref={band} className={`rays ${live ? "is-live" : ""}`} aria-hidden="true">
    <svg viewBox="0 0 1200 240" preserveAspectRatio="none">
      <defs>
        <linearGradient id="ray-in" x1="0" x2="1"><stop offset="0" stopColor="var(--ink)" stopOpacity="0" /><stop offset=".55" stopColor="var(--ink)" stopOpacity=".22" /><stop offset="1" stopColor="var(--viz-a)" stopOpacity=".9" /></linearGradient>
        <linearGradient id="ray-out" x1="0" x2="1"><stop offset="0" stopColor="var(--viz-a)" /><stop offset="1" stopColor="var(--viz-b)" stopOpacity="0" /></linearGradient>
      </defs>
      {lines.map((d, i) => <path key={i} d={d} className="ray" stroke="url(#ray-in)" style={{ animationDelay: `${(i % 7) * -0.6}s` }} />)}
      <path d="M 760 120 L 1200 120" className="ray-beam" stroke="url(#ray-out)" />
    </svg>
    <span className="rays-label rays-label-in">Everything your agent has seen</span>
    <span className="rays-label rays-label-out">What the model needs</span>
  </div>
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
