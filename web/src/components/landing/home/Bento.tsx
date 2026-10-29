import Link from "next/link"
import type { ReactNode } from "react"
import { DEMO_VERSION, HISTORY_RECALL, JAPANESE_RECALL, PLAN_RECALL, STORED_TURNS, SWEEP, SWEEP_OVER } from "@/data/landing-demo"
import { RACE } from "@/data/results-story"
import { contextBlocks } from "@/lib/landing-context"
import { GlassField } from "./GlassField"
import { RevealGroup, RevealItem } from "./motion"
import { SweepChart } from "./SweepChart"
import { ArrowUpRight } from "./icons"

const locomo = RACE.find((set) => set.key === "locomo")!
const slim = locomo.rows.find((row) => row.name === "LLMSlim + reranker")!
const mem0 = locomo.rows.find((row) => row.name === "Mem0")!

const conflicts = contextBlocks(HISTORY_RECALL.text).find((block) => block.kind === "section")!
const japaneseLine = contextBlocks(JAPANESE_RECALL.text).flatMap((block) => block.lines).find((line) => /[぀-ヿ一-鿿]/.test(line.text))!

/** Marks the runs of two or more characters that `text` shares with `query`, the way the eye matches them. */
function shared(text: string, query: string): ReactNode[] {
  const hit = new Array<boolean>(text.length).fill(false)
  for (let start = 0; start < text.length; start++) {
    for (let end = text.length; end > start + 1; end--) {
      if (query.includes(text.slice(start, end))) { hit.fill(true, start, end); break }
    }
  }
  const out: ReactNode[] = []
  let at = 0
  while (at < text.length) {
    let end = at
    while (end < text.length && hit[end] === hit[at]) end++
    const piece = text.slice(at, end)
    out.push(hit[at] ? <mark key={at}>{piece}</mark> : piece)
    at = end
  }
  return out
}

function Card({ className = "", kicker, title, children, body }: { className?: string; kicker: string; title: string; body: ReactNode; children: ReactNode }) {
  return <RevealItem as="article" className={`lp-card lp-glass ${className}`}>
    <div className="lp-card-copy">
      <p className="lp-card-kicker">{kicker}</p>
      <h3>{title}</h3>
      <p className="lp-card-body">{body}</p>
    </div>
    <div className="lp-card-demo">{children}</div>
  </RevealItem>
}

/** Five glass cards, each a small demo of one thing LLMSlim does, with real 0.12.0 output. */
export function Bento() {
  return <GlassField className="lp-bento-field">
    <RevealGroup className="lp-bento">
      <Card className="lp-card-wide" kicker="Never over budget" title="The budget is a hard limit"
        body={<>We asked for the deploy plan at {SWEEP.length} budgets, from {SWEEP[0][0]} to {SWEEP[SWEEP.length - 1][0]} tokens. {SWEEP_OVER === 0 ? "Not one answer went over." : `${SWEEP_OVER} went over.`} Drag to pick a budget.</>}>
        <SweepChart points={SWEEP} question={PLAN_RECALL.question} />
      </Card>

      <Card kicker="Conflicts side by side" title="Both sides of a change"
        body="Ask whether something happened, and the statements that may conflict come back together, oldest first.">
        <p className="lp-demo-q"><span className="lp-sr">Question: </span>{HISTORY_RECALL.question}</p>
        <p className="lp-demo-title">{conflicts.title}</p>
        <ol className="lp-conflicts">
          {conflicts.lines.map((line) => <li key={line.stamp}>
            <span className="lp-stamp">{line.stamp}</span>
            <span>{line.text}</span>
          </li>)}
        </ol>
      </Card>

      <Card kicker="Any language" title="Matched on its letters"
        body="A question in another script finds the turn in that script. The highlighted characters are the ones the two share.">
        <p className="lp-demo-q" lang="ja"><span className="lp-sr" lang="en">Question: </span>{JAPANESE_RECALL.question}</p>
        <p className="lp-demo-answer">
          <span className="lp-stamp">[{japaneseLine.stamp}] {japaneseLine.role}:</span>
          <span lang="ja">{shared(japaneseLine.text, JAPANESE_RECALL.question)}</span>
        </p>
        <p className="lp-demo-meta lp-num">{JAPANESE_RECALL.tokens} of {JAPANESE_RECALL.budget} tokens</p>
      </Card>

      <Card kicker="No LLM calls" title="A third of the cost"
        body={<>Storing is a database write and recall is ranking code, so no model call is paid for either. On LoCoMo, a thousand questions cost:</>}>
        <ul className="lp-cost">
          <li data-kind="llmslim"><span>LLMSlim 0.9 with reranker</span><b className="lp-num">${slim.cost.toFixed(2)}</b><i style={{ width: `${(slim.cost / mem0.cost) * 100}%` }} /></li>
          <li><span>Mem0</span><b className="lp-num">${mem0.cost.toFixed(2)}</b><i style={{ width: "100%" }} /></li>
        </ul>
        <Link className="lp-card-link" href="/results">End to end, with answers by Claude Haiku 5.5. See the results <ArrowUpRight size={14} /></Link>
      </Card>

      <Card kicker="Runs everywhere" title="Your stack, your storage"
        body="The same memory as a Python library, an MCP server, an HTTP server or a TypeScript client.">
        <ul className="lp-runs">
          <li><span>SQLite</span><code>Memory(&quot;memory.db&quot;)</code></li>
          <li><span>Postgres</span><code>Memory(&quot;postgresql://…&quot;)</code></li>
          <li><span>MCP</span><code>llmslim mcp</code></li>
          <li><span>HTTP</span><code>llmslim serve</code></li>
          <li><span>TypeScript</span><code>npm install llmslim</code></li>
        </ul>
      </Card>
    </RevealGroup>
    <p className="lp-bento-foot">Real output from llmslim {DEMO_VERSION}, on the same {STORED_TURNS.length} stored turns as the example at the top.</p>
  </GlassField>
}
