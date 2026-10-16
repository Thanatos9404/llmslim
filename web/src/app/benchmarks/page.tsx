import Link from "next/link"
import { ArrowUpRight } from "lucide-react"
import { ResultBars } from "@/components/benchmarks/ResultBars"
import { Reveal } from "@/components/landing/Premium"
import { StatsBand, type Stat } from "@/components/landing/Visuals"
import { BENCHMARK_SUITES } from "@/data/benchmarks"
import { AGENT_FINDINGS, CORE_VERSION_LONG_DOCS, CORE_VERSION_TESTED, HEAD_TO_HEAD, LIVE_DATE, LIVE_SUITES, LONG_DOC_SUITES, METHOD_NOTES, PLATFORM_VERSION_TESTED, PUBLISHED, ROUND3_REPORT, WEAK_SPOTS, type LiveSuite } from "@/data/live-benchmarks"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({
  title: "Benchmarks | LLMSlim",
  description: "LLMSlim Core 0.9 against Mem0, Zep, LLMLingua-2, LongLLMLingua and RAG on held-out test questions, cost first: accuracy and the cost of 1,000 questions, confidence intervals, weak spots and raw results.",
  path: "/benchmarks",
  markdownPath: "/benchmarks.md",
  // The share images are benchmarks/opengraph-image.tsx and twitter-image.tsx.
  image: null,
})

const stats: Stat[] = [
  { topic: "Chat memory", value: "2.8", unit: "×", label: "lower cost than Mem0 on LoCoMo, with more questions right", source: "LoCoMo, 93.0% vs 91.0% for Mem0 at about 2,500 tokens",
    meter: { before: { name: "Mem0", value: 2.66, display: "$2.66" }, after: { name: "LLMSlim", value: 0.95, display: "$0.95" }, max: 2.66 } },
  { topic: "Long histories", value: "42", unit: "×", label: "lower cost than the whole chat history, at the same accuracy", source: "LongMemEval, 77.8% for both at 10,000 tokens",
    meter: { before: { name: "Whole history", value: 90.21, display: "$90.21" }, after: { name: "LLMSlim", value: 2.13, display: "$2.13" }, max: 90.21 } },
  { topic: "Memory systems", value: "212", unit: "×", label: "lower cost than Mem0 on its own LongMemEval questions, as accurate", source: "Mem0's 60-question sample, 78.3% vs 76.7%",
    meter: { before: { name: "Mem0", value: 220.88, display: "$220.88" }, after: { name: "LLMSlim", value: 1.04, display: "$1.04" }, max: 220.88 } },
  { topic: "Compressors", value: "4", unit: "×", label: "lower cost than LongLLMLingua on retrieval, with more questions right", source: "NaturalQuestions, 72.7% vs 70.5% on its 1,000-question sample",
    meter: { before: { name: "LongLLMLingua", value: 1.32, display: "$1.32" }, after: { name: "LLMSlim", value: 0.33, display: "$0.33" }, max: 1.32 } },
]

function Suite({ suite }: { suite: LiveSuite }) {
  return <article id={suite.id} className="bm-suite">
    <Reveal className="bm-suite-copy">
      <p className="bm-suite-meta">{suite.n} · {suite.metric}</p>
      <h2>{suite.name}</h2>
      <p className="bm-what">{suite.what}</p>
      <p className="bm-takeaway">{suite.takeaway}</p>
      {suite.caveat && <p className="bm-caveat"><span>Note</span>{suite.caveat}</p>}
    </Reveal>
    <div className="bm-results">
      <ResultBars arms={suite.arms} metric={suite.metric} />
      {suite.extra && <div className="bm-fresh">
        <p className="bm-fresh-label"><strong>{suite.extra.label}</strong><span>{suite.extra.n}</span></p>
        <ResultBars arms={suite.extra.arms} metric={suite.metric} compact />
      </div>}
    </div>
  </article>
}

export default function BenchmarksPage() {
  return <div className="bm-page">
    <header className="bm-hero">
      <p className="p-kicker">Benchmarks · {LIVE_DATE}</p>
      <h1>Measured on public benchmarks. <span>Every number published.</span></h1>
      <p className="bm-lede">LLMSlim against Mem0, Zep, LLMLingua-2, LongLLMLingua, RAG and the full context, on held-out test questions. Every system is read by the same model with the same prompt, and every table shows what 1,000 questions cost end to end.</p>
      <p className="bm-story-link"><Link className="text-link" href="/results">Prefer the guided version? See the results as a story <ArrowUpRight size={14} /></Link></p>
      <p className="bm-versions">LLMSlim Core {CORE_VERSION_TESTED} · long documents and agents on Core {CORE_VERSION_LONG_DOCS} · LLMSlim Platform {PLATFORM_VERSION_TESTED} · report, harness and raw results in the <a href={ROUND3_REPORT} target="_blank" rel="noreferrer">public repository <ArrowUpRight size={13} /></a></p>
    </header>

    <section className="bm-band" aria-label="Headline results"><StatsBand stats={stats} /></section>

    <section className="bm-section" aria-labelledby="round3-title">
      <Reveal className="p-head"><p className="p-kicker">Round 3 · Core {CORE_VERSION_TESTED} · 15 Oct 2026</p><h2 id="round3-title">Memory systems and compressors. <span>Cost first.</span></h2>
        <p className="p-body">The question is not only how many answers a context gets right, but what each right answer costs. Costs are per 1,000 questions at list prices, including building Mem0&apos;s and Zep&apos;s memory and every system&apos;s compute.</p></Reveal>
    </section>
    <section className="bm-suites" aria-label="Round 3 results by benchmark">
      {LIVE_SUITES.map((suite) => <Suite key={suite.id} suite={suite} />)}
    </section>

    <section className="bm-section" aria-labelledby="h2h-title">
      <Reveal className="p-head"><p className="p-kicker">Head to head</p><h2 id="h2h-title">The LLMLingua family, same reader. <span>Same questions, same budget.</span></h2>
        <p className="p-body">We ran the best-known open-source prompt compressors ourselves, with their published settings, on the questions they were pre-registered for.</p></Reveal>
      <div className="bm-table-wrap"><table className="bm-table bm-h2h">
        <thead><tr><th scope="col">Compressor</th><th scope="col">Model it runs</th><th scope="col">{HEAD_TO_HEAD.columns[0]}</th><th scope="col">{HEAD_TO_HEAD.columns[1]}</th><th scope="col">{HEAD_TO_HEAD.columns[2]}</th><th scope="col">Cost per 1k</th><th scope="col">Time per question</th></tr></thead>
        <tbody>{HEAD_TO_HEAD.rows.map((row) => <tr key={row.system}>
          <th scope="row" className={row.best ? "is-best" : undefined}>{row.system}</th><td>{row.model}</td>
          <td className={`num${row.best ? " is-best" : ""}`}>{row.scoreA}</td><td className={`num${row.best ? " is-best" : ""}`}>{row.scoreB}</td><td className={`num${row.best ? " is-best" : ""}`}>{row.scoreC}</td>
          <td className="num">{row.cost}</td><td>{row.time}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="bm-note">{HEAD_TO_HEAD.note}</p>
      <p className="bm-note bm-sources">Sources and reruns: {HEAD_TO_HEAD.sources.map((source, index) => <span key={source.url}>{index > 0 && " · "}<a href={source.url} target="_blank" rel="noreferrer">{source.label}</a></span>)}</p>
      <p className="bm-story-link"><Link className="text-link" href="/compare/llmlingua">Choosing between LLMSlim and LLMLingua? Read the comparison, with migration code <ArrowUpRight size={14} /></Link></p>
    </section>

    <section className="bm-section" aria-labelledby="loses-title">
      <Reveal className="p-head"><p className="p-kicker">Weak spots</p><h2 id="loses-title">Where LLMSlim loses. <span>Published with the rest.</span></h2></Reveal>
      <ol className="p-notes">{WEAK_SPOTS.map((spot, index) => <li key={spot.title}><span className="p-note-index">{String(index + 1).padStart(2, "0")}</span><p><strong>{spot.title}.</strong> {spot.body}</p></li>)}</ol>
    </section>

    <section className="bm-section" aria-labelledby="docs-title">
      <Reveal className="p-head"><p className="p-kicker">Long documents · Core {CORE_VERSION_LONG_DOCS} · 12 Oct 2026</p><h2 id="docs-title">Long documents. <span>Against full context and truncation.</span></h2>
        <p className="p-body">From the previous round, with fresh questions run once after the code was frozen. 0.9.0 changes only how chat transcripts are selected. Costs here are the answer call alone.</p></Reveal>
    </section>
    <section className="bm-suites" aria-label="Long-document results">
      {LONG_DOC_SUITES.map((suite) => <Suite key={suite.id} suite={suite} />)}
    </section>

    <section className="bm-section" aria-labelledby="agents-title">
      <Reveal className="p-head"><p className="p-kicker">Agents · Core {CORE_VERSION_LONG_DOCS}</p><h2 id="agents-title">Where compression does not help. <span>Yet.</span></h2></Reveal>
      {AGENT_FINDINGS.map((finding) => <div key={finding.name} className="bm-agent">
        <div className="bm-agent-copy"><h3>{finding.name}</h3><p>{finding.what}</p><p className="bm-takeaway">{finding.takeaway}</p></div>
        <dl className="bm-rows">{finding.rows.map((row) => <div key={row.arm}><dt>{row.arm}</dt><dd><strong>{row.result}</strong><span>{row.detail}</span></dd></div>)}</dl>
      </div>)}
    </section>

    <section className="bm-section" aria-labelledby="others-title">
      <Reveal className="p-head"><p className="p-kicker">Other systems</p><h2 id="others-title">Their own published results. <span>With their readers.</span></h2>
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
      <p className="bm-story-link"><a className="text-link" href={`${siteConfig.github}/tree/main/benchmarks/live/round3`} target="_blank" rel="noreferrer">How the numbers were kept honest, and everything that went wrong <ArrowUpRight size={14} /></a></p>
    </section>

    <section className="bm-section" aria-labelledby="offline-title">
      <h2 id="offline-title" className="bm-small-title">Earlier offline suites</h2>
      <ul className="int-list">{Object.values(BENCHMARK_SUITES).map((suite) => <li key={suite.slug}>
        <Link className="int-row bm-offline-row" href={`/benchmarks/${suite.slug}`}><span className="int-name">{suite.title}<small>deterministic, no model call</small></span><span className="int-tagline">{suite.subtitle}</span><ArrowUpRight className="int-arrow" size={18} aria-hidden="true" /></Link>
      </li>)}</ul>
    </section>
  </div>
}
