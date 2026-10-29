import { Email, PolicyPage } from "@/components/site/PolicyPage"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Privacy Policy",
  description: "What llmslim.app measures and never collects, how Studio handles your text, how payments through Razorpay work, how LLMSlim Orbit will treat your content, and the service providers we use.",
  path: "/privacy",
})

export default function PrivacyPage() {
  const { company } = siteConfig
  return <PolicyPage title="Privacy Policy" lede={<>This policy covers the llmslim.app website, Studio, payments, and LLMSlim Orbit once it opens. LLMSlim is a product of {company.name}, {company.kind}, based in {company.location}. The open-source <code>llmslim</code> package sends nothing to us.</>}>
    <h2>What the website measures</h2>
    <ul>
      <li><strong>Vercel Web Analytics and Speed Insights.</strong> Aggregate page views and performance metrics, without cookies.</li>
      <li><strong>Mixpanel (when enabled).</strong> Ten product events and nothing else:
        <ul>
          <li>page views of the homepage, the Vault page and the Results page;</li>
          <li>clicks on links to the Core documentation, the Studio, the Vault beta and a startup program;</li>
          <li>clicks on a plan button on the Pricing page, with the plan, the currency and the billing period shown (the button opens your email app, and nothing you write is sent to Mixpanel);</li>
          <li>that the Vault beta request form was submitted (the form itself opens your email app, and none of its fields are sent to Mixpanel or to us);</li>
          <li>that the Studio’s Answer with Sarvam step was used, with whether an answer came back and two token counts.</li>
        </ul>
        Each event carries the page path and, where it applies, a fixed label such as <code>hero</code> or <code>mixpanel</code>. We use no Mixpanel SDK or cookie, store no identifier between visits, and ask Mixpanel not to geolocate your IP address. Nothing is sent if your browser signals Do Not Track or Global Privacy Control.</li>
      <li><strong>Sentry (when enabled).</strong> JavaScript error reports with the error type and stack trace. Quoted text and URLs in error messages are redacted, and there is no session replay, user identity, request data, or interaction trail.</li>
      <li><strong>Sentry for server errors (when enabled).</strong> If a Studio function fails unexpectedly, or a call to Sarvam fails, Sentry receives the error type, the stack trace (or, for Sarvam, only the HTTP status) and the function’s name. Request bodies, cookies, query strings and headers are removed before anything is sent, and quoted text, URLs and credentials in error messages are redacted. There is no tracing and no user identity.</li>
      <li><strong>Your country, for prices.</strong> The Pricing page reads the country that our host, Vercel, works out from your connection, only to show prices in rupees in India and in dollars elsewhere. It is not stored or sent anywhere.</li>
    </ul>

    <h2>What we never collect</h2>
    <p>Studio input or output, prompts, model responses, API keys, names, email addresses, or query strings are never sent to analytics or error reporting.</p>

    <h2>Studio</h2>
    <ul>
      <li>Text you submit is sent to the Studio API, compressed with LLMSlim and returned to you. It is not stored, logged, or used for training. Compression calls no model provider.</li>
      <li><strong>Answer with Sarvam (when available).</strong> Only when you press the button, our server sends the compressed context and your question to <a href="https://www.sarvam.ai/privacy-policy" target="_blank" rel="noreferrer">Sarvam AI</a>’s <code>sarvam-105b</code> model and returns its answer to you. We do not store the context, the question or the answer; Sarvam processes them under its own terms and privacy policy. To keep this paid step within its limits, the server keeps request, token and cost counters keyed by one-way keyed hashes of your network address (for IPv6, its /64 prefix) and of a random session ID, never the raw values. The cost shown is an estimate from LLMSlim’s dated price table, not Sarvam’s invoice.</li>
    </ul>

    <h2>In your browser</h2>
    <p>We store your light or dark theme preference, and whether you have finished the Studio tour, in local storage. If you use Answer with Sarvam, the server also sets one HttpOnly cookie holding a random session ID for 24 hours, used only for that step’s rate limits. Nothing else.</p>

    <h2>Emails you send us</h2>
    <p>The founding-list, beta and contact buttons on this site open your own email app; the site itself sends and stores nothing. When you email us, we keep your message and address to reply and to follow up on what you asked, and, if you joined the founding list, to tell you when LLMSlim Orbit opens. We do not sell or share them.</p>

    <h2>Payments</h2>
    <ul>
      <li>Payments are processed by <a href="https://razorpay.com/privacy/" target="_blank" rel="noreferrer">Razorpay</a>. Your card, UPI or bank details go to Razorpay, not to us, and Razorpay handles them under its own privacy policy. We never see or store your card number.</li>
      <li>We keep what invoices, tax records and your subscription need: the Razorpay payment and subscription IDs, amounts, currency, plan and billing period, and the billing details on your invoice, such as your name, email address, billing address and GSTIN if you give one.</li>
      <li>We keep these records for as long as Indian tax law requires, even after an account closes.</li>
    </ul>

    <h2>LLMSlim Orbit, once it opens</h2>
    <ul>
      <li>Orbit stores the content you send it, such as messages, imported history, memory and traces, only to provide the service to you.</li>
      <li>We do not use your content to train AI models, ours or anyone else’s.</li>
      <li>When you ask us to delete content, or close your account, we delete it within 30 days, except billing records the law requires us to keep.</li>
      <li>LLMSlim Vault runs in your own environment, so content stored in Vault never reaches us unless you share it with us.</li>
    </ul>

    <h2>Service providers</h2>
    <p>These companies process data for us today:</p>
    <ul>
      <li><strong>Vercel</strong> hosts the website and the Studio functions, and provides Web Analytics and Speed Insights.</li>
      <li><strong>Sentry</strong> receives error reports, when enabled.</li>
      <li><strong>Mixpanel</strong> receives the product events above, when enabled.</li>
      <li><strong>Razorpay</strong> processes payments.</li>
      <li><strong>Sarvam AI</strong> answers questions in Studio, only when you use Answer with Sarvam. A MongoDB database holds that step’s hashed rate-limit and cost counters.</li>
    </ul>
    <p>We will publish the list of providers that process LLMSlim Orbit customer content before Orbit opens.</p>

    <h2>The llmslim package, MCP server and plugins</h2>
    <p>The open-source library, the <code>llmslim mcp</code> memory server and the plugins for Claude Code and other MCP clients run on your machine. They send nothing to us and include no telemetry.</p>
    <ul>
      <li><strong>What is stored.</strong> The memory server stores the messages you or your agent ask it to remember, word for word, in a SQLite file on your machine (by default <code>~/.llmslim/memory.db</code>) or in a Postgres database you configure. The <code>forget</code> tool deletes one memory, and deleting the file removes all of them.</li>
      <li><strong>No model calls.</strong> Storing, recalling and fitting context call no model provider.</li>
      <li><strong>What reaches the network.</strong> Running through <code>uvx</code> downloads the package from PyPI the first time. The tokenizer downloads one encoding file the first time and caches it. Only if you run <code>llmslim wrap claude</code> or <code>llmslim proxy</code>, a local proxy forwards Claude Code’s own requests to Anthropic’s API.</li>
    </ul>

    <h2>Your requests</h2>
    <p>To ask what we hold about you, or to correct or delete it, email <Email to={siteConfig.businessEmail} />. We reply within 1 to 2 business days. To report a security issue, follow <a href={`${siteConfig.github}/security/policy`} target="_blank" rel="noreferrer">the project’s security policy</a>.</p>
  </PolicyPage>
}
