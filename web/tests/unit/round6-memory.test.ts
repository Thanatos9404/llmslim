import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"
import { MEM0_COMPARISON, ZEP_COMPARISON, type MemoryComparison } from "@/data/memory-comparisons"
import {
  ROUND6_ARMS, ROUND6_BELOW_ZEP, ROUND6_COST_MULTIPLES, ROUND6_DIFFS, ROUND6_FIGURES, ROUND6_WEAK_SPOTS_VS_MEM0, type Round6Diff,
} from "@/data/round6-memory"
import { markdownFor } from "@/lib/agent-content"

/**
 * The round-6 numbers on /compare/mem0 and /compare/zep are copied from the published report, so every one is checked
 * here against benchmarks/live/round6/summary.json, the report's machine-readable twin, to the precision printed.
 */

type Json = Record<string, unknown>
const summary = JSON.parse(readFileSync(fileURLToPath(new URL("../../../benchmarks/live/round6/summary.json", import.meta.url)), "utf8")) as Json

const at = (path: string): unknown => path.split(".").reduce<unknown>((node, key) => (node as Json | undefined)?.[key], summary)
const number = (path: string): number => {
  const value = at(path)
  expect(typeof value, path).toBe("number")
  return value as number
}

/** A printed value rounds the published one: within half a unit of its last printed digit. */
const rounds = (printed: number, path: string, decimals: number) =>
  expect(Math.abs(printed - number(path)), `${path}: ${printed}`).toBeLessThanOrEqual(0.5 * 10 ** -decimals + 1e-9)

const diffPath = (diff: Round6Diff) => (diff.type ? `comparisons.${diff.key}.per_type.${diff.type}` : `comparisons.${diff.key}.difference`)
const decimalsOf = (value: number) => (String(value).split(".")[1] ?? "").length

describe("round 6 numbers on the memory comparison pages", () => {
  it("match summary.json for every arm: tokens, score with its interval, and cost", () => {
    for (const arms of Object.values(ROUND6_ARMS)) {
      for (const arm of Object.values(arms)) {
        const base = `subsets.${arm.subset}.arms.${arm.arm}`
        rounds(arm.tokens, `${base}.context_tokens_cl100k`, 0)
        rounds(arm.score, `${base}.score.mean`, 1)
        rounds(arm.low, `${base}.score.lo`, 1)
        rounds(arm.high, `${base}.score.hi`, 1)
        rounds(arm.cost, `${base}.cost_per_1000_questions_usd.total`, 2)
      }
    }
  })

  it("match summary.json for every paired difference and its intervals", () => {
    for (const diff of Object.values(ROUND6_DIFFS)) {
      rounds(diff.mean, `${diffPath(diff)}.mean`, 1)
      rounds(diff.low, `${diffPath(diff)}.lo`, 1)
      rounds(diff.high, `${diffPath(diff)}.hi`, 1)
      rounds(diff.bootstrapLow, `comparisons.${diff.key}.bootstrap_lo`, 1)
      rounds(diff.bootstrapHigh, `comparisons.${diff.key}.bootstrap_hi`, 1)
    }
    for (const diff of [...ROUND6_WEAK_SPOTS_VS_MEM0, ...ROUND6_BELOW_ZEP]) {
      rounds(diff.mean, `${diffPath(diff)}.mean`, 1)
      rounds(diff.low, `${diffPath(diff)}.lo`, 1)
      rounds(diff.high, `${diffPath(diff)}.hi`, 1)
    }
  })

  it("compare the same arms summary.json compares", () => {
    const pairs: Record<string, [string, string, string]> = {
      M2500: ["llmslim_fix_2500", "mem0_top50", "all"], M10000: ["llmslim_fix_10000", "mem0_top200", "all"],
      Z2500: ["llmslim_fix_2500", "zep", "zep"], Z10000: ["llmslim_fix_10000", "zep", "zep"],
    }
    for (const [key, [a, b, subset]] of Object.entries(pairs)) {
      expect(at(`comparisons.${key}.a`)).toBe(a)
      expect(at(`comparisons.${key}.b`)).toBe(b)
      expect(at(`comparisons.${key}.subset`)).toBe(subset)
    }
  })

  it("list exactly the weak spots summary.json lists against Mem0", () => {
    const published = (at("weak_spots_vs_mem0") as { type: string; budget_tokens: number }[]).map((spot) => `${spot.type}@${spot.budget_tokens}`).sort()
    const shown = ROUND6_WEAK_SPOTS_VS_MEM0.map((diff) => `${diff.type}@${diff.key === "M2500" ? 2500 : 10000}`).sort()
    expect(shown).toEqual(published)
  })

  it("list every question type below Zep, and none is more than 3 points behind", () => {
    const below = (["Z2500", "Z10000"] as const).flatMap((key) =>
      Object.entries(at(`comparisons.${key}.per_type`) as Record<string, { mean: number }>).filter(([, value]) => value.mean < 0).map(([type, value]) => ({ key, type, mean: value.mean })))
    expect(below.map(({ key, type }) => `${type}@${key}`)).toEqual(ROUND6_BELOW_ZEP.map((diff) => `${diff.type}@${diff.key}`))
    for (const { mean } of below) expect(mean).toBeGreaterThan(-3)
  })

  it("match summary.json for every other figure the prose quotes", () => {
    for (const figure of Object.values(ROUND6_FIGURES)) rounds(figure.value, figure.path, decimalsOf(figure.value))
  })

  it("state the cost multiples the report states, which the totals bear out", () => {
    const ratio = (rival: string, ours: string) => number(`subsets.all.arms.${rival}.cost_per_1000_questions_usd.total`) / number(`subsets.all.arms.${ours}.cost_per_1000_questions_usd.total`)
    expect(ratio("mem0_top50", "llmslim_fix_2500").toFixed(1)).toBe("60.0")
    expect(ROUND6_COST_MULTIPLES.at2500).toBe("60x")
    expect(ratio("mem0_top200", "llmslim_fix_10000").toFixed(1)).toBe("28.6")
    expect(ROUND6_COST_MULTIPLES.at10000).toBe("28.6x")
  })
})

/** Every string on a page except its FAQ questions (one asks "Is LLMSlim better than Mem0?"). */
function pageText(page: MemoryComparison): string {
  return JSON.stringify({ ...page, faqs: page.faqs.map(([, answer]) => answer) })
}

describe("round 6 on the memory comparison pages", () => {
  it("leads each page as the latest round, with round 3 kept below it as the earlier one", () => {
    for (const page of [MEM0_COMPARISON, ZEP_COMPARISON]) {
      expect(page.benchmarks.map((block) => [block.id, block.status])).toEqual([["round6", "latest"], ["round3", "earlier"]])
      expect(page.meta.join(" ")).toContain("Latest results: LLMSlim 0.12, round 6 (BEAM-1M)")
      expect(page.benchmarks[1].context).toMatch(/^The earlier round, on different benchmarks/)
    }
  })

  it("call Mem0 on par, never beaten, and Zep's lead only on its 30 conversations", () => {
    const mem0 = pageText(MEM0_COMPARISON)
    expect(mem0).toContain("On par with Mem0")
    expect(mem0).not.toMatch(/\b(?:beats|outperforms?|outperformed|better than) Mem0\b/i)
    const zep = pageText(ZEP_COMPARISON)
    expect(zep).toContain("Ahead of Zep, on its 30 conversations")
    expect(MEM0_COMPARISON.benchmarks[0].pairedDiffs.map((row) => row.reading)).toEqual(["Level", "Level"])
    expect(ZEP_COMPARISON.benchmarks[0].pairedDiffs.map((row) => row.reading)).toEqual(["Ahead", "Ahead"])
  })

  it("show the weak spots on both pages", () => {
    for (const page of [MEM0_COMPARISON, ZEP_COMPARISON]) {
      const rows = page.benchmarks[0].weakSpots!.rows.map((row) => row.comparison).join(" | ")
      for (const type of ["Summarization", "Multi-session reasoning", "Information extraction"]) expect(rows, page.slug).toContain(type)
    }
  })

  it("quote no latency figure and no earlier unpublished round", () => {
    for (const page of [MEM0_COMPARISON, ZEP_COMPARISON]) {
      const round6 = JSON.stringify(page.benchmarks[0])
      expect(round6).not.toMatch(/\d(?:\.\d+)? ?(?:s|ms|seconds)\b/)
      expect(round6).not.toMatch(/latency/i)
      expect(pageText(page)).not.toMatch(/round 5|round-5/i)
    }
  })

  it("render in the Markdown twins", () => {
    const mem0 = markdownFor(["compare", "mem0"])!
    expect(mem0).toContain("## Latest results: Round 6 · LLMSlim 0.12")
    expect(mem0).toContain("| 2,500-token budget | LLMSlim 0.12 + reranker | 2,436 | 44.6 (41.9–47.3) | $1.22 |")
    expect(mem0).toContain("### Where LLMSlim trails Mem0, by question type")
    expect(mem0).toContain("## Earlier round: Round 3 · LLMSlim Core 0.9.0")
    expect(mem0.indexOf("## Latest results")).toBeLessThan(mem0.indexOf("## Earlier round"))
    const zep = markdownFor(["compare", "zep"])!
    expect(zep).toContain("| Zep: 20 facts and 20 entities | Zep (Graphiti 0.30.2 on Neo4j) | 3,397 | 38.4 (35.6–41.2) | $330.07 |")
    expect(zep).toContain("+7.5 (+4.5, +10.4)")
  })
})
