/**
 * /.well-known/security.txt (RFC 9116). Scanners and researchers look for it first; an expired one
 * tells them nobody reads it. This test starts failing two weeks before Expires, so it gets renewed.
 */
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

const FILE = fileURLToPath(new URL("../../public/.well-known/security.txt", import.meta.url))
const DAY = 24 * 60 * 60 * 1000

function fields(text: string): Array<[string, string]> {
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.startsWith("#"))
    .map((line) => {
      const colon = line.indexOf(":")
      return [line.slice(0, colon).trim().toLowerCase(), line.slice(colon + 1).trim()] as [string, string]
    })
}

describe("security.txt", () => {
  const entries = fields(readFileSync(FILE, "utf8"))
  const all = (name: string) => entries.filter(([key]) => key === name).map(([, value]) => value)

  it("has only known fields, each well formed", () => {
    const known = new Set(["contact", "expires", "preferred-languages", "canonical", "policy", "acknowledgments", "encryption", "hiring", "csaf"])
    for (const [key, value] of entries) {
      expect(known.has(key), key).toBe(true)
      expect(value.length, key).toBeGreaterThan(0)
    }
  })

  it("lists HTTPS or mailto contacts", () => {
    const contacts = all("contact")
    expect(contacts.length).toBeGreaterThan(0)
    for (const contact of contacts) expect(contact).toMatch(/^(https:\/\/|mailto:)/)
  })

  it("expires once, within a year, and not in the next two weeks", () => {
    const expires = all("expires")
    expect(expires).toHaveLength(1)
    const when = Date.parse(expires[0])
    expect(Number.isNaN(when)).toBe(false)
    expect(when - Date.now(), "renew security.txt: bump Expires by up to a year").toBeGreaterThan(14 * DAY)
    expect(when - Date.now()).toBeLessThan(366 * DAY)
  })

  it("names its canonical URL on the production site", () => {
    expect(all("canonical")).toEqual(["https://www.llmslim.app/.well-known/security.txt"])
  })
})
