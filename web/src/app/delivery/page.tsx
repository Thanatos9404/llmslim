import Link from "next/link"
import { Email, PolicyPage } from "@/components/site/PolicyPage"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Shipping and Delivery Policy",
  description: "LLMSlim's products are digital and delivered worldwide over the internet, with no shipping charges. Orbit plans activate within minutes of payment; Vault licence keys are emailed within 24 hours.",
  path: "/delivery",
})

export default function DeliveryPage() {
  return <PolicyPage title="Shipping and Delivery Policy" lede="All LLMSlim products are digital. Nothing physical is shipped, and there are no shipping charges.">
    <h2>How each product is delivered</h2>
    <ul>
      <li><strong>LLMSlim Orbit plans.</strong> Your plan activates as soon as your payment succeeds, usually within minutes. You use it through your LLMSlim account.</li>
      <li><strong>LLMSlim Vault licences.</strong> We email your licence key and download access within 24 hours of a successful payment, usually within minutes.</li>
      <li><strong>LLMSlim Core.</strong> Free and open source, so there is nothing to buy. Install it any time with <code>pip install llmslim</code>.</li>
    </ul>

    <h2>Confirmation and invoice</h2>
    <p>After every successful payment, we email a confirmation and a GST invoice to your account’s email address.</p>

    <h2>Where we deliver</h2>
    <p>Worldwide. Every product is delivered over the internet.</p>

    <h2>If something does not arrive</h2>
    <p>If your plan is not active, or your Vault licence has not arrived, within 24 hours of payment, email <Email to={siteConfig.supportEmail} /> with your Razorpay payment ID, and we will resolve it.</p>

    <p>See also our <Link href="/refunds">Cancellation and Refund Policy</Link> and <Link href="/terms">Terms of Service</Link>.</p>
  </PolicyPage>
}
