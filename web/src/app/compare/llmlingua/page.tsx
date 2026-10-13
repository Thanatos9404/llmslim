import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { Reveal } from "@/components/landing/Premium"
import { siteConfig } from "@/config/site"
import { LLMLINGUA_COMPARISON as page } from "@/data/comparisons"
import { HEAD_TO_HEAD } from "@/data/live-benchmarks"
import { breadcrumbJsonLd, constructMetadata, faqJsonLd, isoDate, jsonLdScript, techArticleJsonLd } from "@/lib/seo"

const path = `/compare/${page.slug}`
const ARTICLE = "/articles/llmslim-vs-llmlingua-2-vs-longllmlingua"

export const metadata = constructMetadata({
  title: page.title,
  description: page.description,
  path,
  markdownPath: `${path}.md`,
  type: "article",
  // The share images are opengraph-image.tsx and twitter-image.tsx beside this page (the benchmark card).
  image: null,
})

export default function LLMLinguaComparisonPage() {
  const date = isoDate(page.lastUpdated)
  const jsonLd = [
    techArticleJsonLd({ path, headline: page.title, description: page.description, section: "Comparison", datePublished: date, dateModified: date }),
    breadcrumbJsonLd([["Home", "/"], ["LLMSlim vs LLMLingua", path]]),
    faqJsonLd(page.faqs, path),
  ]
  return <div className="bm-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />

    <header className="bm-hero">
      <p className="p-kicker">{page.kicker}</p>
      <h1>{page.heading[0]} <span>{page.heading[1]}</span></h1>
      <p className="bm-lede">{page.lede}</p>
      <p className="cmp-meta"><span>Updated {page.lastUpdated}</span><span>LLMSlim Core 0.8</span><span>Reader: Claude Haiku 5.5</span></p>
      <p className="cmp-disclosure">{page.disclosure}</p>
    </header>

    <section className="cmp-answer" aria-labelledby="answer-title">
      <h2 id="answer-title">The short answer</h2>
      <ul>{page.shortAnswer.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="glance-title">
      <Reveal className="p-head"><p className="p-kicker">At a glance</p><h2 id="glance-title">Three ways to shrink context. <span>Different trade-offs.</span></h2></Reveal>
      <div className="bm-table-wrap"><table className="bm-table cmp-glance">
        <thead><tr><th scope="col">Aspect</th><th scope="col" className="is-us">LLMSlim</th><th scope="col">LLMLingua-2</th><th scope="col">LongLLMLingua</th></tr></thead>
        <tbody>{page.glance.map((row) => <tr key={row.aspect}>
          <th scope="row">{row.aspect}</th>
          <td className="is-us">{row.llmslim}</td>
          {row.longLingua === undefined ? <td colSpan={2}>{row.lingua2}</td> : <><td>{row.lingua2}</td><td>{row.longLingua}</td></>}
        </tr>)}</tbody>
      </table></div>
    </section>

    <section className="bm-section" aria-labelledby="baselines-title">
      <Reveal className="p-head"><p className="p-kicker">The LLMLingua family</p><h2 id="baselines-title">What LLMLingua-2 and LongLLMLingua are. <span>From their papers.</span></h2></Reveal>
      <div className="cmp-pair">{page.baselines.map((baseline) => <article key={baseline.name}>
        <h3>{baseline.name}</h3>
        <a className="cmp-cite" href={baseline.url} target="_blank" rel="noreferrer">{baseline.citation} <ArrowUpRight size={12} aria-hidden="true" /></a>
        <p>{baseline.body}</p>
      </article>)}</div>
      <p className="cmp-aside">{page.baselinesNote} Code: <a href="https://github.com/microsoft/LLMLingua" target="_blank" rel="noreferrer">github.com/microsoft/LLMLingua</a>.</p>
    </section>

    <section className="bm-section" aria-labelledby="differs-title">
      <Reveal className="p-head"><p className="p-kicker">How LLMSlim differs</p><h2 id="differs-title">Choose sentences, not tokens. <span>No 7B model required.</span></h2></Reveal>
      <ol className="cmp-notes">{page.differences.map((item, index) => <li key={item.title}>
        <span className="p-note-index">{String(index + 1).padStart(2, "0")}</span><h3>{item.title}</h3><p>{item.body}</p>
      </li>)}</ol>
    </section>

    <section className="bm-section" aria-labelledby="h2h-title">
      <Reveal className="p-head"><p className="p-kicker">Head to head</p><h2 id="h2h-title">NaturalQuestions, same reader. <span>Same budget, same cases.</span></h2>
        <p className="p-body">20 retrieved passages per question, a 25% token budget for every compressor, and Claude Haiku 5.5 reading every compressed context. Accuracy is the share of cases where a gold answer appears in the response.</p></Reveal>
      <div className="bm-table-wrap"><table className="bm-table bm-h2h">
        <thead><tr><th scope="col">Compressor</th><th scope="col">Model it runs</th><th scope="col">{HEAD_TO_HEAD.columns[0]}</th><th scope="col">{HEAD_TO_HEAD.columns[1]}</th><th scope="col">{HEAD_TO_HEAD.columns[2]}</th><th scope="col">Tokens kept</th><th scope="col">Time per question</th></tr></thead>
        <tbody>{HEAD_TO_HEAD.rows.map((row) => <tr key={row.system}>
          <th scope="row" className={row.best ? "is-best" : undefined}>{row.system}</th><td>{row.model}</td>
          <td className={`num${row.best ? " is-best" : ""}`}>{row.scoreA}</td><td className={`num${row.best ? " is-best" : ""}`}>{row.scoreB}</td><td className={`num${row.best ? " is-best" : ""}`}>{row.scoreAll}</td>
          <td className="num">{row.tokens}</td><td>{row.time}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="bm-note">{HEAD_TO_HEAD.note}</p>

      <h3 className="cmp-subhead">Paired differences with 95% intervals</h3>
      <div className="bm-table-wrap"><table className="bm-table cmp-diffs">
        <thead><tr><th scope="col">Comparison</th><th scope="col">Original (150 cases)</th><th scope="col">Fresh (150 cases)</th><th scope="col">All 300, by case</th><th scope="col">All 300, by question</th></tr></thead>
        <tbody>{page.pairedDiffs.map((row) => <tr key={row.comparison}>
          <th scope="row">{row.comparison}</th><td>{row.original}</td><td>{row.fresh}</td><td>{row.byCase}</td><td>{row.byQuestion}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="bm-note">{page.pairedNote}</p>

      <h3 className="cmp-subhead">What this does not show</h3>
      <dl className="cmp-caveats">{page.caveats.map((caveat) => <div key={caveat.title}><dt>{caveat.title}</dt><dd>{caveat.body}</dd></div>)}</dl>
      <p className="cmp-links">
        <Link className="text-link" href={ARTICLE}>Full methodology and error analysis <ArrowUpRight size={14} aria-hidden="true" /></Link>
        <Link className="text-link" href="/benchmarks">Every benchmark <ArrowUpRight size={14} aria-hidden="true" /></Link>
        <a className="text-link" href={`${siteConfig.github}/tree/main/benchmarks/live/results`} target="_blank" rel="noreferrer">Per-case results <ArrowUpRight size={14} aria-hidden="true" /></a>
      </p>
    </section>

    <section className="bm-section" aria-labelledby="choose-them-title">
      <Reveal className="p-head"><p className="p-kicker">When to choose LLMLingua</p><h2 id="choose-them-title">Cases where LLMLingua <span>is the better fit.</span></h2></Reveal>
      <ul className="cmp-cards">{page.chooseThem.map((item) => <li key={item.title}><h3>{item.title}</h3><p>{item.body}</p></li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="choose-us-title">
      <Reveal className="p-head"><p className="p-kicker">When LLMSlim fits</p><h2 id="choose-us-title">Where LLMSlim <span>makes sense.</span></h2></Reveal>
      <ul className="cmp-fit">{page.chooseUs.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="migrate-title">
      <Reveal className="p-head"><p className="p-kicker">Migrate</p><h2 id="migrate-title">Swap the class. <span>Keep the pipeline.</span></h2>
        <p className="p-body">The LLMSlim adapters go in the same slots as the LLMLingua classes. Snippets assume your existing retriever, index or pipeline.</p></Reveal>
      {page.migrations.map((migration) => <div key={migration.framework} className="cmp-migration">
        <h3>{migration.framework}</h3>
        <div className="cmp-code-pair">
          {migration.before && <div>
            <p className="cmp-code-label">Before <strong>{migration.before.label}</strong></p>
            <DocCodeBlock language="python" filename={migration.before.filename} code={`# ${migration.before.install}\n${migration.before.code}`} />
          </div>}
          <div>
            <p className="cmp-code-label is-us">{migration.before ? "After" : "Add"} <strong>{migration.after.label}</strong></p>
            <DocCodeBlock language="python" filename={migration.after.filename} code={`# ${migration.after.install}\n${migration.after.code}`} />
          </div>
        </div>
        {migration.notes.length > 0 && <ul className="cmp-migration-notes">{migration.notes.map((note) => <li key={note}>{note}</li>)}</ul>}
        <p className="cmp-migration-foot"><Link className="text-link" href={migration.guide}>{migration.guide.startsWith("/integrations/") ? `${migration.framework} integration guide` : "Document pipelines"} <ArrowUpRight size={14} aria-hidden="true" /></Link></p>
      </div>)}
      <ul className="cmp-migration-general">{page.migrationNotes.map((note) => <li key={note}>{note}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="faq-title">
      <Reveal className="p-head"><p className="p-kicker">FAQ</p><h2 id="faq-title">Questions people ask <span>before switching.</span></h2></Reveal>
      <div className="faq-list cmp-faq">{page.faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus" aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
    </section>

    <section className="bm-section" aria-labelledby="sources-title">
      <h2 id="sources-title" className="bm-small-title">Sources</h2>
      <ul className="cmp-sources">{page.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} <ArrowUpRight size={12} aria-hidden="true" /></a></li>)}</ul>
      <div className="cmp-cta">
        <Link className="button" href="/docs/getting-started">Get started <ArrowRight size={16} aria-hidden="true" /></Link>
        <Link className="button button-outline" href="/integrations">Framework integrations</Link>
        <Link className="button button-outline" href={ARTICLE}>Read the methodology</Link>
      </div>
    </section>
  </div>
}
