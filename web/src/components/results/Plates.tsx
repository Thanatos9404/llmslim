"use client"

import { motion, useMotionValueEvent, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useCallback, useEffect, useRef, useState } from "react"
import { BENCHMARKS, type Arm, type Benchmark } from "@/data/results-story"
import { Count, EASE, fmt } from "./Charts"

const pad = (n: number) => String(n).padStart(2, "0")
const digits = (value: number) => (Number.isInteger(value) ? 0 : 1)

/** One line per configuration: a hairline track and a filled rule up to the score. */
function Ruler({ arms, max }: { arms: Arm[]; max: number }) {
  const reduced = useReducedMotion()
  return <ul className="rs-ruler">
    {arms.map((arm, i) => <li key={arm.name} className={`rs-ruler-row is-${arm.kind}`}>
      <span className="rs-ruler-name">{arm.name}</span>
      <span className="rs-ruler-value">{fmt(arm.score, digits(arm.score))}</span>
      <span className="rs-ruler-track"><motion.span className="rs-ruler-fill" style={{ width: `${Math.max(0.6, (arm.score / max) * 100)}%` }}
        initial={reduced ? false : { scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true, amount: 0.6 }} transition={{ duration: 1.1, ease: EASE, delay: 0.15 + i * 0.08 }} /></span>
    </li>)}
  </ul>
}

/** A strip of squares: how much of the context was kept, or how many tasks came out right. */
function PixelStrip({ total, lit, label }: Benchmark["pixels"]) {
  const reduced = useReducedMotion()
  return <figure className="rs-strip">
    <motion.div className="rs-strip-grid" style={{ gridTemplateColumns: `repeat(${total / 2}, 1fr)` }} initial="off" whileInView="on" viewport={{ once: true, amount: 0.6 }}>
      {Array.from({ length: total }, (_, i) => {
        const on = (i % (total / 2)) * 2 + Math.floor(i / (total / 2)) < lit
        return <motion.i key={i} className={on ? "is-lit" : undefined}
          variants={{ off: { opacity: reduced ? 1 : 0.25 }, on: { opacity: 1 } }} transition={{ duration: 0.3, delay: reduced ? 0 : (on ? 0.2 : 0) + (i % (total / 2)) * 0.012 }} />
      })}
    </motion.div>
    <figcaption>{label}</figcaption>
  </figure>
}

function Plate({ bench, index }: { bench: Benchmark; index: number }) {
  const ours = bench.arms.find((arm) => arm.kind === "llmslim") ?? bench.arms[0]
  const full = bench.arms.find((arm) => arm.kind === "full")
  return <article className="rs-plate" aria-labelledby={`plate-${bench.id}`}>
    <header className="rs-plate-head">
      <span className="rs-plate-no">{pad(index + 1)}<span> / {pad(BENCHMARKS.length)}</span></span>
      <span className="rs-plate-topic">{bench.short}</span>
    </header>
    <div className="rs-plate-body">
      <div className="rs-plate-copy">
        <h3 id={`plate-${bench.id}`}>{bench.name}</h3>
        <p className="rs-plate-question">{bench.question}</p>
        <p className="rs-plate-verdict">{bench.verdict}</p>
      </div>
      <div className="rs-plate-figure">
        <p className="rs-plate-score"><Count to={ours.score} digits={digits(ours.score)} />{bench.unit && <span className="rs-plate-unit">{bench.unit}</span>}</p>
        <p className="rs-plate-vs">{bench.metric}{full ? `, ${fmt(full.score, digits(full.score))} with ${full.name.toLowerCase()}` : ""}</p>
        <Ruler arms={bench.arms} max={bench.max} />
      </div>
    </div>
    <footer className="rs-plate-foot">
      <PixelStrip {...bench.pixels} />
      <dl className="rs-plate-specs">{bench.info.slice(0, 3).map(([term, value]) => <div key={term}><dt>{term}</dt><dd>{value}</dd></div>)}</dl>
    </footer>
  </article>
}

/** Seven benchmarks as plates on a horizontal track. On wide screens the track is pinned and vertical scroll
 *  moves it sideways; on narrow screens and with reduced motion the plates simply stack. */
export function Plates() {
  const section = useRef<HTMLElement>(null)
  const track = useRef<HTMLDivElement>(null)
  const stops = useRef<number[]>([])
  const [distance, setDistance] = useState(0)
  const [wide, setWide] = useState(false)
  const [active, setActive] = useState(0)
  const reduced = useReducedMotion()
  const pinned = wide && !reduced

  const measure = useCallback(() => {
    const isWide = window.innerWidth >= 960
    setWide(isWide)
    const node = track.current
    if (!node) return
    const viewport = window.innerWidth
    const total = node.scrollWidth - viewport
    setDistance(Math.max(0, total))
    stops.current = Array.from(node.querySelectorAll<HTMLElement>(".rs-plate")).map((plate) => Math.max(0, Math.min(total, plate.offsetLeft - (viewport - plate.offsetWidth) / 2)))
  }, [])
  useEffect(() => {
    const frame = requestAnimationFrame(measure)
    const sized = new ResizeObserver(measure)
    if (track.current) sized.observe(track.current)
    window.addEventListener("resize", measure)
    return () => { cancelAnimationFrame(frame); sized.disconnect(); window.removeEventListener("resize", measure) }
  }, [measure])

  const { scrollYProgress } = useScroll({ target: section, offset: ["start start", "end end"] })
  const x = useTransform(scrollYProgress, (p) => -p * distance)
  const bar = useTransform(scrollYProgress, [0, 1], [0, 1])
  useMotionValueEvent(scrollYProgress, "change", (p) => {
    const at = p * distance
    let best = 0
    stops.current.forEach((stop, i) => { if (Math.abs(stop - at) < Math.abs(stops.current[best] - at)) best = i })
    setActive((current) => (current === best ? current : best))
  })
  const go = (i: number) => {
    if (!section.current) return
    const top = section.current.getBoundingClientRect().top + window.scrollY
    window.scrollTo({ top: top + (stops.current[i] ?? 0), behavior: "smooth" })
  }

  return <section ref={section} id="benchmarks" className={`rs-plates${pinned ? " is-pinned" : ""}`} aria-labelledby="plates-title" style={pinned ? { height: `calc(100vh + ${distance}px)` } : undefined}>
    <div className="rs-plates-pin">
      <motion.div ref={track} className="rs-plates-track" style={pinned ? { x } : undefined}>
        <div className="rs-plates-intro">
          <p className="rs-kicker">Seven benchmarks</p>
          <h2 id="plates-title">Memory, retrieval, documents, <em>and agents.</em></h2>
          <p className="rs-lede">Each one public, each one scored by its own official metric. Same reader and prompt for every run.</p>
          {pinned && <p className="rs-plates-hint" aria-hidden="true">Scroll to move through them</p>}
        </div>
        {BENCHMARKS.map((bench, i) => <Plate key={bench.id} bench={bench} index={i} />)}
      </motion.div>
      {pinned && <nav className="rs-plates-index" aria-label="Benchmarks">
        <motion.span className="rs-plates-progress" style={{ scaleX: bar }} aria-hidden="true" />
        {BENCHMARKS.map((bench, i) => <button key={bench.id} type="button" onClick={() => go(i)} aria-current={active === i ? "true" : undefined}>
          <span className="rs-plates-index-no">{pad(i + 1)}</span><span className="rs-plates-index-name">{bench.short}</span>
        </button>)}
      </nav>}
    </div>
  </section>
}
