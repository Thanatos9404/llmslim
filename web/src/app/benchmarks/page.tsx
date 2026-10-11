import Link from "next/link"
import { ArrowUpRight } from "lucide-react"
import { ResultBars } from "@/components/benchmarks/ResultBars"
import { Reveal } from "@/components/landing/Premium"
import { StatsBand, type Stat } from "@/components/landing/Visuals"
import { BENCHMARK_SUITES } from "@/data/benchmarks"
import { AGENT_FINDINGS, CORE_VERSION_TESTED, LIVE_DATE, LIVE_MODEL, LIVE_SUITES, METHOD_NOTES, PLATFORM_VERSION_TESTED, PUBLISHED } from "@/data/live-benchmarks"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Benchmarks | LLMSlim",
  description: `LLMSlim measured on ${LIVE_MODEL} with LongMemEval, LongBench v1 and v2, HotpotQA, NaturalQuestions, SWE-bench Verified and InjecAgent: scores, tokens and cost against full context and truncation, weak spots included.`,
  path: "/benchmarks",
  markdownPath: "/benchmarks.md",
})

const stats: Stat[] = [
  { value: "62", unit: "×", label: "lower cost per question over long chat histories", note: "LongMemEval · 70% vs 82% with full history" },
  { value: "72", unit: "%", label: "fewer tokens on long documents and codebases", note: "LongBench v2 · 53% vs 60% accuracy" },
  { value: "+7.7", label: "points over truncation at the same token budget", note: "LongBench v1 · 95% CI +2.7 to +12.9" },
  { value: "45", unit: "%", label: "lower cost on multi-hop retrieval QA", note: "HotpotQA · F1 68.0 vs 74.9" },
]

export default function BenchmarksPage() {
  return <div className="bm-page">
    <header className="bm-hero">
      <p className="p-kicker">Benchmarks · {LIVE_MODEL} · {LIVE_DATE}</p>
      <h1>Measured on a real model. <span>Weak spots included.</span></h1>
      <p className="bm-lede">Public datasets, official prompts and scoring, and the same model for every configuration. Only the context changes: the full context, LLMSlim, and truncation cut to exactly LLMSlim&apos;s token count.</p>
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
          {suite.caveat && <p className="bm-caveat"><span>Weak spot</span>{suite.caveat}</p>}
        </Reveal>
        <ResultBars arms={suite.arms} metric={suite.metric} />
      </article>)}
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
