import Link from "next/link"
import { ArrowUpRight } from "lucide-react"
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon"
import { ProductLogo } from "@/components/brand/ProductLogo"
import { INTEGRATION_LOGOS } from "@/components/brand/product-logos"

export type IntegrationRow = { slug: string; name: string; badgeText: string; tagline: string; iconKey: string }

/**
 * One group of integration rows, server-rendered. Pointing at a row lifts and tilts its logo tile with a spring
 * curve and nudges the arrow (CSS, integrations.css), and the row's glow follows the pointer (glow-card). The springs
 * that need Framer Motion are on the stage's logos, where there are ten instead of eighteen rows' worth.
 */
export function IntegrationRows({ items }: { items: IntegrationRow[] }) {
  return <ul className="int-list int-rows">{items.map((item) => {
    const logo = INTEGRATION_LOGOS[item.slug]
    return <li key={item.slug}>
      <Link className="int-row glow-card" href={`/integrations/${item.slug}`}>
        <span className="int-icon">
          {logo ? <ProductLogo logo={logo} size={26} /> : <IntegrationIcon iconKey={item.iconKey} className="size-6" />}
        </span>
        <span className="int-name">{item.name}<small>{item.badgeText}</small></span>
        <span className="int-tagline">{item.tagline}</span>
        <span className="int-arrow-wrap" aria-hidden="true"><ArrowUpRight className="int-arrow" size={18} /></span>
      </Link>
    </li>
  })}</ul>
}
