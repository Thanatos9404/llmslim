"use client"

import { motion, useMotionValueEvent, useReducedMotion, useScroll } from "framer-motion"
import { useEffect, useRef, useState } from "react"
import { EASE, fmt } from "./Charts"

/* One square is 100 tokens of a real LongMemEval history: 114,006 tokens in, 7,984 kept. */
const TOTAL = 1140
const KEPT = 80
const TOKENS_IN = 114006
const TOKENS_OUT = 7984
const COST_IN = 90.72
const COST_OUT = 1.45

const STEPS = [
  { kicker: "The history", title: "Fifty chat sessions. 114,006 tokens.", body: "A real long-memory history. The question needs a few lines of it." },
  { kicker: "The read", title: "Every round, scored against the question.", body: "Lexical ranking with no model at all, or a 22M-parameter reranker for a sharper read." },
  { kicker: "The cut", title: "Seven percent stays, in its original order.", body: "Kept rounds go to the model whole, with their session headers. Everything else is left out." },
  { kicker: "The answer", title: "76.7% right. The whole history scored 82.2%.", body: "At 1/62 of the cost at Haiku 5.5 list prices, with 14× fewer tokens. On a fresh sample it scored 76.7% against 72.2% for the whole history, within noise." },
]

const clamp = (value: number) => Math.max(0, Math.min(1, value))
const ease = (t: number) => 1 - Math.pow(1 - t, 3)
const span = (p: number, from: number, to: number) => clamp((p - from) / (to - from))

function random(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Relevance, fall speed and delay per square. Eight relevant rounds of ten squares each are the kept set. */
function model() {
  const next = random(7)
  const kept = new Uint8Array(TOTAL)
  const starts = [52, 171, 318, 402, 597, 731, 902, 1068]
  starts.forEach((start) => { for (let i = 0; i < 10; i++) kept[start + i] = 1 })
  const near = (i: number) => starts.some((start) => i >= start - 8 && i < start + 18)
  return Array.from({ length: TOTAL }, (_, i) => ({
    kept: kept[i] === 1,
    relevance: kept[i] ? 0.8 + next() * 0.2 : near(i) ? 0.3 + next() * 0.35 : Math.pow(next(), 2) * 0.45,
    speed: 0.45 + next() * 1.1,
    delay: next() * 0.55,
    drift: (next() - 0.5) * 40,
  }))
}

function token(element: Element, name: string, fallback: string) {
  return getComputedStyle(element).getPropertyValue(name).trim() || fallback
}

export function Squeeze() {
  const section = useRef<HTMLElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const tokens = useRef<HTMLSpanElement>(null)
  const cost = useRef<HTMLSpanElement>(null)
  const progress = useRef(0)
  const redraw = useRef<() => void>(() => {})
  const reduced = useReducedMotion()
  const [step, setStep] = useState(0)
  const { scrollYProgress } = useScroll({ target: section, offset: ["start start", "end end"] })

  useEffect(() => {
    const element = canvas.current
    const context = element?.getContext("2d")
    if (!element || !context) return
    const squares = model()
    let width = 0, height = 0, frame = 0
    let ink = "#888", accent = "#57dbb7"
    const grid = { cols: 0, cell: 0, x: 0, y: 0 }
    const block = { cols: 10, cell: 0, x: 0, y: 0 }

    const colours = () => { ink = token(element, "--ink", ink); accent = token(element, "--brand", accent) }
    const resize = () => {
      const box = element.getBoundingClientRect()
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = box.width; height = box.height
      element.width = Math.round(width * ratio); element.height = Math.round(height * ratio)
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      grid.cols = Math.max(12, Math.round(Math.sqrt((TOTAL * width) / height)))
      const rows = Math.ceil(TOTAL / grid.cols)
      grid.cell = Math.min(width / grid.cols, height / rows)
      grid.x = (width - grid.cell * grid.cols) / 2
      grid.y = (height - grid.cell * rows) / 2
      block.cell = Math.min(width, height) / 13
      block.x = (width - block.cell * block.cols) / 2
      block.y = (height - block.cell * (KEPT / block.cols)) / 2
    }
    const draw = () => {
      frame = 0
      const p = reduced ? 1 : progress.current
      const appear = span(p, 0, 0.12)
      const scan = span(p, 0.16, 0.42)
      const cut = span(p, 0.46, 0.72)
      const gather = span(p, 0.76, 0.96)
      context.clearRect(0, 0, width, height)
      let keptIndex = 0
      for (let i = 0; i < TOTAL; i++) {
        const square = squares[i]
        const col = i % grid.cols, row = Math.floor(i / grid.cols)
        let x = grid.x + col * grid.cell, y = grid.y + row * grid.cell
        let size = grid.cell * 0.68
        if (i / TOTAL > appear * 1.05) { if (square.kept) keptIndex++; continue }
        const scanned = col / grid.cols < scan
        let alpha = scanned ? 0.1 + square.relevance * 0.55 : 0.2
        let colour = ink
        if (square.kept) {
          if (scanned) { colour = accent; alpha = 1 }
          const local = ease(clamp((gather - (keptIndex / KEPT) * 0.35) / 0.65))
          const bx = block.x + (keptIndex % block.cols) * block.cell
          const by = block.y + Math.floor(keptIndex / block.cols) * block.cell
          x += (bx - x) * local; y += (by - y) * local
          size += (block.cell * 0.78 - size) * local
          keptIndex++
        } else {
          const local = clamp((cut - square.delay * 0.6) / 0.4)
          if (local >= 1) continue
          y += local * local * height * 0.7 * square.speed
          x += local * square.drift
          alpha *= 1 - local
        }
        context.globalAlpha = alpha
        context.fillStyle = colour
        context.fillRect(x, y, size, size)
      }
      if (scan > 0 && scan < 1) {
        context.globalAlpha = 0.5
        context.fillStyle = accent
        context.fillRect(grid.x + scan * grid.cols * grid.cell, grid.y - 12, 1, height - grid.y * 2 + 24)
      }
      context.globalAlpha = 1
      const shrink = ease(cut)
      if (tokens.current) tokens.current.textContent = fmt(Math.round(TOKENS_IN + (TOKENS_OUT - TOKENS_IN) * shrink))
      if (cost.current) cost.current.textContent = `$${fmt(COST_IN + (COST_OUT - COST_IN) * shrink, 2)}`
    }
    redraw.current = () => { if (!frame) frame = requestAnimationFrame(draw) }

    colours(); resize(); draw()
    const sized = new ResizeObserver(() => { resize(); draw() })
    sized.observe(element)
    const themed = new MutationObserver(() => { colours(); draw() })
    themed.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] })
    return () => { cancelAnimationFrame(frame); sized.disconnect(); themed.disconnect() }
  }, [reduced])

  useMotionValueEvent(scrollYProgress, "change", (p) => {
    progress.current = p
    redraw.current()
    const next = p < 0.2 ? 0 : p < 0.45 ? 1 : p < 0.75 ? 2 : 3
    setStep((current) => (current === next ? current : next))
  })

  return <section ref={section} className={`rs-squeeze${reduced ? " is-static" : ""}`} aria-labelledby="squeeze-title">
    <div className="rs-squeeze-pin">
      <div className="rs-squeeze-copy">
        <p className="rs-kicker">One question, one long memory</p>
        <h2 id="squeeze-title" className="rs-visually-hidden">How LLMSlim compresses a long chat history</h2>
        <ol className="rs-steps">
          {STEPS.map((item, index) => <motion.li key={item.kicker} className="rs-step" aria-current={!reduced && step === index ? "step" : undefined}
            animate={reduced ? undefined : { opacity: step === index ? 1 : 0.16, y: step === index ? 0 : step > index ? -6 : 6 }} transition={{ duration: 0.6, ease: EASE }}>
            <span className="rs-step-no">{String(index + 1).padStart(2, "0")}</span>
            <div><p className="rs-step-kicker">{item.kicker}</p><h3>{item.title}</h3><div className="rs-step-more"><p>{item.body}</p></div></div>
          </motion.li>)}
        </ol>
      </div>
      <div className="rs-squeeze-stage">
        <canvas ref={canvas} className="rs-squeeze-canvas" role="img" aria-label="1,140 squares, one per 100 tokens of chat history. Eighty relevant ones are kept and gathered into a small block; the rest fall away." />
        <dl className="rs-squeeze-meter">
          <div><dt>Context</dt><dd><span ref={tokens}>{fmt(reduced ? TOKENS_OUT : TOKENS_IN)}</span> tokens</dd></div>
          <div><dt>Per 1,000 questions</dt><dd><span ref={cost}>{`$${fmt(reduced ? COST_OUT : COST_IN, 2)}`}</span></dd></div>
        </dl>
      </div>
    </div>
  </section>
}
