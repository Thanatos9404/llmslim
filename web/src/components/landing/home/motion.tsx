"use client"

import { m, useReducedMotion, type Variants } from "framer-motion"
import type { ReactNode } from "react"

/** The page's one curve: weighted, decelerating into place. */
export const EASE = [0.22, 1, 0.36, 1] as const

// `custom` carries an optional delay in seconds. It is left out of the transition when there is none, so a parent's
// stagger (which an explicit delay would override) still applies.
const rise: Variants = {
  hidden: { opacity: 0, y: 32 },
  shown: (delay?: number) => ({ opacity: 1, y: 0, transition: { duration: 0.7, ease: EASE, ...(delay ? { delay } : {}) } }),
}
// Reduced motion fades without moving. `y` stays in both states so the first frame clears the 32px offset the server
// rendered (the server cannot know the preference).
const still: Variants = {
  hidden: { opacity: 0, y: 0 },
  shown: (delay?: number) => ({ opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE, ...(delay ? { delay } : {}) } }),
}

type Tag = "div" | "li" | "ul" | "ol" | "article" | "figure"
const TAGS = { div: m.div, li: m.li, ul: m.ul, ol: m.ol, article: m.article, figure: m.figure }

/**
 * Rises 32px and fades in once, when a quarter of it is in view. Reduced motion: a plain fade.
 * Never use it above the fold, where hidden text would delay the largest paint.
 */
export function Reveal({ children, className, as = "div", delay = 0, id }: { children: ReactNode; className?: string; as?: Tag; delay?: number; id?: string }) {
  const reduced = useReducedMotion()
  const Component = TAGS[as]
  return <Component id={id} className={className} variants={reduced ? still : rise} custom={delay} initial="hidden" whileInView="shown" viewport={{ once: true, amount: 0.25 }}>{children}</Component>
}

/** A list whose items (`RevealItem`) arrive one after another, 80ms apart, once the list is in view. */
export function RevealGroup({ children, className, as = "div", label }: { children: ReactNode; className?: string; as?: Tag; label?: string }) {
  const Component = TAGS[as]
  return <Component className={className} aria-label={label} initial="hidden" whileInView="shown" viewport={{ once: true, amount: 0.2 }}
    variants={{ hidden: {}, shown: { transition: { staggerChildren: 0.08 } } }}>{children}</Component>
}

export function RevealItem({ children, className, as = "div" }: { children: ReactNode; className?: string; as?: Tag }) {
  const reduced = useReducedMotion()
  const Component = TAGS[as]
  return <Component className={className} variants={reduced ? still : rise}>{children}</Component>
}
