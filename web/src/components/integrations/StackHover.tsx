"use client"

import type { ReactNode, SyntheticEvent } from "react"

/**
 * The stack drawing's only script: one delegated handler that marks the strands of the logo under the pointer (or in
 * focus) as hot, so CSS sets context flowing along them. No React state, so pointing at a logo re-renders nothing.
 */
export function StackHover({ children }: { children: ReactNode }) {
  const mark = (event: SyntheticEvent<HTMLDivElement>, on: boolean) => {
    const link = (event.target as Element).closest<HTMLElement>("a[data-slug]")
    if (!link) return
    for (const strand of event.currentTarget.querySelectorAll(`.stack-strand[data-slug="${link.dataset.slug}"]`)) strand.classList.toggle("is-hot", on)
  }
  return <div className="stack" onPointerOver={(event) => mark(event, true)} onPointerOut={(event) => mark(event, false)}
    onFocus={(event) => mark(event, true)} onBlur={(event) => mark(event, false)}>
    {children}
  </div>
}
