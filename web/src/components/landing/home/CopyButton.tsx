"use client"

import { useEffect, useRef, useState } from "react"
import { CheckIcon, CopyIcon } from "./icons"

/** Copies `text`; the label says what happened, for screen readers too. */
export function CopyButton({ text, label, className }: { text: string; label: string; className?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle")
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setState("copied")
    } catch {
      setState("failed")
    }
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setState("idle"), 2000)
  }
  const said = state === "copied" ? "Copied" : state === "failed" ? "Copy failed. Select the text instead." : label
  return <button type="button" className={className} onClick={copy} aria-label={said} title={said} data-state={state}>
    {state === "copied" ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
    <span className="lp-sr" aria-live="polite">{state === "idle" ? "" : said}</span>
  </button>
}

/** The install command as a glass pill: `$ pip install llmslim` and a copy button. */
export function InstallPill({ command = "pip install llmslim" }: { command?: string }) {
  return <div className="lp-install">
    <span className="lp-install-prompt" aria-hidden="true">$</span>
    <code>{command}</code>
    <CopyButton text={command} label={`Copy ${command}`} className="lp-install-copy" />
  </div>
}
