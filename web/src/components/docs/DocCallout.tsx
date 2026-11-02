import { Inline } from "@/components/docs/DocInline"
import type { DocCallout as DocCalloutType } from "@/data/docs"
import { DEFAULT_DOCS_VERSION, type DocsVersion } from "@/data/docs-versions"

const labels = { note: "Note", tip: "Tip", warning: "Warning", important: "Important" } as const

export function DocCallout({ callout, version = DEFAULT_DOCS_VERSION }: { callout: DocCalloutType; version?: DocsVersion }) {
  return <aside className={`doc-callout is-${callout.type}`}>
    <p className="doc-callout-label">{labels[callout.type] ?? labels.note}{callout.title && <span>{callout.title}</span>}</p>
    <p className="doc-callout-body"><Inline text={callout.content} version={version} /></p>
  </aside>
}
