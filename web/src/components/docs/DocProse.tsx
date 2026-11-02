import { DocCallout } from "@/components/docs/DocCallout"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { Inline } from "@/components/docs/DocInline"
import type { DocSection } from "@/data/docs"
import type { DocsVersion } from "@/data/docs-versions"

/** A section's body: paragraph, list, table, code, a closing paragraph and a callout, in that order. */
export function DocSectionBody({ section, version }: { section: DocSection; version: DocsVersion }) {
  const snippets = [...(section.codeSnippet ? [section.codeSnippet] : []), ...(section.snippets ?? [])]
  return <>
    <p><Inline text={section.content} version={version} /></p>
    {section.items && <ul className="doc-list">{section.items.map((item) => <li key={item}><Inline text={item} version={version} /></li>)}</ul>}
    {section.table && <div className="doc-table-wrap" role="region" aria-label={`${section.title}: table`} tabIndex={0}>
      <table className="doc-table">
        <thead><tr>{section.table.headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead>
        <tbody>{section.table.rows.map((row) => <tr key={row.join("|")}>{row.map((cell, i) => <td key={i}><Inline text={cell} version={version} /></td>)}</tr>)}</tbody>
      </table>
    </div>}
    {snippets.map((snippet) => <DocCodeBlock key={`${snippet.filename}:${snippet.code.slice(0, 40)}`} language={snippet.language} filename={snippet.filename} code={snippet.code} wrap={snippet.wrap} />)}
    {section.after && <p><Inline text={section.after} version={version} /></p>}
    {section.callout && <DocCallout callout={section.callout} version={version} />}
  </>
}
