"use client"

import { useInView } from "framer-motion"
import { useRef, type CSSProperties, type ReactNode } from "react"

/**
 * Rises into place when scrolled into view. With `fade={false}` it only moves (a short transform, no opacity),
 * so the content is visible from the first paint: use that above the fold, where hidden text delays LCP.
 *
 * The hidden state lives in CSS (`.reveal` in globals.css), not in server-rendered inline styles: it applies only
 * under `prefers-reduced-motion: no-preference`, and a <noscript> rule in the root layout cancels it. So
 * reduced-motion visitors and visitors without scripts see the content from the first paint, instead of after
 * hydration (or never). Framer Motion's `useInView` marks the element shown once, and CSS runs the transition.
 *
 * Its own module (re-exported from landing/Premium.tsx), so a page that only needs a reveal does not load the
 * homepage's hero, photo bands and startup logos with it.
 */
export function Reveal({ children, className = "", delay = 0, as = "div", fade = true }: { children: ReactNode; className?: string; delay?: number; as?: "div" | "section" | "li"; fade?: boolean }) {
  const ref = useRef<HTMLElement>(null)
  const shown = useInView(ref, { once: true, margin: "0px 0px -12% 0px" })
  const Component = as
  const style = delay ? ({ "--reveal-delay": `${delay}s` } as CSSProperties) : undefined
  return <Component ref={ref as never} className={`reveal${fade ? "" : " reveal-move"}${className ? ` ${className}` : ""}`} data-shown={shown ? "" : undefined} style={style}>{children}</Component>
}
