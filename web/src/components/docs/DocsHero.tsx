"use client"
import { m, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, useState, type CSSProperties, type PointerEvent } from "react"
import { Check, Copy } from "lucide-react"
import { PixelField } from "@/components/results/PixelField"

const INSTALL = "pip install llmslim"
const QUICK = `from llmslim import compress

result = compress(chat_history, target_ratio=0.25,
                  query="Where should the card be shipped?")

print(result.compressed_text)   # what the model needs
print(result.tokens_saved)      # what you no longer pay for`

/** The docs front door: a short promise, the install line, and a first call you can copy. */
export function DocsHero() {
  const ref = useRef<HTMLElement>(null)
  const [copied, setCopied] = useState<"" | "install" | "quick">("")
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] })
  const fieldY = useTransform(scrollYProgress, [0, 1], [0, 90])
  const copy = async (what: "install" | "quick") => {
    try { await navigator.clipboard.writeText(what === "install" ? INSTALL : QUICK); setCopied(what); window.setTimeout(() => setCopied(""), 1800) } catch { /* the text stays selectable */ }
  }
  const spot = (event: PointerEvent<HTMLElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty("--mx", `${event.clientX - box.left}px`)
    event.currentTarget.style.setProperty("--my", `${event.clientY - box.top}px`)
  }
  // Entrance from first paint, in CSS, so the copy does not wait for scripts (see .rise in globals.css).
  const rise = (delay: number) => ({ style: { "--rise-delay": `${delay}s` } as CSSProperties })
  return <section ref={ref} className="docs-hero" aria-labelledby="docs-title">
    <m.div className="docs-hero-field" style={reduced ? undefined : { y: fieldY }}><PixelField gap={9} /></m.div>
    <div className="docs-hero-copy">
      <p className="docs-kicker rise" {...rise(0)}>Documentation</p>
      <h1 id="docs-title" className="rise" {...rise(0.06)}>Start in one line. <em>Go as deep as you need.</em></h1>
      <p className="docs-lede rise" {...rise(0.12)}>Short guides for compressing context, keeping provenance, and fitting chat, retrieval and tool output into a real token budget.</p>
      <button type="button" className="docs-install rise" onClick={() => copy("install")} {...rise(0.18)} aria-label="Copy the install command">
        <span className="docs-install-prompt" aria-hidden="true">$</span><code>{INSTALL}</code>
        <span className="docs-install-copy">{copied === "install" ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</span>
      </button>
    </div>
    <figure className="docs-quick rise" onPointerMove={spot} {...rise(0.24)}>
      <figcaption className="doc-code-bar">
        <span className="doc-code-name"><span className="doc-code-pixel" aria-hidden="true" />quickstart.py</span>
        <span className="doc-code-lang">python</span>
        <button type="button" className="doc-code-copy" onClick={() => copy("quick")} aria-label="Copy the example">{copied === "quick" ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</button>
      </figcaption>
      <pre><code>{QUICK}</code></pre>
    </figure>
  </section>
}
