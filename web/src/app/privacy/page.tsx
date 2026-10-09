import { SiteHeader } from "@/components/site/SiteHeader"
import { SiteFooter } from "@/components/site/SiteFooter"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Privacy",
  description: "What llmslim.app measures, what it never collects, and how Studio handles your text.",
  canonicalUrl: `${siteConfig.url}/privacy`,
})

export default function PrivacyPage() {
  return <div className="slim-site"><SiteHeader /><main id="main-content" className="site-width privacy-page">
    <span className="eyebrow">LAST UPDATED 9 OCTOBER 2026</span>
    <h1>Privacy</h1>
    <p>This page covers the llmslim.app website and Studio. The open-source <code>llmslim</code> package sends nothing to us.</p>

    <h2>What the website measures</h2>
    <ul>
      <li><strong>Vercel Web Analytics and Speed Insights.</strong> Aggregate page views and performance metrics, without cookies.</li>
      <li><strong>Mixpanel (when enabled).</strong> A short list of product events: homepage and Platform page views, and clicks on the Core documentation, Studio, Platform beta, and startup program links. Each event carries the page path and, for clicks, a fixed label such as <code>hero</code> or <code>mixpanel</code>. We use no Mixpanel SDK or cookie, store no identifier between visits, and ask Mixpanel not to geolocate your IP address. Nothing is sent if your browser signals Do Not Track or Global Privacy Control.</li>
      <li><strong>Sentry (when enabled).</strong> JavaScript error reports with the error type and stack trace. Quoted text and URLs in error messages are redacted, and there is no session replay, user identity, request data, or interaction trail.</li>
    </ul>

    <h2>What we never collect</h2>
    <p>Studio input or output, prompts, model responses, API keys, names, email addresses, or query strings are never sent to analytics or error reporting.</p>

    <h2>Studio</h2>
    <ul>
      <li>Text you submit is sent to the Studio API to run compression or planning and is returned to you. It is not stored, logged, or used for training.</li>
      <li>Hosted Sarvam requests are forwarded to Sarvam. To enforce fair-use limits we set a 24-hour session cookie and keep usage counters keyed by pseudonymous, keyed hashes of your IP address and session. These counters expire within days and never contain your text.</li>
      <li>With your own Sarvam key, the key is used for that single request and is never stored or logged.</li>
    </ul>

    <h2>In your browser</h2>
    <p>We store your light or dark theme preference in local storage. Nothing else.</p>

    <h2>Questions</h2>
    <p>Contact the maintainer through <a className="text-link" href={siteConfig.github + "/security/policy"} target="_blank" rel="noreferrer">the project’s security policy</a> for anything privacy-related.</p>
  </main><SiteFooter /></div>
}
