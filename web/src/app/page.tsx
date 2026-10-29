import Link from "next/link"
import type { ReactNode } from "react"
import { ProgramLogo, startupProgramCount, startupPrograms } from "@/components/landing/StartupPrograms"
import { Bento } from "@/components/landing/home/Bento"
import { CodeTabs, type CodeTab } from "@/components/landing/home/CodeTabs"
import { InstallPill } from "@/components/landing/home/CopyButton"
import { MarkImage } from "@/components/landing/home/MarkImage"
import { HeroDemo } from "@/components/landing/home/HeroDemo"
import { highlight, type CodeLanguage } from "@/components/landing/home/highlight"
import { ArrowRight, ArrowUpRight, PlusIcon } from "@/components/landing/home/icons"
import { Reveal, RevealGroup, RevealItem } from "@/components/landing/home/motion"
import { ProofBars, type ProofRow } from "@/components/landing/home/ProofBars"
import { TaglineReveal, type TaglineWord } from "@/components/landing/home/TaglineReveal"
import { WorksWith } from "@/components/landing/home/WorksWith"
import { SiteFooter } from "@/components/site/SiteFooter"
import { SiteHeader } from "@/components/site/SiteHeader"
import { PageView } from "@/components/site/Telemetry"
import { TrackedLink } from "@/components/site/TrackedLink"
import { siteConfig } from "@/config/site"
import { homeFaqs } from "@/data/home"
import { HISTORY_RECALL } from "@/data/landing-demo"
import { RACE } from "@/data/results-story"
import { contextBlocks } from "@/lib/landing-context"
import { constructMetadata, faqJsonLd, jsonLdScript } from "@/lib/seo"
import "./lp-base.css"
import "./landing.css"

export const metadata = constructMetadata({
  title: "LLMSlim: Memory for AI agents that no LLM rewrites",
  description: "Open source memory for AI agents. LLMSlim keeps every conversation turn word for word in SQLite or Postgres and returns the turns that answer, inside your token budget, with no LLM call to store or recall. MIT licensed.",
  path: "/",
  markdownPath: "/index.md",
})

/* ------------------------------------------------------------------ Content */

const tagline: TaglineWord[][] = [
  [{ text: "Every", accent: true }, { text: "word", accent: true }, { text: "is" }, { text: "kept." }],
  [{ text: "Only" }, { text: "the" }, { text: "turns" }, { text: "that" }, { text: "answer", accent: true }],
  [{ text: "reach" }, { text: "your" }, { text: "model." }],
  [{ text: "Never" }, { text: "a" }, { text: "token" }, { text: "over" }, { text: "budget.", accent: true }],
]

// The same stored turn, going into an extraction pipeline and coming back from LLMSlim (HISTORY_RECALL, real output).
const fridayTurn = contextBlocks(HISTORY_RECALL.text).flatMap((block) => block.kind === "session" ? block.lines : [])
  .find((line) => line.text.startsWith("I have never deployed on a Friday"))!

const locomo = RACE.find((set) => set.key === "locomo")!
const raceRow = (name: string) => locomo.rows.find((row) => row.name === name)!
// Default LLMSlim (no model) at about 2,500 tokens: level with Mem0 within noise, so the page claims parity, never a win.
const slim = raceRow("LLMSlim")
const mem0 = raceRow("Mem0")
const proofRows: ProofRow[] = [
  { name: "Whole history", detail: "every token, for reference", score: locomo.full.score, kind: "reference" },
  { name: "LLMSlim 0.9", detail: `$${slim.cost.toFixed(2)} per 1,000 questions`, score: slim.score, kind: "llmslim" },
  { name: "Mem0", detail: `$${mem0.cost.toFixed(2)} per 1,000 questions`, score: mem0.score, kind: "rival" },
  { name: "Zep", detail: `$${raceRow("Zep").cost.toFixed(2)} per 1,000 questions`, score: raceRow("Zep").score, kind: "rival" },
  { name: "LongLLMLingua", detail: "on its own 300 questions", score: raceRow("LongLLMLingua").score, kind: "rival", mark: "*" },
]

// Every snippet uses the public API as documented in README.md, docs/MCP.md and docs/SERVER.md.
const CODE: { id: string; label: string; file: string; language: CodeLanguage; code: string; note: ReactNode }[] = [
  {
    id: "python", label: "Python", file: "agent.py", language: "python",
    code: `from llmslim.memory import Memory

# A SQLite file, or a postgresql:// URL with llmslim[postgres]
memory = Memory("memory.db")

# Remember: each turn is stored word for word, with its date
memory.add(
    [{"role": "user", "content": "I prefer pnpm over npm."}],
    user_id="dev",
)

# Recall: the turns that answer, within the budget
context = memory.search(
    "Help me plan Friday's deploy.", user_id="dev", budget=300
)

# Ship: put it in your prompt as data, not instructions
print(context.text, context.tokens)`,
    note: <><code>pip install llmslim</code>, Python 3.9 or newer.</>,
  },
  {
    id: "mcp", label: "MCP", file: "claude_desktop_config.json", language: "json",
    code: `{
  "mcpServers": {
    "llmslim": {
      "command": "uvx",
      "args": ["--from", "llmslim[mcp]", "llmslim", "mcp"]
    }
  }
}`,
    note: <>The same block works in Cursor&apos;s <code>~/.cursor/mcp.json</code>. In Claude Code: <code>claude mcp add llmslim -- uvx --from &quot;llmslim[mcp]&quot; llmslim mcp</code>. Tools: <code>remember</code>, <code>recall</code>, <code>list_memories</code>, <code>forget</code> and <code>fit_context</code>.</>,
  },
  {
    id: "http", label: "HTTP", file: "terminal", language: "bash",
    code: `pip install "llmslim[server]"
llmslim serve   # http://127.0.0.1:8080

curl -s localhost:8080/v1/memories \\
  -H 'content-type: application/json' \\
  -d '{"user_id": "dev", "messages": "I prefer pnpm over npm."}'

curl -s localhost:8080/v1/memories/search \\
  -H 'content-type: application/json' \\
  -d '{"user_id": "dev", "budget": 300,
       "query": "Which package manager do I use?"}'`,
    note: <>One process and one SQLite file. It needs an API key to listen beyond localhost.</>,
  },
  {
    id: "ts", label: "TypeScript", file: "agent.ts", language: "ts",
    code: `import { LLMSlim } from "llmslim";

// llmslim serve at http://127.0.0.1:8080, or LLMSLIM_BASE_URL
const slim = new LLMSlim();

await slim.memories.add({
  userId: "dev",
  messages: "I prefer pnpm over npm.",
});

const context = await slim.memories.search({
  userId: "dev",
  query: "Which package manager do I use?",
  budget: 300,
});`,
    note: <><code>npm install llmslim</code>, Node 18 or newer, against <code>llmslim serve</code>.</>,
  },
]
const codeTabs: CodeTab[] = CODE.map(({ language, ...tab }) => ({ ...tab, body: highlight(tab.code, language) }))

// Phrases in the FAQ answers that link to the page they name.
const FAQ_LINKS: [phrase: string, href: string][] = [
  ["results page", "/results"],
  ["pricing page", "/pricing"],
  ["MCP guide", `${siteConfig.github}/blob/main/docs/MCP.md`],
]
function faqAnswer(answer: string): ReactNode[] {
  const parts: ReactNode[] = [answer]
  for (const [phrase, href] of FAQ_LINKS) {
    const at = parts.findIndex((part) => typeof part === "string" && part.includes(phrase))
    if (at < 0) continue
    const [before, ...rest] = (parts[at] as string).split(phrase)
    const link = href.startsWith("http") ? <a key={href} href={href} target="_blank" rel="noreferrer">{phrase}</a> : <Link key={href} href={href}>{phrase}</Link>
    parts.splice(at, 1, before, link, rest.join(phrase))
  }
  return parts
}

/* ------------------------------------------------------------------ Pieces */

/** The page's one call to action, identical in the hero and at the end. */
function Actions({ location }: { location: "hero" | "final" }) {
  return <>
    <div className="lp-actions">
      <TrackedLink className="lp-btn" href="/docs/getting-started" event="core_docs_clicked" properties={{ location }}>
        Get started free <ArrowRight size={16} />
      </TrackedLink>
      <InstallPill />
    </div>
    <p className="lp-meta">
      <span>Free and MIT licensed</span>
      <span>7,000+ downloads</span>
      <Link href="/pricing" className="lp-meta-link">See pricing <ArrowRight size={14} /></Link>
    </p>
  </>
}

function Head({ kicker, title, id, children, center }: { kicker: string; title: ReactNode; id: string; children?: ReactNode; center?: boolean }) {
  return <Reveal className={center ? "lp-head is-center" : "lp-head"}>
    <p className="lp-kicker">{kicker}</p>
    <h2 id={id} className="lp-h2">{title}</h2>
    {children && <p className="lp-head-body">{children}</p>}
  </Reveal>
}

/* ------------------------------------------------------------------ Page */

export default function Home() {
  return <div className="premium lp">
    <PageView event="homepage_view" />
    <SiteHeader />
    <main id="main-content">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(faqJsonLd(homeFaqs)) }} />

      {/* The headline is never hidden or animated in, so it paints first: it is the page's largest paint. */}
      <section className="lp-hero" aria-labelledby="hero-title">
        <div className="lp-sky" aria-hidden="true"><div className="lp-aurora" /><div className="lp-stars" /></div>
        <div className="lp-wrap lp-hero-copy">
          <Link className="lp-chip" href="/results">
            <span className="lp-chip-tag">LoCoMo</span>
            <span className="lp-chip-text">Accuracy on par with Mem0, at a third of the cost</span>
            <ArrowRight size={14} />
          </Link>
          <h1 id="hero-title" className="lp-h1">Memory for AI agents <br className="lp-br" />that no LLM rewrites.</h1>
          <p className="lp-lead">Open source memory that keeps every conversation turn word for word, then returns the turns that answer, inside your token budget. No LLM call to store or recall.</p>
          <Actions location="hero" />
        </div>
        <div className="lp-wrap lp-hero-stage"><div className="lp-horizon" aria-hidden="true" /><HeroDemo /></div>
      </section>

      <WorksWith />

      <section className="lp-section lp-tagline-section" aria-labelledby="tagline-title">
        <div className="lp-wrap"><TaglineReveal id="tagline-title" lines={tagline} /></div>
      </section>

      <section className="lp-section lp-why" aria-labelledby="why-title">
        <div className="lp-wrap">
          <Head kicker="Why word for word" id="why-title" title={<>Summaries drift. <br className="lp-br" />Words don&apos;t.</>} center>
            Most agent memory asks a model to rewrite each conversation into short facts. LLMSlim keeps what was said, and picks what matters when the question arrives.
          </Head>
          <div className="lp-versus">
            <Reveal as="article" className="lp-vs is-old lp-glass">
              <p className="lp-card-kicker">Extracted memory</p>
              <h3>A model rewrites every turn</h3>
              <div className="lp-flow" aria-hidden="true">
                <span className="lp-flow-turn">{fridayTurn.text}</span>
                <span className="lp-flow-node">LLM call</span>
                <span className="lp-flow-out"><i /><i /><i /></span>
              </div>
              <ul className="lp-points">
                <li>A model call on every write</li>
                <li>The words people used are gone</li>
                <li>A newer fact can quietly replace an older one</li>
                <li>A summary can state things nobody said</li>
              </ul>
            </Reveal>
            <Reveal as="article" className="lp-vs is-new lp-glass" delay={0.12}>
              <p className="lp-card-kicker">LLMSlim</p>
              <h3>Every turn, kept as it was said</h3>
              <div className="lp-flow" aria-hidden="true">
                <span className="lp-flow-turn">{fridayTurn.text}</span>
                <span className="lp-flow-node">SQLite or Postgres</span>
                <span className="lp-flow-kept"><span className="lp-stamp">[{fridayTurn.stamp}] {fridayTurn.role}:</span> {fridayTurn.text}</span>
              </div>
              <ul className="lp-points">
                <li>A database write, no model call</li>
                <li>The exact words, with their date</li>
                <li>Statements that may conflict come back side by side</li>
                <li>Picked at read time, inside your budget</li>
              </ul>
            </Reveal>
          </div>
        </div>
      </section>

      <section className="lp-section lp-benefits" aria-labelledby="bento-title">
        <div className="lp-wrap">
          <Head kicker="What comes back" id="bento-title" title={<>The turns that answer, <br className="lp-br" />in the budget you set.</>} center />
          <Bento />
        </div>
      </section>

      <section className="lp-section lp-how-section" aria-labelledby="how-title">
        <div className="lp-wrap lp-how">
          <div className="lp-how-copy">
            <Head kicker="How it works" id="how-title" title="Remember, recall, ship." />
            <RevealGroup as="ol" className="lp-steps">
              <RevealItem as="li">
                <h3>Remember</h3>
                <p>Add each turn as it happens. It is stored word for word with its date, in SQLite or Postgres. No model reads it on the way in.</p>
              </RevealItem>
              <RevealItem as="li">
                <h3>Recall</h3>
                <p>Ask with the question and a token budget. LLMSlim ranks the stored turns and returns the ones that answer, with standing requests, preferences and possible conflicts in their own sections.</p>
              </RevealItem>
              <RevealItem as="li">
                <h3>Ship</h3>
                <p>Put the context in your prompt as data, not instructions. The same history and question always give the same context, so recall is easy to test.</p>
              </RevealItem>
            </RevealGroup>
          </div>
          <Reveal className="lp-how-code" delay={0.1}><CodeTabs tabs={codeTabs} label="Ways to use LLMSlim memory" /></Reveal>
        </div>
      </section>

      <section className="lp-section lp-proof-section" aria-labelledby="proof-title">
        <div className="lp-wrap">
          <Head kicker="Proof" id="proof-title" title="Accuracy on par with Mem0 on long conversations, at a third of the cost." center>
            On LoCoMo, LLMSlim answered {slim.score.toFixed(1)}% of questions and Mem0 {mem0.score.toFixed(1)}%: the same within noise. At a 1,000 token budget Mem0 is ahead, 88.7% to 87.5%.
          </Head>
          <div className="lp-proof">
            <Reveal className="lp-proof-panel lp-glass">
              <div className="lp-proof-top">
                <span>LoCoMo, questions answered correctly</span>
                <span className="lp-num">1,307 questions</span>
              </div>
              <ProofBars rows={proofRows} caption={`LoCoMo accuracy: whole history ${locomo.full.score.toFixed(1)}%, LLMSlim 0.9 ${slim.score.toFixed(1)}%, Mem0 ${mem0.score.toFixed(1)}%, Zep ${raceRow("Zep").score.toFixed(1)}%, LongLLMLingua ${raceRow("LongLLMLingua").score.toFixed(1)}% on its own 300 questions.`} />
              <p className="lp-proof-note">
                Questions held out from tuning, about 2,500 tokens of context each, every answer read by Claude Haiku 5.5. Costs are end to end, per 1,000 questions. *LongLLMLingua was run on its own 300 questions.
              </p>
            </Reveal>
            <Reveal className="lp-proof-side" delay={0.1}>
              <div className="lp-proof-stat lp-glass">
                <span className="lp-proof-label">Cost per 1,000 questions</span>
                <span className="lp-proof-value"><b className="lp-num">${slim.cost.toFixed(2)}</b><span>against <b className="lp-num">${mem0.cost.toFixed(2)}</b> for Mem0</span></span>
              </div>
              <div className="lp-proof-stat lp-glass">
                <span className="lp-proof-label">Open source, MIT</span>
                <span className="lp-proof-value"><b className="lp-num">7,000+</b><span>downloads</span></span>
              </div>
              <Link className="lp-proof-link" href="/results">See every result, with its method <ArrowUpRight size={16} /></Link>
            </Reveal>
          </div>

          <Reveal className="lp-programs">
            <p className="lp-programs-title">Supported by {startupProgramCount} startup programs</p>
            <ul aria-label={`${startupProgramCount} startup programs`}>
              {startupPrograms.map((program) => <li key={program.id}>
                <TrackedLink href={program.href} target="_blank" rel="noreferrer" aria-label={program.name} title={program.name}
                  event="startup_program_clicked" properties={{ program: program.id }}>
                  <ProgramLogo program={program} />
                </TrackedLink>
              </li>)}
            </ul>
          </Reveal>
        </div>
      </section>

      <section className="lp-section lp-editions-section" aria-labelledby="editions-title">
        <div className="lp-wrap">
          <Head kicker="Editions" id="editions-title" title={<>Start free. <br className="lp-br" />Add hosting when you need it.</>} center />
          <RevealGroup className="lp-editions">
            <RevealItem as="article" className="lp-edition is-core lp-glass">
              <p className="lp-edition-tag">Free and MIT licensed</p>
              <h3>LLMSlim Core</h3>
              <p>The memory engine in your own process: the Python library, the MCP server, the HTTP server and the TypeScript client.</p>
              <code className="lp-edition-code">pip install llmslim</code>
              <TrackedLink className="lp-btn is-small" href="/docs/getting-started" event="core_docs_clicked" properties={{ location: "editions" }}>Get started free <ArrowRight size={14} /></TrackedLink>
              <p className="lp-edition-foot lp-mono">Version {siteConfig.coreVersion}</p>
            </RevealItem>
            <RevealItem as="article" className="lp-edition lp-glass">
              <p className="lp-edition-tag">Opening with LLMSlim 1.0</p>
              <h3>LLMSlim Orbit</h3>
              <p>The hosted edition, run by us: a hosted memory API, a remote MCP server with OAuth, team memory and a context console with traces and replay.</p>
              <Link className="lp-btn is-ghost is-small" href="/pricing">See Orbit plans <ArrowRight size={14} /></Link>
              <p className="lp-edition-foot">Not open yet. Nothing is charged before it opens.</p>
            </RevealItem>
            <RevealItem as="article" className="lp-edition lp-glass">
              <p className="lp-edition-tag">Self hosted, in beta</p>
              <h3>LLMSlim Vault</h3>
              <p>LLMSlim in your own cloud, with a verifiable timeline of what your agents were told and a trace for every context decision.</p>
              <TrackedLink className="lp-btn is-ghost is-small" href="/vault" event="platform_beta_clicked" properties={{ location: "editions" }}>Explore Vault <ArrowRight size={14} /></TrackedLink>
              <p className="lp-edition-foot lp-mono">Beta {siteConfig.vaultVersion}</p>
            </RevealItem>
          </RevealGroup>
          <p className="lp-editions-foot"><Link href="/pricing">Compare plans and limits on the pricing page <ArrowUpRight size={14} /></Link></p>
        </div>
      </section>

      <section className="lp-section lp-faq-section" id="faq" aria-labelledby="faq-title">
        <div className="lp-wrap lp-faq">
          <Head kicker="Questions" id="faq-title" title="Before you install">
            Anything else? Ask in <a href={`${siteConfig.github}/issues`} target="_blank" rel="noreferrer">GitHub issues</a> or write to <a href={`mailto:${siteConfig.supportEmail}`}>{siteConfig.supportEmail}</a>.
          </Head>
          <div className="lp-faq-list">
            {homeFaqs.map(([question, answer]) => <details key={question} className="lp-faq-item">
              <summary><span>{question}</span><PlusIcon size={16} className="lp-faq-icon" /></summary>
              <p>{faqAnswer(answer)}</p>
            </details>)}
          </div>
        </div>
      </section>

      <section className="lp-final" aria-labelledby="final-title">
        <div className="lp-wrap">
          <Reveal className="lp-final-panel lp-glass">
            <div className="lp-final-glow" aria-hidden="true" />
            <MarkImage size={44} className="lp-final-mark" />
            <h2 id="final-title" className="lp-h2">Give your agents a memory <br className="lp-br" />they can quote.</h2>
            <p className="lp-lead">Free and open source. Install it, then point your agent or any MCP client at it.</p>
            <Actions location="final" />
          </Reveal>
        </div>
      </section>
    </main>
    <SiteFooter />
  </div>
}
