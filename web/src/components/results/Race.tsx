"use client"

import { LayoutGroup, motion, useReducedMotion } from "framer-motion"
import { useState } from "react"
import { RACE } from "@/data/results-story"
import { EASE, fmt } from "./Charts"

const SETS = [
  { key: "all", label: "All 300", full: RACE.fullAll, note: "Over all 300 questions, LLMSlim with the reranker and LongLLMLingua are level: +0.7 points, 95% interval −4.7 to +6.0. LLMSlim leads LLMLingua-2 by 9.7 (3.7 to 15.7)." },
  { key: "fresh", label: "Fresh 150", full: RACE.fullFresh, note: "Fresh questions, drawn after the code was frozen and run once: LLMSlim with the reranker leads LongLLMLingua by 7.3 points." },
  { key: "score", label: "Original 150", full: RACE.full, note: "The original questions: LongLLMLingua leads by 6.0 points here, on a 7B model." },
] as const
type SetKey = (typeof SETS)[number]["key"]

const W = 720, H = 430
const M = { left: 52, right: 28, top: 28, bottom: 52 }
const X_MIN = 1, X_MAX = Math.log10(20000)
const Y_MIN = 40, Y_MAX = 95
const sx = (ms: number) => M.left + ((Math.log10(Math.max(ms, 10)) - X_MIN) / (X_MAX - X_MIN)) * (W - M.left - M.right)
const sy = (score: number) => M.top + (1 - (score - Y_MIN) / (Y_MAX - Y_MIN)) * (H - M.top - M.bottom)
const X_TICKS = [[10, "10 ms"], [100, "100 ms"], [1000, "1 s"], [10000, "10 s"]] as const
const Y_TICKS = [50, 60, 70, 80, 90]

const value = (row: (typeof RACE.rows)[number], key: SetKey) => row[key]
const points = RACE.rows.filter((row) => row.ms > 0)
const baseline = RACE.rows.find((row) => row.kind === "baseline")!

/** Accuracy against the time it takes to compress one question. Up and to the left is better. */
export function Race() {
  const [set, setSet] = useState<SetKey>("all")
  const reduced = useReducedMotion()
  const current = SETS.find((item) => item.key === set)!
  const spring = reduced ? { duration: 0 } : { type: "spring" as const, stiffness: 140, damping: 22 }
  const ranked = [...RACE.rows].sort((a, b) => value(b, set) - value(a, set))
  const ours = RACE.rows.find((row) => row.kind === "llmslim")!
  const rival = RACE.rows.find((row) => row.name === "LongLLMLingua")!
  const span = Math.min(sy(value(ours, set)), sy(value(rival, set))) - 34

  return <section className="rs-race" aria-labelledby="race-title">
    <header className="rs-head">
      <p className="rs-kicker">Head to head</p>
      <h2 id="race-title">Level with a 7B compressor. <em>At a hundredth of the compute.</em></h2>
      <p className="rs-lede">NaturalQuestions with 20 retrieved passages and the same token budget for every compressor. We ran LLMLingua-2 and LongLLMLingua ourselves, with their published settings.</p>
    </header>

    <LayoutGroup>
      <div className="rs-race-switch" role="tablist" aria-label="Question set">
        {SETS.map((item) => <button key={item.key} type="button" role="tab" aria-selected={set === item.key} onClick={() => setSet(item.key)}>
          {set === item.key && <motion.span layoutId="race-tab" className="rs-race-tab" transition={spring} />}
          <span>{item.label}</span>
        </button>)}
      </div>

      <div className="rs-race-grid">
        <figure className="rs-race-chart">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Accuracy against compression time on ${current.label}. ${ranked.map((row) => `${row.name} ${fmt(value(row, set), 1)}`).join(", ")}.`}>
            {Y_TICKS.map((tick) => <g key={tick}><line className="rs-grid" x1={M.left} x2={W - M.right} y1={sy(tick)} y2={sy(tick)} /><text className="rs-tick" x={M.left - 12} y={sy(tick) + 4} textAnchor="end">{tick}</text></g>)}
            {X_TICKS.map(([ms, label]) => <g key={ms}><line className="rs-grid" x1={sx(ms)} x2={sx(ms)} y1={M.top} y2={H - M.bottom} /><text className="rs-tick" x={sx(ms)} y={H - M.bottom + 22} textAnchor="middle">{label}</text></g>)}
            <text className="rs-axis" x={W - M.right} y={H - 8} textAnchor="end">Time to compress one question, log scale</text>

            <motion.g initial={false} animate={{ y: sy(current.full) }} transition={spring}>
              <line className="rs-ref" x1={M.left} x2={W - M.right} y1={0} y2={0} />
              <text className="rs-ref-label" x={W - M.right} y={-8} textAnchor="end">Full context {fmt(current.full, 1)}</text>
            </motion.g>
            <motion.g initial={false} animate={{ y: sy(value(baseline, set)) }} transition={spring}>
              <line className="rs-ref is-low" x1={M.left} x2={W - M.right} y1={0} y2={0} />
              <text className="rs-ref-label" x={W - M.right} y={-8} textAnchor="end">Cut to fit {fmt(value(baseline, set), 1)}</text>
            </motion.g>

            <motion.g initial={false} animate={{ y: span }} transition={spring}>
              <line className="rs-span" x1={sx(ours.ms)} x2={sx(rival.ms)} y1={0} y2={0} />
              <line className="rs-span" x1={sx(ours.ms)} x2={sx(ours.ms)} y1={-5} y2={5} />
              <line className="rs-span" x1={sx(rival.ms)} x2={sx(rival.ms)} y1={-5} y2={5} />
              <text className="rs-span-label" x={(sx(ours.ms) + sx(rival.ms)) / 2} y={-10} textAnchor="middle">about 100× less compute</text>
            </motion.g>

            {points.map((row) => <motion.g key={row.name} className={`rs-point is-${row.kind}`} initial={false} animate={{ x: sx(row.ms), y: sy(value(row, set)) }} transition={spring}>
              <circle r={row.kind === "llmslim" ? 8 : 6.5} />
              <text x={row.ms > 2000 ? -14 : 14} y={row.kind === "lite" ? 20 : -12} textAnchor={row.ms > 2000 ? "end" : "start"}>{row.name} <tspan className="rs-point-score">{fmt(value(row, set), 1)}</tspan></text>
            </motion.g>)}
          </svg>
        </figure>

        <ol className="rs-board">
          {ranked.map((row, i) => <motion.li key={row.name} layout transition={spring} className={`rs-board-row is-${row.kind}`}>
            <span className="rs-board-rank">{i + 1}</span>
            <span className="rs-board-name">{row.name}<small>{row.model}</small></span>
            <span className="rs-board-score">{fmt(value(row, set), 1)}</span>
          </motion.li>)}
        </ol>
      </div>
      <motion.p key={set} className="rs-note" initial={reduced ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: EASE }}>{current.note}</motion.p>
    </LayoutGroup>
  </section>
}
