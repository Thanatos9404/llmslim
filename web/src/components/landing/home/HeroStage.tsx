"use client"

import { m, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { ReplayIcon } from "./icons"

/**
 * Wraps the hero demo: tilts it back a little and lays it flat as it scrolls into view, pauses the endless
 * animations (strand pulses, aurora, stars) while the hero is off screen, and replays the search on request.
 * The demo itself is server markup animated by CSS, so it plays from the first paint, before this script runs.
 */
export function HeroStage({ children }: { children: ReactNode }) {
  const frame = useRef<HTMLDivElement>(null)
  const [run, setRun] = useState(0)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: frame, offset: ["start end", "start 0.25"] })
  const rotateX = useTransform(scrollYProgress, [0, 1], [10, 0])
  const scale = useTransform(scrollYProgress, [0, 1], [0.96, 1])

  useEffect(() => {
    const hero = frame.current?.closest("section")
    if (!hero) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) hero.removeAttribute("data-idle")
      else hero.setAttribute("data-idle", "")
    })
    observer.observe(hero)
    return () => observer.disconnect()
  }, [])

  return <div className="lp-stage-frame" ref={frame}>
    <m.div className="lp-stage-tilt" style={reduced ? undefined : { rotateX, scale }}>
      <div className="lp-stage-run" key={run}>{children}</div>
      <button type="button" className="lp-replay" onClick={() => setRun((n) => n + 1)} aria-label="Replay the search" title="Replay the search">
        <ReplayIcon size={14} /><span>Replay</span>
      </button>
    </m.div>
  </div>
}
