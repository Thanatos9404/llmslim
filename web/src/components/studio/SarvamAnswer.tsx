"use client"

import { AnimatePresence, m, useReducedMotion } from "framer-motion"
import Link from "next/link"
import { useEffect, useState } from "react"
import { ArrowRight, LoaderCircle, RotateCcw } from "lucide-react"
import { track } from "@/lib/analytics"

/**
 * Step 4 of the Studio: send the compressed context and the question to Sarvam and show the answer.
 *
 * The page holds no provider credential and stores nothing. It asks the server whether the step is
 * configured (GET) and hides it otherwise; the server owns the key, the spend ledger and the limits.
 * Nothing is sent to Sarvam until the visitor presses the button.
 */

const ENDPOINT = "/api/sarvam_answer"
const EASE = [0.16, 1, 0.3, 1] as const

/** The installed Core's dated price table, which every cost estimate on this step uses. */
export type SarvamPricing = { core_version: string; as_of: string | null; currency: string; input_per_million: number; output_per_million: number }
export type SarvamReadiness = { model: string; maxPromptBytes: number; maxQuestionChars: number; pricing: SarvamPricing | null }

type Usage = {
  estimated?: { input_tokens?: number; max_output_tokens?: number; max_cost_inr?: number } | null
  provider_reported?: { prompt_tokens: number | null; completion_tokens: number | null; total_tokens: number | null; cost_inr: number | null } | null
  accounted_cost_inr?: number | null
  latency_ms?: number | null
}
type Answer = {
  answer: string
  model: string
  context: { submitted_tokens: number; sent_tokens: number | null; further_compressed: boolean }
  usage: Usage | null
  pricing?: SarvamPricing | null
}
type Outcome = { key: string; data?: Answer; error?: string }

const count = (n: number) => n.toLocaleString("en-US")
const rupees = (n: number) => `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: n < 1 ? 4 : 2 })}`
const isCount = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n) && n >= 0
const encoder = typeof TextEncoder === "undefined" ? null : new TextEncoder()
/** UTF-8 bytes, which bound the tokens Sarvam can bill. The server applies the same rule. */
const bytes = (text: string) => (encoder ? encoder.encode(text).length : text.length * 4)
const asPricing = (value: unknown): SarvamPricing | null => {
  const p = value as Partial<SarvamPricing> | null
  return p && typeof p.core_version === "string" && isCount(p.input_per_million) && isCount(p.output_per_million) ? p as SarvamPricing : null
}

/** Asks the server once whether the Sarvam step is configured. Null until it says it is. */
export function useSarvamReadiness(): SarvamReadiness | null {
  const [readiness, setReadiness] = useState<SarvamReadiness | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(ENDPOINT, { signal: controller.signal, cache: "no-store" })
      .then(response => (response.ok ? response.json() : null))
      .then(body => {
        if (body?.ready !== true || typeof body.model !== "string" || !isCount(body.max_prompt_bytes)) return
        setReadiness({ model: body.model, maxPromptBytes: body.max_prompt_bytes, maxQuestionChars: isCount(body.max_question_chars) ? body.max_question_chars : 500, pricing: asPricing(body.pricing) })
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [])
  return readiness
}

export function SarvamAnswer({ readiness, context, question, originalTokens, waiting }: {
  readiness: SarvamReadiness
  /** The compressed text the Studio produced, or null before the first result. */
  context: string | null
  question: string
  originalTokens: number | null
  /** True while the Studio is compressing or its inputs changed since the last run. */
  waiting: boolean
}) {
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  const [busy, setBusy] = useState(false)
  const reduced = useReducedMotion()
  const key = `${question}\u0000${context ?? ""}`
  const shown = outcome?.key === key ? outcome : null

  const blocked = !context
    ? "Compress some text first."
    : waiting
      ? "Run the compression again, then ask Sarvam."
      : !question.trim()
        ? "Ask a question in step 2 first."
        : question.length > readiness.maxQuestionChars
          ? `Keep the question under ${count(readiness.maxQuestionChars)} characters.`
          : bytes(context) + 2 * bytes(question.trim()) > readiness.maxPromptBytes
            ? "This compressed context is too long to send to Sarvam here. Keep less and run again."
            : ""

  const ask = async () => {
    if (blocked || busy || !context) return
    const asked = key
    setBusy(true)
    try {
      const response = await fetch(ENDPOINT, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ context, question }) })
      const body = await response.json().catch(() => null)
      if (!response.ok || typeof body?.data?.answer !== "string") throw new Error(typeof body?.error?.message === "string" ? body.error.message : "Sarvam could not answer this time. Please retry later.")
      const data = body.data as Answer
      setOutcome({ key: asked, data })
      track("studio_sarvam_answer", { ok: true, context_tokens: data.context?.submitted_tokens ?? undefined, original_tokens: originalTokens ?? undefined })
    } catch (problem) {
      setOutcome({ key: asked, error: problem instanceof Error ? problem.message : "Sarvam could not answer this time. Please retry later." })
      track("studio_sarvam_answer", { ok: false, original_tokens: originalTokens ?? undefined })
    } finally {
      setBusy(false)
    }
  }

  const data = shown?.data
  const reported = data?.usage?.provider_reported ?? null
  const tokens = reported?.total_tokens ?? null
  const cost = reported?.cost_inr ?? data?.usage?.accounted_cost_inr ?? data?.usage?.estimated?.max_cost_inr ?? null
  // The Studio's own count of the compressed context, unless the planner had to trim it further.
  const sent = (data?.context.further_compressed ? data.context.sent_tokens : null) ?? data?.context.submitted_tokens ?? null
  const latency = data?.usage?.latency_ms
  const prices = asPricing(data?.pricing) ?? readiness.pricing

  return <section className="lab-answer" data-tour="answer" aria-labelledby="lab-answer-title">
    <div className="lab-answer-ask">
      <h2 id="lab-answer-title" className="lab-legend"><span className="lab-step-no">4</span>Answer with Sarvam</h2>
      <p className="lab-answer-lede">Send only the compressed context and your question to Sarvam’s <code>{readiness.model}</code> and read what it answers.</p>
      <button type="button" className="lab-run lab-answer-run" onClick={() => void ask()} disabled={Boolean(blocked) || busy} aria-describedby="lab-answer-note">
        {busy ? <><LoaderCircle size={16} className="lab-spin" /> Asking Sarvam</> : data ? <><RotateCcw size={15} /> Ask again</> : <>Answer with Sarvam <ArrowRight size={16} /></>}
      </button>
      <p id="lab-answer-note" className="lab-small lab-answer-note">{blocked || <>Sent to Sarvam AI only when you press the button. We store nothing. <Link className="text-link" href="/privacy">Privacy</Link></>}</p>
    </div>

    <div className="lab-answer-out" aria-live="polite">
      <AnimatePresence mode="wait" initial={false}>
        {shown?.error && <m.p key="error" className="lab-error" role="alert" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>{shown.error}</m.p>}
        {data && <m.div key={`answer-${key}`} className={busy ? "is-dim" : undefined} initial={reduced ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.45, ease: EASE }}>
          <p className="lab-answer-label">{data.model} answered</p>
          <div className="lab-answer-text">{data.answer || "Sarvam returned an empty answer."}</div>
          <dl className="lab-metrics lab-answer-metrics">
            <div><dt>Context sent</dt><dd>{sent === null ? "–" : count(sent)}<small>{originalTokens !== null ? `of ${count(originalTokens)}` : "tokens"}</small></dd></div>
            <div><dt>Sarvam counted</dt><dd>{tokens === null ? "–" : count(tokens)}<small>tokens</small></dd></div>
            <div><dt>Cost</dt><dd>{cost === null ? "–" : rupees(cost)}</dd></div>
            <div><dt>Time</dt><dd>{isCount(latency) ? count(Math.round(latency)) : "–"}<small>ms</small></dd></div>
          </dl>
          <p className="lab-small lab-answer-fine">
            {reported && reported.prompt_tokens !== null && reported.completion_tokens !== null ? `Sarvam reported ${count(reported.prompt_tokens)} input and ${count(reported.completion_tokens)} output tokens, including the question and instructions. ` : "Sarvam did not report usage, so the cost shown is the reserved upper bound. "}
            {prices ? `Cost is an estimate from LLMSlim ${prices.core_version}’s price table for ${data.model}${prices.as_of ? ` (as of ${prices.as_of})` : ""}: ₹${prices.input_per_million.toFixed(2)} and ₹${prices.output_per_million.toFixed(2)} per million input and output tokens. Sarvam’s bill may differ.` : "Cost is an estimate from LLMSlim’s price table; Sarvam’s bill may differ."}
            {data.context.further_compressed ? " The context was trimmed further to fit the model budget." : ""}
          </p>
        </m.div>}
        {!shown && <m.p key="empty" className="lab-answer-empty" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>The answer, the tokens Sarvam counted and the cost appear here.</m.p>}
      </AnimatePresence>
    </div>
  </section>
}
