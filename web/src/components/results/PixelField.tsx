"use client"

import { useEffect, useRef } from "react"

/** Reads a colour token from the element, so the canvas follows the light and dark themes. */
function token(element: Element, name: string, fallback: string) {
  return getComputedStyle(element).getPropertyValue(name).trim() || fallback
}

/** "#rrggbb", "#rgb" or "rgb(r, g, b)" as [r, g, b]. */
function rgb(colour: string): [number, number, number] {
  const hex = colour.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i)?.[1]
  if (hex) {
    const full = hex.length === 3 ? hex.replace(/./g, (c) => c + c) : hex
    return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)]
  }
  const parts = colour.match(/\d+(\.\d+)?/g)?.map(Number)
  return parts && parts.length >= 3 ? [parts[0], parts[1], parts[2]] : [136, 136, 136]
}

// The canvas sizes itself, so it never depends on a page stylesheet: without a CSS size, a canvas takes the size of
// its backing store, and growing the store to match the device pixel ratio would grow the canvas without end.
const FILL = { display: "block", width: "100%", height: "100%" } as const

/**
 * A field of small squares that flicker at low opacity and brighten into the accent colour under the pointer.
 * `fade` shapes where the field shows: "center" for a hero, "bottom" for a closing band.
 *
 * Each frame writes one pixel per square into a small grid image and draws it twice: scaled up to the canvas, then
 * cut to squares with a stencil of the gaps. Two draws instead of one fill per square keep the main thread free.
 */
export function PixelField({ className = "", square = 3, gap = 7, fade = "center" }: { className?: string; square?: number; gap?: number; fade?: "center" | "bottom" }) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const element = canvas.current
    const context = element?.getContext("2d")
    const grid = document.createElement("canvas")
    const gridContext = grid.getContext("2d")
    const stencil = document.createElement("canvas")
    const stencilContext = stencil.getContext("2d")
    if (!element || !context || !gridContext || !stencilContext) return
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const step = square + gap
    let width = 0, height = 0, cols = 0, rows = 0
    let cells = new Float32Array(0)
    let shade = new Float32Array(0)
    let image: ImageData | null = null
    let ink: [number, number, number] = [136, 136, 136], accent: [number, number, number] = [87, 219, 183]
    let frame = 0, last = 0, visible = false
    const pointer = { x: -1e4, y: -1e4 }

    const colours = () => { ink = rgb(token(element, "--ink", "#888888")); accent = rgb(token(element, "--brand", "#57dbb7")) }
    const mask = (x: number, y: number) => {
      if (fade === "bottom") return Math.max(0, Math.min(1, (y / height - 0.15) * 1.4))
      const dx = (x - width / 2) / (width * 0.62), dy = (y - height * 0.46) / (height * 0.6)
      return Math.max(0, 1 - Math.sqrt(dx * dx + dy * dy))
    }
    /** Rebuilds the cells, the grid image and the stencil when the canvas changes size. */
    const resize = () => {
      const box = element.getBoundingClientRect()
      if (cols && box.width === width && box.height === height) return false
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      width = box.width; height = box.height
      element.width = Math.round(width * ratio); element.height = Math.round(height * ratio)
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      context.imageSmoothingEnabled = false
      cols = Math.ceil(width / step); rows = Math.ceil(height / step)
      cells = Float32Array.from({ length: cols * rows }, () => Math.random())
      shade = Float32Array.from({ length: cols * rows }, (_, i) => mask((i % cols) * step, Math.floor(i / cols) * step))
      grid.width = Math.max(1, cols); grid.height = Math.max(1, rows)
      image = gridContext.createImageData(grid.width, grid.height)
      stencil.width = Math.max(1, element.width); stencil.height = Math.max(1, element.height)
      stencilContext.setTransform(ratio, 0, 0, ratio, 0, 0)
      stencilContext.fillStyle = "#000"
      for (let row = 0; row < rows; row++) for (let col = 0; col < cols; col++) stencilContext.fillRect(col * step, row * step, square, square)
      return true
    }
    const draw = () => {
      if (!image || !cols) return
      const data = image.data
      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          const i = row * cols + col
          if (!reduced && Math.random() < 0.012) cells[i] = Math.random()
          const x = col * step, y = row * step
          const dx = x - pointer.x, dy = y - pointer.y
          const far = dx > 150 || dx < -150 || dy > 150 || dy < -150
          const near = far ? 0 : Math.max(0, 1 - Math.sqrt(dx * dx + dy * dy) / 150)
          const alpha = far && shade[i] < 0.07 ? 0 : cells[i] * 0.3 * shade[i] + near * near * cells[i] * 0.9
          const colour = near > 0.15 && cells[i] > 0.55 ? accent : ink
          const o = i * 4
          data[o] = colour[0]; data[o + 1] = colour[1]; data[o + 2] = colour[2]
          data[o + 3] = alpha < 0.02 ? 0 : Math.round(Math.min(alpha, 1) * 255)
        }
      }
      gridContext.putImageData(image, 0, 0)
      context.clearRect(0, 0, width, height)
      context.drawImage(grid, 0, 0, cols * step, rows * step)
      // Keep only the squares. The stencil is already at device resolution, so it is drawn untransformed.
      context.save()
      context.setTransform(1, 0, 0, 1, 0, 0)
      context.globalCompositeOperation = "destination-in"
      context.drawImage(stencil, 0, 0)
      context.restore()
    }
    const loop = (time: number) => {
      frame = 0
      if (!visible) return
      frame = requestAnimationFrame(loop)
      if (time - last < 50) return
      last = time
      draw()
    }
    // The loop runs only while the field is on screen.
    const start = () => { if (!reduced && visible && !frame) frame = requestAnimationFrame(loop) }

    colours(); resize(); draw()
    const sized = new ResizeObserver(() => { if (resize()) draw() })
    sized.observe(element)
    const seen = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; start() })
    seen.observe(element)
    const themed = new MutationObserver(() => { colours(); draw() })
    themed.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] })
    const host = element.parentElement
    const move = (event: PointerEvent) => { const box = element.getBoundingClientRect(); pointer.x = event.clientX - box.left; pointer.y = event.clientY - box.top }
    const leave = () => { pointer.x = -1e4; pointer.y = -1e4 }
    host?.addEventListener("pointermove", move)
    host?.addEventListener("pointerleave", leave)
    return () => {
      if (frame) cancelAnimationFrame(frame)
      sized.disconnect(); seen.disconnect(); themed.disconnect()
      host?.removeEventListener("pointermove", move); host?.removeEventListener("pointerleave", leave)
    }
  }, [square, gap, fade])

  return <canvas ref={canvas} className={`rs-field ${className}`} style={FILL} aria-hidden="true" />
}
