import { Fragment } from "react"
import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { Inline } from "@/components/docs/DocInline"
import { Reveal } from "@/components/landing/Premium"
import { DEFAULT_DOCS_VERSION } from "@/data/docs-versions"
import { LLMSLIM_PRICES_TITLE, PRICES_CHECKED, llmslimPriceRows, type MemoryComparison, type PriceRow } from "@/data/memory-comparisons"
import { breadcrumbJsonLd, constructMetadata, faqJsonLd, isoDate, jsonLdScript, techArticleJsonLd } from "@/lib/seo"

/**
 * /compare/mem0 and /compare/zep: the LLMLingua comparison's layout (compare.css, bm-*), for a memory system.
 * Every benchmark round in `page.benchmarks` gets its own block, so a later round is one more entry in the data.
 */

const pathOf = (page: MemoryComparison) => `/compare/${page.slug}`

export function memoryComparisonMetadata(page: MemoryComparison) {
  const path = pathOf(page)
  return constructMetadata({
    title: page.title,
    description: page.description,
    path,
    markdownPath: `${path}.md`,
    type: "article",
    // The share images are opengraph-image.tsx and twitter-image.tsx beside the page (src/lib/og/memory-compare-card.tsx).
    image: null,
  })
}

const text = (value: string) => <Inline text={value} version={DEFAULT_DOCS_VERSION} />

function PriceTable({ caption, rows }: { caption: string; rows: PriceRow[] }) {
  return <div className="bm-table-wrap"><table className="bm-table cmp-prices">
    <caption>{caption}</caption>
    <thead><tr><th scope="col">Plan</th><th scope="col">Price</th><th scope="col">What it includes</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.plan}><th scope="row">{row.plan}</th><td className="cmp-price">{row.price}</td><td>{row.includes}</td></tr>)}</tbody>
  </table></div>
}

export function MemoryComparisonPage({ page }: { page: MemoryComparison }) {
  const path = pathOf(page)
  const date = isoDate(page.lastUpdated)
  const jsonLd = [
    techArticleJsonLd({ path, headline: page.title, description: page.description, section: "Comparison", datePublished: date, dateModified: date }),
    breadcrumbJsonLd([["Home", "/"], [`LLMSlim vs ${page.rival}`, path]]),
    faqJsonLd(page.faqs, path),
  ]
  return <div className="bm-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />

    <header className="bm-hero">
      <p className="p-kicker">{page.kicker}</p>
      <h1>{page.heading[0]} <span>{page.heading[1]}</span></h1>
      <p className="bm-lede">{page.lede}</p>
      <p className="cmp-meta">{page.meta.map((item) => <span key={item}>{item}</span>)}</p>
      <p className="cmp-disclosure">{page.disclosure}</p>
    </header>

    <section className="cmp-answer" aria-labelledby="answer-title">
      <h2 id="answer-title">The short answer</h2>
      <ul>{page.shortAnswer.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="glance-title">
      <Reveal className="p-head"><p className="p-kicker">At a glance</p><h2 id="glance-title">Two ways to remember. <span>Different trade-offs.</span></h2></Reveal>
      <div className="bm-table-wrap"><table className="bm-table cmp-glance cmp-glance-two">
        <thead><tr><th scope="col">Aspect</th><th scope="col" className="is-us">LLMSlim</th><th scope="col">{page.rival}</th></tr></thead>
        <tbody>{page.glance.map((row) => <tr key={row.aspect}>
          <th scope="row">{row.aspect}</th><td className="is-us">{row.llmslim}</td><td>{row.rival}</td>
        </tr>)}</tbody>
      </table></div>
    </section>

    <section className="bm-section" aria-labelledby="about-title">
      <Reveal className="p-head"><p className="p-kicker">What {page.rival} is</p><h2 id="about-title">What {page.rival} is. <span>From its own docs.</span></h2></Reveal>
      <div className="cmp-pair">{page.about.map((item) => <article key={item.name}>
        <h3>{item.name}</h3>
        <a className="cmp-cite" href={item.url} target="_blank" rel="noreferrer">{item.cite} <ArrowUpRight size={12} aria-hidden="true" /></a>
        <p>{item.body}</p>
      </article>)}</div>
      <p className="cmp-aside">{page.aboutNote}</p>
    </section>

    <section className="bm-section" aria-labelledby="differs-title">
      <Reveal className="p-head"><p className="p-kicker">How LLMSlim differs</p><h2 id="differs-title">Keep what was said. <span>No LLM on the way in.</span></h2></Reveal>
      <ol className="cmp-notes">{page.differences.map((item, index) => <li key={item.title}>
        <span className="p-note-index">{String(index + 1).padStart(2, "0")}</span><h3>{item.title}</h3><p>{item.body}</p>
      </li>)}</ol>
    </section>

    {page.benchmarks.map((block) => <section key={block.id} id={block.id} className="bm-section" aria-labelledby={`${block.id}-title`}>
      <Reveal className="p-head"><p className="p-kicker">Head to head · {block.kicker}</p><h2 id={`${block.id}-title`}>{block.heading[0]} <span>{block.heading[1]}</span></h2>
        <p className="p-body">{block.intro}</p></Reveal>
      {block.tables.map((table) => <div key={table.title} className="cmp-result">
        <h3 className="cmp-subhead">{table.title}</h3>
        <div className="bm-table-wrap"><table className="bm-table bm-h2h cmp-results">
          <thead><tr><th scope="col">System</th><th scope="col">Context tokens</th><th scope="col">Accuracy (95% CI)</th><th scope="col">Cost per 1k questions</th></tr></thead>
          <tbody>{table.rows.map((row, index) => <Fragment key={`${row.system}-${row.tokens}`}>
            {row.budget && row.budget !== table.rows[index - 1]?.budget && <tr className="cmp-budget"><th scope="rowgroup" colSpan={4}>{row.budget}</th></tr>}
            <tr className={`is-${row.kind}`}>
              <th scope="row">{row.system}</th><td className="num">{row.tokens}</td><td className="num">{row.score}</td><td className="num">{row.cost}</td>
            </tr>
          </Fragment>)}</tbody>
        </table></div>
        <p className="bm-note">{table.note}</p>
      </div>)}

      <h3 className="cmp-subhead">Paired differences with 95% intervals</h3>
      <div className="bm-table-wrap"><table className="bm-table cmp-diffs">
        <thead><tr><th scope="col">Comparison</th><th scope="col">Benchmark (questions)</th><th scope="col">Difference (95% CI)</th><th scope="col">Reading</th></tr></thead>
        <tbody>{block.pairedDiffs.map((row) => <tr key={`${row.benchmark}-${row.comparison}`}>
          <th scope="row">{row.comparison}</th><td>{row.benchmark}</td><td>{row.difference}</td><td>{row.reading}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="bm-note">{block.pairedNote}</p>

      <h3 className="cmp-subhead">What this does not show</h3>
      <dl className="cmp-caveats">{block.caveats.map((caveat) => <div key={caveat.title}><dt>{caveat.title}</dt><dd>{caveat.body}</dd></div>)}</dl>
      <p className="cmp-links">
        {block.links.map((link) => <a key={link.url} className="text-link" href={link.url} target="_blank" rel="noreferrer">{link.label} <ArrowUpRight size={14} aria-hidden="true" /></a>)}
        <Link className="text-link" href="/benchmarks">Every benchmark <ArrowUpRight size={14} aria-hidden="true" /></Link>
      </p>
    </section>)}

    <section className="bm-section" aria-labelledby="choose-them-title">
      <Reveal className="p-head"><p className="p-kicker">When to choose {page.rival}</p><h2 id="choose-them-title">Cases where {page.rival} <span>is the better fit.</span></h2></Reveal>
      <ul className="cmp-cards">{page.chooseThem.map((item) => <li key={item.title}><h3>{item.title}</h3><p>{item.body}</p></li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="choose-us-title">
      <Reveal className="p-head"><p className="p-kicker">When LLMSlim fits</p><h2 id="choose-us-title">Where LLMSlim <span>makes sense.</span></h2></Reveal>
      <ul className="cmp-fit">{page.chooseUs.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="pricing-title">
      <Reveal className="p-head"><p className="p-kicker">Pricing · checked {PRICES_CHECKED}</p><h2 id="pricing-title">What each costs. <span>From each pricing page.</span></h2>
        <p className="p-body">{page.pricing.intro}</p></Reveal>
      <PriceTable caption={page.rival} rows={page.pricing.rival.rows} />
      <p className="bm-note bm-sources">Source: <a href={page.pricing.rival.url} target="_blank" rel="noreferrer">{page.pricing.rival.url.replace(/^https:\/\//, "")}</a>, checked {PRICES_CHECKED}. Prices change; check the page before you decide.</p>
      <PriceTable caption={LLMSLIM_PRICES_TITLE} rows={llmslimPriceRows()} />
      <p className="bm-note bm-sources">Source: <Link href="/pricing">llmslim.app/pricing</Link>, which also lists the plans in rupees.</p>
      <ul className="cmp-migration-general cmp-price-notes">{page.pricing.notes.map((note) => <li key={note}>{note}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="migrate-title">
      <Reveal className="p-head"><p className="p-kicker">Migrate</p><h2 id="migrate-title">Bring your memory across. <span>Tested, with real output.</span></h2>
        <p className="p-body">{text(page.migration.intro)}</p></Reveal>
      {page.migration.steps.map((step) => <div key={step.title} className="cmp-migration">
        <h3>{step.title}</h3>
        <p className="cmp-step-body">{text(step.body)}</p>
        <div className="cmp-code-pair">
          {step.samples.map((sample) => <DocCodeBlock key={sample.filename + sample.code.slice(0, 40)} language={sample.language} filename={sample.filename} code={sample.code} wrap={sample.wrap} />)}
        </div>
        {step.after && <p className="cmp-step-body">{text(step.after)}</p>}
      </div>)}
      <ul className="cmp-migration-general">{page.migration.notes.map((note) => <li key={note}>{text(note)}</li>)}</ul>
      <p className="cmp-migration-foot"><Link className="text-link" href={page.migration.guide.href}>{page.migration.guide.label} <ArrowUpRight size={14} aria-hidden="true" /></Link></p>
    </section>

    <section className="bm-section" aria-labelledby="faq-title">
      <Reveal className="p-head"><p className="p-kicker">FAQ</p><h2 id="faq-title">Questions people ask <span>before switching.</span></h2></Reveal>
      <div className="faq-list cmp-faq">{page.faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus" aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
    </section>

    <section className="bm-section" aria-labelledby="sources-title">
      <h2 id="sources-title" className="bm-small-title">Sources</h2>
      <ul className="cmp-sources">{page.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} <ArrowUpRight size={12} aria-hidden="true" /></a></li>)}</ul>
      <div className="cmp-cta">
        <Link className="button" href="/docs/quickstart-python">Get started <ArrowRight size={16} aria-hidden="true" /></Link>
        <Link className="button button-outline" href="/docs/quickstart-mcp">MCP quickstart</Link>
        <Link className="button button-outline" href="/benchmarks">Every benchmark</Link>
      </div>
    </section>
  </div>
}
