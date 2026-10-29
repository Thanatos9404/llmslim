// Small line icons for the home page, drawn here so the page needs no icon package: 16px, 1.5px strokes.

type IconProps = { size?: number; className?: string }

const base = (size: number) => ({ width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, focusable: false })

export function ArrowRight({ size = 16, className }: IconProps) {
  return <svg {...base(size)} className={className}><path d="M3 8h10M9 4l4 4-4 4" /></svg>
}

export function ArrowUpRight({ size = 16, className }: IconProps) {
  return <svg {...base(size)} className={className}><path d="M5 11l6-6M6 5h5v5" /></svg>
}

export function CopyIcon({ size = 16, className }: IconProps) {
  return <svg {...base(size)} className={className}><rect x="5.5" y="5.5" width="8" height="8" rx="2" /><path d="M10.5 3.5v-.5a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 3v5A1.5 1.5 0 0 0 4 9.5h.5" /></svg>
}

export function CheckIcon({ size = 16, className }: IconProps) {
  return <svg {...base(size)} className={className}><path d="M3.5 8.5l3 3 6-7" /></svg>
}

export function ReplayIcon({ size = 16, className }: IconProps) {
  return <svg {...base(size)} className={className}><path d="M2.5 8a5.5 5.5 0 1 0 1.6-3.9M2.5 2.5v3h3" /></svg>
}

export function PlusIcon({ size = 16, className }: IconProps) {
  return <svg {...base(size)} className={className}><path d="M8 3v10M3 8h10" /></svg>
}
