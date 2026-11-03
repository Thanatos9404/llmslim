"use client"
import { m, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, useState, type CSSProperties, type PointerEvent } from "react"
import { Check, Copy } from "lucide-react"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { CodeMark } from "@/components/docs/DocCodeBlock"
import { PixelField } from "@/components/results/PixelField"

const INSTALL = "pip install llmslim"
const QUICK = `from llmslim.memory import Memory

memory = Memory("memory.db")
memory.add("I moved to Pune last month.",
           user_id="asha")

context = memory.search("Where did I move to?",
                        user_id="asha")
print(context.text)   # what answers it`

/** The docs front door: a short promise, the install line, and a first call you can copy. `kicker` names the version when it isn't the current one. */
export function DocsHero({ kicker = "Documentation" }: { kicker?: string }) {
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
      <p className="docs-kicker has-glyph rise" {...rise(0)}><MemoryGlyph size={14} />{kicker}</p>
      <h1 id="docs-title" className="rise" {...rise(0.06)}>Start in one line. <em>Go as deep as you need.</em></h1>
      <p className="docs-lede rise" {...rise(0.12)}>Short guides for agent memory with no LLM in the loop, from Python, MCP, HTTP and TypeScript, and for fitting chat, retrieval and tool output into a real token budget.</p>
      <button type="button" className="docs-install rise" onClick={() => copy("install")} {...rise(0.18)} aria-label="Copy the install command">
        <span className="docs-install-prompt" aria-hidden="true">$</span><code>{INSTALL}</code>
        <span className="docs-install-copy">{copied === "install" ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</span>
      </button>
    </div>
    <figure className="docs-quick rise" onPointerMove={spot} {...rise(0.24)}>
      <figcaption className="doc-code-bar">
        <span className="doc-code-name"><CodeMark language="python" />quickstart.py</span>
        <span className="doc-code-lang">python</span>
        <button type="button" className="doc-code-copy" onClick={() => copy("quick")} aria-label="Copy the example">{copied === "quick" ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</button>
      </figcaption>
      <pre><code>{QUICK}</code></pre>
    </figure>
  </section>
}
