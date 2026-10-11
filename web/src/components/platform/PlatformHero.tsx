"use client"

import Image from "next/image"
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, type PointerEvent } from "react"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { TrackedLink } from "@/components/site/TrackedLink"

const EASE = [0.16, 1, 0.3, 1] as const
const PROOF = [
  { label: "Audit", title: "A tamper-evident timeline", body: "Every fact your agents were told, with when and from where." },
  { label: "Trace", title: "Every decision explained", body: "What went in, what was left out and why, replayable later." },
  { label: "Deploy", title: "Runs in your environment", body: "Your data stays with you. Safety rules are never learned away." },
]

/** A full-bleed photograph under a theme-aware veil. The photo drifts with the scroll, the glass panel rises. */
export function PlatformHero({ version }: { version: string }) {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] })
  const photoY = useTransform(scrollYProgress, [0, 1], [0, 160])
  const photoScale = useTransform(scrollYProgress, [0, 1], [1.06, 1.16])
  const copyY = useTransform(scrollYProgress, [0, 1], [0, -70])
  const rise = (delay: number) => (reduced ? {} : { initial: { opacity: 0, y: 24, filter: "blur(8px)" }, animate: { opacity: 1, y: 0, filter: "blur(0px)" }, transition: { duration: 1, ease: EASE, delay } })
  const spot = (event: PointerEvent<HTMLElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty("--mx", `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty("--my", `${event.clientY - box.top}px`)
  }
  return <section ref={ref} className="ph" aria-labelledby="platform-title">
    <motion.div className="ph-photo" aria-hidden="true" style={reduced ? undefined : { y: photoY, scale: photoScale }}>
      <Image className="art-dark" src="/media/platform-night.webp" alt="" fill priority sizes="100vw" />
      <Image className="art-light" src="/media/platform-day.webp" alt="" fill priority sizes="100vw" />
    </motion.div>
    <div className="ph-veil" aria-hidden="true" />
    <motion.div className="ph-copy" style={reduced ? undefined : { y: copyY }}>
      <motion.p className="ph-kicker" {...rise(0)}>Platform {version}, private beta</motion.p>
      <motion.h1 id="platform-title" {...rise(0.08)}>Context intelligence<br /><em>for agents in production.</em></motion.h1>
      <motion.p className="ph-lede" {...rise(0.16)}>LLMSlim Platform builds on the open-source Core. It records what your agents were told, works out what is still true, explains every context decision, and learns from outcomes which context helps, without handing safety decisions to a model.</motion.p>
      <motion.div className="ph-actions" {...rise(0.24)}>
        <TrackedLink className="button" href="#beta" event="platform_beta_clicked" properties={{ location: "platform_hero" }}>Request beta access <ArrowRight size={16} /></TrackedLink>
        <TrackedLink className="button button-outline" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "platform_hero" }}>Start with Core <ArrowUpRight size={16} /></TrackedLink>
      </motion.div>
    </motion.div>
    <motion.ul className="ph-proof" onPointerMove={spot} initial={reduced ? false : { opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1.1, ease: EASE, delay: 0.4 }}>
      {PROOF.map((item) => <li key={item.label}><span className="ph-proof-label">{item.label}</span><strong>{item.title}</strong><span>{item.body}</span></li>)}
    </motion.ul>
  </section>
}
