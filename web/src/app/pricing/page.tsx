import Link from "next/link"
import { headers } from "next/headers"
import { ArrowRight, ArrowUpRight, Check } from "lucide-react"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { TrackedLink } from "@/components/site/TrackedLink"
import { siteConfig } from "@/config/site"
import {
  BILLINGS, CURRENCIES, CURRENCY_LABEL, FEATURE_MATRIX, LAUNCH_OFFERS, PLANS, PRICING_FAQS, formatPrice,
  type Billing, type Cell, type Currency, type Plan,
} from "@/data/pricing"
import { constructMetadata, faqJsonLd, jsonLdScript, orbitPricingJsonLd } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Pricing",
  description: "LLMSlim Core is free and MIT licensed, forever. LLMSlim Orbit, the hosted edition, opens with LLMSlim 1.0: Free, Pro, Team, Business and Enterprise plans in rupees (GST included) or dollars, with launch offers.",
  path: "/pricing",
  markdownPath: "/pricing.md",
})

type SearchParams = Promise<Record<string, string | string[] | undefined>>

function pick<T extends string>(value: string | string[] | undefined, options: readonly T[]): T | undefined {
  return typeof value === "string" && (options as readonly string[]).includes(value) ? (value as T) : undefined
}

/** Until checkout exists, every plan button opens an email to the founder, as the Vault beta form does. */
function mailto(subject: string, lines: string[]): string {
  return `mailto:${siteConfig.founderEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join("\n"))}`
}

function planMail(plan: Plan, currency: Currency, billing: Billing): string {
  if (plan.id === "enterprise") return mailto(`LLMSlim Enterprise (${CURRENCY_LABEL[currency]})`, [
    "Hi,", "", "I would like to talk about LLMSlim Enterprise.", "",
    "Company:", "Team size:", "What we need (limits, SSO, SLA, security review, Vault):", "",
  ])
  return mailto(`Founding list: LLMSlim Orbit ${plan.name} (${CURRENCY_LABEL[currency]}, ${billing})`, [
    "Hi,", "", "I would like to join the founding list for LLMSlim Orbit.", "",
    `Plan: ${plan.name}`, `Currency: ${CURRENCY_LABEL[currency]}`, `Billing: ${billing}`, "",
    "Name:", "Company or project:", "What I want to use LLMSlim for:", "",
  ])
}

const offerMail = mailto("LLMSlim launch offer", [
  "Hi,", "", "I would like to apply for an LLMSlim launch offer.", "",
  "Offer (startup / student / open-source maintainer):", "GitHub profile:", "Company or project, and how much it has raised (startups):", "",
])

function PriceLine({ plan, currency, billing }: { plan: Plan; currency: Currency; billing: Billing }) {
  if (!plan.prices) return <p className="pr-price"><span className="pr-amount">Custom</span></p>
  const amount = plan.prices[currency][billing]
  return <p className="pr-price">
    <span className="pr-amount">{formatPrice(amount, currency)}</span>
    <span className="pr-per">{amount > 0 && billing === "annual" ? "a year" : "a month"}</span>
  </p>
}

function priceNote(plan: Plan, currency: Currency, billing: Billing): string {
  if (!plan.prices) return "Limits, SLA and terms to fit"
  if (plan.prices[currency].monthly === 0) return currency === "inr" ? "No charge, no GST" : "No charge"
  const tax = currency === "inr" ? "Includes 18% GST" : "For customers outside India"
  return billing === "annual" ? `${tax} · 2 months free` : tax
}

function CellValue({ value }: { value: Cell }) {
  if (value === true) return <><Check size={16} aria-hidden="true" className="pr-yes" /><span className="sr-only">Included</span></>
  if (value === false) return <><span aria-hidden="true" className="pr-no">–</span><span className="sr-only">Not included</span></>
  return <>{value}</>
}

export default async function PricingPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams
  // Vercel sets the visitor's country on every request; rupees for India, dollars elsewhere, unless the visitor chose.
  const country = (await headers()).get("x-vercel-ip-country")
  const currency: Currency = pick(params.currency, CURRENCIES) ?? (country?.toUpperCase() === "IN" ? "inr" : "usd")
  const billing: Billing = pick(params.billing, BILLINGS) ?? "monthly"
  const href = (next: { currency?: Currency; billing?: Billing }) => `/pricing?currency=${next.currency ?? currency}&billing=${next.billing ?? billing}`
  const faqs = PRICING_FAQS.map((faq) => [faq.question, faq.answer] as const)

  return <div className="slim-site"><SiteHeader /><main id="main-content" className="pricing-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(faqJsonLd(faqs, "/pricing")) }} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(orbitPricingJsonLd()) }} />

    <header className="site-width pr-head">
      <p className="p-kicker">Pricing</p>
      <h1>Start free. <span>Pay when your agents grow.</span></h1>
      <p className="pr-lede">LLMSlim Core is free and open source, forever. LLMSlim Orbit, the hosted edition we run for you, opens with LLMSlim 1.0. These are its plans at launch: join the founding list, and we will email you when it opens.</p>
      <div className="pr-toggles">
        <div className="pr-toggle" role="group" aria-label="Currency">
          {CURRENCIES.map((option) => <Link key={option} href={href({ currency: option })} scroll={false} replace prefetch={false} rel="nofollow" aria-current={option === currency ? "true" : undefined}>
            {option === "inr" ? "₹ INR" : "$ USD"}
          </Link>)}
        </div>
        <div className="pr-toggle" role="group" aria-label="Billing period">
          {BILLINGS.map((option) => <Link key={option} href={href({ billing: option })} scroll={false} replace prefetch={false} rel="nofollow" aria-current={option === billing ? "true" : undefined}>
            {option === "monthly" ? "Monthly" : <>Annual <span className="pr-save">2 months free</span></>}
          </Link>)}
        </div>
      </div>
    </header>

    <section className="site-width pr-core" aria-labelledby="core-title">
      <div>
        <p className="pr-eyebrow">Open source · MIT licence</p>
        <h2 id="core-title">LLMSlim Core <span>Free forever</span></h2>
        <p>The Python library, MCP server and HTTP server. Self-host it with no account and no limits on projects, turns or searches.</p>
      </div>
      <div className="pr-core-actions">
        <code>pip install llmslim</code>
        <TrackedLink className="button button-outline" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "pricing" }}>Read the docs <ArrowRight size={16} /></TrackedLink>
      </div>
    </section>

    <section className="site-width pr-orbit" aria-labelledby="orbit-title">
      <div className="pr-orbit-head">
        <h2 id="orbit-title">LLMSlim Orbit</h2>
        <p className="pr-status"><span aria-hidden="true" />Opening with LLMSlim 1.0</p>
      </div>
      <p className="pr-orbit-sub">Hosted memory and remote MCP for your agents, run by us. Prices in {currency === "inr" ? "rupees, including 18% GST" : "US dollars, for customers outside India"}.</p>
      <ul className="pr-plans">
        {PLANS.map((plan) => <li key={plan.id} className="pr-plan">
          <h3>{plan.name}</h3>
          <p className="pr-summary">{plan.summary}</p>
          <PriceLine plan={plan} currency={currency} billing={billing} />
          <p className="pr-note">{priceNote(plan, currency, billing)}</p>
          <TrackedLink className={plan.id === "team" ? "button" : "button button-outline"} href={planMail(plan, currency, billing)} event="pricing_cta_clicked" properties={{ plan: plan.id, currency, billing }}>
            {plan.id === "enterprise" ? "Talk to us" : "Join the founding list"}
          </TrackedLink>
          <ul className="pr-limits">
            {plan.seats && <li><Check size={14} aria-hidden="true" />{plan.seats[currency]}</li>}
            {plan.limits.map((limit) => <li key={limit}><Check size={14} aria-hidden="true" />{limit}</li>)}
          </ul>
          {plan.id === "business" && currency === "inr" && billing === "monthly" && <p className="pr-mandate">Monthly debits above ₹15,000 need your approval each time (RBI e-mandate rules). Annual billing avoids this.</p>}
        </li>)}
      </ul>
      <p className="pr-fine">Nothing is charged before Orbit opens. Payments will be processed by Razorpay: UPI, cards and net banking in India, and international cards.</p>
    </section>

    <section className="site-width pr-offers" aria-labelledby="offers-title">
      <h2 id="offers-title" className="pr-eyebrow">Launch offers</h2>
      <ul>
        {LAUNCH_OFFERS.map((offer) => <li key={offer.title}><strong>{offer.title}</strong><span>{offer.body}</span></li>)}
      </ul>
      <p className="pr-offers-foot">Offers don’t stack: one per customer. <a href={offerMail}>Apply by email <ArrowUpRight size={13} /></a></p>
    </section>

    <section className="site-width pr-compare" aria-labelledby="matrix-title">
      <div className="p-head">
        <p className="p-kicker">Compare the plans</p>
        <h2 id="matrix-title">The plans at launch. <span>Orbit opens with LLMSlim 1.0.</span></h2>
      </div>
      <div className="pr-matrix-wrap" role="region" aria-labelledby="matrix-title" tabIndex={0}>
        <table className="pr-matrix">
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">Feature</span></th>
              {PLANS.map((plan) => <th scope="col" key={plan.id}>{plan.name}<span>{plan.prices ? `${formatPrice(plan.prices[currency][billing], currency)} ${plan.prices[currency][billing] > 0 && billing === "annual" ? "a year" : "a month"}` : "Custom"}</span></th>)}
            </tr>
          </thead>
          <tbody>
            {FEATURE_MATRIX.map((row) => <tr key={row.feature}>
              <th scope="row">{row.feature}{row.note && <span>{row.note}</span>}</th>
              {row.cells.map((cell, index) => <td key={PLANS[index].id}><CellValue value={cell} /></td>)}
            </tr>)}
          </tbody>
        </table>
      </div>
      <p className="pr-fine">{currency === "inr" ? "Rupee prices include 18% GST." : "Dollar prices are for customers outside India."} Team adds seats at {currency === "inr" ? "₹1,199" : "$15"} each a month beyond the five included. Self-hosting? <Link href="/vault">LLMSlim Vault</Link> runs in your own VPC.</p>
    </section>

    <section className="site-width pr-faq questions-section" aria-labelledby="faq-title">
      <div><p className="p-kicker">Questions</p><h2 id="faq-title">Before you <span>choose a plan.</span></h2></div>
      <div className="faq-list">{PRICING_FAQS.map((faq) => <details key={faq.question}>
        <summary>{faq.question}<span className="faq-plus" aria-hidden="true">+</span></summary>
        <p>{faq.answer}{faq.link && <> <Link className="pr-faq-link" href={faq.link.href}>{faq.link.label}</Link></>}</p>
      </details>)}</div>
    </section>
  </main><SiteFooter /></div>
}
