"use client"

import { inView } from "framer-motion"
import { animate } from "framer-motion/dom/mini"
import { useEffect, useRef, type ReactNode } from "react"

/**
 * Plays a results table when it scrolls into view: score bars grow (Framer Motion's WAAPI `animate`, transform only)
 * and numbers count up to the value printed on the page. The table itself is server-rendered markup (score-parts.tsx),
 * with every number in its final form, so search engines, screen readers, reduced-motion visitors and visitors
 * without scripts all get the same text. Only a table that starts below the fold is armed; one already on screen
 * stays still rather than blinking. Nothing changes size, so nothing shifts.
 */

const EASE = [0.22, 1, 0.36, 1] as const
const DURATION = 1.1
const STAGGER = 0.05

/** "90.5" -> [90.5, 1, "", ""]; "$2,495" -> [2495, 0, "$", ""]. Null when the text is not one number. */
function parse(text: string): [value: number, decimals: number, prefix: string, suffix: string] | null {
  const match = text.match(/^([^\d−-]*)([\d,]+(?:\.(\d+))?)(\D*)$/)
  if (!match) return null
  return [Number(match[2].replace(/,/g, "")), match[3]?.length ?? 0, match[1], match[4]]
}

function format(value: number, decimals: number, grouped: boolean) {
  return value.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: grouped })
}

/** Counts a ticker's run text from zero to its value; the final text is revealed when it lands. */
function count(ticker: HTMLElement, delay: number) {
  const run = ticker.querySelector<HTMLElement>(".tk-run")
  const parsed = parse(ticker.dataset.tick ?? "")
  if (!run || !parsed) return Promise.resolve()
  const [value, decimals, prefix, suffix] = parsed
  const grouped = (ticker.dataset.tick ?? "").includes(",")
  return new Promise<void>((resolve) => {
    const start = performance.now() + delay * 1000
    const step = (now: number) => {
      const t = Math.min(1, Math.max(0, (now - start) / (DURATION * 1000)))
      const eased = 1 - Math.pow(1 - t, 4)
      run.textContent = `${prefix}${format(value * eased, decimals, grouped)}${suffix}`
      if (t < 1) requestAnimationFrame(step)
      else resolve()
    }
    requestAnimationFrame(step)
  })
}

export function MotionTable({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const root = ref.current
    if (!root || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    // Already on screen (or scrolled past): leave it still.
    if (root.getBoundingClientRect().top < window.innerHeight * 0.9) return
    const tickers = Array.from(root.querySelectorAll<HTMLElement>("[data-tick]"))
    for (const ticker of tickers) {
      const parsed = parse(ticker.dataset.tick ?? "")
      const run = ticker.querySelector<HTMLElement>(".tk-run")
      if (parsed && run) run.textContent = `${parsed[2]}${format(0, parsed[1], false)}${parsed[3]}`
    }
    root.dataset.phase = "armed"
    const stop = inView(root, () => {
      stop()
      root.dataset.phase = "play"
      const rows = Array.from(root.querySelectorAll("tbody tr"))
      const delayOf = (element: Element) => Math.min(rows.findIndex((row) => row.contains(element)), 12) * STAGGER
      const bars = Array.from(root.querySelectorAll<HTMLElement>(".sb-fill, .dp-mark"))
      const runs = [
        // Each bar grows from its origin (the left edge, or a difference's zero line) to the transform in its --to.
        ...bars.map((bar) => animate(bar, { transform: ["scaleX(0)", getComputedStyle(bar).getPropertyValue("--to").trim() || "none"] },
          { duration: DURATION, ease: EASE, delay: delayOf(bar) + 0.1 }).then(() => undefined)),
        ...tickers.map((ticker) => count(ticker, delayOf(ticker))),
      ]
      Promise.all(runs).then(() => { root.dataset.phase = "done" })
    }, { margin: "0px 0px -10% 0px" })
    return stop
  }, [])
  return <div ref={ref} className={`motion-table ${className}`}>{children}</div>
}
