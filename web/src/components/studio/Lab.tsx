"use client"

import { AnimatePresence, motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react"
import { ArrowRight, Check, CircleHelp, LoaderCircle, RotateCcw, X } from "lucide-react"
import { PRESETS, type Preset } from "@/data/studio-presets"
import { PixelField } from "@/components/results/PixelField"
import { Tour, useTour } from "./Tour"

type Result = {
  version: string
  selection: string | null
  original_tokens: number
  kept_tokens: number
  elapsed_ms: number
  compressed_text: string
  segments: [string, boolean][]
  baseline: { keep: "head" | "tail"; text: string; tokens: number }
}
type View = "marked" | "sent" | "cut"

const EASE = [0.16, 1, 0.3, 1] as const
const PRICE_PER_MILLION = 3
const fmt = (n: number, digits = 0) => n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
const has = (text: string, answer: string) => Boolean(answer) && text.toLowerCase().includes(answer.toLowerCase())

const TOUR = [
  { target: "scenario", title: "Pick a scenario", body: "Start with a real kind of context an agent carries: a long chat, search results or a CI log. Or paste your own." },
  { target: "question", title: "Ask what the agent needs", body: "LLMSlim keeps what answers this question. Change it and run again to see a different cut." },
  { target: "keep", title: "Choose how much to keep", body: "Drag to set the budget. A quarter of the text is a good start for long histories." },
  { target: "result", title: "See what stayed", body: "Kept lines are highlighted in place. The check shows whether the answer survived, next to plain truncation to the same size." },
]

/** Numbers that roll to their new value. */
function Rolling({ value, digits = 0 }: { value: number; digits?: number }) {
  return <AnimatePresence mode="popLayout" initial={false}>
    <motion.span key={value.toFixed(digits)} className="lab-roll" initial={{ y: "60%", opacity: 0, filter: "blur(4px)" }} animate={{ y: 0, opacity: 1, filter: "blur(0px)" }} exit={{ y: "-60%", opacity: 0, filter: "blur(4px)" }} transition={{ duration: 0.45, ease: EASE }}>
      {fmt(value, digits)}
    </motion.span>
  </AnimatePresence>
}

function Survival({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return <div className={`lab-check ${ok ? "is-ok" : "is-lost"}`}>
    <span className="lab-check-icon" aria-hidden="true">{ok ? <Check size={14} strokeWidth={2.4} /> : <X size={14} strokeWidth={2.4} />}</span>
    <span><strong>{label}</strong><small>{detail}</small></span>
  </div>
}

export function StudioLab() {
  const [presetId, setPresetId] = useState(PRESETS[0].id)
  const preset = PRESETS.find((item) => item.id === presetId) ?? PRESETS[0]
  const [text, setText] = useState(PRESETS[0].text)
  const [question, setQuestion] = useState(PRESETS[0].question)
  const [keep, setKeep] = useState(PRESETS[0].keep)
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [view, setView] = useState<View>("marked")
  const [stale, setStale] = useState(false)
  const request = useRef(0)
  const hero = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const tour = useTour("llmslim-studio-tour", TOUR.length)
  const { scrollYProgress } = useScroll({ target: hero, offset: ["start start", "end start"] })
  const fieldY = useTransform(scrollYProgress, [0, 1], [0, 120])
  const copyY = useTransform(scrollYProgress, [0, 1], [0, -50])

  const run = async (input: { text: string; question: string; keep: number; baseline: Preset["baseline"] }) => {
    if (!input.text.trim()) { setError("Paste some text first."); return }
    const id = ++request.current
    setBusy(true); setError("")
    try {
      const response = await fetch("/api/studio", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(input) })
      const body = await response.json().catch(() => null)
      if (id !== request.current) return
      if (!response.ok || !body?.data) throw new Error(body?.error?.message ?? "The Studio could not run. Please retry.")
      setResult(body.data as Result); setStale(false)
    } catch (problem) {
      if (id === request.current) setError(problem instanceof Error ? problem.message : "The Studio could not run. Please retry.")
    } finally {
      if (id === request.current) setBusy(false)
    }
  }

  // Run the first scenario as soon as the page opens, so there is a result to look at straight away.
  useEffect(() => {
    const timer = window.setTimeout(() => void run({ text: PRESETS[0].text, question: PRESETS[0].question, keep: PRESETS[0].keep, baseline: PRESETS[0].baseline }))
    return () => window.clearTimeout(timer)
  }, [])

  const choose = (next: Preset) => {
    setPresetId(next.id); setText(next.text); setQuestion(next.question); setKeep(next.keep); setView("marked")
    if (next.text) void run({ text: next.text, question: next.question, keep: next.keep, baseline: next.baseline })
    else { setResult(null); setError("") }
  }
  const go = () => void run({ text, question, keep, baseline: preset.baseline })

  const estimate = Math.round(text.length / 4)
  const saved = result ? result.original_tokens - result.kept_tokens : 0
  const smaller = result ? Math.round((saved / Math.max(1, result.original_tokens)) * 100) : 0
  const answer = preset.answer
  const keptAnswer = result ? has(result.compressed_text, answer) : false
  const cutAnswer = result ? has(result.baseline.text, answer) : false
  const pieces = useMemo(() => (result ? result.segments.filter(([piece]) => piece.trim()) : []), [result])
  const spot = (event: PointerEvent<HTMLElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty("--mx", `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty("--my", `${event.clientY - box.top}px`)
  }

  return <div className="lab">
    <section ref={hero} className="lab-hero" aria-labelledby="studio-title">
      <motion.div className="lab-hero-field" style={reduced ? undefined : { y: fieldY }}><PixelField /></motion.div>
      <motion.div className="lab-hero-copy" style={reduced ? undefined : { y: copyY }}>
        <p className="lab-kicker">Studio, running LLMSlim Core {result?.version ?? "0.8"}</p>
        <h1 id="studio-title">See what your agent <em>actually needs.</em></h1>
        <p className="lab-lede">Pick a scenario, ask a question and watch LLMSlim cut the context down to what answers it. Then see what plain truncation would have kept instead.</p>
        <button type="button" className="lab-tour-button" onClick={tour.start}><CircleHelp size={15} /> Take the 30-second tour</button>
      </motion.div>
    </section>

    <section className="lab-bench" aria-label="Compression lab" onPointerMove={spot}>
      <div className="lab-controls">
        <fieldset className="lab-step" data-tour="scenario">
          <legend><span className="lab-step-no">1</span>Pick a scenario</legend>
          <div className="lab-presets" role="radiogroup" aria-label="Scenario">
            {PRESETS.map((item) => <button key={item.id} type="button" role="radio" aria-checked={presetId === item.id} className="lab-preset" onClick={() => choose(item)}>
              {presetId === item.id && <motion.span layoutId="lab-preset" className="lab-preset-on" transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} />}
              <span className="lab-preset-name">{item.name}</span>
              <span className="lab-preset-blurb">{item.blurb}</span>
              {item.text && <span className="lab-preset-size">{fmt(Math.round(item.text.length / 4 / 100) / 10, 1)}k tokens</span>}
            </button>)}
          </div>
          {presetId === "own" && <textarea className="lab-paste" value={text} onChange={(event) => { setText(event.target.value); setStale(true) }} placeholder="Paste a long chat, a document, search results or a log. Up to about 16,000 tokens." rows={8} aria-label="Your text" />}
        </fieldset>

        <div className="lab-step" data-tour="question">
          <label className="lab-legend" htmlFor="lab-question"><span className="lab-step-no">2</span>Ask what the agent needs</label>
          <input id="lab-question" className="lab-input" value={question} onChange={(event) => { setQuestion(event.target.value); setStale(true) }} onKeyDown={(event) => { if (event.key === "Enter") go() }} placeholder="What should the model be able to answer?" />
        </div>

        <div className="lab-step" data-tour="keep">
          <label className="lab-legend" htmlFor="lab-keep"><span className="lab-step-no">3</span>Choose how much to keep</label>
          <div className="lab-keep">
            <span className="lab-keep-value">{Math.round(keep * 100)}<small>%</small></span>
            <span className="lab-keep-note">about {fmt(Math.round(estimate * keep))} of {fmt(estimate)} tokens</span>
          </div>
          <input id="lab-keep" type="range" min={0.1} max={0.6} step={0.05} value={keep} onChange={(event) => { setKeep(Number(event.target.value)); setStale(true) }} className="lab-range" style={{ ["--fill" as string]: `${((keep - 0.1) / 0.5) * 100}%` }} />
          <div className="lab-range-labels" aria-hidden="true"><span>Tighter</span><span>Looser</span></div>
        </div>

        <button type="button" className="lab-run" onClick={go} disabled={busy}>
          {busy ? <><LoaderCircle size={16} className="lab-spin" /> Compressing</> : <>{result && !stale ? <><RotateCcw size={15} /> Run again</> : <>Compress <ArrowRight size={16} /></>}</>}
        </button>
        <p className="lab-small">Runs on our server and returns the result. Nothing you paste is stored or logged.</p>
      </div>

      <div className="lab-output" data-tour="result" aria-live="polite">
        {error && <p className="lab-error" role="alert">{error}</p>}
        {!result && !error && <div className="lab-empty"><p>{presetId === "own" ? "Paste your text, ask a question and press Compress." : "Compressing…"}</p></div>}
        {result && <motion.div className={`lab-result${busy || stale ? " is-dim" : ""}`} initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }}>
          <dl className="lab-metrics">
            <div><dt>Tokens sent</dt><dd><Rolling value={result.kept_tokens} /><small>of {fmt(result.original_tokens)}</small></dd></div>
            <div><dt>Smaller</dt><dd><Rolling value={smaller} /><small>%</small></dd></div>
            <div><dt>Saved per 1,000 calls</dt><dd><small>$</small><Rolling value={(saved * 1000 * PRICE_PER_MILLION) / 1_000_000} digits={2} /></dd></div>
            <div><dt>Time</dt><dd><Rolling value={result.elapsed_ms} digits={0} /><small>ms</small></dd></div>
          </dl>
          {answer && <div className="lab-checks">
            <Survival label={keptAnswer ? "LLMSlim kept the answer" : "LLMSlim dropped the answer"} ok={keptAnswer} detail={`“${answer}” is ${keptAnswer ? "in" : "not in"} the compressed context`} />
            <Survival label={cutAnswer ? "Truncation kept it too" : "Truncation lost it"} ok={cutAnswer} detail={`Keeping the ${result.baseline.keep === "tail" ? "most recent" : "first"} ${fmt(result.baseline.tokens)} tokens`} />
          </div>}
          <div className="lab-map" aria-hidden="true">{pieces.map(([, kept], i) => <i key={i} className={kept ? "is-kept" : undefined} />)}</div>
          <div className="lab-tabs" role="tablist" aria-label="View">
            {([["marked", "Kept, in place"], ["sent", "What the model gets"], ["cut", "Plain truncation"]] as const).map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={view === key} onClick={() => setView(key)}>
              {view === key && <motion.span layoutId="lab-tab" className="lab-tab-on" transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} />}<span>{label}</span>
            </button>)}
          </div>
          <div className={`lab-text${preset.mono ? " is-mono" : ""}`} role="tabpanel">
            {view === "marked" && result.segments.map(([piece, kept], i) => piece.trim() ? <span key={i} className={kept ? "lab-kept" : "lab-dropped"}>{piece}</span> : piece)}
            {view === "sent" && result.compressed_text}
            {view === "cut" && result.baseline.text}
          </div>
        </motion.div>}
      </div>
    </section>

    <Tour steps={TOUR} state={tour} />
  </div>
}
