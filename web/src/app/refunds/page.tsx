import Link from "next/link"
import { Email, PolicyPage } from "@/components/site/PolicyPage"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Cancellation and Refund Policy",
  description: "Cancel LLMSlim any time; it takes effect at the end of the billing period. A 14-day money-back guarantee on the first payment of a new subscription or Vault licence, and full refunds for duplicate charges.",
  path: "/refunds",
})

export default function RefundsPage() {
  const { company } = siteConfig
  return <PolicyPage title="Cancellation and Refund Policy" lede={<>This policy covers LLMSlim Orbit subscriptions and LLMSlim Vault licences bought from {company.name}. LLMSlim Core is free, so there is nothing to refund.</>}>
    <h2>Cancelling</h2>
    <ul>
      <li>You can cancel at any time from your account page, once it is available, or by emailing <Email to={siteConfig.supportEmail} /> from your account’s email address.</li>
      <li>Cancellation takes effect at the end of your current billing period. Your plan stays active until then, and you will not be charged again.</li>
    </ul>

    <h2>14-day money-back guarantee</h2>
    <p>If you are not happy with a new paid subscription or a new Vault licence, ask for a refund within 14 days of its first payment, and we will refund that payment in full. The guarantee covers the first payment only, not renewals.</p>

    <h2>After 14 days</h2>
    <p>We do not refund partial periods, on monthly or annual plans. If you cancel an annual plan, it stays active until the end of the year you paid for.</p>

    <h2>Duplicate or wrong charges</h2>
    <p>If you were charged twice, or charged an amount you did not agree to, we refund the extra charge in full.</p>

    <h2>How refunds are paid</h2>
    <p>Approved refunds go back to the original payment method, through Razorpay, within 5 to 7 business days. Your bank may take longer to show the credit.</p>

    <h2>How to ask for a refund</h2>
    <p>Email <Email to={siteConfig.supportEmail} /> with your Razorpay payment ID. You will find it in your payment confirmation email; it starts with <code>pay_</code>. We reply to every request by email.</p>

    <h2>Offers and discounts</h2>
    <p>Offers and discounts have no cash value and are not refundable as cash. A refund is for the amount you actually paid.</p>

    <h2>Questions</h2>
    <p>Email <Email to={siteConfig.supportEmail} />. Our <Link href="/terms">Terms of Service</Link> cover billing and renewal in full.</p>
  </PolicyPage>
}
