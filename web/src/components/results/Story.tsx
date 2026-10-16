"use client"

import Link from "next/link"
import { m, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, type CSSProperties } from "react"
import { ArrowDown, ArrowRight, ArrowUpRight } from "lucide-react"
import { READER, STILL_AHEAD } from "@/data/results-story"
import { ROUND3_REPORT, WEAK_SPOTS } from "@/data/live-benchmarks"
import { PixelField } from "./PixelField"
import { Plates } from "./Plates"
import { Race } from "./Race"
import { Squeeze } from "./Squeeze"

const FIGURES = [
  { value: "42", unit: "×", text: "lower cost than the whole chat history on LongMemEval, at the same accuracy (77.8%)" },
  { value: "212", unit: "×", text: "lower cost than Mem0 on its own LongMemEval questions, and as accurate (78.3% vs 76.7%)" },
  { value: "20", unit: "pts", text: "ahead of LongLLMLingua on LoCoMo conversations (93.3% vs 73.3%), at a seventh of its cost" },
]

function Hero() {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] })
  const copyY = useTransform(scrollYProgress, [0, 1], [0, -90])
  const fieldY = useTransform(scrollYProgress, [0, 1], [0, 140])
  const fade = useTransform(scrollYProgress, [0, 0.75], [1, 0])
  // Entrance from first paint, in CSS, so the copy does not wait for scripts (see .rise in globals.css).
  const rise = (delay: number) => ({ style: { "--rise-delay": `${delay}s` } as CSSProperties })
  return <section ref={ref} className="rs-hero" aria-labelledby="results-title">
    <m.div className="rs-hero-field" style={reduced ? undefined : { y: fieldY }}><PixelField /></m.div>
    <m.div className="rs-hero-copy" style={reduced ? undefined : { y: copyY, opacity: fade }}>
      <p className="rs-kicker rise" {...rise(0)}>Results, October 2026<a href="#fine-print" className="rs-star" aria-label="How these were measured">*</a></p>
      <h1 id="results-title" className="rise" {...rise(0.1)}>Cut the context.<br /><em>Keep the answers.</em></h1>
      <p className="rs-hero-lede rise" {...rise(0.2)}>LLMSlim Core 0.9 against Mem0, Zep, LLMLingua-2, LongLLMLingua and dense retrieval, on held-out test questions read by the same model. Only the context changed between runs, and every cost is end to end.</p>
      <dl className="rs-figures rise" {...rise(0.32)}>
        {FIGURES.map((figure) => <div key={figure.text}><dt><span>{figure.value}</span><em>{figure.unit}</em></dt><dd>{figure.text}</dd></div>)}
      </dl>
    </m.div>
    <a className="rs-scroll" href="#squeeze-anchor"><span>See one question through</span><ArrowDown size={15} /></a>
  </section>
}

/** Where LLMSlim still trails, from the round-3 report. */
function Loses() {
  return <section className="rs-held" aria-labelledby="loses-title">
    <header className="rs-head">
      <p className="rs-kicker">Weak spots</p>
      <h2 id="loses-title">Where it loses. <em>Published with the rest.</em></h2>
      <p className="rs-lede">LLMSlim was tuned on separate development questions, and the test questions were read once. These are the places it trails.</p>
    </header>
    <div className="rs-held-row">
      {WEAK_SPOTS.map((spot) => <article key={spot.title} className="rs-held-cell rs-loses-cell"><h3>{spot.title}</h3><p>{spot.body}</p></article>)}
    </div>
  </section>
}

function Close() {
  return <section className="rs-close" aria-labelledby="close-title">
    <div className="rs-close-field"><PixelField fade="bottom" gap={8} /></div>
    <h2 id="close-title">Run it on <em>your</em> context.</h2>
    <p className="rs-lede">Paste a long history, a stack of passages or a CI log, and watch what stays.</p>
    <div className="rs-close-actions">
      <Link className="button" href="/playground">Open the Studio <ArrowRight size={16} /></Link>
      <a className="button button-outline" href={ROUND3_REPORT} target="_blank" rel="noreferrer">Full report <ArrowUpRight size={16} /></a>
    </div>
    <div id="fine-print" className="rs-fine">
      <p>* Every context was read by {READER} with the same prompt; only the context changed. Costs are per 1,000 questions at list prices, end to end: the answer call, Mem0&apos;s and Zep&apos;s memory-building calls, and each system&apos;s compute. Confidence intervals are paired bootstrap 95% over the same questions. Long documents and agents were measured on Core 0.8. The reranker is optional: <code>pip install &quot;llmslim[semantic]&quot;</code>, then <code>relevance=&quot;semantic&quot;</code>.</p>
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
    <Loses />
    <Close />
  </div>
}
