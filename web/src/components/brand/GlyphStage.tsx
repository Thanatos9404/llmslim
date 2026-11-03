"use client"

import { inView } from "framer-motion"
import { useEffect, useRef, useState } from "react"
import { MemoryGlyph } from "./MemoryGlyph"

/**
 * The hero's memory glyph. It plays once on load (CSS, from the first paint). Where the plate starts below the fold
 * (phones), it plays again when it scrolls into view, so the first run is not spent off screen. Pointing at it plays
 * it again, at most once per run (2.2 s); performance.now() counts from the page load, so no run is cut short.
 */
export function GlyphStage({ size = 168 }: { size?: number }) {
  const [run, setRun] = useState(0)
  const stage = useRef<HTMLDivElement>(null)
  const last = useRef(0)
  const replay = () => {
    const now = performance.now()
    if (now - last.current < 2200) return
    last.current = now
    setRun((value) => value + 1)
  }
  useEffect(() => {
    const element = stage.current
    if (!element || element.getBoundingClientRect().top < window.innerHeight) return
    const stop = inView(element, () => {
      stop()
      last.current = performance.now()
      setRun((value) => value + 1)
    }, { amount: 0.5 })
    return stop
  }, [])
  return <div ref={stage} className="glyph-stage" onPointerEnter={replay}>
    <MemoryGlyph key={run} size={size} animate />
  </div>
}
