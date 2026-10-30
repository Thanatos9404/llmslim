import Link from "next/link"
import { Email, PolicyPage } from "@/components/site/PolicyPage"
import { startupProgramCount, startupProgramNames } from "@/components/landing/StartupPrograms"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "About",
  description: "LLMSlim gives AI agents memory and context with no LLM in the memory path. Three editions: the free, open-source Core, the hosted Orbit and the self-hosted Vault. A product of AMEYOR, Jaipur, India.",
  path: "/about",
})

export default function AboutPage() {
  const { company } = siteConfig
  return <PolicyPage title="About LLMSlim" lede="LLMSlim gives AI agents memory and context with no LLM in the memory path. It stores what users and agents say word for word, then returns the parts that answer a question within a token budget you set.">
    <h2>What LLMSlim does</h2>
    <p>An agent either forgets what it was told, or sends its whole history to the model again on every call and pays for it each time. LLMSlim sits between the agent and its model. It keeps every message as it was said and, when the agent needs context, selects what the next call needs: the turns that answer the question, the instructions that must stay, and the retrieved text that fits the budget.</p>
    <p>Because no model builds or reads the memory, storing and recalling make no model calls, the same input gives the same result, and nothing is turned into a fact that was never said. Instructions, retrieved documents and tool output keep their roles, so untrusted text is never promoted to an instruction. We publish our <Link href="/results">benchmark results</Link> with their code, including where LLMSlim loses.</p>

    <h2>Three editions</h2>
    <ul>
      <li><strong>LLMSlim Core.</strong> Free and open source under the MIT licence: a Python library, an MCP server and a small HTTP server, installed with <code>pip install llmslim</code>. Available today, version {siteConfig.coreVersion}. <Link href="/docs/getting-started">Read the docs</Link>.</li>
      <li><strong>LLMSlim Orbit.</strong> The hosted edition, which we run for you: a hosted memory API, a remote MCP server with OAuth for Claude.ai, ChatGPT, Cursor and Claude Code, team memory, a context console with traces and replay, a truth timeline, webhooks, SSO and governance. Orbit opens with LLMSlim 1.0. <Link href="/pricing">See the plans and join the founding list</Link>.</li>
      <li><strong>LLMSlim Vault.</strong> The self-hosted edition, run in your own VPC, so memory and traces stay in your environment. It was called LLMSlim Platform until October 2026 and is in private beta, version {siteConfig.vaultVersion}. <Link href="/vault">Learn about Vault</Link>.</li>
    </ul>

    <h2>Who builds it</h2>
    <p>LLMSlim is built in Jaipur by its founder, {company.proprietor}. It is a product of {company.name}, {company.kind}, of which {company.proprietor} is the proprietor.</p>
    <p>LLMSlim is part of {startupProgramCount} startup programs: {startupProgramNames}. They provide credits, tools and guidance.</p>

    <h2>Contact</h2>
    <ul>
      <li><strong>Business, billing and legal:</strong> <Email to={siteConfig.businessEmail} /></li>
      <li><strong>Product support:</strong> <Email to={siteConfig.supportEmail} /></li>
      <li><strong>The founder:</strong> <Email to={siteConfig.founderEmail} /></li>
    </ul>
    <p>More on the <Link href="/contact">contact page</Link>. {company.name}, {company.location}.</p>
  </PolicyPage>
}
