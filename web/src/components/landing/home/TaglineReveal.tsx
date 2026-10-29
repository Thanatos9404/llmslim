"use client"

import { useMotionValueEvent, useScroll } from "framer-motion"
import { Fragment, useRef, useState } from "react"

/** A word, and whether it lights up in the brand gradient instead of plain ink. */
export type TaglineWord = { text: string; accent?: boolean }

/**
 * The large tagline: every word starts muted and lights up, one at a time in reading order, as the block scrolls
 * past the middle of the screen, and stays lit. One scroll subscription (Framer Motion's, batched per frame), and React renders
 * only when the count of lit words changes. Reduced motion: every word is lit, by CSS (landing.css).
 */
export function TaglineReveal({ lines, id }: { lines: TaglineWord[][]; id: string }) {
  const block = useRef<HTMLHeadingElement>(null)
  const total = lines.reduce((sum, line) => sum + line.length, 0)
  const [lit, setLit] = useState(0)
  const { scrollYProgress } = useScroll({ target: block, offset: ["start 0.8", "end 0.45"] })
  useMotionValueEvent(scrollYProgress, "change", (progress) => {
    // Words stay lit once lit: like every reveal on the page, it plays once.
    const count = Math.round(Math.min(1, Math.max(0, progress)) * total)
    setLit((current) => Math.max(current, count))
  })
  let index = 0
  return <h2 ref={block} id={id} className="lp-tagline">
    {lines.map((line, row) => <Fragment key={row}>
      {row > 0 && <br className="lp-tagline-break" />}
      {line.map((word, w) => {
        const at = index++
        return <Fragment key={w}>
          {w > 0 && " "}
          <span className="lp-word" data-lit={at < lit ? "" : undefined} data-accent={word.accent ? "" : undefined}>{word.text}</span>
        </Fragment>
      })}
      {row < lines.length - 1 && " "}
    </Fragment>)}
  </h2>
}
