"use client"
import { useEffect, useRef, useState } from "react"
import { Check, Copy } from "lucide-react"

/**
 * A code window in the product-card style: file name, language, and a copy button that confirms.
 * `wrap` soft-wraps long lines, for program output and prose rather than code.
 */
export function DocCodeBlock({ language = "bash", filename, code, wrap = false }: { language?: string; filename?: string; code: string; wrap?: boolean }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState("")
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true); setCopyError("")
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), 2000)
    } catch { setCopied(false); setCopyError("Select the code and copy it manually.") }
  }
  return <figure className="doc-code">
    <figcaption className="doc-code-bar">
      <span className="doc-code-name"><span className="doc-code-pixel" aria-hidden="true" />{filename || language}</span>
      <span className="doc-code-lang">{language}</span>
      <button type="button" className="doc-code-copy" onClick={handleCopy} aria-label={copied ? "Copied" : "Copy code"}>{copied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</button>
    </figcaption>
    {copyError && <p role="status" className="doc-code-error">{copyError}</p>}
    <pre className={wrap ? "doc-code-wrap" : undefined}><code>{code}</code></pre>
  </figure>
}
