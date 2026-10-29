import type { Recall, StoredTurn } from "@/data/landing-demo"

/** One dated line of a returned context: `[stamp] text` in a section, `[stamp] role: text` in a session. */
export type ContextLine = { stamp: string; role?: "user" | "assistant"; text: string }

/** A returned context, split the way `Memory.search` lays it out: titled sections first, then sessions of turns. */
export type ContextBlock =
  | { kind: "section"; title: string; lines: ContextLine[] }
  | { kind: "session"; lines: ContextLine[] }

const SECTION_ITEM = /^- \[([^\]]+)\] (.*)$/
const TURN_LINE = /^\[([^\]]+)\] (user|assistant): (.*)$/

/** Splits a context's text into its blocks, keeping every line's text exactly as it was returned. */
export function contextBlocks(text: string): ContextBlock[] {
  return text.split("\n\n").map((chunk): ContextBlock => {
    const rows = chunk.split("\n")
    if (rows[0].endsWith(":") && rows.slice(1).every((row) => SECTION_ITEM.test(row))) {
      return { kind: "section", title: rows[0], lines: rows.slice(1).map((row) => {
        const [, stamp, body] = SECTION_ITEM.exec(row)!
        return { stamp, text: body }
      }) }
    }
    return { kind: "session", lines: rows.map((row) => {
      const match = TURN_LINE.exec(row)
      if (!match) throw new Error(`unexpected context line: ${row}`)
      return { stamp: match[1], role: match[2] as "user" | "assistant", text: match[3] }
    }) }
  })
}

/** Indexes of the stored turns a context returned, whole or cut short, matched on date and text. */
export function returnedTurns(turns: readonly StoredTurn[], recall: Recall): Set<number> {
  const lines = contextBlocks(recall.text).flatMap((block) => block.lines)
  const kept = new Set<number>()
  turns.forEach((turn, index) => {
    const day = turn.at.slice(0, 10)
    if (lines.some((line) => line.stamp.startsWith(day) && line.text.length > 0 && turn.text.startsWith(line.text))) kept.add(index)
  })
  return kept
}

/** "2026-09-02T10:14" as the stamp `Memory.search` prints: "2026-09-02 (Wed) 10:14". */
export function printedStamp(at: string): string {
  const date = new Date(`${at}:00Z`)
  const day = date.toLocaleDateString("en-GB", { weekday: "short", timeZone: "UTC" })
  return `${at.slice(0, 10)} (${day}) ${at.slice(11, 16)}`
}
