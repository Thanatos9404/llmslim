"use client"

import { useRef, type PointerEvent, type ReactNode } from "react"

/**
 * Lights the edge of the glass card under the mouse: one pointer listener for the whole grid, at most one update a
 * frame, writing two CSS variables on the card (no React render).
 */
export function GlassField({ children, className }: { children: ReactNode; className?: string }) {
  const frame = useRef(0)
  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== "mouse" || frame.current) return
    const { clientX, clientY, target, currentTarget } = event
    frame.current = requestAnimationFrame(() => {
      frame.current = 0
      const card = (target as Element).closest<HTMLElement>(".lp-card")
      if (!card || !currentTarget.contains(card)) return
      const box = card.getBoundingClientRect()
      card.style.setProperty("--mx", `${clientX - box.left}px`)
      card.style.setProperty("--my", `${clientY - box.top}px`)
    })
  }
  return <div className={className} onPointerMove={onMove}>{children}</div>
}
