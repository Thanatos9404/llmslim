"use client"

import { useEffect, useRef } from "react"
import { PixelField } from "@/components/results/PixelField"
import { MARK_ASCII } from "./backdrop-art"

/**
 * The backdrop behind a page's opening, after the docs hero: the pixel field, the LLMSlim mark drawn in
 * ASCII and a faint code snippet. Under the pointer the ASCII and the code light up in the brand colour,
 * and every `.glow-card` on the page gets a spotlight that follows the pointer.
 * `layout="split"` puts the art either side of a centred column instead of to the right of the copy, and
 * `low` drops the mark below a heading that runs the full width.
 */
export function PageBackdrop({ code, layout = "right", low = false }: { code: string; layout?: "right" | "split"; low?: boolean }) {
  const backdrop = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = backdrop.current
    if (!element) return
    let frame = 0
    let last: PointerEvent | null = null
    // One write per frame: the pointer position relative to the backdrop, and to the card under it.
    const paint = () => {
      frame = 0
      if (!last) return
      const box = element.getBoundingClientRect()
      const x = last.clientX - box.left, y = last.clientY - box.top
      element.style.setProperty("--mx", `${x}px`)
      element.style.setProperty("--my", `${y}px`)
      element.toggleAttribute("data-lit", x >= 0 && y >= 0 && x <= box.width && y <= box.height)
      const card = last.target instanceof Element ? last.target.closest<HTMLElement>(".glow-card") : null
      if (card) {
        const cardBox = card.getBoundingClientRect()
        card.style.setProperty("--mx", `${last.clientX - cardBox.left}px`)
        card.style.setProperty("--my", `${last.clientY - cardBox.top}px`)
      }
    }
    const move = (event: PointerEvent) => {
      if (event.pointerType !== "mouse") return
      last = event
      if (!frame) frame = requestAnimationFrame(paint)
    }
    const leave = () => element.removeAttribute("data-lit")
    window.addEventListener("pointermove", move, { passive: true })
    document.documentElement.addEventListener("pointerleave", leave)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener("pointermove", move)
      document.documentElement.removeEventListener("pointerleave", leave)
    }
  }, [])

  const art = <><pre className="backdrop-ascii">{MARK_ASCII}</pre><pre className="backdrop-code">{code}</pre></>
  return <div ref={backdrop} className={low ? "page-backdrop page-backdrop-low" : "page-backdrop"} data-layout={layout} aria-hidden="true">
    <div className="page-backdrop-field"><PixelField gap={9} /></div>
    <div className="page-backdrop-art">{art}</div>
    <div className="page-backdrop-art page-backdrop-glow">{art}</div>
  </div>
}
