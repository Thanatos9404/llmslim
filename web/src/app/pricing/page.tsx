import Link from "next/link"
import { getImageProps } from "next/image"
import { headers } from "next/headers"
import { preload } from "react-dom"
import { ArrowRight, ArrowUpRight, Check } from "lucide-react"
import { GlyphStage } from "@/components/brand/GlyphStage"
import { LogoMark } from "@/components/brand/LogoMark"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { ProductLogo } from "@/components/brand/ProductLogo"
import { Reveal } from "@/components/motion/Reveal"
import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { PageBackdrop } from "@/components/site/PageBackdrop"
import { BACKDROP_CODE } from "@/components/site/backdrop-code"
import { FoundingListButton } from "@/components/site/FoundingListButton"
import { TrackedLink } from "@/components/site/TrackedLink"
import { siteConfig } from "@/config/site"
import {
  BILLINGS, CURRENCIES, CURRENCY_LABEL, FEATURE_MATRIX, FOUNDING_LIST_COUNTER, LAUNCH_OFFERS, PLANS, PRICING_FAQS, formatPrice,
  type Billing, type Cell, type Currency, type Plan,
} from "@/data/pricing"
import { getAuthConfig } from "@/lib/auth/config"
import { foundingListFeatures } from "@/lib/founding-list/features"
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

/**
 * Until checkout exists, every plan button is an email to the founder. "Join the founding list" turns into a one-click
 * join or a small form once the page is interactive (FoundingListButton); the email stays the no-JavaScript fallback.
 */
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

/** Five squares, one more lit per plan, Free to Enterprise: where a plan sits in the ladder. Decoration only. */
function TierMeter({ tier }: { tier: number }) {
  return <span className="pr-tier" aria-hidden="true">{PLANS.map((plan, index) => <i key={plan.id} className={index <= tier ? "is-on" : undefined} />)}</span>
}

/** A blank pixel for the plate's photo under 980px, where the plate is hidden, so phones never download it. */
const BLANK_PIXEL = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

/**
 * The hero's dark plate: a server-room photo under a veil, the memory glyph playing on it, and the hosted edition's
 * name under the glyph (both already on the page; the plate is decoration, hidden from assistive technology). Plates
 * are dark in both themes. Shown from 980px; narrower screens go straight from the heading to the plans.
 */
function OrbitPlate() {
  const { props: photo } = getImageProps({ src: "/media/stock/server-aisle.webp", alt: "", fill: true, loading: "eager", sizes: "460px", style: { objectPosition: "50% 45%" } })
  return <div className="pr-plate on-dark" aria-hidden="true">
    <div className="px-photo"><div className="px-photo-media">
      <picture>
        <source media="(max-width: 980px)" srcSet={BLANK_PIXEL} />
        {/* A plain img: next/image cannot sit inside <picture>; getImageProps gives it the same optimized srcset. */}
        <img {...photo} alt="" />
      </picture>
    </div></div>
    <div className="pr-plate-veil" />
    <GlyphStage size={132} />
    <div className="pr-plate-foot">
      <span className="pr-plate-brand"><LogoMark size={16} />LLMSlim Orbit</span>
      <span className="pr-plate-status"><i />Opening with LLMSlim 1.0</span>
    </div>
  </div>
}

function CellValue({ value }: { value: Cell }) {
  if (value === true) return <><Check size={16} aria-hidden="true" className="pr-yes" /><span className="sr-only">Included</span></>
  if (value === false) return <><span aria-hidden="true" className="pr-no">–</span><span className="sr-only">Not included</span></>
  return <>{value}</>
}

export default async function PricingPage({ searchParams }: { searchParams: SearchParams }) {
  // The headline's two faces, requested with the stylesheet instead of after it: with the serif half on its own line,
  // a late swap changed the headline's height and moved the lede under it on phones.
  preload("/fonts/geist-latin.woff2", { as: "font", type: "font/woff2", crossOrigin: "anonymous" })
  preload("/fonts/InstrumentSerif-Italic.woff2", { as: "font", type: "font/woff2", crossOrigin: "anonymous" })
  const params = await searchParams
  const requestHeaders = await headers()
  // Vercel sets the visitor's country on every request; rupees for India, dollars elsewhere, unless the visitor chose.
  const country = requestHeaders.get("x-vercel-ip-country")
  const currency: Currency = pick(params.currency, CURRENCIES) ?? (country?.toUpperCase() === "IN" ? "inr" : "usd")
  const billing: Billing = pick(params.billing, BILLINGS) ?? "monthly"
  const href = (next: { currency?: Currency; billing?: Billing }) => `/pricing?currency=${next.currency ?? currency}&billing=${next.billing ?? billing}`
  const faqs = PRICING_FAQS.map((faq) => [faq.question, faq.answer] as const)
  const founding = foundingListFeatures(getAuthConfig(), requestHeaders)
  // Off by default: the founder decides when a public count is worth showing (src/data/pricing.ts).
  const members = FOUNDING_LIST_COUNTER.show ? await (await import("@/lib/founding-list/server")).publicFoundingCount(FOUNDING_LIST_COUNTER.minimum) : null

  return <div className="slim-site"><SiteHeader /><main id="main-content" className="pricing-page has-backdrop">
    <PageBackdrop code={BACKDROP_CODE.memory} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(faqJsonLd(faqs, "/pricing")) }} />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(orbitPricingJsonLd()) }} />

    <header className="site-width pr-head">
      <div className="pr-head-copy">
      <p className="p-kicker g-kicker"><MemoryGlyph size={14} />Pricing</p>
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
      </div>
      <OrbitPlate />
    </header>

    <section className="site-width pr-core glow-card" aria-labelledby="core-title">
      <div>
        <p className="pr-eyebrow">Open source · MIT licence</p>
        <h2 id="core-title"><LogoMark size={20} className="pr-mark" />LLMSlim Core <span>Free forever</span></h2>
        <p>The Python library, MCP server and HTTP server. Self-host it with no account and no limits on projects, turns or searches.</p>
        <ul className="pr-chips" aria-label="Products named here">
          <li><ProductLogo logo="python" size={14} />Python</li>
          <li><ProductLogo logo="mcp" size={14} />MCP</li>
        </ul>
      </div>
      <div className="pr-core-actions">
        <code>pip install llmslim</code>
        <TrackedLink className="button button-outline" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "pricing" }}>Read the docs <ArrowRight size={16} /></TrackedLink>
      </div>
    </section>

    <section className="site-width pr-orbit" aria-labelledby="orbit-title">
      <div className="pr-orbit-head">
        <h2 id="orbit-title"><LogoMark size={24} className="pr-mark" />LLMSlim Orbit</h2>
        <p className="pr-status"><span aria-hidden="true" />Opening with LLMSlim 1.0</p>
      </div>
      <p className="pr-orbit-sub">Hosted memory and remote MCP for your agents, run by us. Prices in {currency === "inr" ? "rupees, including 18% GST" : "US dollars, for customers outside India"}.</p>
      <ul className="pr-plans">
        {PLANS.map((plan, index) => <li key={plan.id} className={`pr-plan glow-card${plan.featured ? " is-featured" : ""}`}>
          <TierMeter tier={index} />
          <h3>{plan.name}</h3>
          <p className="pr-summary">{plan.summary}</p>
          <PriceLine plan={plan} currency={currency} billing={billing} />
          <p className="pr-note">{priceNote(plan, currency, billing)}</p>
          {plan.id === "enterprise"
            ? <TrackedLink className="button button-outline" href={planMail(plan, currency, billing)} event="pricing_cta_clicked" properties={{ plan: plan.id, currency, billing }}>Talk to us</TrackedLink>
            : <FoundingListButton className={plan.id === "team" ? "button" : "button button-outline"} href={planMail(plan, currency, billing)} choice={{ plan: plan.id, currency, billing }} planName={plan.name} features={founding}>Join the founding list</FoundingListButton>}
          <ul className="pr-limits">
            {plan.seats && <li><Check size={14} aria-hidden="true" />{plan.seats[currency]}</li>}
            {plan.limits.map((limit) => <li key={limit}><Check size={14} aria-hidden="true" />{limit}</li>)}
          </ul>
          {plan.id === "business" && currency === "inr" && billing === "monthly" && <p className="pr-mandate">Monthly debits above ₹15,000 need your approval each time (RBI e-mandate rules). Annual billing avoids this.</p>}
        </li>)}
      </ul>
      <p className="pr-fine">{members !== null && <>{members.toLocaleString("en-US")} people are on the founding list. </>}Nothing is charged before Orbit opens. Payments will be processed by <ProductLogo logo="razorpay" size={13} className="pr-inline-logo" />Razorpay: UPI, cards and net banking in India, and international cards.</p>
    </section>

    <section className="site-width pr-offers" aria-labelledby="offers-title">
      <h2 id="offers-title" className="pr-eyebrow">Launch offers</h2>
      <ul>
        {LAUNCH_OFFERS.map((offer) => <li key={offer.title}><strong>{offer.title}</strong><span>{offer.body}</span></li>)}
      </ul>
      <p className="pr-offers-foot">Offers don’t stack: one per customer. <a href={offerMail}>Apply by email <ArrowUpRight size={13} /></a></p>
    </section>

    <section className="site-width pr-compare" aria-labelledby="matrix-title">
      <Reveal className="p-head">
        <p className="p-kicker g-kicker"><MemoryGlyph size={14} animate />Compare the plans</p>
        <h2 id="matrix-title">The plans at launch. <span>Orbit opens with LLMSlim 1.0.</span></h2>
      </Reveal>
      <div className="pr-matrix-wrap" role="region" aria-labelledby="matrix-title" tabIndex={0}>
        <table className="pr-matrix">
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">Feature</span></th>
              {PLANS.map((plan, index) => <th scope="col" key={plan.id} className={plan.featured ? "is-featured" : undefined}><TierMeter tier={index} />{plan.name}<span>{plan.prices ? `${formatPrice(plan.prices[currency][billing], currency)} ${plan.prices[currency][billing] > 0 && billing === "annual" ? "a year" : "a month"}` : "Custom"}</span></th>)}
            </tr>
          </thead>
          <tbody>
            {FEATURE_MATRIX.map((row) => <tr key={row.feature}>
              <th scope="row">{row.feature}{row.note && <span>{row.note}</span>}</th>
              {row.cells.map((cell, index) => <td key={PLANS[index].id} className={PLANS[index].featured ? "is-featured" : undefined}><CellValue value={cell} /></td>)}
            </tr>)}
          </tbody>
        </table>
      </div>
      <p className="pr-fine">{currency === "inr" ? "Rupee prices include 18% GST." : "Dollar prices are for customers outside India."} Team adds seats at {currency === "inr" ? "₹1,199" : "$15"} each a month beyond the five included. Self-hosting? <Link href="/vault">LLMSlim Vault</Link> runs in your own VPC.</p>
    </section>

    <section className="site-width pr-faq questions-section" aria-labelledby="faq-title">
      <Reveal><p className="p-kicker g-kicker"><MemoryGlyph size={14} animate />Questions</p><h2 id="faq-title">Before you <span>choose a plan.</span></h2></Reveal>
      <div className="faq-list">{PRICING_FAQS.map((faq) => <details key={faq.question}>
        <summary>{faq.question}<span className="faq-plus" aria-hidden="true">+</span></summary>
        <p>{faq.answer}{faq.link && <> <Link className="pr-faq-link" href={faq.link.href}>{faq.link.label}</Link></>}</p>
      </details>)}</div>
    </section>
  </main><SiteFooter /></div>
}
