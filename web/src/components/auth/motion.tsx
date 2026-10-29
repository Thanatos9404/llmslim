"use client"

import { m, useReducedMotion } from "framer-motion"
import type { ReactNode } from "react"

const EASE = [0.22, 1, 0.36, 1] as const

/**
 * A step that replaces another after the visitor acts (a form giving way to "check your email"): it rises 12px and
 * unblurs into place. Only for content that appears after an interaction, never for what the server renders, so the
 * first paint is never hidden. Reduced motion: shown at once.
 */
export function Step({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = useReducedMotion()
  return <m.div className={className} initial={reduced ? false : { opacity: 0, y: 12, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
    transition={{ duration: 0.55, ease: EASE }}>{children}</m.div>
}
