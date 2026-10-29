/**
 * Plans at the LLMSlim 1.0 launch (founder's decision, 29 October 2026). Rendered by /pricing, /pricing.md and the
 * pricing structured data, so every view shows the same numbers.
 *
 * LLMSlim Orbit, the hosted edition, does not exist yet: it opens with LLMSlim 1.0. Until checkout exists, every
 * paid-plan button is a mailto to the founder. INR prices include 18% GST; USD prices are for customers outside India.
 */

export const CURRENCIES = ["inr", "usd"] as const
export type Currency = (typeof CURRENCIES)[number]
export const BILLINGS = ["monthly", "annual"] as const
export type Billing = (typeof BILLINGS)[number]
export type PlanId = "free" | "pro" | "team" | "business" | "enterprise"

/** Whole currency units, GST included for INR. Annual is ten months' price (two months free). */
type PriceTable = Record<Currency, Record<Billing, number>>

export interface Plan {
  id: PlanId
  name: string
  summary: string
  /** null: priced per customer (Enterprise). */
  prices: PriceTable | null
  /** Seats line, per currency (Team's extra seats are priced). */
  seats?: Record<Currency, string>
  /** The three limits shown on the card. */
  limits: readonly string[]
  featured?: boolean
}

export const PLANS: readonly Plan[] = [
  {
    id: "free", name: "Free", summary: "Try hosted memory on one small project.",
    prices: { inr: { monthly: 0, annual: 0 }, usd: { monthly: 0, annual: 0 } },
    limits: ["1 project", "1,000 stored turns", "1,000 searches a month"],
  },
  {
    id: "pro", name: "Pro", summary: "For one developer and the agents they run.",
    prices: { inr: { monthly: 1499, annual: 14990 }, usd: { monthly: 19, annual: 190 } },
    limits: ["3 projects", "250,000 stored turns", "100,000 searches a month"],
  },
  {
    id: "team", name: "Team", summary: "Shared memory, roles and a truth timeline for a team.", featured: true,
    prices: { inr: { monthly: 7999, annual: 79990 }, usd: { monthly: 99, annual: 990 } },
    seats: { inr: "5 seats included, then ₹1,199 per extra seat a month", usd: "5 seats included, then $15 per extra seat a month" },
    limits: ["10 projects", "2M stored turns", "1M searches a month"],
  },
  {
    id: "business", name: "Business", summary: "Governance, retention and a self-hosted Vault licence.",
    prices: { inr: { monthly: 31999, annual: 319990 }, usd: { monthly: 399, annual: 3990 } },
    seats: { inr: "15 seats included", usd: "15 seats included" },
    limits: ["Unlimited projects", "10M stored turns", "5M searches a month"],
  },
  {
    id: "enterprise", name: "Enterprise", summary: "Custom limits, an SLA, SAML with SCIM and a security review.",
    prices: null,
    limits: ["Custom limits", "SAML SSO with SCIM", "An SLA and a DPA"],
  },
]

/** Indian digit grouping for rupees (₹3,19,990); US grouping for dollars. */
export function formatPrice(amount: number, currency: Currency): string {
  return currency === "inr" ? `₹${amount.toLocaleString("en-IN")}` : `$${amount.toLocaleString("en-US")}`
}

export const CURRENCY_LABEL: Record<Currency, string> = { inr: "INR", usd: "USD" }

/** A cell of the feature matrix: text, or included / not included. */
export type Cell = string | boolean
export interface FeatureRow { feature: string; note?: string; cells: readonly [Cell, Cell, Cell, Cell, Cell] }

/** The plans at launch, column order Free, Pro, Team, Business, Enterprise. Free is minimal on purpose. */
export const FEATURE_MATRIX: readonly FeatureRow[] = [
  { feature: "Projects", cells: ["1", "3", "10", "Unlimited", "Custom"] },
  { feature: "Stored turns", cells: ["1,000", "250,000", "2M", "10M", "Custom"] },
  { feature: "Searches a month", cells: ["1,000", "100,000", "1M", "5M", "Custom"] },
  { feature: "Hosted memory API and remote MCP", cells: [true, true, true, true, true] },
  { feature: "Import history", note: "Claude Code, ChatGPT and Mem0 exports", cells: [true, true, true, true, true] },
  { feature: "Context console, trace retention", cells: [false, "7 days", "30 days", "90 days", "Custom"] },
  { feature: "Team memory and roles", cells: [false, false, true, true, true] },
  { feature: "Truth timeline, point-in-time recall", cells: [false, false, true, true, true] },
  { feature: "Savings and cache report, webhooks", cells: [false, false, true, true, true] },
  { feature: "SSO", cells: [false, false, "OIDC", "OIDC + SAML", "SAML + SCIM"] },
  { feature: "Audit log export", cells: [false, false, true, true, true] },
  { feature: "Retention policies, PII redaction, erasure receipts", cells: [false, false, false, true, true] },
  { feature: "Policy lab", note: "Outcome-learned context policies, shadow mode first", cells: [false, false, false, true, true] },
  { feature: "LLMSlim Vault self-hosted licence", cells: [false, false, false, "1 production instance", "Custom"] },
  { feature: "Support", cells: ["Community", "Email, 2 business days", "Email, 1 business day", "Priority, shared channel", "SLA, security review, DPA"] },
]

export interface Offer { title: string; body: string }

/** Launch offers. They don't stack, and there is no live counter (there is no backend yet). */
export const LAUNCH_OFFERS: readonly Offer[] = [
  { title: "40% off your first 12 months", body: "For the first 100 paying customers, on any paid plan, monthly or annual. After 12 months the plan's normal price applies." },
  { title: "Business free for 3 months for startups", body: "For startups that have raised less than US$2M in total." },
  { title: "Pro free for open-source maintainers and students", body: "Verified with GitHub when Orbit opens. Until then, apply by email." },
]

export interface PricingFaq { question: string; answer: string; link?: { href: string; label: string } }

export const PRICING_FAQS: readonly PricingFaq[] = [
  { question: "Does LLMSlim Core stay free?", answer: "Yes. LLMSlim Core is MIT licensed and stays free forever. Install it with pip install llmslim and run it yourself, with no limits on projects, turns or searches. Orbit and Vault are separate paid editions built on Core." },
  { question: "What counts as a stored turn and a search?", answer: "A stored turn is one message kept in your hosted memory, such as a user message or an agent reply, including messages you import. It counts once, however often it is recalled, and deleting it frees the space. A search is one request that reads from memory, through the API or the remote MCP server." },
  { question: "Are taxes included? Do I get an invoice?", answer: "INR prices include 18% GST, and we issue a GST invoice for every payment. USD prices are for customers outside India: these are exports, so no Indian GST is charged, but local taxes may apply." },
  { question: "How can I pay?", answer: "Payments are processed by Razorpay. In India you can pay with UPI, cards or net banking; from outside India, with an international card. We never see or store your card number." },
  { question: "Why is Business in India billed annually?", answer: "Under RBI e-mandate rules, each card or UPI renewal above ₹15,000 needs the payer's approval. So in India, Business is billed annually in advance, or monthly with that approval step on every debit." },
  { question: "Can I cancel, and do you give refunds?", answer: "Cancel any time. Your plan stays active until the end of the period you paid for, and you are not charged again. The first payment of a new subscription or Vault licence has a 14-day money-back guarantee.", link: { href: "/refunds", label: "Read the Cancellation and Refund Policy." } },
  { question: "What happens to my data?", answer: "Your memory is yours. We store it only to run the service, never use it to train models, and delete it within 30 days of a deletion request or of closing your account, except billing records the law requires us to keep.", link: { href: "/privacy", label: "Read the Privacy Policy." } },
  { question: "Can I host it myself?", answer: "Yes. LLMSlim Vault is the self-hosted edition: it runs in your own VPC, so memory and traces stay in your environment. Business includes a licence for one production instance, and Enterprise licences are custom. Vault is in private beta today.", link: { href: "/vault", label: "About LLMSlim Vault." } },
  { question: "How do open-source maintainers and students get Pro free?", answer: "Verification with GitHub opens with Orbit. Until then, email us your GitHub profile and the project you maintain, or proof that you are a student, and we will add you to the list." },
  { question: "Which startups qualify for the startup offer?", answer: "Startups that have raised less than US$2M in total get LLMSlim Business free for 3 months. Email us your company name and how much you have raised. Offers don't stack: one offer per customer." },
  { question: "When does Orbit open?", answer: "With LLMSlim 1.0. Join the founding list and we will email you when it opens. Nothing is charged until you choose a plan." },
]
