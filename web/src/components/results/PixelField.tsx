"use client"

import { useEffect, useRef } from "react"

/** Reads a colour token from the element, so the canvas follows the light and dark themes. */
function token(element: Element, name: string, fallback: string) {
  return getComputedStyle(element).getPropertyValue(name).trim() || fallback
}

/**
 * A field of small squares that flicker at low opacity and brighten into the accent colour under the pointer.
 * `fade` shapes where the field shows: "center" for a hero, "bottom" for a closing band.
 */
export function PixelField({ className = "", square = 3, gap = 7, fade = "center" }: { className?: string; square?: number; gap?: number; fade?: "center" | "bottom" }) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const element = canvas.current
    const context = element?.getContext("2d")
    if (!element || !context) return
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const step = square + gap
    let width = 0, height = 0, cols = 0, rows = 0
    let cells = new Float32Array(0)
    let shade = new Float32Array(0)
    let ink = "#888", accent = "#57dbb7"
    let frame = 0, last = 0, visible = true
    const pointer = { x: -1e4, y: -1e4 }

    const colours = () => { ink = token(element, "--ink", ink); accent = token(element, "--brand", accent) }
    const mask = (x: number, y: number) => {
      if (fade === "bottom") return Math.max(0, Math.min(1, (y / height - 0.15) * 1.4))
      const dx = (x - width / 2) / (width * 0.62), dy = (y - height * 0.46) / (height * 0.6)
      return Math.max(0, 1 - Math.sqrt(dx * dx + dy * dy))
    }
    const resize = () => {
      const box = element.getBoundingClientRect()
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = box.width; height = box.height
      element.width = Math.round(width * ratio); element.height = Math.round(height * ratio)
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      cols = Math.ceil(width / step); rows = Math.ceil(height / step)
      cells = Float32Array.from({ length: cols * rows }, () => Math.random())
      shade = Float32Array.from({ length: cols * rows }, (_, i) => mask((i % cols) * step, Math.floor(i / cols) * step))
    }
    const draw = () => {
      context.clearRect(0, 0, width, height)
      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          const i = row * cols + col
          if (!reduced && Math.random() < 0.012) cells[i] = Math.random()
          const x = col * step, y = row * step
          const dx = x - pointer.x, dy = y - pointer.y
          const far = dx > 150 || dx < -150 || dy > 150 || dy < -150
          if (far && shade[i] < 0.07) continue
          const near = far ? 0 : Math.max(0, 1 - Math.sqrt(dx * dx + dy * dy) / 150)
          const alpha = cells[i] * 0.3 * shade[i] + near * near * cells[i] * 0.9
          if (alpha < 0.02) continue
          context.globalAlpha = Math.min(alpha, 1)
          context.fillStyle = near > 0.15 && cells[i] > 0.55 ? accent : ink
          context.fillRect(x, y, square, square)
        }
      }
      context.globalAlpha = 1
    }
    const loop = (time: number) => {
      frame = requestAnimationFrame(loop)
      if (!visible || time - last < 50) return
      last = time
      draw()
    }

    colours(); resize(); draw()
    const sized = new ResizeObserver(() => { resize(); draw() })
    sized.observe(element)
    const seen = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting })
    seen.observe(element)
    const themed = new MutationObserver(() => { colours(); draw() })
    themed.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] })
    const host = element.parentElement
    const move = (event: PointerEvent) => { const box = element.getBoundingClientRect(); pointer.x = event.clientX - box.left; pointer.y = event.clientY - box.top }
    const leave = () => { pointer.x = -1e4; pointer.y = -1e4 }
    host?.addEventListener("pointermove", move)
    host?.addEventListener("pointerleave", leave)
    if (!reduced) frame = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(frame); sized.disconnect(); seen.disconnect(); themed.disconnect()
      host?.removeEventListener("pointermove", move); host?.removeEventListener("pointerleave", leave)
    }
  }, [square, gap, fade])

  return <canvas ref={canvas} className={`rs-field ${className}`} aria-hidden="true" />
}
