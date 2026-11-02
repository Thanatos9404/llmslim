import type { ReactNode } from "react"
import { LogoMark } from "@/components/brand/LogoMark"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { ProductLogo } from "@/components/brand/ProductLogo"
import { productsNamedIn, PRODUCT_LOGOS, type ProductLogoKey } from "@/components/brand/product-logos"
import { Reveal } from "@/components/motion/Reveal"

/** A section's kicker and two-tone heading, rising into view, with the memory glyph lighting up beside the kicker. */
export function SectionHead({ kicker, id, heading, children }: { kicker: string; id: string; heading: readonly [string, string]; children?: ReactNode }) {
  return <Reveal className="p-head cmp-head">
    <p className="p-kicker cmp-kicker"><MemoryGlyph size={14} animate />{kicker}</p>
    <h2 id={id}>{heading[0]} <span>{heading[1]}</span></h2>
    {children}
  </Reveal>
}

/** Small logo chips for the products a sentence names (nominative: they only identify the product). */
export function NamedProducts({ text }: { text: string }) {
  const keys = productsNamedIn(text)
  if (keys.length === 0) return null
  return <ul className="cmp-chips" aria-label="Products named here">
    {keys.map((key) => <li key={key}><ProductLogo logo={key} size={14} />{PRODUCT_LOGOS[key].name}</li>)}
  </ul>
}

/** A column heading with the product's logo: LLMSlim's mark, or the other product's. */
export function ProductHeading({ name, logo }: { name: string; logo: ProductLogoKey | "llmslim" }) {
  return <span className="cmp-th-product">
    {logo === "llmslim" ? <LogoMark size={11} /> : <ProductLogo logo={logo} size={16} />}
    {name}
  </span>
}
