"use client"

import Link from "next/link"
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"
import { ArrowDown, ArrowRight, ArrowUpRight } from "lucide-react"
import { CONSISTENCY, READER, STILL_AHEAD } from "@/data/results-story"
import { siteConfig } from "@/config/site"
import { EASE, fmt } from "./Charts"
import { PixelField } from "./PixelField"
import { Plates } from "./Plates"
import { Race } from "./Race"
import { Squeeze } from "./Squeeze"

const FIGURES = [
  { value: "62", unit: "×", text: "cheaper long-chat memory at Haiku 5.5 list prices (14× fewer tokens), within noise of the whole history" },
  { value: "3", unit: "×", text: "fewer tokens on long documents, for the same score" },
  { value: "100", unit: "×", text: "faster per question than LongLLMLingua, and level with it on retrieval" },
]

function Hero() {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] })
  const copyY = useTransform(scrollYProgress, [0, 1], [0, -90])
  const fieldY = useTransform(scrollYProgress, [0, 1], [0, 140])
  const fade = useTransform(scrollYProgress, [0, 0.75], [1, 0])
  const rise = (delay: number) => (reduced ? {} : { initial: { opacity: 0, y: 26, filter: "blur(8px)" }, animate: { opacity: 1, y: 0, filter: "blur(0px)" }, transition: { duration: 1, ease: EASE, delay } })
  return <section ref={ref} className="rs-hero" aria-labelledby="results-title">
    <motion.div className="rs-hero-field" style={reduced ? undefined : { y: fieldY }}><PixelField /></motion.div>
    <motion.div className="rs-hero-copy" style={reduced ? undefined : { y: copyY, opacity: fade }}>
      <motion.p className="rs-kicker" {...rise(0)}>Results, October 2026<a href="#fine-print" className="rs-star" aria-label="How these were measured">*</a></motion.p>
      <motion.h1 id="results-title" {...rise(0.1)}>Cut the context.<br /><em>Keep the answers.</em></motion.h1>
      <motion.p className="rs-hero-lede" {...rise(0.2)}>Seven public benchmarks, run against full context and plain truncation, plus a head-to-head with the best-known open compressors on NaturalQuestions. Only the context changed between runs.</motion.p>
      <motion.dl className="rs-figures" {...rise(0.32)}>
        {FIGURES.map((figure) => <div key={figure.text}><dt><span>{figure.value}</span><em>{figure.unit}</em></dt><dd>{figure.text}</dd></div>)}
      </motion.dl>
    </motion.div>
    <a className="rs-scroll" href="#squeeze-anchor"><span>See one question through</span><ArrowDown size={15} /></a>
  </section>
}

/** Original and fresh questions side by side: one line for LLMSlim, a dashed one for full context. */
function Held() {
  const reduced = useReducedMotion()
  const lo = 50, hi = 92
  const y = (v: number) => 14 + (1 - (v - lo) / (hi - lo)) * 112
  return <section className="rs-held" aria-labelledby="held-title">
    <header className="rs-head">
      <p className="rs-kicker">Fresh questions</p>
      <h2 id="held-title">It held on questions <em>nobody had seen.</em></h2>
      <p className="rs-lede">Settings were tuned on separate development questions. After the code was frozen, every suite ran once more on a fresh sample.</p>
    </header>
    <div className="rs-held-row">
      {CONSISTENCY.map((row, i) => <figure key={row.suite} className="rs-held-cell">
        <figcaption><span>{row.suite}</span><small>{row.metric}</small></figcaption>
        <svg viewBox="0 0 220 140" role="img" aria-label={`${row.suite}: ${fmt(row.original, 1)} on the original questions, ${fmt(row.fresh, 1)} on fresh ones. Full context ${fmt(row.fullOriginal, 1)} and ${fmt(row.fullFresh, 1)}.`}>
          <line className="rs-held-axis" x1="40" x2="40" y1="8" y2="132" /><line className="rs-held-axis" x1="180" x2="180" y1="8" y2="132" />
          <motion.line className="rs-held-full" x1="40" x2="180" y1={y(row.fullOriginal)} y2={y(row.fullFresh)} initial={reduced ? false : { opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ duration: 1, ease: EASE, delay: 0.1 + i * 0.1 }} />
          <motion.line className="rs-held-ours" x1="40" x2="180" y1={y(row.original)} y2={y(row.fresh)} initial={reduced ? false : { pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: 1.1, ease: EASE, delay: 0.25 + i * 0.1 }} />
          <rect className="rs-held-dot" x="36" y={y(row.original) - 4} width="8" height="8" /><rect className="rs-held-dot" x="176" y={y(row.fresh) - 4} width="8" height="8" />
          <text className="rs-held-num" x="30" y={y(row.original) + 4} textAnchor="end">{fmt(row.original, 1)}</text>
          <text className="rs-held-num" x="190" y={y(row.fresh) + 4}>{fmt(row.fresh, 1)}</text>
        </svg>
        <p className="rs-held-legend"><span>Original</span><span>Fresh</span></p>
      </figure>)}
    </div>
    <p className="rs-note"><span className="rs-key is-ours" />LLMSlim with the reranker <span className="rs-key is-full" />Full context</p>
  </section>
}

function Close() {
  return <section className="rs-close" aria-labelledby="close-title">
    <div className="rs-close-field"><PixelField fade="bottom" gap={8} /></div>
    <h2 id="close-title">Run it on <em>your</em> context.</h2>
    <p className="rs-lede">Paste a long history, a stack of passages or a CI log, and watch what stays.</p>
    <div className="rs-close-actions">
      <Link className="button" href="/playground">Open the Studio <ArrowRight size={16} /></Link>
      <a className="button button-outline" href={`${siteConfig.github}/tree/main/benchmarks/live`} target="_blank" rel="noreferrer">Full report <ArrowUpRight size={16} /></a>
    </div>
    <div id="fine-print" className="rs-fine">
      <p>* Every context was read by {READER} with the same prompt; only the context changed. Confidence intervals are paired bootstrap 95% over the same questions. Times are to compress one question on one machine. The reranker is optional: <code>pip install &quot;llmslim[semantic]&quot;</code>, then <code>relevance=&quot;semantic&quot;</code>.</p>
      <p>{STILL_AHEAD} <Link href="/benchmarks">Every table and method</Link>.</p>
    </div>
  </section>
}

export function ResultsStory() {
  return <div className="rs">
    <Hero />
    <div id="squeeze-anchor" />
    <Squeeze />
    <Plates />
    <Race />
    <Held />
    <Close />
  </div>
}
