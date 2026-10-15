"use client"

import { LayoutGroup, m, useReducedMotion } from "framer-motion"
import { useState } from "react"
import { HEAD_TO_HEAD } from "@/data/live-benchmarks"
import { RACE, type RacePoint } from "@/data/results-story"
import { EASE, fmt } from "./Charts"

const W = 720, H = 430
const M = { left: 52, right: 28, top: 28, bottom: 52 }
/** Cost per 1,000 questions, log scale: 10 cents to $1,000. */
const X_MIN = -1, X_MAX = 3
const X_TICKS = [[0.1, "$0.10"], [1, "$1"], [10, "$10"], [100, "$100"], [1000, "$1,000"]] as const
const sx = (cost: number) => M.left + ((Math.log10(Math.max(cost, 0.1)) - X_MIN) / (X_MAX - X_MIN)) * (W - M.left - M.right)

function ticks([lo, hi]: [number, number]) {
  const step = hi - lo > 30 ? 10 : 5
  const out: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v)
  return out
}

function ratio(rival: RacePoint, ours: RacePoint) {
  const r = rival.cost / ours.cost
  return r >= 10 ? Math.round(r).toLocaleString("en-US") : r.toFixed(1)
}

/** Accuracy against what 1,000 questions cost end to end. Up and to the left is better. */
export function Race() {
  const [key, setKey] = useState(RACE[0].key)
  const reduced = useReducedMotion()
  const set = RACE.find((item) => item.key === key)!
  const [lo, hi] = set.y
  const sy = (score: number) => M.top + (1 - (Math.min(Math.max(score, lo), hi) - lo) / (hi - lo)) * (H - M.top - M.bottom)
  const spring = reduced ? { duration: 0 } : { type: "spring" as const, stiffness: 140, damping: 22 }
  const ranked = [...set.rows].sort((a, b) => b.score - a.score || a.cost - b.cost)
  const ours = set.rows.find((row) => row.kind === "llmslim")!
  const rival = set.rows.find((row) => row.name === set.rival)!
  const spanY = Math.min(Math.max(sy(ours.score), sy(rival.score)) + 30, H - M.bottom - 6)
  const flip = (row: RacePoint) => sx(row.cost) > W - 200
  const below = (row: RacePoint) => (row.place ?? (row.kind === "lite" || row.kind === "baseline" ? "below" : "above")) === "below"

  return <section className="rs-race" aria-labelledby="race-title">
    <header className="rs-head">
      <p className="rs-kicker">Head to head</p>
      <h2 id="race-title">More right answers per dollar. <em>Against memory systems and compressors.</em></h2>
      <p className="rs-lede">Accuracy against what 1,000 questions cost end to end, including the model calls that build Mem0&apos;s and Zep&apos;s memory. Up and to the left is better. We ran every system ourselves, with its own settings, on held-out questions.</p>
    </header>

    <LayoutGroup>
      <div className="rs-race-switch" role="tablist" aria-label="Benchmark">
        {RACE.map((item) => <button key={item.key} type="button" role="tab" aria-selected={key === item.key} onClick={() => setKey(item.key)}>
          {key === item.key && <m.span layoutId="race-tab" className="rs-race-tab" transition={spring} />}
          <span>{item.label}</span>
        </button>)}
      </div>

      <div className="rs-race-grid">
        <figure className="rs-race-chart">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${set.label}, ${set.n}: ${set.metric} against cost per 1,000 questions. ${ranked.map((row) => `${row.name} ${fmt(row.score, 1)} for $${fmt(row.cost, 2)}`).join(", ")}. ${set.full.label} ${fmt(set.full.score, 1)} for $${fmt(set.full.cost, 2)}.`}>
            {ticks(set.y).map((tick) => <g key={`${key}-${tick}`}><line className="rs-grid" x1={M.left} x2={W - M.right} y1={sy(tick)} y2={sy(tick)} /><text className="rs-tick" x={M.left - 12} y={sy(tick) + 4} textAnchor="end">{tick}</text></g>)}
            {X_TICKS.map(([cost, label]) => <g key={cost}><line className="rs-grid" x1={sx(cost)} x2={sx(cost)} y1={M.top} y2={H - M.bottom} /><text className="rs-tick" x={sx(cost)} y={H - M.bottom + 22} textAnchor="middle">{label}</text></g>)}
            <text className="rs-axis" x={W - M.right} y={H - 8} textAnchor="end">Cost per 1,000 questions, log scale</text>

            <m.g initial={false} animate={{ y: sy(set.full.score) }} transition={spring}>
              <line className="rs-ref" x1={M.left} x2={W - M.right} y1={0} y2={0} />
              <text className="rs-ref-label" x={W - M.right} y={-8} textAnchor="end">{set.full.label} {fmt(set.full.score, 1)} · ${fmt(set.full.cost, 2)}</text>
            </m.g>

            <m.g initial={false} animate={{ y: spanY }} transition={spring}>
              <line className="rs-span" x1={sx(ours.cost)} x2={sx(rival.cost)} y1={0} y2={0} />
              <line className="rs-span" x1={sx(ours.cost)} x2={sx(ours.cost)} y1={-5} y2={5} />
              <line className="rs-span" x1={sx(rival.cost)} x2={sx(rival.cost)} y1={-5} y2={5} />
              <text className="rs-span-label" x={(sx(ours.cost) + sx(rival.cost)) / 2} y={18} textAnchor="middle">{set.rival} costs {ratio(rival, ours)}× more</text>
            </m.g>

            {set.rows.map((row) => <m.g key={`${key}-${row.name}`} className={`rs-point is-${row.kind}`} initial={false} animate={{ x: sx(row.cost), y: sy(row.score) }} transition={spring}>
              <circle r={row.kind === "llmslim" ? 8 : 6.5} />
              <text x={flip(row) ? -14 : 14} y={row.dy ?? (below(row) ? 20 : -12)} textAnchor={flip(row) ? "end" : "start"}>{row.name} <tspan className="rs-point-score">{fmt(row.score, 1)}</tspan></text>
            </m.g>)}
          </svg>
        </figure>

        <ol className="rs-board">
          {ranked.map((row, i) => <m.li key={`${key}-${row.name}`} layout transition={spring} className={`rs-board-row is-${row.kind}`}>
            <span className="rs-board-rank">{i + 1}</span>
            <span className="rs-board-name">{row.name}<small>{row.model} · ${fmt(row.cost, 2)} per 1k</small></span>
            <span className="rs-board-score">{fmt(row.score, 1)}</span>
          </m.li>)}
        </ol>
      </div>
      <m.p key={key} className="rs-note" initial={reduced ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: EASE }}><strong>{set.n}.</strong> {set.note}</m.p>
      <p className="rs-note rs-sources">{HEAD_TO_HEAD.sources.map((source, index) => <span key={source.url}>{index > 0 && " · "}<a href={source.url} target="_blank" rel="noreferrer">{source.label}</a></span>)}</p>
    </LayoutGroup>
  </section>
}
