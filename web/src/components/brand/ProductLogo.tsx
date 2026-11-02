import Image from "next/image"
import type { CSSProperties } from "react"
import { PRODUCT_LOGOS, type ProductLogoKey, type ProductLogoSpec } from "./product-logos"

type ProductLogoProps = {
  logo: ProductLogoKey
  /** Height in pixels; wordmarks take their width from their ratio. */
  size?: number
  className?: string
  /** Give the logo the product's name as its accessible name. Leave it out when the name is written beside it. */
  labelled?: boolean
}

/** A product's logo, self-hosted (public/logos/SOURCES.md), to identify a product a page names. */
export function ProductLogo({ logo, size = 20, className = "", labelled = false }: ProductLogoProps) {
  const spec: ProductLogoSpec = PRODUCT_LOGOS[logo]
  const width = Math.round(size * (spec.ratio ?? 1))
  const a11y = labelled ? { role: "img", "aria-label": spec.name } : { "aria-hidden": true }
  if (spec.kind === "mask") {
    const style = {
      "--logo": `url(${spec.src})`,
      ...(spec.color ? { "--logo-c": spec.color } : {}),
      ...(spec.colorDark ? { "--logo-cd": spec.colorDark } : {}),
      width, height: size,
    } as CSSProperties
    return <span className={`plogo plogo-mask ${className}`} style={style} {...a11y} />
  }
  const alt = labelled ? spec.name : ""
  const image = (src: string, theme: string) => <Image key={src} src={src} width={width} height={size} alt={alt} unoptimized
    className={`plogo plogo-img ${theme} ${className}`} style={{ width, height: size }} />
  if (!spec.srcDark) return image(spec.src, "")
  return <>{image(spec.src, "art-light")}{image(spec.srcDark, "art-dark")}</>
}
