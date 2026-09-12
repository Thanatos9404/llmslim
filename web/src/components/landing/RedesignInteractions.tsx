"use client"

import Image from "next/image"
import { useEffect, useRef, useState } from "react"
import { Check, Copy, RotateCcw } from "lucide-react"

export function HomeEffects() {
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)")
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add("revealed"); observer.unobserve(entry.target) }
    }), { threshold: .12 })
    const reveals = document.querySelectorAll<HTMLElement>("[data-reveal]")
    if (!media.matches) reveals.forEach(el => { el.classList.add("reveal-ready"); observer.observe(el) })
    const layers = [...document.querySelectorAll<HTMLElement>("[data-parallax]")]
    let frame = 0
    const render = () => {
      frame = 0
      layers.forEach(el => {
        const rect = el.getBoundingClientRect()
        if (rect.bottom < -400 || rect.top > innerHeight + 400) return
        const offset = media.matches ? 0 : Math.max(-130, Math.min(130, (innerHeight / 2 - (rect.top + rect.height / 2)) * Number(el.dataset.parallax)))
        el.style.setProperty("--scroll-y", `${offset}px`)
      })
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(render) }
    window.addEventListener("scroll", schedule, { passive: true })
    media.addEventListener("change", schedule)
    schedule()
    return () => { observer.disconnect(); cancelAnimationFrame(frame); window.removeEventListener("scroll", schedule); media.removeEventListener("change", schedule); reveals.forEach(el => el.classList.remove("reveal-ready")) }
  }, [])
  return null
}

export function HeroArtwork() {
  const artwork = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = artwork.current
    const hero = element?.parentElement
    if (!element || !hero) return
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)")
    let frame = 0
    let offset = 0
    const move = (event: PointerEvent) => {
      if (reduced.matches || event.pointerType !== "mouse") return
      const bounds = hero.getBoundingClientRect()
      offset = ((event.clientX - bounds.left) / bounds.width - .5) * 24
      if (!frame) frame = requestAnimationFrame(() => { element.style.setProperty("--pointer-x", `${offset}px`); frame = 0 })
    }
    const reset = () => { cancelAnimationFrame(frame); frame = 0; element.style.setProperty("--pointer-x", "0px") }
    hero.addEventListener("pointermove", move)
    hero.addEventListener("pointerleave", reset)
    reduced.addEventListener("change", reset)
    return () => { reset(); hero.removeEventListener("pointermove", move); hero.removeEventListener("pointerleave", reset); reduced.removeEventListener("change", reset) }
  }, [])
  return <div ref={artwork} className="hero-artwork" aria-hidden="true" data-parallax="0.18"><Image src="/compression-ribbon-dark.webp" alt="" width={1536} height={1024} className="art-dark" priority sizes="100vw" /><Image src="/compression-ribbon-light.webp" alt="" width={1536} height={1024} className="art-light" priority sizes="100vw" /></div>
}

export function CopyCommand() {
  const [status, setStatus] = useState("Copy install command")
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])
  async function copy() {
    try { await navigator.clipboard.writeText("pip install llmslim"); setStatus("Copied!") }
    catch { setStatus("Select the command to copy") }
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setStatus("Copy install command"), 2500)
  }
  return <div className="install-command"><span aria-hidden="true">$</span><code>pip install llmslim</code><button onClick={copy} aria-label={status} title={status}>{status === "Copied!" ? <Check size={14} /> : <Copy size={14} />}</button><span className="sr-only" role="status">{status}</span></div>
}

const sentences = [
  { text: "The deployment is scheduled for Thursday at 14:00 UTC.", keep: true },
  { text: "The engineering team discussed the deployment during the weekly planning meeting.", keep: false },
  { text: "All API keys must be stored in environment variables.", keep: true },
  { text: "The discussion also covered the general background of the project and a review of previous meetings.", keep: false },
  { text: "Roll back if the error rate exceeds 2 percent.", keep: true },
]

export function ContextPreview() {
  const [compressed, setCompressed] = useState(false)
  const wordCount = sentences.filter(s => !compressed || s.keep).reduce((n,s) => n + s.text.split(/\s+/).length, 0)
  return <div className={`context-preview ${compressed ? "is-compressed" : ""}`} data-reveal>
    <div className="preview-toolbar"><span>context.txt</span><div><span className="preview-count" aria-live="polite">{wordCount} words</span><button className="preview-switch" aria-pressed={compressed} onClick={() => setCompressed(!compressed)}>{compressed ? <><RotateCcw size={13} />Show original</> : <>Focus the context <span>↗</span></>}</button></div></div>
    <div className="preview-document" aria-live="polite">{sentences.map((sentence,i) => <span key={i} className={sentence.keep ? "sentence-kept" : "sentence-extra"} hidden={compressed && !sentence.keep}>{sentence.text}{" "}</span>)}</div>
    <div className="preview-caption"><span>Illustrative excerpt · word counts, not tokens</span><span>{compressed ? "Relevant details, brought forward." : "A deployment note with room to trim."}</span></div>
  </div>
}

const snippets = {
  compress: <><span className="code-purple">from</span> llmslim <span className="code-purple">import</span> compress{"\n\n"}<span className="code-comment"># Keep the useful. Leave the rest.</span>{"\n"}result = compress({"\n"}    long_context,{"\n"}    target_ratio=<span className="code-green">0.5</span>,{"\n"}){"\n\n"}<span className="code-comment"># Ready for your model</span>{"\n"}context = result.compressed_text</>,
  rag: <><span className="code-purple">from</span> llmslim <span className="code-purple">import</span> compress_documents{"\n\n"}<span className="code-comment"># Retrieved content keeps its RAG role.</span>{"\n"}results = compress_documents({"\n"}    retrieved_docs,{"\n"}    query=user_question,{"\n"}    target_ratio=<span className="code-green">0.5</span>,{"\n"}){"\n\n"}context = <span className="code-green">&quot;\n\n&quot;</span>.join({"\n"}    item.compressed_text <span className="code-purple">for</span> item <span className="code-purple">in</span> results{"\n"})</>,
}

export function CodeExample() {
  const [selected, setSelected] = useState<"compress" | "rag">("compress")
  return <div className="developer-code" data-reveal><div className="code-toolbar"><div role="tablist" aria-label="Python examples">{(["compress", "rag"] as const).map((key, index) => <button id={`tab-${key}`} role="tab" aria-selected={selected === key} aria-controls="code-panel" tabIndex={selected === key ? 0 : -1} key={key} onClick={() => setSelected(key)} onKeyDown={(e) => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) { e.preventDefault(); const next = e.key === "Home" ? "compress" : e.key === "End" ? "rag" : index === 0 ? "rag" : "compress"; setSelected(next); document.getElementById(`tab-${next}`)?.focus() } }}>{key === "compress" ? "compress.py" : "rag_pipeline.py"}</button>)}</div><span>PYTHON</span></div><pre id="code-panel" role="tabpanel" aria-labelledby={`tab-${selected}`} tabIndex={0}><code>{snippets[selected]}</code></pre><div className="code-status"><span><span className="status-dot" /> Runs locally</span><span>No API key needed</span></div></div>
}
