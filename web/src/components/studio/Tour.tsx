"use client"

import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react"
import { createPortal } from "react-dom"
import { ArrowLeft, ArrowRight, X } from "lucide-react"

type Step = { target: string; title: string; body: string }
type Box = { top: number; left: number; width: number; height: number }
export type TourState = ReturnType<typeof useTour>

const PAD = 10
const subscribe = () => () => {}
const CARD = 340

/** Opens once on the first visit; Skip or Done remembers that for this browser. */
export function useTour(key: string, count: number) {
  const [step, setStep] = useState(0)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    let seen = true
    try { seen = window.localStorage.getItem(key) === "done" } catch { /* storage blocked: treat as seen */ }
    if (seen) return
    const timer = window.setTimeout(() => setOpen(true), 1100)
    return () => window.clearTimeout(timer)
  }, [key])
  const finish = useCallback(() => {
    setOpen(false)
    try { window.localStorage.setItem(key, "done") } catch { /* nothing to remember */ }
  }, [key])
  return {
    step, open, count,
    start: () => { setStep(0); setOpen(true) },
    next: () => (step + 1 >= count ? finish() : setStep(step + 1)),
    back: () => setStep(Math.max(0, step - 1)),
    finish,
  }
}

function measure(target: string): Box | null {
  const element = document.querySelector<HTMLElement>(`[data-tour="${target}"]`)
  if (!element) return null
  const box = element.getBoundingClientRect()
  return { top: box.top - PAD, left: box.left - PAD, width: box.width + PAD * 2, height: box.height + PAD * 2 }
}

/** Where the card goes: beside the target when there is room, below or above it otherwise, and docked to the
 *  bottom of the screen on phones. */
function place(box: Box) {
  const vw = window.innerWidth, vh = window.innerHeight
  const width = Math.min(CARD, vw - 32)
  if (vw >= 900 && box.left + box.width + 16 + width <= vw - 16) return { left: box.left + box.width + 16, top: Math.min(Math.max(16, box.top), vh - 260), width }
  if (vw >= 900 && box.left - 16 - width >= 16) return { left: box.left - 16 - width, top: Math.min(Math.max(16, box.top), vh - 260), width }
  if (vw < 900) return { left: 16, top: vh - 236, width: vw - 32 }
  const left = Math.min(Math.max(16, box.left), vw - width - 16)
  return box.top + box.height + 240 < vh ? { left, top: box.top + box.height + 14, width } : { left, top: Math.max(16, box.top - 234), width }
}

export function Tour({ steps, state }: { steps: Step[]; state: TourState }) {
  const [box, setBox] = useState<Box | null>(null)
  const mounted = useSyncExternalStore(subscribe, () => true, () => false)
  const nextButton = useRef<HTMLButtonElement>(null)
  const reduced = useReducedMotion()
  const current = steps[state.step]

  useLayoutEffect(() => {
    if (!state.open || !current) return
    const element = document.querySelector<HTMLElement>(`[data-tour="${current.target}"]`)
    element?.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" })
    let frame = 0
    const update = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => setBox(measure(current.target))) }
    update()
    const settle = window.setTimeout(update, 450)
    window.addEventListener("scroll", update, { passive: true })
    window.addEventListener("resize", update)
    return () => { cancelAnimationFrame(frame); window.clearTimeout(settle); window.removeEventListener("scroll", update); window.removeEventListener("resize", update) }
  }, [state.open, current, reduced])
  useEffect(() => {
    if (!state.open) return
    nextButton.current?.focus({ preventScroll: true })
    const keys = (event: KeyboardEvent) => {
      if (event.key === "Escape") state.finish()
      if (event.key === "ArrowRight") state.next()
      if (event.key === "ArrowLeft") state.back()
    }
    window.addEventListener("keydown", keys)
    return () => window.removeEventListener("keydown", keys)
  }, [state, state.open, state.step])

  if (!mounted) return null
  const spring = reduced ? { duration: 0 } : { type: "spring" as const, stiffness: 260, damping: 30 }
  const spot = box ? place(box) : null
  return createPortal(<AnimatePresence>
    {state.open && current && box && spot && <motion.div key="tour" className="tour" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
      <motion.div className="tour-hole" aria-hidden="true" initial={false} animate={box} transition={spring} />
      <motion.div className="tour-card" role="dialog" aria-modal="false" aria-labelledby="tour-title" initial={false} animate={{ top: spot.top, left: spot.left, width: spot.width }} transition={spring}>
        <div className="tour-head">
          <span className="tour-count">Step {state.step + 1} of {state.count}</span>
          <button type="button" className="tour-skip" onClick={state.finish}>Skip tour <X size={13} /></button>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={state.step} initial={reduced ? false : { opacity: 0, y: 8, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={{ opacity: 0, y: -6, filter: "blur(4px)" }} transition={{ duration: 0.25 }}>
            <h2 id="tour-title" className="tour-title">{current.title}</h2>
            <p className="tour-body">{current.body}</p>
          </motion.div>
        </AnimatePresence>
        <div className="tour-foot">
          <div className="tour-dots" aria-hidden="true">{steps.map((item, i) => <i key={item.target} className={i === state.step ? "is-on" : i < state.step ? "is-done" : undefined} />)}</div>
          <div className="tour-actions">
            {state.step > 0 && <button type="button" className="tour-back" onClick={state.back} aria-label="Previous step"><ArrowLeft size={15} /></button>}
            <button ref={nextButton} type="button" className="tour-next" onClick={state.next}>{state.step + 1 === state.count ? "Done" : <>Next <ArrowRight size={14} /></>}</button>
          </div>
        </div>
      </motion.div>
    </motion.div>}
  </AnimatePresence>, document.body)
}
