import Link from "next/link"
import { Fragment, type ReactNode } from "react"
import { resolveDocLink, type DocsVersion } from "@/data/docs-versions"

const TOKEN = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g

/** Docs text with `code`, **bold** and [links](href). */
export function Inline({ text, version, links = true }: { text: string; version: DocsVersion; links?: boolean }) {
  const parts = text.split(TOKEN)
  return <>{parts.map((part, i): ReactNode => {
    if (i % 2 === 0) return part ? <Fragment key={i}>{part}</Fragment> : null
    if (part.startsWith("**")) return <strong key={i}><Inline text={part.slice(2, -2)} version={version} links={links} /></strong>
    if (part.startsWith("`")) return <code key={i} className="doc-inline-code">{part.slice(1, -1)}</code>
    const [, label, href] = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/) ?? []
    const content = <Inline text={label} version={version} links={false} />
    if (!links) return <Fragment key={i}>{content}</Fragment>
    const target = resolveDocLink(href, version)
    return /^https?:/.test(target)
      ? <a key={i} href={target} className="doc-link" rel="noopener noreferrer">{content}</a>
      : <Link key={i} href={target} className="doc-link">{content}</Link>
  })}</>
}

/** Docs text without its markup, for structured data and plain-text fields. */
export function plainText(text: string): string {
  return text.replace(/\[([^\]]+)\]\([^)\s]+\)/g, "$1").replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1")
}
