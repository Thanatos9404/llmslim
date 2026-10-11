"use client"

import { animate, useInView, useReducedMotion } from "framer-motion"
import { useEffect, useRef } from "react"

export const EASE = [0.16, 1, 0.3, 1] as const

export function fmt(value: number, digits = 0) {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Counts to `to` the first time it is seen; `from` lets a number count down. */
export function Count({ to, from = 0, digits = 0, prefix = "", suffix = "", duration = 1.6, delay = 0 }: { to: number; from?: number; digits?: number; prefix?: string; suffix?: string; duration?: number; delay?: number }) {
  const node = useRef<HTMLSpanElement>(null)
  const inView = useInView(node, { once: true, amount: 0.6 })
  const reduced = useReducedMotion()
  useEffect(() => {
    if (!inView || reduced || !node.current) return
    node.current.textContent = `${prefix}${fmt(from, digits)}${suffix}`
    const controls = animate(from, to, { duration, delay, ease: EASE, onUpdate: (v) => { if (node.current) node.current.textContent = `${prefix}${fmt(v, digits)}${suffix}` } })
    return () => controls.stop()
  }, [inView, reduced]) // eslint-disable-line react-hooks/exhaustive-deps
  return <span ref={node}>{`${prefix}${fmt(to, digits)}${suffix}`}</span>
}
