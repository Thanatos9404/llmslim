import { useId, type CSSProperties } from "react"

/**
 * The memory glyph: the LogoMark's idea (five strands of context, three kept) drawn as a memory. Five stored turns,
 * with the mark's rounded ends, stack up; the three that fit the token budget light up in the mark's spectrum and get
 * a pixel on the budget rail beside them; the other two dim. Colours come from the --mark-* tokens, so it follows the
 * theme like the mark does. Styles and keyframes are in globals.css (.mg).
 *
 * `animate` plays the sequence once (CSS only, so it runs from the first paint and needs no script); reduced-motion
 * visitors get the final state. Inside a Reveal, it waits until the section is shown.
 */

const BOX = { width: 120, height: 100 }
const ROW_HEIGHT = 12
/** Each stored turn: its length and whether it fits the budget. */
const TURNS = [
  { y: 8, width: 70, kept: false },
  { y: 27, width: 50, kept: true },
  { y: 46, width: 86, kept: true },
  { y: 65, width: 38, kept: false },
  { y: 84, width: 62, kept: true },
] as const
const X = 8
const RAIL_X = 108

type MemoryGlyphProps = {
  /** Height in pixels; the width follows the 6:5 box. */
  size?: number
  /** Play the slide-in and light-up once. */
  animate?: boolean
  className?: string
  /** Accessible name. Leave it out where the glyph is decoration. */
  title?: string
}

export function MemoryGlyph({ size = 20, animate = false, className, title }: MemoryGlyphProps) {
  const gradient = `mg-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`
  let keptIndex = 0
  return <svg
    className={`mg${className ? ` ${className}` : ""}`}
    viewBox={`0 0 ${BOX.width} ${BOX.height}`}
    width={Math.round((size * BOX.width) / BOX.height)}
    height={size}
    data-anim={animate ? "" : undefined}
    role={title ? "img" : undefined}
    aria-label={title}
    aria-hidden={title ? undefined : true}
    focusable="false"
  >
    <defs>
      <linearGradient id={gradient} gradientUnits="userSpaceOnUse" x1={X} y1={0} x2={X + 86} y2={0}>
        <stop offset={0} style={{ stopColor: "var(--mark-left-0)" }} />
        <stop offset={0.46} style={{ stopColor: "var(--mark-left-2)" }} />
        <stop offset={1} style={{ stopColor: "var(--mark-end-4)" }} />
      </linearGradient>
    </defs>
    <rect className="mg-rail" x={RAIL_X} y={TURNS[0].y} width={2} height={TURNS[TURNS.length - 1].y + ROW_HEIGHT - TURNS[0].y} rx={1} />
    {TURNS.map((turn, index) => {
      const k = turn.kept ? keptIndex++ : -1
      const style = { "--i": index, "--k": k } as CSSProperties
      return <g key={turn.y} className={`mg-row${turn.kept ? " is-kept" : " is-out"}`} style={style}>
        <rect className="mg-base" x={X} y={turn.y} width={turn.width} height={ROW_HEIGHT} rx={ROW_HEIGHT / 2} />
        {turn.kept && <rect className="mg-lit" x={X} y={turn.y} width={turn.width} height={ROW_HEIGHT} rx={ROW_HEIGHT / 2} fill={`url(#${gradient})`} />}
        {turn.kept && <rect className="mg-pin" x={RAIL_X - 2} y={turn.y + 3} width={6} height={6} />}
      </g>
    })}
  </svg>
}
