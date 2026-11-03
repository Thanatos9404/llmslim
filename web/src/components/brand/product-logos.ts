/**
 * Product logos, self-hosted in public/logos (sources, licences and dates in public/logos/SOURCES.md). They identify
 * the products a page names, nothing more: no endorsement or partnership is implied.
 *
 * - "mask": a single-colour mark drawn as a CSS mask, in the product's colour (`color`, and `colorDark` where the
 *   light-theme colour is too dark on the dark surface) or, when neither is set, in the ink colour.
 * - "image": the vendor's own multi-colour file, shown as it is (`srcDark` for its variant on dark backgrounds).
 */
export type ProductLogoSpec = {
  name: string
  kind: "mask" | "image"
  src: string
  srcDark?: string
  color?: string
  colorDark?: string
  /** Width over height, for wordmarks; marks are square. */
  ratio?: number
}

export const PRODUCT_LOGOS = {
  anthropic: { name: "Anthropic", kind: "mask", src: "/logos/anthropic.svg" },
  claude: { name: "Claude", kind: "mask", src: "/logos/claude.svg", color: "#D97757" },
  "claude-code": { name: "Claude Code", kind: "mask", src: "/logos/claude-code.svg", color: "#D97757" },
  cursor: { name: "Cursor", kind: "mask", src: "/logos/cursor.svg" },
  exa: { name: "Exa", kind: "image", src: "/startups/exa-blue.svg", srcDark: "/startups/exa-white.svg", ratio: 1 },
  gemini: { name: "Google Gemini", kind: "mask", src: "/logos/google-gemini.svg", color: "#8E75B2", colorDark: "#A893D4" },
  gptme: { name: "gptme", kind: "mask", src: "/logos/gptme-mono.svg" },
  haystack: { name: "Haystack", kind: "mask", src: "/logos/haystack.svg", color: "#0EAF9C" },
  langchain: { name: "LangChain", kind: "mask", src: "/logos/langchain.svg", colorDark: "#7FC8FF" },
  llamaindex: { name: "LlamaIndex", kind: "image", src: "/logos/llamaindex-icon.svg" },
  llmlingua: { name: "LLMLingua", kind: "image", src: "/logos/llmlingua.webp" },
  mastra: { name: "Mastra", kind: "mask", src: "/logos/mastra.svg", ratio: 34 / 21 },
  mcp: { name: "Model Context Protocol", kind: "mask", src: "/logos/mcp.svg" },
  mem0: { name: "Mem0", kind: "image", src: "/logos/mem0-icon.svg" },
  "mem0-wordmark": { name: "Mem0", kind: "image", src: "/logos/mem0-wordmark-light.svg", srcDark: "/logos/mem0-wordmark-dark.svg", ratio: 3760 / 1050 },
  mongodb: { name: "MongoDB", kind: "mask", src: "/logos/mongodb.svg", color: "#47A248" },
  neo4j: { name: "Neo4j", kind: "mask", src: "/logos/neo4j.svg", color: "#4581C3", colorDark: "#6FA0DC" },
  openai: { name: "OpenAI", kind: "mask", src: "/openai-symbol.svg" },
  postgresql: { name: "PostgreSQL", kind: "mask", src: "/logos/postgresql.svg", color: "#4169E1", colorDark: "#6F8FF0" },
  pydantic: { name: "Pydantic", kind: "mask", src: "/logos/pydantic.svg", color: "#E92063" },
  python: { name: "Python", kind: "mask", src: "/logos/python.svg", color: "#3776AB", colorDark: "#6FA3D8" },
  qwen: { name: "Qwen", kind: "mask", src: "/logos/qwen.svg", color: "#6950EF", colorDark: "#8F7DF5" },
  razorpay: { name: "Razorpay", kind: "mask", src: "/logos/razorpay.svg", color: "#0C2451", colorDark: "#3395FF" },
  sarvam: { name: "Sarvam", kind: "mask", src: "/sarvam-symbol.svg" },
  sqlite: { name: "SQLite", kind: "mask", src: "/logos/sqlite.svg", color: "#003B57", colorDark: "#5FB4E0" },
  vercel: { name: "Vercel", kind: "mask", src: "/logos/vercel.svg" },
  zep: { name: "Zep", kind: "image", src: "/logos/zep-icon.svg" },
  // One colour, Zep's purple; on dark backgrounds it is drawn in the ink colour instead (no light variant is published).
  "zep-wordmark": { name: "Zep", kind: "mask", src: "/logos/zep-lockup.svg", color: "#4226AA", colorDark: "var(--ink)", ratio: 603.74 / 226.75 },
  zoho: { name: "Zoho", kind: "mask", src: "/logos/zoho.svg", color: "#E42527" },
} satisfies Record<string, ProductLogoSpec>

export type ProductLogoKey = keyof typeof PRODUCT_LOGOS

/** Integration pages (data/integrations.ts slugs) to logos. A slug not listed (hermes-agent) keeps IntegrationIcon. */
export const INTEGRATION_LOGOS: Partial<Record<string, ProductLogoKey>> = {
  sarvam: "sarvam", zoho: "zoho", mongodb: "mongodb", exa: "exa", neo4j: "neo4j", openai: "openai", anthropic: "anthropic",
  gemini: "gemini", langchain: "langchain", llamaindex: "llamaindex", haystack: "haystack", gptme: "gptme",
  "pydantic-ai": "pydantic", "vercel-ai-sdk": "vercel", mastra: "mastra", mcp: "mcp", "claude-code": "claude-code",
}

/** Products a sentence names, in the order they are listed here: for small logo chips beside that sentence. */
const NAMED: [RegExp, ProductLogoKey][] = [
  [/\bClaude Code\b/, "claude-code"], [/\bClaude Desktop\b/, "claude"], [/\bCursor\b/, "cursor"], [/\bMCP\b/, "mcp"],
  [/\bVercel AI SDK\b/, "vercel"], [/\bMastra\b/, "mastra"], [/\bSQLite\b/, "sqlite"], [/\bPostgres(?:QL)?\b/, "postgresql"],
  [/\bMongoDB\b/, "mongodb"], [/\bNeo4j\b/, "neo4j"], [/\bLangChain\b/, "langchain"], [/\bLlamaIndex\b/, "llamaindex"], [/\bHaystack\b/, "haystack"],
]

export function productsNamedIn(text: string): ProductLogoKey[] {
  return NAMED.filter(([pattern]) => pattern.test(text)).map(([, key]) => key)
}

/** The logo for a system named in a results table, if the name starts with a product. */
export function logoForSystem(system: string): ProductLogoKey | "llmslim" | undefined {
  if (/^LLMSlim\b/.test(system)) return "llmslim"
  if (/^Mem0\b/.test(system)) return "mem0"
  if (/^Zep\b/.test(system)) return "zep"
  if (/^(?:LLMLingua|LongLLMLingua)/.test(system)) return "llmlingua"
  if (/Qwen/.test(system)) return "qwen"
  return undefined
}
