"use client"
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, useState, type PointerEvent } from "react"
import { Check, Copy } from "lucide-react"
import { PixelField } from "@/components/results/PixelField"

const EASE = [0.16, 1, 0.3, 1] as const
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
  const rise = (delay: number) => (reduced ? {} : { initial: { opacity: 0, y: 18, filter: "blur(6px)" }, animate: { opacity: 1, y: 0, filter: "blur(0px)" }, transition: { duration: 0.9, ease: EASE, delay } })
  return <section ref={ref} className="docs-hero" aria-labelledby="docs-title">
    <motion.div className="docs-hero-field" style={reduced ? undefined : { y: fieldY }}><PixelField gap={9} /></motion.div>
    <div className="docs-hero-copy">
      <motion.p className="docs-kicker" {...rise(0)}>Documentation</motion.p>
      <motion.h1 id="docs-title" {...rise(0.06)}>Start in one line. <em>Go as deep as you need.</em></motion.h1>
      <motion.p className="docs-lede" {...rise(0.12)}>Short guides for compressing context, keeping provenance, and fitting chat, retrieval and tool output into a real token budget.</motion.p>
      <motion.button type="button" className="docs-install" onClick={() => copy("install")} {...rise(0.18)} aria-label="Copy the install command">
        <span className="docs-install-prompt" aria-hidden="true">$</span><code>{INSTALL}</code>
        <span className="docs-install-copy">{copied === "install" ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</span>
      </motion.button>
    </div>
    <motion.figure className="docs-quick" onPointerMove={spot} {...rise(0.24)}>
      <figcaption className="doc-code-bar">
        <span className="doc-code-name"><span className="doc-code-pixel" aria-hidden="true" />quickstart.py</span>
        <span className="doc-code-lang">python</span>
        <button type="button" className="doc-code-copy" onClick={() => copy("quick")} aria-label="Copy the example">{copied === "quick" ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</button>
      </figcaption>
      <pre><code>{QUICK}</code></pre>
    </motion.figure>
  </section>
}
