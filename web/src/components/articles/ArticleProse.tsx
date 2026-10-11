import React from "react"
import Link from "next/link"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

/**
 * Renders an article section's Markdown `content` as HTML. The same string is served verbatim in the page's
 * Markdown twin (lib/agent-content.ts), so only a small, predictable subset is supported: paragraphs, "###"
 * subheadings, "-" and "1." lists, "|" tables (with "---:" for right-aligned columns), fenced code blocks
 * ("```lang optional-filename") and inline `code`, **bold** and [links](url). Anything else stays plain text.
 */

type Block =
  | { kind: "p"; text: string }
  | { kind: "h3"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "code"; language: string; filename?: string; code: string }
  | { kind: "table"; headers: string[]; rows: string[][]; right: boolean[] }

const FENCE = /^```([\w+-]*)(?:\s+(\S+))?\s*$/
const BULLET = /^[-*] /
const NUMBERED = /^\d+\. /
const TABLE_ROW = /^\|.*\|\s*$/
const TABLE_RULE = /^\|(?:\s*:?-{3,}:?\s*\|)+\s*$/

// "\|" is a literal pipe inside a cell, as lib/agent-content.ts escapes it.
const cells = (row: string) => row.trim().replace(/^\||\|$/g, "").replace(/\\\|/g, "\u0000").split("|").map((cell) => cell.trim().replace(/\u0000/g, "|"))

function startsBlock(lines: string[], i: number): boolean {
  const line = lines[i]
  return FENCE.test(line) || line.startsWith("### ") || BULLET.test(line) || NUMBERED.test(line) || (TABLE_ROW.test(line) && TABLE_RULE.test(lines[i + 1] ?? ""))
}

export function parseBlocks(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n")
  const blocks: Block[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    const fence = line.match(FENCE)
    if (fence) {
      const body: string[] = []
      i++
      while (i < lines.length && !/^```\s*$/.test(lines[i])) body.push(lines[i++])
      i++
      blocks.push({ kind: "code", language: fence[1] || "text", filename: fence[2], code: body.join("\n") })
      continue
    }
    if (line.startsWith("### ")) { blocks.push({ kind: "h3", text: line.slice(4).trim() }); i++; continue }
    if (TABLE_ROW.test(line) && TABLE_RULE.test(lines[i + 1] ?? "")) {
      const headers = cells(line)
      const right = cells(lines[i + 1]).map((rule) => rule.endsWith(":") && !rule.startsWith(":"))
      const rows: string[][] = []
      i += 2
      while (i < lines.length && TABLE_ROW.test(lines[i])) rows.push(cells(lines[i++]))
      blocks.push({ kind: "table", headers, rows, right })
      continue
    }
    if (BULLET.test(line) || NUMBERED.test(line)) {
      const ordered = NUMBERED.test(line)
      const marker = ordered ? NUMBERED : BULLET
      const items: string[] = []
      while (i < lines.length && lines[i].trim()) {
        if (marker.test(lines[i])) items.push(lines[i].replace(marker, "").trim())
        else if (/^\s+\S/.test(lines[i]) && items.length) items[items.length - 1] += " " + lines[i].trim()
        else break
        i++
      }
      blocks.push({ kind: "list", ordered, items })
      continue
    }
    const text: string[] = []
    while (i < lines.length && lines[i].trim() && (text.length === 0 || !startsBlock(lines, i))) text.push(lines[i++].trim())
    blocks.push({ kind: "p", text: text.join(" ") })
  }
  return blocks
}

const INLINE = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)/g

export function Inline({ text }: { text: string }) {
  const out: React.ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(INLINE)) {
    const at = match.index ?? 0
    if (at > last) out.push(text.slice(last, at))
    const [, code, bold, label, href] = match
    if (code !== undefined) out.push(<code key={at} className="rounded-md border border-border bg-muted px-1.5 py-0.5 font-mono text-[0.85em] text-foreground">{code}</code>)
    else if (bold !== undefined) out.push(<strong key={at} className="font-semibold text-foreground"><Inline text={bold} /></strong>)
    else if (href.startsWith("/") || href.startsWith("#")) out.push(<Link key={at} href={href} className="text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"><Inline text={label} /></Link>)
    else out.push(<a key={at} href={href} target="_blank" rel="noreferrer" className="break-words text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"><Inline text={label} /></a>)
    last = at + match[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return <>{out}</>
}

export function ArticleProse({ content }: { content: string }) {
  return <>{parseBlocks(content).map((block, index) => {
    switch (block.kind) {
      case "h3":
        return <h3 key={index} className="mt-8 text-lg font-semibold tracking-tight">{block.text}</h3>
      case "list": {
        const List = block.ordered ? "ol" : "ul"
        return <List key={index} className={`mt-4 space-y-2 pl-5 leading-7 text-muted-foreground ${block.ordered ? "list-decimal" : "list-disc"}`}>{block.items.map((item, itemIndex) => <li key={itemIndex}><Inline text={item} /></li>)}</List>
      }
      case "code":
        return <div key={index} className="mt-5"><DocCodeBlock language={block.language} filename={block.filename} code={block.code} /></div>
      case "table":
        return <div key={index} className="mt-5 rounded-xl border border-border">
          <Table>
            <TableHeader><TableRow>{block.headers.map((header, cellIndex) => <TableHead key={cellIndex} className={`whitespace-normal align-bottom ${block.right[cellIndex] ? "text-right" : ""}`}><Inline text={header} /></TableHead>)}</TableRow></TableHeader>
            <TableBody>{block.rows.map((row, rowIndex) => <TableRow key={rowIndex}>{row.map((cell, cellIndex) => <TableCell key={cellIndex} className={block.right[cellIndex] ? "text-right font-mono tabular-nums" : "min-w-32 whitespace-normal"}><Inline text={cell} /></TableCell>)}</TableRow>)}</TableBody>
          </Table>
        </div>
      default:
        return <p key={index} className="mt-4 leading-7 text-muted-foreground"><Inline text={block.text} /></p>
    }
  })}</>
}
