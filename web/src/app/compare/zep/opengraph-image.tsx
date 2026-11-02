import { memoryCardAlt, memoryCardSize, memoryCompareCard } from "@/lib/og/memory-compare-card"

// Open Graph image for /compare/zep: LoCoMo, LLMSlim against Zep (src/lib/og/memory-compare-card.tsx).
// Generated at build time. The page leaves `images` out of its metadata so this file is used.
export const alt = memoryCardAlt("zep")
export const size = memoryCardSize
export const contentType = "image/png"

export default function Image() {
  return memoryCompareCard("zep")
}
