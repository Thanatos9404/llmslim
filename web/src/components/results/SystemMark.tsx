import { LogoMark } from "@/components/brand/LogoMark"
import { ProductLogo } from "@/components/brand/ProductLogo"
import { logoForSystem } from "@/components/brand/product-logos"

/**
 * The logo for a results row, from the system its name starts with (`logoForSystem`): LLMSlim's mark, or the other
 * product's logo (public/logos/SOURCES.md), and a neutral pixel for a baseline such as the full context. Decoration
 * only: the name is always written beside it. Styled by `.sys-mark` in results/story.css and globals.css (/benchmarks).
 */
export function SystemMark({ name, size = 16 }: { name: string; size?: number }) {
  const logo = logoForSystem(name)
  return <span className="sys-mark" aria-hidden="true" style={{ width: size + 2, height: size + 2 }}>
    {logo === "llmslim" ? <LogoMark size={Math.round(size * 0.6)} />
      : logo ? <ProductLogo logo={logo} size={size} />
      : <span className="sys-mark-dot" />}
  </span>
}
