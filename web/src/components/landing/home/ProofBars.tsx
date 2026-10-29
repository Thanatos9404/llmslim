"use client"

import { m, useReducedMotion } from "framer-motion"
import type { CSSProperties } from "react"
import { EASE } from "./motion"

export type ProofRow = { name: string; detail: string; score: number; kind: "llmslim" | "rival" | "reference"; mark?: string }

/** Accuracy bars on a full 0 to 100 scale, growing in once when the chart scrolls into view. */
export function ProofBars({ rows, caption }: { rows: ProofRow[]; caption: string }) {
  const reduced = useReducedMotion()
  return <figure className="lp-bars">
    <figcaption className="lp-sr">{caption}</figcaption>
    <ul>
      {rows.map((row, index) => <li key={row.name} data-kind={row.kind}>
        <div className="lp-bars-head">
          <span className="lp-bars-name">{row.name}{row.mark && <sup>{row.mark}</sup>}</span>
          <span className="lp-bars-detail">{row.detail}</span>
          <span className="lp-bars-score lp-num">{row.score.toFixed(1)}%</span>
        </div>
        <div className="lp-bars-track">
          <m.span className="lp-bars-fill" style={{ width: `${row.score}%`, originX: 0 } as CSSProperties}
            {...(reduced ? { initial: false, animate: { scaleX: 1 } } : { initial: { scaleX: 0 }, whileInView: { scaleX: 1 }, viewport: { once: true, amount: 0.6 }, transition: { duration: 1.1, ease: EASE, delay: index * 0.08 } })} />
        </div>
      </li>)}
    </ul>
  </figure>
}
