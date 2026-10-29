import { useId } from "react"
import { MARK_BOX, MARK_GRADIENT_X, MARK_ORDER, MARK_PALETTES, MARK_STRANDS, type MarkPalette } from "./mark-data"

type LogoMarkProps = {
  /** Height in pixels; the width follows the mark's proportions. */
  size?: number
  /** A fixed palette. Leave it out to follow the site theme (the --mark-* colours in globals.css). */
  palette?: MarkPalette
  /** One flat colour for every strand, for monochrome uses. */
  mono?: string
  className?: string
  /** Accessible name. Leave it out when a visible wordmark sits beside the mark. */
  title?: string
}

type Stop = "left" | "right" | "end"

/** The LLMSlim mark as inline SVG, so it stays sharp at any size and follows the theme. */
export function LogoMark({ size = 24, palette, mono, className, title }: LogoMarkProps) {
  const id = `llmslim-mark-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`
  const width = (size * MARK_BOX.width) / MARK_BOX.height
  const colour = (stop: Stop, strand: number) =>
    palette ? MARK_PALETTES[palette][stop][strand] : `var(--mark-${stop}-${strand})`
  return <svg
    className={className}
    viewBox={`${MARK_BOX.x} ${MARK_BOX.y} ${MARK_BOX.width} ${MARK_BOX.height}`}
    width={Math.round(width * 100) / 100}
    height={size}
    role={title ? "img" : undefined}
    aria-label={title}
    aria-hidden={title ? undefined : true}
    focusable="false"
  >
    {mono ? null : <defs>
      {MARK_STRANDS.map((strand, i) => <linearGradient key={i} id={`${id}-${i}`} gradientUnits="userSpaceOnUse"
        x1={MARK_GRADIENT_X.from} y1={0} x2={MARK_GRADIENT_X.to} y2={0}>
        <stop offset={strand.o1} style={{ stopColor: colour("left", i) }} />
        <stop offset={strand.o2} style={{ stopColor: colour("right", i) }} />
        <stop offset={1} style={{ stopColor: colour("end", i) }} />
      </linearGradient>)}
    </defs>}
    {MARK_ORDER.map((i) => <path key={i} d={MARK_STRANDS[i].d} fill={mono ?? `url(#${id}-${i})`} />)}
  </svg>
}
