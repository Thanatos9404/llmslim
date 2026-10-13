import { benchmarkCard, benchmarkCardAlt, benchmarkCardSize } from "@/lib/og/benchmark-card"

// Twitter image for /compare/llmlingua: the NaturalQuestions head-to-head (src/lib/og/benchmark-card.tsx).
// Generated at build time. The page leaves `images` out of its metadata so this file is used.
export const alt = benchmarkCardAlt
export const size = benchmarkCardSize
export const contentType = "image/png"

export default function Image() {
  return benchmarkCard("/compare/llmlingua")
}
