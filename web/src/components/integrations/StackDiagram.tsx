import Link from "next/link"
import type { CSSProperties } from "react"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { ProductLogo } from "@/components/brand/ProductLogo"
import { PRODUCT_LOGOS, type ProductLogoKey } from "@/components/brand/product-logos"
import { StackHover } from "./StackHover"

/**
 * The integrations hero: frameworks on one side, the model clients on the other, and LLMSlim between them, joined by
 * strands like the mark's. Each logo links to its guide; pointing at one (or focusing it) lifts it on a spring curve and
 * sets context flowing along its strand (StackHover and integrations.css). Nothing animates on its own, so the page
 * does no repaint work while it loads, and the drawing is server-rendered: only the hover handler hydrates.
 *
 * Two drawings of the strands, wide and tall, so the logos keep their size on a phone instead of shrinking with the
 * drawing; the logos themselves are rendered once and placed by CSS variables for each layout.
 */

type Node = { slug: string; logo: ProductLogoKey; side: "in" | "out" }

const NODES: Node[] = [
  { slug: "langchain", logo: "langchain", side: "in" },
  { slug: "llamaindex", logo: "llamaindex", side: "in" },
  { slug: "haystack", logo: "haystack", side: "in" },
  { slug: "pydantic-ai", logo: "pydantic", side: "in" },
  { slug: "vercel-ai-sdk", logo: "vercel", side: "in" },
  { slug: "mastra", logo: "mastra", side: "in" },
  { slug: "openai", logo: "openai", side: "out" },
  { slug: "anthropic", logo: "anthropic", side: "out" },
  { slug: "gemini", logo: "gemini", side: "out" },
  { slug: "sarvam", logo: "sarvam", side: "out" },
]
const NAMES: Record<string, string> = { "pydantic-ai": "Pydantic AI", "vercel-ai-sdk": "Vercel AI SDK" }

type Point = readonly [number, number]
type Layout = { width: number; height: number; center: Point; at: (node: Node, index: number, count: number) => Point; strand: (from: Point, to: Point, side: Node["side"]) => string }

const WIDE: Layout = {
  width: 640, height: 400, center: [320, 200],
  at: (node, index, count) => [node.side === "in" ? 70 : 570, node.side === "in" ? 50 + index * 60 : 200 - ((count - 1) * 64) / 2 + index * 64],
  strand: ([x1, y1], [x2, y2], side) => side === "in"
    ? `M${x1 + 26} ${y1} C${x1 + 130} ${y1} ${x2 - 150} ${y2} ${x2 - 52} ${y2}`
    : `M${x2 + 52} ${y2} C${x2 + 150} ${y2} ${x1 - 130} ${y1} ${x1 - 26} ${y1}`,
}
const TALL: Layout = {
  width: 360, height: 470, center: [180, 235],
  at: (node, index, count) => node.side === "in"
    ? [180 - ((count - 1) * 56) / 2 + index * 56, 40]
    : [180 - ((count - 1) * 72) / 2 + index * 72, 430],
  strand: ([x1, y1], [x2, y2], side) => side === "in"
    ? `M${x1} ${y1 + 24} C${x1} ${y1 + 110} ${x2} ${y2 - 130} ${x2} ${y2 - 52}`
    : `M${x2} ${y2 + 52} C${x2} ${y2 + 130} ${x1} ${y1 - 110} ${x1} ${y1 - 24}`,
}

/** Each node's position in a layout. */
function place(layout: Layout) {
  const ins = NODES.filter((node) => node.side === "in")
  const outs = NODES.filter((node) => node.side === "out")
  return new Map(NODES.map((node) => {
    const group = node.side === "in" ? ins : outs
    return [node.slug, layout.at(node, group.indexOf(node), group.length)] as const
  }))
}
const PLACED = { wide: place(WIDE), tall: place(TALL) }
const pct = (value: number, total: number) => `${(value / total) * 100}%`
const position = (wide: Point, tall: Point) => ({ "--wx": pct(wide[0], WIDE.width), "--wy": pct(wide[1], WIDE.height), "--tx": pct(tall[0], TALL.width), "--ty": pct(tall[1], TALL.height) }) as CSSProperties

function Strands({ layout, name }: { layout: Layout; name: "wide" | "tall" }) {
  return <svg className={`stack-strands stack-strands-${name}`} viewBox={`0 0 ${layout.width} ${layout.height}`} aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id={`stack-spectrum-${name}`} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={name === "tall" ? 0 : layout.width} y2={name === "tall" ? layout.height : 0}>
        <stop offset="0" style={{ stopColor: "var(--mark-left-0)" }} />
        <stop offset=".5" style={{ stopColor: "var(--mark-left-2)" }} />
        <stop offset="1" style={{ stopColor: "var(--mark-end-4)" }} />
      </linearGradient>
    </defs>
    {NODES.map((node) => {
      const d = layout.strand(PLACED[name].get(node.slug)!, layout.center, node.side)
      return <g key={node.slug} className="stack-strand" data-slug={node.slug}>
        <path className="stack-strand-base" d={d} />
        <path className="stack-strand-flow" d={d} stroke={`url(#stack-spectrum-${name})`} pathLength={100} />
      </g>
    })}
  </svg>
}

export function StackDiagram() {
  return <StackHover>
    <Strands layout={WIDE} name="wide" />
    <Strands layout={TALL} name="tall" />
    <div className="stack-core" style={position(WIDE.center, TALL.center)}><MemoryGlyph size={44} title="LLMSlim" /></div>
    {NODES.map((node) => {
      const label = `${NAMES[node.slug] ?? PRODUCT_LOGOS[node.logo].name} integration`
      return <div key={node.slug} className="stack-node" style={position(PLACED.wide.get(node.slug)!, PLACED.tall.get(node.slug)!)}>
        <Link href={`/integrations/${node.slug}`} data-slug={node.slug} aria-label={label} title={label.replace(/ integration$/, "")}>
          <ProductLogo logo={node.logo} size={22} />
        </Link>
      </div>
    })}
  </StackHover>
}
