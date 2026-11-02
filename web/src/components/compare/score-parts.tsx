import type { CSSProperties } from "react"
import { LogoMark } from "@/components/brand/LogoMark"
import { ProductLogo } from "@/components/brand/ProductLogo"
import { logoForSystem } from "@/components/brand/product-logos"

/**
 * Server-rendered pieces of the results tables. Every number is printed exactly as the data has it; the bars and
 * plots beside them are aria-hidden drawings of those same numbers, and MotionTable animates them on the client.
 */

const toNumber = (text: string) => Number(text.replace(/−/g, "-").replace(/,/g, ""))

/** A number that counts up when its table scrolls into view. The text in the page is the final text. */
export function Tick({ text }: { text: string }) {
  return <span className="tk" data-tick={text}><span className="tk-final">{text}</span><span className="tk-run" aria-hidden="true" /></span>
}

/** A 0 to 100 bar for an accuracy, with its 95% interval as a faint band when there is one. */
export function ScoreBar({ value, low, high }: { value: number; low?: number; high?: number }) {
  const style = {
    "--v": value / 100,
    ...(low !== undefined && high !== undefined ? { "--ci-l": `${low}%`, "--ci-w": `${high - low}%` } : {}),
  } as CSSProperties
  return <span className="sb" style={style} aria-hidden="true">
    {low !== undefined && <span className="sb-ci" />}
    <span className="sb-fill" />
  </span>
}

/** "91.7 (90.3–93.3)": the score counts up, the interval stays as printed, and a bar draws both. */
export function ScoreCell({ score }: { score: string }) {
  const match = score.match(/^(\d+(?:\.\d+)?) \((\d+(?:\.\d+)?)–(\d+(?:\.\d+)?)\)$/)
  if (!match) return <>{score}</>
  const [, value, low, high] = match
  return <>
    <span className="sc-text"><Tick text={value} />{" "}<span className="sc-ci">({low}–{high})</span></span>
    <ScoreBar value={Number(value)} low={Number(low)} high={Number(high)} />
  </>
}

/** A plain number (a score, tokens or a cost) that counts up; anything else ("not run", "74.4 / 74.4") stays text. */
export function NumberCell({ text, bar = false }: { text: string; bar?: boolean }) {
  if (!/^\$?[\d,]+(?:\.\d+)?$/.test(text)) return <>{text}</>
  return <>
    <span className="sc-text"><Tick text={text} /></span>
    {bar && <ScoreBar value={toNumber(text)} />}
  </>
}

/** "+0.8 (−0.9, +2.5)" -> [0.8, -0.9, 2.5]. */
export function parseDifference(difference: string): [number, number, number] | null {
  const numbers = difference.replace(/−/g, "-").match(/[-+]?\d+(?:\.\d+)?/g)
  return numbers && numbers.length === 3 ? (numbers.map(Number) as [number, number, number]) : null
}

/** The half-width of a difference axis that fits every interval in a table, rounded up to 5 points. */
export function differenceDomain(differences: string[]) {
  const extent = Math.max(5, ...differences.flatMap((text) => (parseDifference(text) ?? [0]).map(Math.abs)))
  return Math.ceil(extent / 5) * 5
}

/** A paired difference on an axis centred on zero: the interval as a band, the estimate as a dot. */
export function DiffPlot({ difference, domain, reading }: { difference: string; domain: number; reading: string }) {
  const parsed = parseDifference(difference)
  if (!parsed) return null
  const [point, low, high] = parsed
  const at = (value: number) => 50 + (value / domain) * 50
  const style = { "--ci-l": `${at(low)}%`, "--ci-w": `${at(high) - at(low)}%`, "--p": `${at(point)}%` } as CSSProperties
  return <span className={`dp is-${reading.toLowerCase()}`} aria-hidden="true">
    <span className="dp-axis" />
    <span className="dp-mark" style={style}><span className="dp-ci" /><span className="dp-dot" /></span>
  </span>
}

/** Level, Ahead or Behind, as a small labelled pill. */
export function Reading({ reading }: { reading: string }) {
  return <span className={`rd is-${reading.toLowerCase()}`}>{reading}</span>
}

/** A system's name with its product's logo, when the name starts with a product. */
export function SystemName({ system }: { system: string }) {
  const logo = logoForSystem(system)
  return <span className="sys">
    <span className="sys-logo" aria-hidden="true">
      {logo === "llmslim" ? <LogoMark size={11} /> : logo ? <ProductLogo logo={logo} size={16} /> : <span className="sys-dot" />}
    </span>
    <span>{system}</span>
  </span>
}
