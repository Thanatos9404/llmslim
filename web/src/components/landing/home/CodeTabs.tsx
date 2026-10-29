"use client"

import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react"
import { CopyButton } from "./CopyButton"

export type CodeTab = { id: string; label: string; file: string; code: string; body: ReactNode; note?: ReactNode }

/**
 * Tabs over pre-highlighted code (highlighted on the server, passed in as `body`). The WAI-ARIA tabs pattern:
 * arrow keys, Home and End move between tabs and select them; Tab moves into the code.
 */
export function CodeTabs({ tabs, label }: { tabs: CodeTab[]; label: string }) {
  const [active, setActive] = useState(0)
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const base = useId()
  const select = (index: number) => {
    const next = (index + tabs.length) % tabs.length
    setActive(next)
    buttons.current[next]?.focus()
  }
  const onKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const moves: Record<string, number> = { ArrowRight: active + 1, ArrowLeft: active - 1, Home: 0, End: tabs.length - 1 }
    if (event.key in moves) { event.preventDefault(); select(moves[event.key]) }
  }
  return <div className="lp-code lp-glass">
    <div className="lp-code-tabs" role="tablist" aria-label={label}>
      {tabs.map((item, index) => <button key={item.id} ref={(node) => { buttons.current[index] = node }} type="button" role="tab"
        id={`${base}-tab-${item.id}`} aria-selected={index === active} aria-controls={`${base}-panel-${item.id}`} tabIndex={index === active ? 0 : -1}
        onClick={() => setActive(index)} onKeyDown={onKey}>{item.label}</button>)}
    </div>
    {tabs.map((item, index) => <div key={item.id} role="tabpanel" id={`${base}-panel-${item.id}`} aria-labelledby={`${base}-tab-${item.id}`} hidden={index !== active} className="lp-code-panel">
      <div className="lp-code-bar">
        <span className="lp-mono">{item.file}</span>
        <CopyButton text={item.code} label={`Copy the ${item.label} example`} className="lp-code-copy" />
      </div>
      <pre tabIndex={0} aria-label={`${item.label} example`}><code>{item.body}</code></pre>
      {item.note && <p className="lp-code-note">{item.note}</p>}
    </div>)}
  </div>
}
