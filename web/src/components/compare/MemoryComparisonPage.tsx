import { Fragment } from "react"
import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { ProductLogo } from "@/components/brand/ProductLogo"
import type { ProductLogoKey } from "@/components/brand/product-logos"
import { CompareHero } from "@/components/compare/CompareHero"
import { NamedProducts, ProductHeading, SectionHead } from "@/components/compare/compare-parts"
import { MotionTable } from "@/components/compare/MotionTable"
import { DiffPlot, NumberCell, Reading, ScoreCell, SystemName, differenceDomain } from "@/components/compare/score-parts"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { Inline } from "@/components/docs/DocInline"
import { DEFAULT_DOCS_VERSION } from "@/data/docs-versions"
import { LLMSLIM_PRICES_TITLE, PRICES_CHECKED, llmslimPriceRows, type MemoryComparison, type PriceRow } from "@/data/memory-comparisons"
import { breadcrumbJsonLd, constructMetadata, faqJsonLd, isoDate, jsonLdScript, techArticleJsonLd } from "@/lib/seo"

/**
 * /compare/mem0 and /compare/zep: the LLMLingua comparison's layout (compare.css, bm-*), for a memory system.
 * Every benchmark round in `page.benchmarks` gets its own block, so a later round is one more entry in the data.
 * The words and numbers all come from the data; the logos, bars and plots only draw what it says.
 */

const pathOf = (page: MemoryComparison) => `/compare/${page.slug}`

/** Per rival: its logo and wordmark, and the photo on the hero plate (public/media/stock/CREDITS.md). */
const RIVALS: Record<string, { icon: ProductLogoKey; wordmark: ProductLogoKey; photo: { src: string; position?: string } }> = {
  mem0: { icon: "mem0", wordmark: "mem0-wordmark", photo: { src: "/media/stock/fiber-blue-green.webp", position: "50% 70%" } },
  zep: { icon: "zep", wordmark: "zep-wordmark", photo: { src: "/media/stock/fiber-violet.webp", position: "50% 40%" } },
}

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

function PriceTable({ caption, rows, logo }: { caption: string; rows: PriceRow[]; logo: ProductLogoKey | "llmslim" }) {
  return <div className="bm-table-wrap"><table className="bm-table cmp-prices">
    <caption><ProductHeading name={caption} logo={logo} /></caption>
    <thead><tr><th scope="col">Plan</th><th scope="col">Price</th><th scope="col">What it includes</th></tr></thead>
    <tbody>{rows.map((row) => <tr key={row.plan}><th scope="row">{row.plan}</th><td className="cmp-price">{row.price}</td><td>{row.includes}</td></tr>)}</tbody>
  </table></div>
}

export function MemoryComparisonPage({ page }: { page: MemoryComparison }) {
  const path = pathOf(page)
  const date = isoDate(page.lastUpdated)
  const rival = RIVALS[page.slug] ?? RIVALS.mem0
  const jsonLd = [
    techArticleJsonLd({ path, headline: page.title, description: page.description, section: "Comparison", datePublished: date, dateModified: date }),
    breadcrumbJsonLd([["Home", "/"], [`LLMSlim vs ${page.rival}`, path]]),
    faqJsonLd(page.faqs, path),
  ]
  return <div className="bm-page cmp-page">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />

    <CompareHero kicker={page.kicker} heading={page.heading} lede={page.lede} meta={page.meta} disclosure={page.disclosure}
      rival={{ name: page.rival, logo: rival.wordmark, wordmark: true }} photo={rival.photo} />

    <section className="cmp-answer" aria-labelledby="answer-title">
      <h2 id="answer-title">The short answer</h2>
      <ul>{page.shortAnswer.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="glance-title">
      <SectionHead kicker="At a glance" id="glance-title" heading={["Two ways to remember.", "Different trade-offs."]} />
      <div className="bm-table-wrap"><table className="bm-table cmp-glance cmp-glance-two">
        <thead><tr><th scope="col">Aspect</th><th scope="col" className="is-us"><ProductHeading name="LLMSlim" logo="llmslim" /></th><th scope="col"><ProductHeading name={page.rival} logo={rival.icon} /></th></tr></thead>
        <tbody>{page.glance.map((row) => <tr key={row.aspect}>
          <th scope="row">{row.aspect}</th><td className="is-us">{row.llmslim}</td><td>{row.rival}</td>
        </tr>)}</tbody>
      </table></div>
    </section>

    <section className="bm-section" aria-labelledby="about-title">
      <SectionHead kicker={`What ${page.rival} is`} id="about-title" heading={[`What ${page.rival} is.`, "From its own docs."]} />
      <div className="cmp-pair">{page.about.map((item) => <article key={item.name} className="glow-card">
        <ProductLogo logo={rival.icon} size={28} className="cmp-pair-logo" />
        <h3>{item.name}</h3>
        <a className="cmp-cite" href={item.url} target="_blank" rel="noreferrer">{item.cite} <ArrowUpRight size={12} aria-hidden="true" /></a>
        <p>{item.body}</p>
      </article>)}</div>
      <p className="cmp-aside">{page.aboutNote}</p>
    </section>

    <section className="bm-section" aria-labelledby="differs-title">
      <SectionHead kicker="How LLMSlim differs" id="differs-title" heading={["Keep what was said.", "No LLM on the way in."]} />
      <ol className="cmp-notes">{page.differences.map((item, index) => <li key={item.title}>
        <span className="p-note-index">{String(index + 1).padStart(2, "0")}</span><h3>{item.title}</h3><p>{item.body}</p>
        <NamedProducts text={item.body} />
      </li>)}</ol>
    </section>

    {page.benchmarks.map((block) => {
      const domain = differenceDomain(block.pairedDiffs.map((row) => row.difference))
      return <section key={block.id} id={block.id} className="bm-section" aria-labelledby={`${block.id}-title`}>
        <SectionHead kicker={`Head to head · ${block.kicker}`} id={`${block.id}-title`} heading={block.heading}>
          <p className="p-body">{block.intro}</p>
        </SectionHead>
        {block.tables.map((table) => <div key={table.title} className="cmp-result">
          <h3 className="cmp-subhead">{table.title}</h3>
          <MotionTable className="bm-table-wrap"><table className="bm-table bm-h2h cmp-results">
            <thead><tr><th scope="col">System</th><th scope="col">Context tokens</th><th scope="col">Accuracy (95% CI)</th><th scope="col">Cost per 1k questions</th></tr></thead>
            <tbody>{table.rows.map((row, index) => <Fragment key={`${row.system}-${row.tokens}`}>
              {row.budget && row.budget !== table.rows[index - 1]?.budget && <tr className="cmp-budget"><th scope="rowgroup" colSpan={4}>{row.budget}</th></tr>}
              <tr className={`is-${row.kind}`}>
                <th scope="row"><SystemName system={row.system} /></th>
                <td className="num"><NumberCell text={row.tokens} /></td>
                <td className="num cmp-score"><ScoreCell score={row.score} /></td>
                <td className="num"><NumberCell text={row.cost} /></td>
              </tr>
            </Fragment>)}</tbody>
          </table></MotionTable>
          <p className="bm-note">{table.note}</p>
        </div>)}

        <h3 className="cmp-subhead">Paired differences with 95% intervals</h3>
        <MotionTable className="bm-table-wrap"><table className="bm-table cmp-diffs">
          <thead><tr><th scope="col">Comparison</th><th scope="col">Benchmark (questions)</th><th scope="col">Difference (95% CI)</th><th scope="col">Reading</th></tr></thead>
          <tbody>{block.pairedDiffs.map((row) => <tr key={`${row.benchmark}-${row.comparison}`}>
            <th scope="row">{row.comparison}</th><td>{row.benchmark}</td>
            <td className="cmp-diff"><span className="cmp-diff-text">{row.difference}</span><DiffPlot difference={row.difference} domain={domain} reading={row.reading} /></td>
            <td><Reading reading={row.reading} /></td>
          </tr>)}</tbody>
        </table></MotionTable>
        <p className="bm-note">{block.pairedNote} <span className="cmp-axis-note">Each plot runs from −{domain} to +{domain} points, with zero in the middle.</span></p>

        <h3 className="cmp-subhead">What this does not show</h3>
        <dl className="cmp-caveats">{block.caveats.map((caveat) => <div key={caveat.title}><dt>{caveat.title}</dt><dd>{caveat.body}</dd></div>)}</dl>
        <p className="cmp-links">
          {block.links.map((link) => <a key={link.url} className="text-link" href={link.url} target="_blank" rel="noreferrer">{link.label} <ArrowUpRight size={14} aria-hidden="true" /></a>)}
          <Link className="text-link" href="/benchmarks">Every benchmark <ArrowUpRight size={14} aria-hidden="true" /></Link>
        </p>
      </section>
    })}

    <section className="bm-section" aria-labelledby="choose-them-title">
      <SectionHead kicker={`When to choose ${page.rival}`} id="choose-them-title" heading={[`Cases where ${page.rival}`, "is the better fit."]} />
      <ul className="cmp-cards">{page.chooseThem.map((item) => <li key={item.title} className="glow-card"><h3>{item.title}</h3><p>{item.body}</p></li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="choose-us-title">
      <SectionHead kicker="When LLMSlim fits" id="choose-us-title" heading={["Where LLMSlim", "makes sense."]} />
      <ul className="cmp-fit">{page.chooseUs.map((line) => <li key={line}>{line}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="pricing-title">
      <SectionHead kicker={`Pricing · checked ${PRICES_CHECKED}`} id="pricing-title" heading={["What each costs.", "From each pricing page."]}>
        <p className="p-body">{page.pricing.intro}</p>
      </SectionHead>
      <PriceTable caption={page.rival} rows={page.pricing.rival.rows} logo={rival.icon} />
      <p className="bm-note bm-sources">Source: <a href={page.pricing.rival.url} target="_blank" rel="noreferrer">{page.pricing.rival.url.replace(/^https:\/\//, "")}</a>, checked {PRICES_CHECKED}. Prices change; check the page before you decide.</p>
      <PriceTable caption={LLMSLIM_PRICES_TITLE} rows={llmslimPriceRows()} logo="llmslim" />
      <p className="bm-note bm-sources">Source: <Link href="/pricing">llmslim.app/pricing</Link>, which also lists the plans in rupees.</p>
      <ul className="cmp-migration-general cmp-price-notes">{page.pricing.notes.map((note) => <li key={note}>{note}</li>)}</ul>
    </section>

    <section className="bm-section" aria-labelledby="migrate-title">
      <SectionHead kicker="Migrate" id="migrate-title" heading={["Bring your memory across.", "Tested, with real output."]}>
        <p className="p-body">{text(page.migration.intro)}</p>
      </SectionHead>
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
      <SectionHead kicker="FAQ" id="faq-title" heading={["Questions people ask", "before switching."]} />
      <div className="faq-list cmp-faq">{page.faqs.map(([question, answer]) => <details key={question}><summary>{question}<span className="faq-plus" aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div>
    </section>

    <section className="bm-section" aria-labelledby="sources-title">
      <h2 id="sources-title" className="bm-small-title">Sources</h2>
      <ul className="cmp-sources">{page.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label} <ArrowUpRight size={12} aria-hidden="true" /></a></li>)}</ul>
      <div className="cmp-end">
        <MemoryGlyph size={56} />
        <div className="cmp-cta">
          <Link className="button" href="/docs/quickstart-python">Get started <ArrowRight size={16} aria-hidden="true" /></Link>
          <Link className="button button-outline" href="/docs/quickstart-mcp">MCP quickstart</Link>
          <Link className="button button-outline" href="/benchmarks">Every benchmark</Link>
        </div>
      </div>
    </section>
  </div>
}
