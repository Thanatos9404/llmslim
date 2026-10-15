import { ImageResponse } from "next/og"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { RACE } from "@/data/results-story"

/**
 * The share card for /benchmarks, /results and /compare/llmlingua: round 3's LoCoMo head-to-head as bars, with what
 * 1,000 questions cost. Scores and costs come from RACE (src/data/results-story.ts), the same data the pages show.
 *
 * Fonts (assets/og) are static TTF instances of the site's own woff2 files in public/fonts (Geist 400/600,
 * Geist Mono 500, Instrument Serif italic; SIL OFL 1.1), made with fontTools: the image renderer cannot read
 * woff2 or variable fonts. Their GSUB and GPOS tables are removed because the renderer fails on GSUB
 * contextual lookups and mis-spaces words with these GPOS tables.
 */

export const benchmarkCardSize = { width: 1200, height: 630 }

const locomo = RACE.find((set) => set.key === "locomo")!
const row = (name: string) => locomo.rows.find((item) => item.name === name)!
const slim = row("LLMSlim + reranker")
const mem0 = row("Mem0")
const zep = row("Zep")
const longLingua = row("LongLLMLingua")

const percent = (score: number) => `${score.toFixed(1)}%`
const dollars = (cost: number) => `$${cost.toFixed(2)}`

export const benchmarkCardAlt =
  `LoCoMo, 1,307 held-out questions at about 2,500 tokens, read by Claude Haiku 5.5: ` +
  `LLMSlim 0.9 with its 22M reranker ${percent(slim.score)} for ${dollars(slim.cost)} per 1,000 questions, ` +
  `Mem0 ${percent(mem0.score)} for ${dollars(mem0.cost)}, Zep ${percent(zep.score)} for ${dollars(zep.cost)}, ` +
  `LongLLMLingua ${percent(longLingua.score)} on its 300-question sample; the whole history ${percent(locomo.full.score)}.`

// The site's dark theme tokens (src/app/globals.css, .dark).
const C = {
  surface: "#0b0b0a",
  ink: "#ededea",
  inkDim: "#b4b3ae",
  subtle: "#8f8e89",
  line: "#252523",
  track: "#171716",
  brand: "#ff7a3d",
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

type Bar = { name: string; model: string; score: number; fill: string; value: string; reference?: boolean }

const bars: Bar[] = [
  { name: "LLMSlim 0.9 + reranker", model: `${dollars(slim.cost)} per 1k`, score: slim.score, fill: C.brand, value: C.brand },
  { name: "Mem0", model: `${dollars(mem0.cost)} per 1k`, score: mem0.score, fill: C.rival, value: C.ink },
  { name: "Zep", model: `${dollars(zep.cost)} per 1k`, score: zep.score, fill: C.rival, value: C.ink },
  { name: "LongLLMLingua", model: `${dollars(longLingua.cost)} per 1k`, score: longLingua.score, fill: C.rival, value: C.ink },
  { name: "Whole history", model: "every token, for reference", score: locomo.full.score, fill: "rgba(237,237,234,0.10)", value: C.inkDim, reference: true },
]

/** The site's mark: five lines of context folding into three, with the kept lines in the accent. */
function Mark({ size }: { size: number }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" fill="none" strokeLinecap="round" strokeWidth="2.6">
    <path d="M4 7h8c5 0 5 6 10 6" stroke={C.ink} /><path d="M4 11.5h8c5 0 5 1.5 10 1.5" stroke={C.ink} /><path d="M4 16h18" stroke={C.ink} />
    <path d="M4 20.5h8c5 0 5-1.5 10-1.5" stroke={C.ink} /><path d="M4 25h8c5 0 5-6 10-6" stroke={C.ink} />
    <path d="M22 13h6" stroke={C.brand} /><path d="M22 16h6" stroke={C.brand} /><path d="M22 19h6" stroke={C.brand} />
  </svg>
}

function BarRow({ bar }: { bar: Bar }) {
  return <div style={{ display: "flex", flexDirection: "column", marginTop: bar.reference ? 26 : 0 }}>
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
      <div style={{ display: "flex", alignItems: "baseline" }}>
        <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: -0.4, color: bar.reference ? C.inkDim : C.ink }}>{bar.name}</span>
        <span style={{ marginLeft: 10, fontSize: 17, color: C.subtle }}>{bar.model}</span>
      </div>
      <span style={{ fontFamily: "Geist Mono", fontSize: 25, fontWeight: 500, letterSpacing: -0.5, color: bar.value }}>{percent(bar.score)}</span>
    </div>
    <div style={{ display: "flex", marginTop: 9, height: 20, borderRadius: 5, backgroundColor: C.track }}>
      <div style={{ display: "flex", width: `${bar.score}%`, height: "100%", borderRadius: 5, backgroundColor: bar.fill, border: bar.reference ? "1.5px solid rgba(237,237,234,0.42)" : "none" }} />
    </div>
  </div>
}

export async function benchmarkCard(path: "/benchmarks" | "/results" | "/compare/llmlingua") {
  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%", padding: "52px 64px 44px", backgroundColor: C.surface, backgroundImage: "radial-gradient(circle at 92% 0%, rgba(255,122,61,0.16) 0%, rgba(255,122,61,0) 46%)", color: C.ink, fontFamily: "Geist" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <Mark size={34} />
          <div style={{ display: "flex", marginLeft: 12, fontSize: 28, fontWeight: 600 }}>LLM<span style={{ fontWeight: 400 }}>Slim</span></div>
        </div>
        <span style={{ fontFamily: "Geist Mono", fontSize: 17, fontWeight: 500, color: C.subtle }}>llmslim.app{path}</span>
      </div>

      <div style={{ display: "flex", flex: 1, alignItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", width: 440, marginRight: 60 }}>
          <div style={{ display: "flex", alignItems: "center", fontSize: 18, color: C.subtle }}>
            <div style={{ display: "flex", width: 8, height: 8, marginRight: 10, backgroundColor: C.brand }} />
            LoCoMo, long conversations
          </div>
          <div style={{ display: "flex", marginTop: 18, fontSize: 54, fontWeight: 600, lineHeight: 1.04, letterSpacing: -2.2 }}>Ahead of Mem0 and Zep.</div>
          <div style={{ display: "flex", marginTop: 4, fontFamily: "Instrument Serif", fontStyle: "italic", fontSize: 62, lineHeight: 1.05, letterSpacing: -1, color: C.inkDim }}>At a third of the cost.</div>
          <div style={{ display: "flex", marginTop: 22, fontSize: 19, color: C.subtle }}>Cost of 1,000 questions, end to end</div>
          <div style={{ display: "flex", alignItems: "baseline", marginTop: 6, fontFamily: "Geist Mono", fontSize: 22, fontWeight: 500 }}>
            <span style={{ color: C.brand }}>{dollars(slim.cost)}</span>
            <span style={{ marginLeft: 12, fontFamily: "Geist", fontSize: 19, color: C.subtle }}>against</span>
            <span style={{ marginLeft: 12, color: C.ink }}>{dollars(mem0.cost)}</span>
            <span style={{ marginLeft: 10, fontFamily: "Geist", fontSize: 19, color: C.subtle }}>for Mem0</span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
          {bars.map((bar, index) => <div key={bar.name} style={{ display: "flex", flexDirection: "column", marginTop: index === 0 ? 0 : 20 }}><BarRow bar={bar} /></div>)}
        </div>
      </div>

      <div style={{ display: "flex", paddingTop: 18, borderTop: `1px solid ${C.line}`, fontSize: 17, lineHeight: 1.45, color: C.subtle }}>
        Reader: Claude Haiku 5.5. 1,307 held-out questions at about 2,500 tokens (LongLLMLingua: its 300-question sample). Costs include the model calls that build Mem0&apos;s and Zep&apos;s memory.
      </div>
    </div>,
    { ...benchmarkCardSize, fonts: await fonts },
  )
}
