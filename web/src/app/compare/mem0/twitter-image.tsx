import { memoryCardAlt, memoryCardSize, memoryCompareCard } from "@/lib/og/memory-compare-card"

// Twitter image for /compare/mem0: LoCoMo, LLMSlim against Mem0 (src/lib/og/memory-compare-card.tsx).
// Generated at build time. The page leaves `images` out of its metadata so this file is used.
export const alt = memoryCardAlt("mem0")
export const size = memoryCardSize
export const contentType = "image/png"

export default function Image() {
  return memoryCompareCard("mem0")
}
