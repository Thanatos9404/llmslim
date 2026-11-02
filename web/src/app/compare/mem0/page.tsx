import { MemoryComparisonPage, memoryComparisonMetadata } from "@/components/compare/MemoryComparisonPage"
import { MEM0_COMPARISON } from "@/data/memory-comparisons"

export const metadata = memoryComparisonMetadata(MEM0_COMPARISON)

export default function Mem0ComparisonPage() {
  return <MemoryComparisonPage page={MEM0_COMPARISON} />
}
