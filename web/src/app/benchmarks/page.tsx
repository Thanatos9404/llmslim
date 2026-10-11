import Link from "next/link"
import { ArrowUpRight } from "lucide-react"
import { ResultBars } from "@/components/benchmarks/ResultBars"
import { Reveal } from "@/components/landing/Premium"
import { StatsBand, type Stat } from "@/components/landing/Visuals"
import { BENCHMARK_SUITES } from "@/data/benchmarks"
import { AGENT_FINDINGS, CORE_VERSION_TESTED, HEAD_TO_HEAD, LIVE_DATE, LIVE_SUITES, METHOD_NOTES, PLATFORM_VERSION_TESTED, PUBLISHED } from "@/data/live-benchmarks"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Benchmarks | LLMSlim",
  description: "LLMSlim on seven public benchmarks, head to head with LLMLingua-2 and LongLLMLingua at the same token budget: scores, tokens, cost, confidence intervals, weak spots and raw results.",
  path: "/benchmarks",
  markdownPath: "/benchmarks.md",
  // The share images are benchmarks/opengraph-image.tsx and twitter-image.tsx.
  image: null,
})

const stats: Stat[] = [
  { topic: "Chat memory", value: "62", unit: "×", label: "lower cost per question over long chat histories, at Haiku 5.5 list prices", source: "LongMemEval, 76.7% vs 82.2% with the whole history; 14× fewer tokens",
    meter: { before: { name: "Whole history", value: 90.72, display: "$90.72" }, after: { name: "LLMSlim", value: 1.45, display: "$1.45" }, max: 90.72 } },
  { topic: "Long documents", value: "3", unit: "×", label: "fewer tokens on long documents, for the same score", source: "LongBench v1, 54.9 vs 54.9 with full context",
    meter: { before: { name: "Full document", value: 15532, display: "15.5k tokens" }, after: { name: "LLMSlim", value: 5232, display: "5.2k" }, max: 15532 } },
  { topic: "Retrieval", value: "+23", label: "points over truncation at the same token budget", source: "NaturalQuestions, 20 passages, 25% budget",
    meter: { before: { name: "Cut to fit", value: 52, display: "52.0" }, after: { name: "LLMSlim", value: 75, display: "75.0" }, max: 100 } },
  { topic: "Agent turns", value: "0", label: "repeated tool calls across 1,054 agent turns", source: "InjecAgent, Platform agent turns",
    meter: { before: { name: "Before", value: 50, display: "50" }, after: { name: "Agent turn", value: 0, display: "0" }, max: 50 } },
]

export default function BenchmarksPage() {
  return <div className="bm-page">
    <header className="bm-hero">
      <p className="p-kicker">Benchmarks · {LIVE_DATE}</p>
      <h1>Measured on public benchmarks. <span>Every number published.</span></h1>
      <p className="bm-lede">Public datasets, official prompts and scoring, and the same model for every configuration. Only the context changes: the full context, LLMSlim, and truncation cut to exactly LLMSlim&apos;s token count.</p>
      <p className="bm-story-link"><Link className="text-link" href="/results">Prefer the guided version? See the results as a story <ArrowUpRight size={14} /></Link></p>
      <p className="bm-versions">LLMSlim Core {CORE_VERSION_TESTED} · LLMSlim Platform {PLATFORM_VERSION_TESTED} · harness and raw results in the <a href={`${siteConfig.github}/tree/main/benchmarks/live`} target="_blank" rel="noreferrer">public repository <ArrowUpRight size={13} /></a></p>
    </header>

    <section className="bm-band" aria-label="Headline results"><StatsBand stats={stats} /></section>

    <section className="bm-suites" aria-label="Results by benchmark">
      {LIVE_SUITES.map((suite) => <article key={suite.id} id={suite.id} className="bm-suite">
        <Reveal className="bm-suite-copy">
          <p className="bm-suite-meta">{suite.n} · {suite.metric}</p>
          <h2>{suite.name}</h2>
          <p className="bm-what">{suite.what}</p>
          <p className="bm-takeaway">{suite.takeaway}</p>
          {suite.caveat && <p className="bm-caveat"><span>Note</span>{suite.caveat}</p>}
        </Reveal>
        <div className="bm-results">
          <ResultBars arms={suite.arms} metric={suite.metric} />
          {suite.fresh && <div className="bm-fresh">
            <p className="bm-fresh-label"><strong>Fresh questions, never used in development</strong><span>{suite.fresh.n}</span></p>
            <ResultBars arms={suite.fresh.arms} metric={suite.metric} compact />
          </div>}
        </div>
      </article>)}
    </section>

    <section className="bm-section" aria-labelledby="h2h-title">
      <Reveal className="p-head"><p className="p-kicker">Head to head</p><h2 id="h2h-title">Other compressors, same reader. <span>Same questions, same budget.</span></h2>
        <p className="p-body">We ran the best-known open-source prompt compressors ourselves, with the same reader for every compressed context and the same token budget for each.</p></Reveal>
      <div className="bm-table-wrap"><table className="bm-table bm-h2h">
        <thead><tr><th scope="col">Compressor</th><th scope="col">Model it runs</th><th scope="col">{HEAD_TO_HEAD.columns[0]}</th><th scope="col">{HEAD_TO_HEAD.columns[1]}</th><th scope="col">{HEAD_TO_HEAD.columns[2]}</th><th scope="col">Tokens kept</th><th scope="col">Time per question</th></tr></thead>
        <tbody>{HEAD_TO_HEAD.rows.map((row) => <tr key={row.system}>
          <th scope="row" className={row.best ? "is-best" : undefined}>{row.system}</th><td>{row.model}</td>
          <td className={`num${row.best ? " is-best" : ""}`}>{row.scoreA}</td><td className={`num${row.best ? " is-best" : ""}`}>{row.scoreB}</td><td className={`num${row.best ? " is-best" : ""}`}>{row.scoreAll}</td>
          <td className="num">{row.tokens}</td><td>{row.time}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="bm-note">{HEAD_TO_HEAD.note}</p>
      <p className="bm-note bm-sources">Sources and reruns: {HEAD_TO_HEAD.sources.map((source, index) => <span key={source.url}>{index > 0 && " · "}<a href={source.url} target="_blank" rel="noreferrer">{source.label}</a></span>)}</p>
    </section>

    <section className="bm-section" aria-labelledby="agents-title">
      <Reveal className="p-head"><p className="p-kicker">Agents</p><h2 id="agents-title">Where compression does not help. <span>Yet.</span></h2></Reveal>
      {AGENT_FINDINGS.map((finding) => <div key={finding.name} className="bm-agent">
        <div className="bm-agent-copy"><h3>{finding.name}</h3><p>{finding.what}</p><p className="bm-takeaway">{finding.takeaway}</p></div>
        <dl className="bm-rows">{finding.rows.map((row) => <div key={row.arm}><dt>{row.arm}</dt><dd><strong>{row.result}</strong><span>{row.detail}</span></dd></div>)}</dl>
      </div>)}
    </section>

    <section className="bm-section" aria-labelledby="others-title">
      <Reveal className="p-head"><p className="p-kicker">Other systems</p><h2 id="others-title">Published results, side by side. <span>With their readers.</span></h2>
        <p className="p-body">These numbers come from each project&apos;s paper or a third-party re-run, with different reader models. Compare each system&apos;s gap to its own full-context baseline, not raw scores across models.</p></Reveal>
      <div className="bm-table-wrap"><table className="bm-table">
        <thead><tr><th scope="col">System</th><th scope="col">Benchmark</th><th scope="col">Reader</th><th scope="col">Score</th><th scope="col">Full context</th><th scope="col">Tokens</th><th scope="col">Source</th></tr></thead>
        <tbody>{PUBLISHED.map((row) => <tr key={`${row.system}-${row.benchmark}`}>
          <th scope="row">{row.system}</th><td>{row.benchmark}</td><td>{row.reader}</td><td>{row.score}</td><td>{row.fullContext}</td><td>{row.tokens}</td>
          <td><a href={row.url} target="_blank" rel="noreferrer">{row.source} <ArrowUpRight size={12} /></a></td>
        </tr>)}</tbody>
      </table></div>
    </section>

    <section className="bm-section bm-method" aria-labelledby="method-title">
      <Reveal className="p-head"><p className="p-kicker">How we measured</p><h2 id="method-title">Same model. Same questions. <span>Only the context changes.</span></h2></Reveal>
      <ol className="p-notes">{METHOD_NOTES.map((note, index) => <li key={note}><span className="p-note-index">{String(index + 1).padStart(2, "0")}</span><p>{note}</p></li>)}</ol>
    </section>

    <section className="bm-section" aria-labelledby="offline-title">
      <h2 id="offline-title" className="bm-small-title">Earlier offline suites</h2>
      <ul className="int-list">{Object.values(BENCHMARK_SUITES).map((suite) => <li key={suite.slug}>
        <Link className="int-row bm-offline-row" href={`/benchmarks/${suite.slug}`}><span className="int-name">{suite.title}<small>deterministic, no model call</small></span><span className="int-tagline">{suite.subtitle}</span><ArrowUpRight className="int-arrow" size={18} aria-hidden="true" /></Link>
      </li>)}</ul>
    </section>
  </div>
}
