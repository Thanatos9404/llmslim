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

type Dot = { ox: number; oy: number; x: number; y: number; vx: number; vy: number }

/**
 * Grid of small squares that scatter away from the cursor and spring back.
 *
 * Cost is kept local: the resting grid is drawn once (lazily, when the wall first becomes visible),
 * then each frame repaints only the small rectangle around the cursor and the dots still settling.
 * Nothing runs during scrolling, on touch devices, or with reduced motion.
 */
function PixelField() {
  const canvas = useRef<HTMLCanvasElement>(null)
  const reduced = useReducedMotion()
  useEffect(() => {
    const element = canvas.current
    const host = element?.parentElement
    const context = element?.getContext("2d")
    if (!element || !host || !context || reduced) return
    const GAP = 22, RADIUS = 110
    const active = new Map<number, Dot>()
    let width = 0, height = 0, cols = 0, frame = 0, ready = false
    let ink = "", hot = ""
    let dirty: { x0: number; y0: number; x1: number; y1: number } | null = null
    const pointer = { x: 0, y: 0, inside: false }
    const origin = (index: number) => ({ ox: (index % cols) * GAP + GAP / 2, oy: Math.floor(index / cols) * GAP + GAP / 2 })
    const square = (x: number, y: number, size: number, color: string) => { context.fillStyle = color; context.fillRect(Math.round(x - size / 2), Math.round(y - size / 2), size, size) }
    // Resting dots inside a rectangle, skipping the ones currently displaced.
    const restIn = (x0: number, y0: number, x1: number, y1: number) => {
      const c0 = Math.max(0, Math.floor(x0 / GAP)), c1 = Math.min(cols - 1, Math.ceil(x1 / GAP))
      const r0 = Math.max(0, Math.floor(y0 / GAP)), r1 = Math.ceil(y1 / GAP)
      for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
        const index = r * cols + c, { ox, oy } = origin(index)
        if (oy > height || active.has(index)) continue
        square(ox, oy, 2, ink)
      }
    }
    const setup = () => {
      const w = host.clientWidth, h = host.clientHeight
      if (ready && w === width && h === height) return
      width = w; height = h; cols = Math.ceil(width / GAP)
      element.width = width; element.height = height  // 1x: these are 2-3px squares, extra pixels buy nothing
      const style = getComputedStyle(host)
      ink = style.getPropertyValue("--field-ink").trim() || "rgba(128,128,128,.3)"
      hot = style.getPropertyValue("--field-hot").trim() || "#57dbb7"
      active.clear(); dirty = null
      context.clearRect(0, 0, width, height)
      restIn(0, 0, width, height)
      ready = true
    }
    const step = () => {
      frame = 0
      if (pointer.inside) {
        const c0 = Math.max(0, Math.floor((pointer.x - RADIUS) / GAP)), c1 = Math.min(cols - 1, Math.ceil((pointer.x + RADIUS) / GAP))
        const r0 = Math.max(0, Math.floor((pointer.y - RADIUS) / GAP)), r1 = Math.ceil((pointer.y + RADIUS) / GAP)
        for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
          const index = r * cols + c
          const dot = active.get(index) ?? (() => { const { ox, oy } = origin(index); return { ox, oy, x: ox, y: oy, vx: 0, vy: 0 } })()
          const dx = dot.x - pointer.x, dy = dot.y - pointer.y, d2 = dx * dx + dy * dy
          if (d2 >= RADIUS * RADIUS) continue
          const d = Math.sqrt(d2) || 1, force = (1 - d2 / (RADIUS * RADIUS)) * 2.4
          dot.vx += (dx / d) * force; dot.vy += (dy / d) * force
          active.set(index, dot)
        }
      }
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity
      for (const [index, dot] of active) {
        dot.vx = (dot.vx + (dot.ox - dot.x) * 0.06) * 0.82; dot.vy = (dot.vy + (dot.oy - dot.y) * 0.06) * 0.82
        dot.x += dot.vx; dot.y += dot.vy
        if (Math.abs(dot.vx) + Math.abs(dot.vy) < 0.04 && Math.abs(dot.x - dot.ox) + Math.abs(dot.y - dot.oy) < 0.5) { active.delete(index); continue }
        x0 = Math.min(x0, dot.x, dot.ox); y0 = Math.min(y0, dot.y, dot.oy); x1 = Math.max(x1, dot.x, dot.ox); y1 = Math.max(y1, dot.y, dot.oy)
      }
      // Repaint only the union of last frame's and this frame's affected area.
      const next = active.size ? { x0: x0 - 4, y0: y0 - 4, x1: x1 + 4, y1: y1 + 4 } : null
      const area = dirty && next ? { x0: Math.min(dirty.x0, next.x0), y0: Math.min(dirty.y0, next.y0), x1: Math.max(dirty.x1, next.x1), y1: Math.max(dirty.y1, next.y1) } : dirty ?? next
      if (area) {
        context.clearRect(area.x0 - GAP, area.y0 - GAP, area.x1 - area.x0 + GAP * 2, area.y1 - area.y0 + GAP * 2)
        restIn(area.x0 - GAP, area.y0 - GAP, area.x1 + GAP, area.y1 + GAP)
        for (const dot of active.values()) square(dot.x, dot.y, Math.abs(dot.x - dot.ox) + Math.abs(dot.y - dot.oy) > 3 ? 3 : 2, Math.abs(dot.x - dot.ox) + Math.abs(dot.y - dot.oy) > 3 ? hot : ink)
      }
      dirty = next
      if (pointer.inside || active.size) frame = requestAnimationFrame(step)
    }
    const kick = () => { if (!frame && ready) frame = requestAnimationFrame(step) }
    const move = (event: globalThis.PointerEvent) => {
      if (event.pointerType !== "mouse") return
      const box = host.getBoundingClientRect()
      pointer.x = event.clientX - box.left; pointer.y = event.clientY - box.top; pointer.inside = true
      kick()
    }
    const leave = () => { pointer.inside = false; kick() }
    // Draw the resting grid only once the wall is near the viewport, and again only if its size changes.
    const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) setup() }, { rootMargin: "200px" })
    const resizer = new ResizeObserver(() => { if (ready) setup() })
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
