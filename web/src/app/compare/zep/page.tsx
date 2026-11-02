import { MemoryComparisonPage, memoryComparisonMetadata } from "@/components/compare/MemoryComparisonPage"
import { ZEP_COMPARISON } from "@/data/memory-comparisons"

export const metadata = memoryComparisonMetadata(ZEP_COMPARISON)

export default function ZepComparisonPage() {
  return <MemoryComparisonPage page={ZEP_COMPARISON} />
}
