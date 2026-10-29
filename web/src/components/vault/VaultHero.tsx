"use client"

import Image from "next/image"
import { m, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, type CSSProperties, type PointerEvent } from "react"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { TrackedLink } from "@/components/site/TrackedLink"

const PROOF = [
  { label: "Audit", title: "A tamper-evident timeline", body: "Every fact your agents were told, with when and from where." },
  { label: "Trace", title: "Every decision explained", body: "What went in, what was left out and why, replayable later." },
  { label: "Deploy", title: "Runs in your environment", body: "Your data stays with you. Safety rules are never learned away." },
]

/** A full-bleed photograph under a theme-aware veil. The photo drifts with the scroll, the glass panel rises. */
export function VaultHero({ version }: { version: string }) {
  const ref = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] })
  const photoY = useTransform(scrollYProgress, [0, 1], [0, 160])
  const photoScale = useTransform(scrollYProgress, [0, 1], [1.06, 1.16])
  const copyY = useTransform(scrollYProgress, [0, 1], [0, -70])
  // Entrance from first paint, in CSS, so the copy does not wait for scripts (see .rise in globals.css).
  const rise = (delay: number) => ({ style: { "--rise-delay": `${delay}s` } as CSSProperties })
  const spot = (event: PointerEvent<HTMLElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty("--mx", `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty("--my", `${event.clientY - box.top}px`)
  }
  return <section ref={ref} className="ph" aria-labelledby="vault-title">
    <m.div className="ph-photo" aria-hidden="true" style={reduced ? undefined : { y: photoY, scale: photoScale }}>
      {/* The night photo (the default theme) is fetched first; the day photo waits until it is shown. */}
      <Image className="art-dark" src="/media/platform-night.webp" alt="" fill sizes="100vw" loading="eager" fetchPriority="high" />
      <Image className="art-light" src="/media/platform-day.webp" alt="" fill sizes="100vw" />
    </m.div>
    <div className="ph-veil" aria-hidden="true" />
    <m.div className="ph-copy" style={reduced ? undefined : { y: copyY }}>
      <p className="ph-kicker rise" {...rise(0)}>LLMSlim Vault {version}, private beta</p>
      <h1 id="vault-title" className="rise" {...rise(0.08)}>Context intelligence<br /><em>for agents in production.</em></h1>
      <p className="ph-lede rise" {...rise(0.16)}>LLMSlim Vault is the self-hosted edition, built on the open-source Core and run in your own VPC. It records what your agents were told, works out what is still true, explains every context decision, and learns from outcomes which context helps, without handing safety decisions to a model.</p>
      <div className="ph-actions rise" {...rise(0.24)}>
        <TrackedLink className="button" href="#beta" event="platform_beta_clicked" properties={{ location: "platform_hero" }}>Request beta access <ArrowRight size={16} /></TrackedLink>
        <TrackedLink className="button button-outline" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "platform_hero" }}>Start with Core <ArrowUpRight size={16} /></TrackedLink>
      </div>
    </m.div>
    <ul className="ph-proof rise" onPointerMove={spot} {...rise(0.4)}>
      {PROOF.map((item) => <li key={item.label}><span className="ph-proof-label">{item.label}</span><strong>{item.title}</strong><span>{item.body}</span></li>)}
    </ul>
  </section>
}
