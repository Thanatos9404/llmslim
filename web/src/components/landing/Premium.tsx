"use client"

import Image, { getImageProps } from "next/image"
import { m, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from "framer-motion"
import { useRef, type PointerEvent, type ReactNode } from "react"
import { track } from "@/lib/analytics"
import { ProgramLogo, startupPrograms } from "./StartupPrograms"

// Every effect here animates transform/opacity only (compositor work, no layout or canvas),
// and reduced-motion users get the final, still state. Above-the-fold copy never starts hidden:
// the hero headline is static and its other lines use `fade={false}`, so they are painted on first load.

const EASE = [0.16, 1, 0.3, 1] as const

/* ------------------------------------------------------------------ Reveal */

/**
 * Rises into place when scrolled into view. With `fade={false}` it only moves (a short transform, no opacity),
 * so the content is visible from the first paint: use that above the fold, where hidden text delays LCP.
 */
export function Reveal({ children, className = "", delay = 0, as = "div", fade = true }: { children: ReactNode; className?: string; delay?: number; as?: "div" | "section" | "li"; fade?: boolean }) {
  const reduced = useReducedMotion()
  const Component = as === "section" ? m.section : as === "li" ? m.li : m.div
  const from = fade ? { opacity: 0, y: 28 } : { y: 14 }
  const to = fade ? { opacity: 1, y: 0 } : { y: 0 }
  // The server cannot know the motion preference, so the HTML arrives in the hidden `from` state and hydration
  // does not patch styles. Setting `to` on mount (no animation) shows the content for reduced-motion users.
  if (reduced) return <Component className={className} initial={false} animate={to}>{children}</Component>
  return <Component className={className} initial={from} whileInView={to} viewport={{ once: true, amount: 0.25 }} transition={{ duration: 0.9, ease: EASE, delay }}>{children}</Component>
}

/* ------------------------------------------------------------------ Hero */

/**
 * One sky per theme, as a single picture: the portrait photo under 700px, the wide one above, so a phone downloads
 * only the photo it shows. The dark sky (the default theme) loads at once; the light one waits until it is shown.
 */
function HeroSky({ wide, tall, className, eager }: { wide: string; tall: string; className: string; eager?: boolean }) {
  const common = { alt: "", fill: true, sizes: "100vw", loading: eager ? "eager" : "lazy" } as const
  const { props: { srcSet: portrait } } = getImageProps({ ...common, src: tall })
  const { props } = getImageProps({ ...common, src: wide })
  return <div className={`p-hero-sky-set ${className}`}>
    <picture>
      <source media="(max-width: 700px)" srcSet={portrait} sizes="100vw" />
      <img {...props} alt="" />
    </picture>
  </div>
}

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
  return <section ref={section} className="p-hero on-photo" aria-labelledby="hero-title" onPointerMove={move}>
    <m.div className="p-hero-sky" style={reduced ? undefined : { y: skyY }} aria-hidden="true">
      <HeroSky wide="/media/hero-sky.webp" tall="/media/hero-sky-portrait.webp" className="art-dark" eager />
      <HeroSky wide="/media/hero-sky-light.webp" tall="/media/hero-sky-light-portrait.webp" className="art-light" />
    </m.div>
    <div className="p-hero-veil" aria-hidden="true" />
    <m.div className="p-hero-ribbon" aria-hidden="true" style={reduced ? undefined : { y: ribbonY, x: shiftX, rotateX, rotateY }}>
      <div className="p-hero-ribbon-float">
        {/* The ribbon is the largest element above the fold: the dark one (the default theme) is fetched first. */}
        <Image src="/compression-ribbon-dark.webp" alt="" width={1536} height={1024} sizes="(max-width: 800px) 120vw, 70vw" className="art-dark" loading="eager" fetchPriority="high" />
        <Image src="/compression-ribbon-light.webp" alt="" width={1536} height={1024} sizes="(max-width: 800px) 120vw, 70vw" className="art-light" />
      </div>
    </m.div>
    <m.div className="p-hero-copy" style={reduced ? undefined : { opacity: copyOpacity }}>{children}</m.div>
  </section>
}

/* ------------------------------------------------------------------ Photo sections */

/** A full-bleed band whose photo drifts against the scroll; `lightSrc` is the photo for the light theme. */
export function PhotoSection({ src, lightSrc, children, className = "", id, labelledBy, position = "center", lightPosition }: { src: string; lightSrc?: string; children: ReactNode; className?: string; id?: string; labelledBy?: string; position?: string; lightPosition?: string }) {
  const section = useRef<HTMLElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: section, offset: ["start end", "end start"] })
  const y = useTransform(scrollYProgress, [0, 1], ["-12%", "12%"])
  const scale = useTransform(scrollYProgress, [0, 0.5, 1], [1.12, 1.04, 1.12])
  return <section ref={section} id={id} aria-labelledby={labelledBy} className={`photo-section on-photo ${className}`}>
    <m.div className="photo-section-media" aria-hidden="true" style={reduced ? undefined : { y, scale }}>
      <div className={lightSrc ? "photo-set art-dark" : "photo-set"}><Image src={src} alt="" fill sizes="100vw" style={{ objectPosition: position }} /></div>
      {lightSrc && <div className="photo-set art-light"><Image src={lightSrc} alt="" fill sizes="100vw" style={{ objectPosition: lightPosition ?? position }} /></div>}
    </m.div>
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
  return <m.ul ref={list} className="logo-cloud" aria-label={`${startupPrograms.length} startup programs`} style={reduced ? undefined : { y }}>
    {startupPrograms.map((program, index) => <m.li key={program.id} className="logo-cloud-item"
      initial={reduced ? undefined : { opacity: 0, filter: "blur(10px)" }} whileInView={reduced ? undefined : { opacity: 1, filter: "blur(0px)" }} viewport={{ once: true, amount: 0.6 }} transition={{ duration: 1.1, ease: EASE, delay: (index % 4) * 0.08 }}>
      <a href={program.href} target="_blank" rel="noreferrer" aria-label={program.name} title={program.name} onClick={() => track("startup_program_clicked", { program: program.id })}>
        <ProgramLogo program={program} />
      </a>
    </m.li>)}
  </m.ul>
}
