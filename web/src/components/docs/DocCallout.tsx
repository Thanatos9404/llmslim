import { DocCallout as DocCalloutType } from "@/data/docs"

const labels = { note: "Note", tip: "Tip", warning: "Warning", important: "Important" } as const

export function DocCallout({ callout }: { callout: DocCalloutType }) {
  return <aside className={`doc-callout is-${callout.type}`}>
    <p className="doc-callout-label">{labels[callout.type] ?? labels.note}{callout.title && <span>{callout.title}</span>}</p>
    <p className="doc-callout-body">{callout.content}</p>
  </aside>
}
