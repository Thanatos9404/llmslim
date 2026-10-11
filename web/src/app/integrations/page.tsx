import Link from "next/link"
import { ArrowUpRight } from "lucide-react"
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon"
import { constructMetadata } from "@/lib/seo"
import { INTEGRATIONS_REGISTRY, INTEGRATION_CATEGORIES } from "@/data/integrations"

export const metadata = constructMetadata({ title: "Python Integrations | LLMSlim", description: "Use LLMSlim output with documented Python model-client examples.", path: "/integrations", markdownPath: "/integrations.md" })

export default function IntegrationsIndexPage() {
  const integrations = Object.values(INTEGRATIONS_REGISTRY)
  return <div className="int-page">
    <header className="int-hero">
      <p className="p-kicker">Python integrations</p>
      <h1>Output that fits <span>your existing stack.</span></h1>
      <p>Pass LLMSlim output straight into the model client you already use. Provider calls stay in your application.</p>
    </header>
    {INTEGRATION_CATEGORIES.map((category) => {
      const entries = integrations.filter((item) => item.category === category)
      return entries.length ? <section key={category} className="int-group" aria-label={category}>
        <h2>{category}</h2>
        <ul className="int-list">{entries.map((item) => <li key={item.slug}>
          <Link className="int-row" href={`/integrations/${item.slug}`}>
            <span className="int-icon"><IntegrationIcon iconKey={item.iconKey} className="size-6" /></span>
            <span className="int-name">{item.name}<small>{item.badgeText}</small></span>
            <span className="int-tagline">{item.tagline}</span>
            <ArrowUpRight className="int-arrow" size={18} aria-hidden="true" />
          </Link>
        </li>)}</ul>
      </section> : null
    })}
  </div>
}
