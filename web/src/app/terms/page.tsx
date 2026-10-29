import Link from "next/link"
import { Email, PolicyPage } from "@/components/site/PolicyPage"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Terms of Service",
  description: "The terms for the llmslim.app website and LLMSlim's paid services, LLMSlim Orbit and LLMSlim Vault: accounts, billing and renewal through Razorpay, your content, the Vault licence, liability and governing law.",
  path: "/terms",
})

export default function TermsPage() {
  const { company } = siteConfig
  return <PolicyPage title="Terms of Service" lede={<>These terms are an agreement between you and {company.name}, {company.kind}, which makes LLMSlim (“we”, “us”). They cover the llmslim.app website and LLMSlim’s paid services: LLMSlim Orbit, the hosted edition, and LLMSlim Vault, the self-hosted edition.</>}>
    <p>By using the website or a paid service, you accept these terms. If you accept them for a company or another organisation, you confirm that you can bind it, and “you” means that organisation.</p>

    <h2>1. LLMSlim Core</h2>
    <p>LLMSlim Core, the open-source <code>llmslim</code> package, is licensed under the <a href={siteConfig.license} target="_blank" rel="noreferrer">MIT licence</a>. Your use of Core is governed by that licence, not by these terms.</p>

    <h2>2. Accounts</h2>
    <ul>
      <li>Give accurate details when you sign up, and keep them up to date.</li>
      <li>Keep your login and API keys secure. You are responsible for what happens under your account. If you think someone has used it without permission, tell us at <Email to={siteConfig.supportEmail} /> straight away.</li>
      <li>You must be at least 18 years old to open an account.</li>
    </ul>

    <h2>3. Acceptable use</h2>
    <p>Do not use LLMSlim to:</p>
    <ul>
      <li>break the law, or store or process content you have no right to use;</li>
      <li>send malware or spam, or harm other people;</li>
      <li>try to reach another customer’s data, or probe, scan or test the security of the service, except as our <a href={`${siteConfig.github}/security/policy`} target="_blank" rel="noreferrer">security policy</a> allows;</li>
      <li>disrupt or overload the service, or get around its limits;</li>
      <li>resell the hosted service, or offer it to others as your own, unless we agree in writing.</li>
    </ul>
    <p>We may remove content or limit an account that breaks these rules (see section 13).</p>

    <h2>4. Plans, billing and renewal</h2>
    <ul>
      <li>Plans, prices and limits are listed on our <Link href="/pricing">pricing page</Link>.</li>
      <li>Payments are processed by Razorpay. We never see or store your card number.</li>
      <li>INR prices include 18% GST. USD prices are for customers outside India; they include no Indian GST, and you are responsible for any local taxes where you are.</li>
      <li>Paid plans renew automatically on the same plan and billing period, monthly or annual, until you cancel. By subscribing, you authorise us to charge your chosen payment method through Razorpay at the start of each period.</li>
      <li>Under RBI e-mandate rules, Indian card and UPI renewals above ₹15,000 need your approval on each debit. When a renewal needs it, you will be asked before the charge.</li>
      <li>We email a GST invoice for every payment.</li>
      <li>If we change a plan’s price, we will email you before the new price applies to your renewal, and you can cancel before it does.</li>
      <li>Cancellations and refunds follow our <Link href="/refunds">Cancellation and Refund Policy</Link>.</li>
    </ul>

    <h2>5. Failed payments</h2>
    <p>If a renewal payment fails, Razorpay retries it. If it still fails at the end of a grace period, your account moves to the Free plan. We delete no data for 30 days after that, so you can pay and go back to your plan with everything in place. After 30 days, we may delete content above the Free plan’s limits, after telling you by email.</p>

    <h2>6. Offers and discounts</h2>
    <ul>
      <li>One offer per customer. Offers do not stack, cannot be transferred and cannot be exchanged for cash.</li>
      <li>The launch offer of 40% off lasts for the first 12 months of a paid plan. After 12 months, the plan’s normal price applies.</li>
      <li>We may ask for proof of eligibility for the startup, student and open-source offers.</li>
      <li>We may end or change any offer for new sign-ups at any time. Customers who already have an offer keep it for its stated term.</li>
    </ul>

    <h2>7. Your content</h2>
    <ul>
      <li>You own the content you put into LLMSlim Orbit or LLMSlim Vault, such as messages, memory, documents and traces (“your content”).</li>
      <li>You give us permission to store, copy, process and transmit your content only as needed to provide, secure and support the service for you, and as you instruct.</li>
      <li>We do not use your content to train AI models, ours or anyone else’s.</li>
      <li>You are responsible for having the right to use your content with LLMSlim.</li>
      <li>Content in LLMSlim Vault stays in your environment. We see it only if you share it with us, for example in a support request.</li>
      <li>Our <Link href="/privacy">Privacy Policy</Link> describes how we handle and delete your content.</li>
    </ul>

    <h2>8. The LLMSlim Vault licence</h2>
    <ul>
      <li>A Vault licence lets you install and run LLMSlim Vault on the number of production instances the licence names, for your own business, for the term you paid for.</li>
      <li>You may not redistribute, sublicense, sell, rent or lend Vault, or run it as a service for third parties.</li>
      <li>Vault checks its licence key. Do not remove, disable or get around the licence checks.</li>
      <li>You may not reverse engineer Vault, except where the law allows it despite this term.</li>
      <li>Vault is licensed, not sold. When your licence ends, stop running Vault in production.</li>
    </ul>

    <h2>9. Other services</h2>
    <p>Razorpay processes payments under its own terms. When you connect Orbit to another service, such as Claude.ai, ChatGPT, Cursor or Claude Code, that service’s own terms apply to it.</p>

    <h2>10. Availability</h2>
    <p>We work to keep Orbit fast and available, but we do not promise any level of uptime, except under a signed Enterprise agreement with a service level agreement (SLA). We may change, add or remove features over time.</p>

    <h2>11. Intellectual property</h2>
    <p>We own LLMSlim Orbit, LLMSlim Vault, this website and the LLMSlim name and logos. These terms give you only the rights they state. LLMSlim Core is open source under the MIT licence. If you send us feedback or ideas, we may use them without any obligation to you.</p>

    <h2>12. Disclaimer and limitation of liability</h2>
    <p>Except as these terms say, the services are provided “as is” and “as available”. To the fullest extent the law allows, we disclaim all implied warranties, including merchantability, fitness for a particular purpose and non-infringement. LLMSlim chooses what context reaches an AI model; we do not promise that the model’s answers will be correct, complete or right for your use.</p>
    <p>To the fullest extent the law allows:</p>
    <ul>
      <li>we are not liable for indirect, incidental, special, consequential or punitive losses, or for lost profits, revenue, goodwill or data;</li>
      <li>our total liability for all claims about the services is limited to the fees you paid us for them in the 12 months before the claim arose.</li>
    </ul>
    <p>Nothing in these terms limits liability that the law does not allow to be limited.</p>

    <h2>13. Suspension and termination</h2>
    <ul>
      <li>You can stop using the services and cancel at any time, as our <Link href="/refunds">Cancellation and Refund Policy</Link> describes.</li>
      <li>We may suspend or close an account that breaks these terms, does not pay, puts the service or other customers at risk, or where the law requires it. Where it is reasonable, we will tell you first and give you a chance to fix the problem.</li>
      <li>When an account closes, we delete its content within 30 days, except billing records the law requires us to keep.</li>
      <li>Sections 7 and 11 to 15 continue to apply after an account closes.</li>
    </ul>

    <h2>14. Changes to these terms</h2>
    <p>We may update these terms. We will post the new version on this page with a new “Last updated” date, and we will email paid customers before a change that affects them takes effect. If you keep using the services after that, you accept the new terms. If you do not accept them, you can cancel.</p>

    <h2>15. Governing law</h2>
    <p>These terms are governed by the laws of India. The courts at Jaipur, Rajasthan have exclusive jurisdiction over any dispute about these terms or the services.</p>

    <h2>16. Contact</h2>
    <p>{company.name}, {company.location}. Email <Email to={siteConfig.businessEmail} /> about these terms, or <Email to={siteConfig.supportEmail} /> for help with the services.</p>
  </PolicyPage>
}
