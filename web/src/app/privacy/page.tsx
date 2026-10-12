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
    <span className="eyebrow">LAST UPDATED 12 OCTOBER 2026</span>
    <h1>Privacy</h1>
    <p>This page covers the llmslim.app website and Studio. The open-source <code>llmslim</code> package sends nothing to us.</p>

    <h2>What the website measures</h2>
    <ul>
      <li><strong>Vercel Web Analytics and Speed Insights.</strong> Aggregate page views and performance metrics, without cookies.</li>
      <li><strong>Mixpanel (when enabled).</strong> Nine product events and nothing else:
        <ul>
          <li>page views of the homepage, the Platform page and the Results page;</li>
          <li>clicks on links to the Core documentation, the Studio, the Platform beta and a startup program;</li>
          <li>that the Platform beta request form was submitted (the form itself opens your email app, and none of its fields are sent to Mixpanel or to us);</li>
          <li>that the Studio’s Answer with Sarvam step was used, with whether an answer came back and two token counts.</li>
        </ul>
        Each event carries the page path and, where it applies, a fixed label such as <code>hero</code> or <code>mixpanel</code>. We use no Mixpanel SDK or cookie, store no identifier between visits, and ask Mixpanel not to geolocate your IP address. Nothing is sent if your browser signals Do Not Track or Global Privacy Control.</li>
      <li><strong>Sentry (when enabled).</strong> JavaScript error reports with the error type and stack trace. Quoted text and URLs in error messages are redacted, and there is no session replay, user identity, request data, or interaction trail.</li>
      <li><strong>Sentry for server errors (when enabled).</strong> If a Studio function fails unexpectedly, or a call to Sarvam fails, Sentry receives the error type, the stack trace (or, for Sarvam, only the HTTP status) and the function’s name. Request bodies, cookies, query strings and headers are removed before anything is sent, and quoted text, URLs and credentials in error messages are redacted. There is no tracing and no user identity.</li>
    </ul>

    <h2>What we never collect</h2>
    <p>Studio input or output, prompts, model responses, API keys, names, email addresses, or query strings are never sent to analytics or error reporting.</p>

    <h2>Studio</h2>
    <ul>
      <li>Text you submit is sent to the Studio API, compressed with LLMSlim and returned to you. It is not stored, logged, or used for training. Compression calls no model provider.</li>
      <li><strong>Answer with Sarvam (when available).</strong> Only when you press the button, our server sends the compressed context and your question to <a className="text-link" href="https://www.sarvam.ai/privacy-policy" target="_blank" rel="noreferrer">Sarvam AI</a>’s <code>sarvam-105b</code> model and returns its answer to you. We do not store the context, the question or the answer; Sarvam processes them under its own terms and privacy policy. To keep this paid step within its limits, the server keeps request, token and cost counters keyed by one-way keyed hashes of your network address (for IPv6, its /64 prefix) and of a random session ID, never the raw values. The cost shown is an estimate from LLMSlim’s dated price table, not Sarvam’s invoice.</li>
    </ul>

    <h2>In your browser</h2>
    <p>We store your light or dark theme preference, and whether you have finished the Studio tour, in local storage. If you use Answer with Sarvam, the server also sets one HttpOnly cookie holding a random session ID for 24 hours, used only for that step’s rate limits. Nothing else.</p>

    <h2>Questions</h2>
    <p>Contact the maintainer through <a className="text-link" href={siteConfig.github + "/security/policy"} target="_blank" rel="noreferrer">the project’s security policy</a> for anything privacy-related.</p>
  </main><SiteFooter /></div>
}
