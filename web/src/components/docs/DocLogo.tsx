import type { CSSProperties } from "react"
import { PRODUCT_LOGOS, type ProductLogoKey, type ProductLogoSpec } from "@/components/brand/product-logos"

/**
 * A product's logo for the docs (public/logos/SOURCES.md): the same files and colours as ProductLogo, drawn without
 * next/image. On the docs overview every next/image instance hydrated as a client component and pulled the image
 * script into the page, which cost the phone score more than the logos are worth; a 13 to 15px self-hosted SVG needs
 * no responsive sizes. Decoration only (the name is written beside it), so it is hidden from assistive technology.
 */
export function DocLogo({ logo, size = 14, className = "" }: { logo: ProductLogoKey; size?: number; className?: string }) {
  const spec: ProductLogoSpec = PRODUCT_LOGOS[logo]
  const width = Math.round(size * (spec.ratio ?? 1))
  if (spec.kind === "mask") {
    const style = {
      "--logo": `url(${spec.src})`,
      ...(spec.color ? { "--logo-c": spec.color } : {}),
      ...(spec.colorDark ? { "--logo-cd": spec.colorDark } : {}),
      width, height: size,
    } as CSSProperties
    return <span className={`plogo plogo-mask ${className}`} style={style} aria-hidden="true" />
  }
  // eslint-disable-next-line @next/next/no-img-element -- see above: a tiny self-hosted logo, no next/image
  return <img src={spec.src} width={width} height={size} alt="" aria-hidden="true" loading="lazy" decoding="async" className={`plogo plogo-img ${className}`} />
}
