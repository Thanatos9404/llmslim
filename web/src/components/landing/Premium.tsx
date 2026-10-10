"use client"

import Image from "next/image"
import { animate, motion, useInView, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from "framer-motion"
import { Fragment, useEffect, useRef, type PointerEvent, type ReactNode } from "react"
import { track } from "@/lib/analytics"
import { ProgramLogo, startupPrograms } from "./StartupPrograms"

// Every effect here animates transform/opacity only (compositor work, no layout or canvas),
// and reduced-motion users get the final, still state.

const EASE = [0.16, 1, 0.3, 1] as const

/* ------------------------------------------------------------------ Reveal */

export function Reveal({ children, className = "", delay = 0, as = "div" }: { children: ReactNode; className?: string; delay?: number; as?: "div" | "section" | "li" }) {
  const reduced = useReducedMotion()
  const Component = as === "section" ? motion.section : as === "li" ? motion.li : motion.div
  if (reduced) return <Component className={className}>{children}</Component>
  return <Component className={className} initial={{ opacity: 0, y: 28 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.25 }} transition={{ duration: 0.9, ease: EASE, delay }}>{children}</Component>
}

/** A headline whose words rise out of a soft blur, one after another. The full text stays in the DOM for readers. */
export function RevealWords({ text, className = "", delay = 0 }: { text: string; className?: string; delay?: number }) {
  const reduced = useReducedMotion()
  if (reduced) return <span className={className}>{text}</span>
  return <span className={className}>
    {text.split(" ").map((word, index) => <Fragment key={index}>{index > 0 && " "}<span className="word-mask"><motion.span className="word" initial={{ y: "105%", opacity: 0, filter: "blur(8px)" }} animate={{ y: "0%", opacity: 1, filter: "blur(0px)" }} transition={{ duration: 1, ease: EASE, delay: delay + index * 0.07 }}>{word}</motion.span></span></Fragment>)}
  </span>
}

/* ------------------------------------------------------------------ Hero */

/**
 * Full-bleed night sky with three depths: the photo drifts slowly, the 3D ribbon floats and tilts
 * toward the cursor, and the copy scrolls at normal speed.
 */
export function PremiumHero({ children }: { children: ReactNode }) {
  const section = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: section, offset: ["start start", "end start"] })
  const skyY = useTransform(scrollYProgress, [0, 1], [0, 180])
  const ribbonY = useTransform(scrollYProgress, [0, 1], [0, -120])
  const copyOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0])
  const px = useMotionValue(0), py = useMotionValue(0)
  const rotateY = useSpring(useTransform(px, [-0.5, 0.5], [-14, 14]), { stiffness: 60, damping: 18 })
  const rotateX = useSpring(useTransform(py, [-0.5, 0.5], [10, -10]), { stiffness: 60, damping: 18 })
  const shiftX = useSpring(useTransform(px, [-0.5, 0.5], [-30, 30]), { stiffness: 60, damping: 18 })
  const move = (event: PointerEvent<HTMLElement>) => {
    if (reduced || event.pointerType !== "mouse") return
    const box = event.currentTarget.getBoundingClientRect()
    px.set((event.clientX - box.left) / box.width - 0.5)
    py.set((event.clientY - box.top) / box.height - 0.5)
  }
  return <section ref={section} className="p-hero on-dark" aria-labelledby="hero-title" onPointerMove={move}>
    <motion.div className="p-hero-sky" style={reduced ? undefined : { y: skyY }} aria-hidden="true">
      <Image src="/media/hero-sky.webp" alt="" fill priority sizes="100vw" className="p-hero-sky-wide" />
      <Image src="/media/hero-sky-portrait.webp" alt="" fill sizes="100vw" className="p-hero-sky-tall" />
    </motion.div>
    <div className="p-hero-veil" aria-hidden="true" />
    <motion.div className="p-hero-ribbon" aria-hidden="true" style={reduced ? undefined : { y: ribbonY, x: shiftX, rotateX, rotateY }}>
      <div className="p-hero-ribbon-float"><Image src="/compression-ribbon-dark.webp" alt="" width={1536} height={1024} sizes="(max-width: 800px) 120vw, 70vw" /></div>
    </motion.div>
    <motion.div className="p-hero-copy" style={reduced ? undefined : { opacity: copyOpacity }}>{children}</motion.div>
  </section>
}

/* ------------------------------------------------------------------ Photo sections */

/** A full-bleed band whose photo drifts against the scroll. Always dark, in either theme. */
export function PhotoSection({ src, children, className = "", id, labelledBy, position = "center" }: { src: string; children: ReactNode; className?: string; id?: string; labelledBy?: string; position?: string }) {
  const section = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: section, offset: ["start end", "end start"] })
  const y = useTransform(scrollYProgress, [0, 1], ["-12%", "12%"])
  const scale = useTransform(scrollYProgress, [0, 0.5, 1], [1.12, 1.04, 1.12])
  return <section ref={section} id={id} aria-labelledby={labelledBy} className={`photo-section on-dark ${className}`}>
    <motion.div className="photo-section-media" aria-hidden="true" style={reduced ? undefined : { y, scale }}>
      <Image src={src} alt="" fill sizes="100vw" style={{ objectPosition: position }} />
    </motion.div>
    <div className="photo-section-veil" aria-hidden="true" />
    <div className="photo-section-content">{children}</div>
  </section>
}

/* ------------------------------------------------------------------ Logo cloud */

/** Startup-program logos only: no tiles, no captions. The cloud drifts against the photo behind it, so rows stay aligned. */
export function LogoCloud() {
  const list = useRef<HTMLUListElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: list, offset: ["start end", "end start"] })
  const y = useTransform(scrollYProgress, [0, 1], [48, -48])
  return <motion.ul ref={list} className="logo-cloud" aria-label={`${startupPrograms.length} startup programs`} style={reduced ? undefined : { y }}>
    {startupPrograms.map((program, index) => <motion.li key={program.id} className="logo-cloud-item"
      initial={reduced ? undefined : { opacity: 0, filter: "blur(10px)" }} whileInView={reduced ? undefined : { opacity: 1, filter: "blur(0px)" }} viewport={{ once: true, amount: 0.6 }} transition={{ duration: 1.1, ease: EASE, delay: (index % 4) * 0.08 }}>
      <a href={program.href} target="_blank" rel="noreferrer" aria-label={program.name} title={program.name} onClick={() => track("startup_program_clicked", { program: program.id })}>
        <ProgramLogo program={program} />
      </a>
    </motion.li>)}
  </motion.ul>
}

/* ------------------------------------------------------------------ Stacked glass sheets */

/** Two glass sheets that tilt flat as they scroll into view, with a light glare sweeping across. */
export function GlassSheet({ children, className = "" }: { children: ReactNode; className?: string }) {
  const sheet = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: sheet, offset: ["start end", "start 0.62"] })
  const rotateX = useTransform(scrollYProgress, [0, 1], [18, 0])
  const y = useTransform(scrollYProgress, [0, 1], [60, 0])
  const opacity = useTransform(scrollYProgress, [0, 0.6], [0.2, 1])
  const glare = useTransform(scrollYProgress, [0.3, 1], ["-60%", "160%"])
  return <div className="glass-stage">
    <motion.div ref={sheet} className={`glass-sheet ${className}`} style={reduced ? undefined : { rotateX, y, opacity, transformPerspective: 1200 }}>
      <motion.span className="glass-glare" aria-hidden="true" style={reduced ? undefined : { x: glare }} />
      {children}
    </motion.div>
  </div>
}

/* ------------------------------------------------------------------ Count-up receipts */

export type Receipt = { value: number; decimals?: number; prefix?: string; suffix: string; label: string; note: string }

function CountUp({ receipt }: { receipt: Receipt }) {
  const node = useRef<HTMLSpanElement>(null)
  const inView = useInView(node, { once: true, amount: 0.6 })
  const reduced = useReducedMotion()
  const format = (v: number) => `${receipt.prefix ?? ""}${v.toLocaleString("en-US", { minimumFractionDigits: receipt.decimals ?? 0, maximumFractionDigits: receipt.decimals ?? 0 })}`
  useEffect(() => {
    if (!inView || !node.current) return
    if (reduced) { node.current.textContent = format(receipt.value); return }
    const controls = animate(0, receipt.value, { duration: 1.6, ease: [0.16, 1, 0.3, 1], onUpdate: (v) => { if (node.current) node.current.textContent = format(v) } })
    return () => controls.stop()
  }, [inView, reduced]) // eslint-disable-line react-hooks/exhaustive-deps
  // Server markup shows the final value, so the number is correct without JavaScript.
  return <span className="receipt-value"><span ref={node}>{format(receipt.value)}</span><span className="receipt-unit">{receipt.suffix}</span></span>
}

/** Large figures on hairlines: no boxes. Each counts up once when it scrolls into view. */
export function Receipts({ items }: { items: Receipt[] }) {
  return <dl className="receipts">{items.map((item) => <div key={item.label} className="receipt">
    <dt className="receipt-label">{item.label}</dt>
    <dd><CountUp receipt={item} /><span className="receipt-note">{item.note}</span></dd>
  </div>)}</dl>
}
