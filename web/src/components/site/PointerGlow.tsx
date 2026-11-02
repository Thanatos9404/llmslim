"use client"

import { useEffect } from "react"

/**
 * The `.glow-card` spotlight for pages without a PageBackdrop (which does the same with its own art): the card under a
 * mouse pointer gets --mx and --my, written once per animation frame. Renders nothing.
 */
export function PointerGlow() {
  useEffect(() => {
    let frame = 0
    let last: PointerEvent | null = null
    const paint = () => {
      frame = 0
      const card = last?.target instanceof Element ? last.target.closest<HTMLElement>(".glow-card") : null
      if (!last || !card) return
      const box = card.getBoundingClientRect()
      card.style.setProperty("--mx", `${last.clientX - box.left}px`)
      card.style.setProperty("--my", `${last.clientY - box.top}px`)
    }
    const move = (event: PointerEvent) => {
      if (event.pointerType !== "mouse") return
      last = event
      if (!frame) frame = requestAnimationFrame(paint)
    }
    window.addEventListener("pointermove", move, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener("pointermove", move)
    }
  }, [])
  return null
}
