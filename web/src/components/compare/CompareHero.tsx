import type { ReactNode } from "react"
import { GlyphStage } from "@/components/brand/GlyphStage"
import { LogoMark } from "@/components/brand/LogoMark"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { ProductLogo } from "@/components/brand/ProductLogo"
import type { ProductLogoKey } from "@/components/brand/product-logos"
import { ParallaxPhoto } from "@/components/site/ParallaxPhoto"

type CompareHeroProps = {
  kicker: string
  heading: readonly [string, string]
  lede: ReactNode
  meta: string[]
  disclosure: string
  /** The other product, as the versus lockup shows it. */
  rival: { name: string; logo: ProductLogoKey; wordmark?: boolean }
  photo: { src: string; position?: string }
}

/** Small logos for the meta line: the reader model's maker, where the line names it. */
const metaLogo = (item: string): ProductLogoKey | undefined => (/\bClaude\b/.test(item) ? "claude" : undefined)

/**
 * The comparison hero: the headline at display size, then the lede and its facts beside a plate where the memory glyph
 * plays over a photo, under the two products' logos. The plate is always dark, like a screen, in both themes.
 */
export function CompareHero({ kicker, heading, lede, meta, disclosure, rival, photo }: CompareHeroProps) {
  return <header className="cmp-hero">
    <p className="p-kicker cmp-kicker"><MemoryGlyph size={14} />{kicker}</p>
    <h1 className="cmp-title">{heading[0]} <span>{heading[1]}</span></h1>
    <div className="cmp-hero-grid">
      <div className="cmp-hero-copy">
        <p className="cmp-lede">{lede}</p>
        <ul className="cmp-facts" aria-label="About this comparison">
          {meta.map((item) => {
            const logo = metaLogo(item)
            return <li key={item}>{logo && <ProductLogo logo={logo} size={14} />}{item}</li>
          })}
        </ul>
        <p className="cmp-disclosure">{disclosure}</p>
      </div>
      <div className="cmp-plate on-dark" aria-hidden="true">
        <ParallaxPhoto src={photo.src} position={photo.position} sizes="(max-width: 900px) 100vw, 520px" eager />
        <div className="cmp-plate-veil" />
        <GlyphStage />
        <div className="cmp-versus">
          <span className="cmp-versus-us"><LogoMark size={20} /><span>LLMSlim</span></span>
          <span className="cmp-versus-vs">vs</span>
          <span className="cmp-versus-them">
            <ProductLogo logo={rival.logo} size={rival.wordmark ? 22 : 26} />
            {!rival.wordmark && <span>{rival.name}</span>}
          </span>
        </div>
      </div>
    </div>
  </header>
}
