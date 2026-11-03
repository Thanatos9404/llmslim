import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { ProductLogo } from "@/components/brand/ProductLogo"
import { productsNamedIn } from "@/components/brand/product-logos"
import { CompareHero } from "@/components/compare/CompareHero"
import { NamedProducts, ProductHeading, SectionHead } from "@/components/compare/compare-parts"
import { MotionTable } from "@/components/compare/MotionTable"
import { DiffPlot, NumberCell, Reading, SystemName, differenceDomain } from "@/components/compare/score-parts"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { siteConfig } from "@/config/site"
import { LLMLINGUA_COMPARISON as page } from "@/data/comparisons"
import { HEAD_TO_HEAD, ROUND3_REPORT } from "@/data/live-benchmarks"
import { breadcrumbJsonLd, constructMetadata, faqJsonLd, isoDate, jsonLdScript, techArticleJsonLd } from "@/lib/seo"

const path = `/compare/${page.slug}`
const ROUND3 = `${siteConfig.github}/tree/main/benchmarks/live/round3`

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
  const domain = differenceDomain(page.pairedDiffs.map((row) => row.difference))
  return <div className="bm-page cmp-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />

    <CompareHero kicker={page.kicker} heading={page.heading} lede={page.lede}
      meta={[`Updated ${page.lastUpdated}`, "LLMSlim Core 0.9", "Reader: Claude Haiku 5.5"]} disclosure={page.disclosure}
      rival={{ name: "LLMLingua", logo: "llmlingua" }} photo={{ src: "/media/stock/server-aisle.webp", position: "60% 50%" }} />

    <section className="cmp-answer" aria-labelledby="answer-title">
      <h2 id="answer-title">The short answer</h2>
      <ul>{page.shortAnswer.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="glance-title">
      <SectionHead kicker="At a glance" id="glance-title" heading={["Three ways to shrink context.", "Different trade-offs."]} />
      <div className="bm-table-wrap"><table className="bm-table cmp-glance">
        <thead><tr><th scope="col">Aspect</th><th scope="col" className="is-us"><ProductHeading name="LLMSlim" logo="llmslim" /></th><th scope="col"><ProductHeading name="LLMLingua-2" logo="llmlingua" /></th><th scope="col"><ProductHeading name="LongLLMLingua" logo="llmlingua" /></th></tr></thead>
        <tbody>{page.glance.map((row) => <tr key={row.aspect}>
          <th scope="row">{row.aspect}</th>
          <td className="is-us">{row.llmslim}</td>
          {row.longLingua === undefined ? <td colSpan={2}>{row.lingua2}</td> : <><td>{row.lingua2}</td><td>{row.longLingua}</td></>}
        </tr>)}</tbody>
      </table></div>
    </section>

    <section className="bm-section" aria-labelledby="baselines-title">
      <SectionHead kicker="The LLMLingua family" id="baselines-title" heading={["What LLMLingua-2 and LongLLMLingua are.", "From their papers."]} />
      <div className="cmp-pair">{page.baselines.map((baseline) => <article key={baseline.name} className="glow-card">
        <ProductLogo logo="llmlingua" size={28} className="cmp-pair-logo is-rounded" />
        <h3>{baseline.name}</h3>
        <a className="cmp-cite" href={baseline.url} target="_blank" rel="noreferrer">{baseline.citation} <ArrowUpRight size={12} aria-hidden="true" /></a>
        <p>{baseline.body}</p>
      </article>)}</div>
      <p className="cmp-aside">{page.baselinesNote} Code: <a href="https://github.com/microsoft/LLMLingua" target="_blank" rel="noreferrer">github.com/microsoft/LLMLingua</a>.</p>
    </section>

    <section className="bm-section" aria-labelledby="differs-title">
      <SectionHead kicker="How LLMSlim differs" id="differs-title" heading={["Choose sentences, not tokens.", "No 7B model required."]} />
      <ol className="cmp-notes">{page.differences.map((item, index) => <li key={item.title}>
        <span className="p-note-index">{String(index + 1).padStart(2, "0")}</span><h3>{item.title}</h3><p>{item.body}</p>
        <NamedProducts text={item.body} />
      </li>)}</ol>
    </section>

    <section className="bm-section" aria-labelledby="h2h-title">
      <SectionHead kicker="Head to head" id="h2h-title" heading={["Three benchmarks, same reader.", "Same questions, same budget."]}>
        <p className="p-body">{page.headToHeadIntro}</p>
      </SectionHead>
      <MotionTable className="bm-table-wrap"><table className="bm-table bm-h2h cmp-results cmp-lingua">
        <thead><tr><th scope="col">Compressor</th><th scope="col">Model it runs</th><th scope="col">{HEAD_TO_HEAD.columns[0]}</th><th scope="col">{HEAD_TO_HEAD.columns[1]}</th><th scope="col">{HEAD_TO_HEAD.columns[2]}</th><th scope="col">Cost per 1k</th><th scope="col">Time per question</th></tr></thead>
        <tbody>{HEAD_TO_HEAD.rows.map((row) => <tr key={row.system} className={/^LLMSlim/.test(row.system) ? "is-llmslim" : /Lingua/.test(row.system) ? "is-rival" : "is-other"}>
          <th scope="row" className={row.best ? "is-best" : undefined}><SystemName system={row.system} /></th><td>{row.model}</td>
          <td className={`num cmp-score${row.best ? " is-best" : ""}`}><NumberCell text={row.scoreA} bar /></td>
          <td className={`num cmp-score${row.best ? " is-best" : ""}`}><NumberCell text={row.scoreB} bar /></td>
          <td className={`num cmp-score${row.best ? " is-best" : ""}`}><NumberCell text={row.scoreC} bar /></td>
          <td className="num"><NumberCell text={row.cost} /></td><td>{row.time}</td>
        </tr>)}</tbody>
      </table></MotionTable>
      <p className="bm-note">{HEAD_TO_HEAD.note}</p>

      <h3 className="cmp-subhead">Paired differences with 95% intervals</h3>
      <MotionTable className="bm-table-wrap"><table className="bm-table cmp-diffs">
        <thead><tr><th scope="col">Comparison</th><th scope="col">Benchmark (questions)</th><th scope="col">Difference (95% CI)</th><th scope="col">Reading</th></tr></thead>
        <tbody>{page.pairedDiffs.map((row) => <tr key={`${row.benchmark}-${row.comparison}`}>
          <th scope="row">{row.comparison}</th><td>{row.benchmark}</td>
          <td className="cmp-diff"><span className="cmp-diff-text">{row.difference}</span><DiffPlot difference={row.difference} domain={domain} reading={row.reading} /></td>
          <td><Reading reading={row.reading} /></td>
        </tr>)}</tbody>
      </table></MotionTable>
      <p className="bm-note">{page.pairedNote} <span className="cmp-axis-note">Each plot runs from −{domain} to +{domain} points, with zero in the middle.</span></p>

      <h3 className="cmp-subhead">On every test question</h3>
      <MotionTable className="bm-table-wrap"><table className="bm-table bm-h2h cmp-results">
        <thead><tr><th scope="col">System</th>{page.testSets.columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>{page.testSets.rows.map((row) => <tr key={row.system} className={/^LLMSlim/.test(row.system) ? "is-llmslim" : /Lingua/.test(row.system) ? "is-rival" : "is-other"}>
          <th scope="row"><SystemName system={row.system} /></th>{row.cells.map((value, index) => <td key={page.testSets.columns[index]} className="num"><NumberCell text={value} /></td>)}
        </tr>)}</tbody>
      </table></MotionTable>
      <p className="bm-note">{page.testSets.note}</p>

      <h3 className="cmp-subhead">What this does not show</h3>
      <dl className="cmp-caveats">{page.caveats.map((caveat) => <div key={caveat.title}><dt>{caveat.title}</dt><dd>{caveat.body}</dd></div>)}</dl>
      <p className="cmp-links">
        <a className="text-link" href={ROUND3_REPORT} target="_blank" rel="noreferrer">Round 3 report and tables <ArrowUpRight size={14} aria-hidden="true" /></a>
        <a className="text-link" href={ROUND3} target="_blank" rel="noreferrer">How the runs were kept honest <ArrowUpRight size={14} aria-hidden="true" /></a>
        <Link className="text-link" href="/benchmarks">Every benchmark <ArrowUpRight size={14} aria-hidden="true" /></Link>
        <a className="text-link" href={`${ROUND3}/results`} target="_blank" rel="noreferrer">Per-question results <ArrowUpRight size={14} aria-hidden="true" /></a>
      </p>
    </section>

    <section className="bm-section" aria-labelledby="choose-them-title">
      <SectionHead kicker="When to choose LLMLingua" id="choose-them-title" heading={["Cases where LLMLingua", "is the better fit."]} />
      <ul className="cmp-cards">{page.chooseThem.map((item) => <li key={item.title} className="glow-card"><h3>{item.title}</h3><p>{item.body}</p></li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="choose-us-title">
      <SectionHead kicker="When LLMSlim fits" id="choose-us-title" heading={["Where LLMSlim", "makes sense."]} />
      <ul className="cmp-fit">{page.chooseUs.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="migrate-title">
      <SectionHead kicker="Migrate" id="migrate-title" heading={["Swap the class.", "Keep the pipeline."]}>
        <p className="p-body">The LLMSlim adapters go in the same slots as the LLMLingua classes. Snippets assume your existing retriever, index or pipeline.</p>
      </SectionHead>
      {page.migrations.map((migration) => {
        const logo = productsNamedIn(migration.framework)[0]
        return <div key={migration.framework} className="cmp-migration">
          <h3 className="cmp-migration-title">{logo && <ProductLogo logo={logo} size={24} />}{migration.framework}</h3>
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
        </div>
      })}
      <ul className="cmp-migration-general">{page.migrationNotes.map((note) => <li key={note}>{note}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="faq-title">
      <SectionHead kicker="FAQ" id="faq-title" heading={["Questions people ask", "before switching."]} />
      <div className="faq-list cmp-faq">{page.faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus" aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
    </section>

    <section className="bm-section" aria-labelledby="sources-title">
      <h2 id="sources-title" className="bm-small-title">Sources</h2>
      <ul className="cmp-sources">{page.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} <ArrowUpRight size={12} aria-hidden="true" /></a></li>)}</ul>
      <div className="cmp-end">
        <MemoryGlyph size={56} />
        <div className="cmp-cta">
          <Link className="button" href="/docs/getting-started">Get started <ArrowRight size={16} aria-hidden="true" /></Link>
          <Link className="button button-outline" href="/integrations">Framework integrations</Link>
          <Link className="button button-outline" href="/benchmarks">Every benchmark</Link>
        </div>
      </div>
    </section>
  </div>
}
