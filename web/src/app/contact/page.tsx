import { Email, PolicyPage } from "@/components/site/PolicyPage"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Contact",
  description: "Contact LLMSlim by email: hello@ameyor.in for business and billing, support@llmslim.app for product support, founder@llmslim.app for the founder. AMEYOR, Jaipur, Rajasthan, India.",
  path: "/contact",
})

export default function ContactPage() {
  const { company } = siteConfig
  return <PolicyPage title="Contact" lede="We handle every enquiry by email and reply within 1 to 2 business days. Pick the address that fits, so your message reaches the right inbox first time.">
    <h2>Email</h2>
    <dl className="policy-contacts">
      <div>
        <dt>Business, billing and legal</dt>
        <dd><Email to={siteConfig.businessEmail} /></dd>
        <dd>Invoices and GST, contracts, partnerships and press, and privacy or data requests.</dd>
      </div>
      <div>
        <dt>Product support</dt>
        <dd><Email to={siteConfig.supportEmail} /></dd>
        <dd>Help with LLMSlim Core, Orbit or Vault, payments, cancellations and refunds. For anything about a payment, include your Razorpay payment ID.</dd>
      </div>
      <div>
        <dt>The founder</dt>
        <dd><Email to={siteConfig.founderEmail} /></dd>
        <dd>The Orbit founding list, Enterprise plans, the Vault beta and the launch offers.</dd>
      </div>
    </dl>

    <h2>Response time</h2>
    <p>We reply within 1 to 2 business days, Monday to Friday, India time.</p>

    <h2>Bugs and feature requests</h2>
    <p>For LLMSlim Core, open an issue on <a href={`${siteConfig.github}/issues`} target="_blank" rel="noreferrer">GitHub</a>, so others can follow the fix. For Orbit or Vault, email <Email to={siteConfig.supportEmail} />.</p>

    <h2>Security</h2>
    <p>Please do not report a vulnerability in a public issue. Email <Email to={siteConfig.supportEmail} /> with the subject <code>[SECURITY] Potential vulnerability in llmslim</code>, or open a private GitHub security advisory, as our <a href={`${siteConfig.github}/security/policy`} target="_blank" rel="noreferrer">security policy</a> describes.</p>

    <h2>Company</h2>
    <p>LLMSlim is a product of {company.name}, {company.kind}. Proprietor: {company.proprietor}. Location: {company.location}.</p>
  </PolicyPage>
}
