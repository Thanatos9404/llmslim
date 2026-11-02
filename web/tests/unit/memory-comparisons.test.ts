import { describe, expect, it } from "vitest"
import { MEMORY_COMPARISONS, PRICES_CHECKED, llmslimPriceRows } from "@/data/memory-comparisons"
import { PLANS } from "@/data/pricing"
import { llmsTxt, markdownFor, markdownPaths } from "@/lib/agent-content"

const pages = Object.values(MEMORY_COMPARISONS)

/** "+0.8 (−0.9, +2.5)" -> [0.8, -0.9, 2.5]; the pages print minus signs as U+2212. */
function interval(difference: string): [number, number, number] {
  const numbers = difference.replace(/−/g, "-").match(/[-+]?\d+(?:\.\d+)?/g)!.map(Number)
  expect(numbers, difference).toHaveLength(3)
  return numbers as [number, number, number]
}

describe("memory comparisons", () => {
  it("are /compare/mem0 and /compare/zep", () => {
    expect(Object.keys(MEMORY_COMPARISONS).sort()).toEqual(["mem0", "zep"])
    for (const [slug, page] of Object.entries(MEMORY_COMPARISONS)) expect(page.slug).toBe(slug)
  })

  it("read every paired difference by its interval: level when it includes zero", () => {
    for (const page of pages) {
      for (const block of page.benchmarks) {
        expect(block.pairedDiffs.length, `${page.slug}/${block.id}`).toBeGreaterThan(0)
        for (const row of block.pairedDiffs) {
          const [point, low, high] = interval(row.difference)
          const where = `${page.slug}: ${row.comparison}, ${row.benchmark}`
          expect(low <= point && point <= high, where).toBe(true)
          expect(row.reading, where).toBe(low > 0 ? "Ahead" : high < 0 ? "Behind" : "Level")
        }
      }
    }
  })

  it("print each score with its interval, and the score inside it", () => {
    for (const page of pages) {
      for (const table of page.benchmarks.flatMap((block) => block.tables)) {
        for (const row of table.rows) {
          const match = row.score.match(/^(\d+\.\d) \((\d+\.\d)–(\d+\.\d)\)$/)
          expect(match, `${page.slug}: ${row.system} ${row.score}`).not.toBeNull()
          const [score, low, high] = match!.slice(1).map(Number)
          expect(low <= score && score <= high, `${page.slug}: ${row.system}`).toBe(true)
          expect(row.cost, `${page.slug}: ${row.system}`).toMatch(/^\$\d[\d,]*\.\d\d$/)
        }
      }
    }
  })

  it("date the competitors' prices and show Orbit's from the pricing data", () => {
    for (const page of pages) {
      expect(page.meta.join(" ")).toContain(`Prices checked ${PRICES_CHECKED}`)
      expect(page.pricing.rival.url).toMatch(/^https:\/\//)
      expect(page.pricing.notes.join(" ")).toContain("opens with LLMSlim 1.0")
    }
    const rows = llmslimPriceRows()
    expect(rows).toHaveLength(PLANS.length + 1)
    expect(rows[0].plan).toBe("Core")
    expect(rows.find((row) => row.plan === "Orbit Pro")?.price).toContain("$19 a month")
  })

  it("are served as Markdown and listed for agents", () => {
    const paths = markdownPaths().map((path) => path.join("/"))
    const llms = llmsTxt()
    for (const page of pages) {
      expect(paths).toContain(`compare/${page.slug}`)
      const text = markdownFor(["compare", page.slug])!
      expect(text).toContain(`# ${page.title}`)
      expect(text).toContain(`## Pricing (checked ${PRICES_CHECKED})`)
      expect(text).toContain("## Migrate")
      expect(llms).toContain(`https://www.llmslim.app/compare/${page.slug}.md`)
    }
  })
})
