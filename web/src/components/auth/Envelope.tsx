import type { CSSProperties } from "react"

type Vars = CSSProperties & Record<`--${string}`, string | number>

/**
 * "Check your email": an envelope drawn in one stroke, with three strands converging into it and a soft glow when
 * they arrive. Plain SVG and CSS; reduced motion shows the finished drawing.
 */
export function Envelope({ id }: { id: string }) {
  const strands = [
    "M4 30 C44 30 56 54 92 54",
    "M4 54 C44 54 56 56 92 56",
    "M4 78 C44 78 56 58 92 58",
  ]
  return <svg className="auth-envelope" viewBox="0 0 200 112" width="200" height="112" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id={`${id}-strand`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" className="lp-stop-violet" /><stop offset=".6" className="lp-stop-blue" /><stop offset="1" className="lp-stop-green" />
      </linearGradient>
    </defs>
    {strands.map((d, index) => <path key={d} d={d} pathLength={1} className="auth-envelope-strand" stroke={`url(#${id}-strand)`} style={{ "--i": index } as Vars} />)}
    <rect x="92" y="24" width="96" height="64" rx="10" pathLength={1} className="auth-envelope-body" />
    <path d="M96 30 L140 62 L184 30" pathLength={1} className="auth-envelope-flap" />
    <circle cx="184" cy="26" r="6" className="auth-envelope-dot" />
  </svg>
}
