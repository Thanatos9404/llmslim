"use client"

import { animate, motion, useInView, useMotionTemplate, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform } from "framer-motion"
import { useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react"
import { ArrowUpRight } from "lucide-react"
import { track } from "@/lib/analytics"
import { ProgramLogo, startupPrograms, type StartupProgram } from "./StartupPrograms"

/** Deterministic pseudo-random sequence, so server and client render identical markup. */
function seeded(seed: number) {
  let state = seed * 2654435761 % 4294967296
  return () => { state = (state * 1664525 + 1013904223) % 4294967296; return state / 4294967296 }
}

/* ------------------------------------------------------------------ Tilt + spotlight card */

/**
 * A card that tilts toward the cursor in 3D and carries a spotlight that follows it.
 * Mouse only: touch and reduced-motion users get a still card.
 */
export function TiltCard({ children, className = "", depth = 10, as = "div" }: { children: ReactNode; className?: string; depth?: number; as?: "div" | "article" | "li" }) {
  const reduced = useReducedMotion()
  const px = useMotionValue(0.5)
  const py = useMotionValue(0.5)
  const rotateX = useSpring(useTransform(py, [0, 1], [depth, -depth]), { stiffness: 220, damping: 20 })
  const rotateY = useSpring(useTransform(px, [0, 1], [-depth, depth]), { stiffness: 220, damping: 20 })
  const spotX = useTransform(px, (v) => `${v * 100}%`)
  const spotY = useTransform(py, (v) => `${v * 100}%`)
  const spotlight = useMotionTemplate`radial-gradient(420px circle at ${spotX} ${spotY}, var(--spotlight), transparent 60%)`
  const move = (event: PointerEvent<HTMLElement>) => {
    if (reduced || event.pointerType !== "mouse") return
    const box = event.currentTarget.getBoundingClientRect()
    px.set((event.clientX - box.left) / box.width)
    py.set((event.clientY - box.top) / box.height)
  }
  const leave = () => { px.set(0.5); py.set(0.5) }
  const Component = as === "article" ? motion.article : as === "li" ? motion.li : motion.div
  return <Component className={`tilt-card ${className}`} onPointerMove={move} onPointerLeave={leave} style={reduced ? undefined : { rotateX, rotateY, transformPerspective: 900 }}>
    <motion.span className="tilt-spotlight" aria-hidden="true" style={{ background: spotlight }} />
    {children}
  </Component>
}

/* ------------------------------------------------------------------ Pixel displace field */

/** Canvas grid of small squares that scatter away from the cursor and spring back. Runs only while visible. */
function PixelField() {
  const canvas = useRef<HTMLCanvasElement>(null)
  const reduced = useReducedMotion()
  useEffect(() => {
    const element = canvas.current
    const host = element?.parentElement
    const context = element?.getContext("2d")
    if (!element || !host || !context) return
    const gap = 22
    let points: { x: number; y: number; ox: number; oy: number; vx: number; vy: number }[] = []
    let width = 0, height = 0, frame = 0, visible = false
    const pointer = { x: -9999, y: -9999 }
    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = host.clientWidth; height = host.clientHeight
      element.width = width * ratio; element.height = height * ratio
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      points = []
      for (let y = gap / 2; y < height; y += gap) for (let x = gap / 2; x < width; x += gap) points.push({ x, y, ox: x, oy: y, vx: 0, vy: 0 })
      draw()
    }
    const draw = () => {
      context.clearRect(0, 0, width, height)
      const ink = getComputedStyle(host).getPropertyValue("--field-ink").trim() || "rgba(128,128,128,.35)"
      const hot = getComputedStyle(host).getPropertyValue("--field-hot").trim() || "#57dbb7"
      for (const p of points) {
        const dist = Math.hypot(p.x - p.ox, p.y - p.oy)
        context.fillStyle = dist > 3 ? hot : ink
        const size = dist > 3 ? 3 : 2
        context.fillRect(Math.round(p.x - size / 2), Math.round(p.y - size / 2), size, size)
      }
    }
    const step = () => {
      frame = 0
      let moving = false
      for (const p of points) {
        const dx = p.x - pointer.x, dy = p.y - pointer.y
        const d2 = dx * dx + dy * dy
        if (d2 < 14400) { const force = (14400 - d2) / 14400 * 2.4; const d = Math.sqrt(d2) || 1; p.vx += dx / d * force; p.vy += dy / d * force }
        p.vx += (p.ox - p.x) * 0.06; p.vy += (p.oy - p.y) * 0.06
        p.vx *= 0.82; p.vy *= 0.82
        p.x += p.vx; p.y += p.vy
        // Snap to the grid as it settles, for the pixel look.
        if (Math.abs(p.vx) + Math.abs(p.vy) > 0.05) moving = true
      }
      draw()
      if (visible && (moving || pointer.x > -9000)) frame = requestAnimationFrame(step)
    }
    const kick = () => { if (!frame && visible && !reduced) frame = requestAnimationFrame(step) }
    const move = (event: globalThis.PointerEvent) => {
      if (event.pointerType !== "mouse") return
      const box = host.getBoundingClientRect()
      pointer.x = event.clientX - box.left; pointer.y = event.clientY - box.top
      kick()
    }
    const leave = () => { pointer.x = -9999; pointer.y = -9999; kick() }
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) kick() })
    const resizer = new ResizeObserver(resize)
    resize()
    observer.observe(host); resizer.observe(host)
    host.addEventListener("pointermove", move); host.addEventListener("pointerleave", leave)
    return () => { cancelAnimationFrame(frame); observer.disconnect(); resizer.disconnect(); host.removeEventListener("pointermove", move); host.removeEventListener("pointerleave", leave) }
  }, [reduced])
  return <canvas ref={canvas} className="pixel-field" aria-hidden="true" />
}

/* ------------------------------------------------------------------ Pixel program wall */

const COLS = 12
const ROWS = 6

/** Blocks that cover a logo, then dissolve in a seeded order; hovering re-pixelates and resolves again. */
function PixelVeil({ seed, live, hover }: { seed: number; live: boolean; hover: number }) {
  const cells = useMemo(() => {
    const random = seeded(seed + 1)
    return Array.from({ length: COLS * ROWS }, () => ({ delay: random() * 0.55, tone: random() }))
  }, [seed])
  return <span className={`pixel-veil ${live ? "is-live" : ""}`} aria-hidden="true" key={hover} style={{ "--cols": COLS, "--rows": ROWS } as CSSProperties}>
    {cells.map((cell, index) => <span key={index} className="pixel-cell" style={{ "--d": `${cell.delay.toFixed(3)}s`, "--t": cell.tone.toFixed(3) } as CSSProperties} />)}
  </span>
}

function ProgramTile({ program, index }: { program: StartupProgram; index: number }) {
  const tile = useRef<HTMLDivElement>(null)
  const inView = useInView(tile, { once: true, amount: 0.4 })
  const [hover, setHover] = useState(0)
  // `order` keeps the numbered sequence when the columns flatten into one grid on small screens.
  return <div ref={tile} role="listitem" className="program-tile-wrap" style={{ order: index }}>
    <TiltCard className="program-tile" depth={12}>
      <a href={program.href} target="_blank" rel="noreferrer" className="program-tile-link" onPointerEnter={(event) => { if (event.pointerType === "mouse") setHover((n) => n + 1) }} onClick={() => track("startup_program_clicked", { program: program.id })}>
        <span className="program-tile-index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
        <span className="program-tile-art" aria-hidden="true"><ProgramLogo program={program} /><PixelVeil seed={index} live={inView} hover={hover} /></span>
        <span className="program-tile-name">{program.name}<ArrowUpRight size={13} aria-hidden="true" /></span>
      </a>
    </TiltCard>
  </div>
}

/** All startup programs as a pixel-resolving, cursor-reactive wall with depth parallax on scroll. */
export function PixelProgramWall() {
  const section = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: section, offset: ["start end", "end start"] })
  const slow = useTransform(scrollYProgress, [0, 1], [40, -40])
  const fast = useTransform(scrollYProgress, [0, 1], [110, -110])
  const columns = [0, 1, 2].map((column) => startupPrograms.map((program, index) => ({ program, index })).filter(({ index }) => index % 3 === column))
  return <div ref={section} className="program-wall">
    <PixelField />
    <div role="list" className="program-wall-grid" aria-label={`${startupPrograms.length} startup programs`}>
      {columns.map((items, column) => <motion.div key={column} className="program-wall-column" style={reduced ? undefined : { y: column === 1 ? fast : slow }}>
        {items.map(({ program, index }) => <ProgramTile key={program.id} program={program} index={index} />)}
      </motion.div>)}
    </div>
  </div>
}

/* ------------------------------------------------------------------ Count-up receipts */

export type Receipt = { value: number; decimals?: number; prefix?: string; suffix: string; label: string; note: string }

function CountUp({ receipt }: { receipt: Receipt }) {
  const node = useRef<HTMLSpanElement>(null)
  const inView = useInView(node, { once: true, amount: 0.6 })
  const reduced = useReducedMotion()
  const format = (v: number) => `${receipt.prefix ?? ""}${v.toLocaleString("en-US", { minimumFractionDigits: receipt.decimals ?? 0, maximumFractionDigits: receipt.decimals ?? 0 })}${receipt.suffix}`
  useEffect(() => {
    if (!inView || !node.current) return
    if (reduced) { node.current.textContent = format(receipt.value); return }
    const controls = animate(0, receipt.value, { duration: 1.6, ease: [0.16, 1, 0.3, 1], onUpdate: (v) => { if (node.current) node.current.textContent = format(v) } })
    return () => controls.stop()
  }, [inView, reduced]) // eslint-disable-line react-hooks/exhaustive-deps
  // Server markup shows the final value, so the number is correct without JavaScript.
  return <span ref={node} className="receipt-value">{format(receipt.value)}</span>
}

export function Receipts({ items }: { items: Receipt[] }) {
  return <dl className="receipts">{items.map((item) => <TiltCard key={item.label} className="receipt" depth={6}>
    <dt className="sr-only">{item.label}</dt>
    <dd><CountUp receipt={item} /><span className="receipt-label">{item.label}</span><span className="receipt-note">{item.note}</span></dd>
  </TiltCard>)}</dl>
}

/* ------------------------------------------------------------------ Decode text */

const GLYPHS = "▓▒░█▚▞▟▙01<>/{}[]#"

/** Text that resolves from pixel glyphs into the real words. Screen readers get the real text throughout. */
export function DecodeText({ text, className = "" }: { text: string; className?: string }) {
  const reduced = useReducedMotion()
  const [shown, setShown] = useState(text)
  useEffect(() => {
    if (reduced) return
    const random = seeded(text.length)
    let frame = 0
    let tick = 0
    const total = 26
    const run = () => {
      tick += 1
      const done = Math.floor((tick / total) * text.length)
      setShown(text.split("").map((char, index) => (char === " " || index < done ? char : GLYPHS[Math.floor(random() * GLYPHS.length)])).join(""))
      if (tick < total) frame = window.setTimeout(run, 38)
      else setShown(text)
    }
    frame = window.setTimeout(run, 250)
    return () => window.clearTimeout(frame)
  }, [text, reduced])
  return <span className={className}><span className="sr-only">{text}</span><span aria-hidden="true">{shown}</span></span>
}
