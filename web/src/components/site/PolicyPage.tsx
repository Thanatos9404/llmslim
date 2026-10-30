import type { ReactNode } from "react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { siteConfig } from "@/config/site"

/** The company and policy pages (About, Contact, Terms, Privacy, Refunds, Delivery): one narrow column of plain text. */
export function PolicyPage({ title, lede, updated = siteConfig.policiesUpdated, children }: { title: string; lede?: ReactNode; updated?: string; children: ReactNode }) {
  return <div className="slim-site"><SiteHeader /><main id="main-content" className="site-width policy-page">
    <p className="policy-updated">Last updated: {updated}</p>
    <h1>{title}</h1>
    {lede && <p className="policy-lede">{lede}</p>}
    {children}
  </main><SiteFooter /></div>
}

/** A mailto link that shows the address. */
export function Email({ to }: { to: string }) {
  return <a href={`mailto:${to}`}>{to}</a>
}
