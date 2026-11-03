"use client"

import Image from "next/image"
import { m, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"

/**
 * A self-hosted stock photo (public/media/stock, credits in CREDITS.md) that drifts a little against the scroll inside
 * its frame. The frame clips it and the photo is drawn 14% taller than the frame (.px-photo in globals.css), so the
 * 6% drift either way never shows an edge.
 * Transform only; reduced-motion visitors get a still photo. Decorative, so it has no alt text.
 */
export function ParallaxPhoto({ src, sizes, position = "center", eager = false, className = "" }: { src: string; sizes: string; position?: string; eager?: boolean; className?: string }) {
  const frame = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: frame, offset: ["start end", "end start"] })
  const y = useTransform(scrollYProgress, [0, 1], ["-6%", "6%"])
  return <div ref={frame} className={`px-photo ${className}`} aria-hidden="true">
    <m.div className="px-photo-media" style={reduced ? undefined : { y }}>
      {/* Eager but at the browser's own priority: on a phone the plate is below the fold, and a high-priority photo
          there would compete with the stylesheet and fonts the first paint needs. */}
      <Image src={src} alt="" fill sizes={sizes} loading={eager ? "eager" : "lazy"} style={{ objectPosition: position }} />
    </m.div>
  </div>
}
