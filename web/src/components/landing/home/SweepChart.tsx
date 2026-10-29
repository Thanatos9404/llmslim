"use client"

import { m, useReducedMotion } from "framer-motion"
import { useId, useState } from "react"
import { EASE } from "./motion"

type Point = readonly [budget: number, tokens: number]

// Chart frame, in viewBox units.
const W = 640, H = 248
const LEFT = 44, RIGHT = 12, TOP = 12, BOTTOM = 32
const MIN = 0, MAX = 300

/**
 * The plan question asked at every budget from 30 to 300 tokens: what came back (the filled line) never crosses
 * the budget (the diagonal). A range input picks a budget and reads off what came back at it.
 */
export function SweepChart({ points, question }: { points: readonly Point[]; question: string }) {
  const reduced = useReducedMotion()
  const id = useId()
  const [budget, setBudget] = useState(points[points.length - 1][0])
  const first = points[0][0], last = points[points.length - 1][0]
  const x = (b: number) => LEFT + ((b - first) / (last - first)) * (W - LEFT - RIGHT)
  const y = (t: number) => TOP + (1 - (t - MIN) / (MAX - MIN)) * (H - TOP - BOTTOM)
  const line = points.map(([b, t], i) => `${i ? "L" : "M"}${x(b).toFixed(1)} ${y(t).toFixed(1)}`).join(" ")
  const area = `${line} L${x(last).toFixed(1)} ${y(0)} L${x(first).toFixed(1)} ${y(0)} Z`
  const limit = `M${x(first)} ${y(first)} L${x(last)} ${y(last)}`
  const over = `M${x(first)} ${y(first)} L${x(last)} ${y(last)} L${x(last)} ${y(MAX)} L${x(first)} ${y(MAX)} Z`
  const current = points.find(([b]) => b === budget) ?? points[points.length - 1]
  // Reduced motion: the final state at once. `animate` (not nothing) so it overrides the hidden state the server rendered.
  const draw = reduced ? { initial: false, animate: { pathLength: 1 } } : { initial: { pathLength: 0 }, whileInView: { pathLength: 1 }, viewport: { once: true, amount: 0.4 }, transition: { duration: 1.6, ease: EASE } }
  const fade = reduced ? { initial: false, animate: { opacity: 1 } } : { initial: { opacity: 0 }, whileInView: { opacity: 1 }, viewport: { once: true, amount: 0.4 }, transition: { duration: 1, ease: EASE, delay: 0.6 } }

  return <div className="lp-sweep">
    <div className="lp-sweep-read" aria-hidden="true">
      <span><b className="lp-num">{current[0]}</b> token budget</span>
      <span><b className="lp-num">{current[1]}</b> tokens returned</span>
    </div>
    <svg className="lp-sweep-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={`${id}-title`}>
      <title id={`${id}-title`}>{`"${question}" asked at ${points.length} budgets from ${first} to ${last} tokens. Every answer stayed at or under its budget.`}</title>
      <defs>
        <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" className="lp-sweep-fill-top" /><stop offset="1" className="lp-sweep-fill-bottom" />
        </linearGradient>
        <linearGradient id={`${id}-line`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" className="lp-stop-violet" /><stop offset=".5" className="lp-stop-blue" /><stop offset="1" className="lp-stop-green" />
        </linearGradient>
        <pattern id={`${id}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" className="lp-sweep-hatch" />
        </pattern>
      </defs>
      {[100, 200, 300].map((t) => <g key={t} className="lp-sweep-grid">
        <line x1={LEFT} x2={W - RIGHT} y1={y(t)} y2={y(t)} />
        <text x={LEFT - 8} y={y(t) + 4} textAnchor="end">{t}</text>
      </g>)}
      <path d={over} fill={`url(#${id}-hatch)`} className="lp-sweep-over" />
      <text x={x(first) + 8} y={y(MAX) + 18} className="lp-sweep-label">Over budget</text>
      <path d={limit} className="lp-sweep-limit" />
      <m.path d={area} fill={`url(#${id}-fill)`} {...fade} />
      <m.path d={line} className="lp-sweep-line" stroke={`url(#${id}-line)`} {...draw} />
      <line x1={x(current[0])} x2={x(current[0])} y1={y(MAX)} y2={y(0)} className="lp-sweep-cursor" />
      <circle cx={x(current[0])} cy={y(current[0])} r="3.5" className="lp-sweep-budget-dot" />
      <circle cx={x(current[0])} cy={y(current[1])} r="5" className="lp-sweep-dot" />
      <text x={x(first)} y={H - 10} className="lp-sweep-axis">{first}</text>
      <text x={x(last)} y={H - 10} textAnchor="end" className="lp-sweep-axis">{last} tokens</text>
    </svg>
    <label className="lp-sweep-range">
      <span className="lp-sr">Token budget</span>
      <input type="range" min={first} max={last} step={1} value={budget} onChange={(event) => setBudget(Number(event.target.value))}
        aria-valuetext={`${current[0]} token budget, ${current[1]} tokens returned`} />
    </label>
  </div>
}
