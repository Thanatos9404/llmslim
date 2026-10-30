import { existsSync, readdirSync, readFileSync } from "node:fs"
import path from "node:path"
import { E2E } from "./env"

type SinkMail = { to: string; kind: string; subject: string; url?: string; sentAt: string }

function read(): SinkMail[] {
  if (!existsSync(E2E.mailDir)) return []
  return readdirSync(E2E.mailDir)
    .filter((name) => name.endsWith(".json"))
    .map((name) => JSON.parse(readFileSync(path.join(E2E.mailDir, name), "utf8")) as SinkMail)
    .sort((a, b) => a.sentAt.localeCompare(b.sentAt))
}

/** Waits for the newest email of a kind to an address, sent after `since`, and returns it. */
export async function waitForMail(to: string, kind: string, since: Date, timeoutMs = 15_000): Promise<SinkMail> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const match = read()
      .filter((mail) => mail.to === to && mail.kind === kind && new Date(mail.sentAt) >= since)
      .pop()
    if (match) return match
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`No ${kind} email to ${to} within ${timeoutMs} ms`)
}

export function mailCount(to: string, kind?: string): number {
  return read().filter((mail) => mail.to === to && (!kind || mail.kind === kind)).length
}
