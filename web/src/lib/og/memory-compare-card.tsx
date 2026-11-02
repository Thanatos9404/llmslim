import { ImageResponse } from "next/og"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { MARK_BOX, MARK_GRADIENT_X, MARK_ORDER, MARK_PALETTES, MARK_STRANDS } from "@/components/brand/mark-data"
import { MEMORY_COMPARISONS, type MemoryComparison } from "@/data/memory-comparisons"

/**
 * The share card for /compare/mem0 and /compare/zep, in the design of the benchmark card (src/lib/og/benchmark-card.tsx):
 * round 3's LoCoMo results at about 2,500 tokens, LLMSlim against one memory system, with what 1,000 questions cost.
 * Every number is read from the page's own data (src/data/memory-comparisons.ts), so the card can't disagree with the
 * page. The headline follows the page's wording rule: "level" when the paired 95% interval includes zero.
 */

export const memoryCardSize = { width: 1200, height: 630 }

type CardCopy = { rivalRow: string; headline: [string, string]; footnote: string }

const COPY: Record<string, CardCopy> = {
  mem0: {
    rivalRow: "Mem0, top 50 memories",
    headline: ["Level with Mem0.", "At a third of the cost."],
    footnote: "Reader: Claude Haiku 5.5. 1,307 held-out LoCoMo questions at about 2,500 tokens, LLMSlim Core 0.9.0 (round 3). Costs include the model calls that build Mem0's memory.",
  },
  zep: {
    rivalRow: "Zep (Graphiti on Neo4j)",
    headline: ["Ahead of Zep.", "Same reader, same questions."],
    footnote: "Reader: Claude Haiku 5.5. 1,307 held-out LoCoMo questions at about 2,500 tokens, LLMSlim Core 0.9.0 (round 3). Zep is Graphiti 0.30.2, its open-source framework. Costs include building its graph.",
  },
}

type Bar = { name: string; note: string; score: number; fill: string; value: string; reference?: boolean }

const percent = (score: number) => `${score.toFixed(1)}%`
const dollars = (cost: number) => `$${cost.toFixed(2)}`

/** LoCoMo at about 2,500 tokens, from the page's round 3 table. */
function locomo(page: MemoryComparison) {
  const rows = page.benchmarks.find((block) => block.id === "round3")!.tables[0].rows
  const pick = (system: string, tokens?: string) => {
    const row = rows.find((item) => item.system === system && (!tokens || item.tokens === tokens))
    if (!row) throw new Error(`memory card: no "${system}" row on /compare/${page.slug}`)
    return { score: Number.parseFloat(row.score), cost: Number.parseFloat(row.cost.replace("$", "")) }
  }
  return {
    reranker: pick("LLMSlim 0.9 + reranker", "2,495"),
    plain: pick("LLMSlim 0.9", "2,492"),
    rival: pick(COPY[page.slug].rivalRow),
    full: pick("Full history, read from the prompt cache"),
  }
}

export function memoryCardAlt(slug: string): string {
  const page = MEMORY_COMPARISONS[slug]
  const data = locomo(page)
  return `LoCoMo, 1,307 held-out questions at about 2,500 tokens, read by Claude Haiku 5.5: LLMSlim 0.9 with its 22M reranker ` +
    `${percent(data.reranker.score)} for ${dollars(data.reranker.cost)} per 1,000 questions, LLMSlim 0.9 with no model ${percent(data.plain.score)} ` +
    `for ${dollars(data.plain.cost)}, ${COPY[slug].rivalRow} ${percent(data.rival.score)} for ${dollars(data.rival.cost)}; the whole history ${percent(data.full.score)}.`
}

// The site's dark theme tokens (src/app/globals.css, .dark), as in the benchmark card.
const C = {
  surface: "#0b0b0a",
  ink: "#ededea",
  inkDim: "#b4b3ae",
  subtle: "#8f8e89",
  line: "#252523",
  track: "#171716",
  brand: "#00f59b",
  brandDim: "rgba(0,245,155,0.55)",
  rival: "#5d5c58",
}

const fontDir = join(process.cwd(), "assets/og")
const fonts = Promise.all([
  readFile(join(fontDir, "Geist-Regular.ttf")),
  readFile(join(fontDir, "Geist-SemiBold.ttf")),
  readFile(join(fontDir, "GeistMono-Medium.ttf")),
  readFile(join(fontDir, "InstrumentSerif-Italic.ttf")),
]).then(([regular, semibold, mono, serif]) => [
  { name: "Geist", data: regular, weight: 400 as const, style: "normal" as const },
  { name: "Geist", data: semibold, weight: 600 as const, style: "normal" as const },
  { name: "Geist Mono", data: mono, weight: 500 as const, style: "normal" as const },
  { name: "Instrument Serif", data: serif, weight: 400 as const, style: "italic" as const },
])

/** The LLMSlim mark in the dark palette. Plain SVG with fixed gradient ids: the image renderer has no React hooks. */
function Mark({ size }: { size: number }) {
  const pal = MARK_PALETTES.dark
  return <svg width={(size * MARK_BOX.width) / MARK_BOX.height} height={size} viewBox={`${MARK_BOX.x} ${MARK_BOX.y} ${MARK_BOX.width} ${MARK_BOX.height}`}>
    <defs>
      {MARK_STRANDS.map((strand, i) => <linearGradient key={i} id={`og-cmp-mark-${i}`} gradientUnits="userSpaceOnUse" x1={MARK_GRADIENT_X.from} y1={0} x2={MARK_GRADIENT_X.to} y2={0}>
        <stop offset={strand.o1} stopColor={pal.left[i]} /><stop offset={strand.o2} stopColor={pal.right[i]} /><stop offset={1} stopColor={pal.end[i]} />
      </linearGradient>)}
    </defs>
    {MARK_ORDER.map((i) => <path key={i} d={MARK_STRANDS[i].d} fill={`url(#og-cmp-mark-${i})`} />)}
  </svg>
}

function BarRow({ bar }: { bar: Bar }) {
  return <div style={{ display: "flex", flexDirection: "column", marginTop: bar.reference ? 26 : 0 }}>
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
      <div style={{ display: "flex", alignItems: "baseline" }}>
        <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: -0.4, color: bar.reference ? C.inkDim : C.ink }}>{bar.name}</span>
        <span style={{ marginLeft: 10, fontSize: 17, color: C.subtle }}>{bar.note}</span>
      </div>
      <span style={{ fontFamily: "Geist Mono", fontSize: 25, fontWeight: 500, letterSpacing: -0.5, color: bar.value }}>{percent(bar.score)}</span>
    </div>
    <div style={{ display: "flex", marginTop: 9, height: 20, borderRadius: 5, backgroundColor: C.track }}>
      <div style={{ display: "flex", width: `${bar.score}%`, height: "100%", borderRadius: 5, backgroundColor: bar.fill, border: bar.reference ? "1.5px solid rgba(237,237,234,0.42)" : "none" }} />
    </div>
  </div>
}

export async function memoryCompareCard(slug: "mem0" | "zep") {
  const page = MEMORY_COMPARISONS[slug]
  const copy = COPY[slug]
  const data = locomo(page)
  const bars: Bar[] = [
    { name: "LLMSlim 0.9 + reranker", note: `${dollars(data.reranker.cost)} per 1k`, score: data.reranker.score, fill: C.brand, value: C.brand },
    { name: "LLMSlim 0.9, no model", note: `${dollars(data.plain.cost)} per 1k`, score: data.plain.score, fill: C.brandDim, value: C.brand },
    { name: page.rival, note: `${dollars(data.rival.cost)} per 1k`, score: data.rival.score, fill: C.rival, value: C.ink },
    { name: "Whole history", note: "every token, for reference", score: data.full.score, fill: "rgba(237,237,234,0.10)", value: C.inkDim, reference: true },
  ]
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%", padding: "52px 64px 44px", backgroundColor: C.surface, backgroundImage: "radial-gradient(circle at 92% 0%, rgba(124,92,255,0.18) 0%, rgba(124,92,255,0) 46%)", color: C.ink, fontFamily: "Geist" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <Mark size={34} />
          <div style={{ display: "flex", marginLeft: 12, fontSize: 28, fontWeight: 600 }}>LLM<span style={{ color: C.brand }}>Slim</span></div>
        </div>
        <span style={{ fontFamily: "Geist Mono", fontSize: 17, fontWeight: 500, color: C.subtle }}>llmslim.app/compare/{slug}</span>
      </div>

      <div style={{ display: "flex", flex: 1, alignItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", width: 440, marginRight: 60 }}>
          <div style={{ display: "flex", alignItems: "center", fontSize: 18, color: C.subtle }}>
            <div style={{ display: "flex", width: 8, height: 8, marginRight: 10, backgroundColor: C.brand }} />
            LoCoMo, long conversations
          </div>
          <div style={{ display: "flex", marginTop: 18, fontSize: 54, fontWeight: 600, lineHeight: 1.04, letterSpacing: -2.2 }}>{copy.headline[0]}</div>
          <div style={{ display: "flex", marginTop: 4, fontFamily: "Instrument Serif", fontStyle: "italic", fontSize: 62, lineHeight: 1.05, letterSpacing: -1, color: C.inkDim }}>{copy.headline[1]}</div>
          <div style={{ display: "flex", marginTop: 22, fontSize: 19, color: C.subtle }}>Cost of 1,000 questions, end to end</div>
          <div style={{ display: "flex", alignItems: "baseline", marginTop: 6, fontFamily: "Geist Mono", fontSize: 22, fontWeight: 500 }}>
            <span style={{ color: C.brand }}>{dollars(data.reranker.cost)}</span>
            <span style={{ marginLeft: 12, fontFamily: "Geist", fontSize: 19, color: C.subtle }}>against</span>
            <span style={{ marginLeft: 12, color: C.ink }}>{dollars(data.rival.cost)}</span>
            <span style={{ marginLeft: 10, fontFamily: "Geist", fontSize: 19, color: C.subtle }}>for {page.rival}</span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
          {bars.map((bar, index) => <div key={bar.name} style={{ display: "flex", flexDirection: "column", marginTop: index === 0 ? 0 : 20 }}><BarRow bar={bar} /></div>)}
        </div>
      </div>

      <div style={{ display: "flex", paddingTop: 18, borderTop: `1px solid ${C.line}`, fontSize: 17, lineHeight: 1.45, color: C.subtle }}>
        {copy.footnote}
      </div>
    </div>,
    { ...memoryCardSize, fonts: await fonts },
  )
}
