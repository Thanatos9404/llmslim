"use client"

import { useEffect, useRef, useState } from "react"
import { Check, Copy, RotateCcw } from "lucide-react"

// The home page's scroll reveals are the shared Reveal (components/motion/Reveal.tsx), on the site's one curve.

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
  return <div className={`context-preview ${compressed ? "is-compressed" : ""}`}>
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
  return <div className="developer-code"><div className="code-toolbar"><div role="tablist" aria-label="Python examples">{(["compress", "rag"] as const).map((key, index) => <button id={`tab-${key}`} role="tab" aria-selected={selected === key} aria-controls="code-panel" tabIndex={selected === key ? 0 : -1} key={key} onClick={() => setSelected(key)} onKeyDown={(e) => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) { e.preventDefault(); const next = e.key === "Home" ? "compress" : e.key === "End" ? "rag" : index === 0 ? "rag" : "compress"; setSelected(next); document.getElementById(`tab-${next}`)?.focus() } }}>{key === "compress" ? "compress.py" : "rag_pipeline.py"}</button>)}</div><span>PYTHON</span></div><pre id="code-panel" role="tabpanel" aria-labelledby={`tab-${selected}`} tabIndex={0}><code>{snippets[selected]}</code></pre><div className="code-status"><span><span className="status-dot" /> Runs locally</span><span>No API key needed</span></div></div>
}
