import { markdownFor, markdownPaths } from "@/lib/agent-content"
import { absoluteUrl } from "@/lib/seo"

// Served at "<page>.md" through a rewrite in next.config.ts; "/index.md" is the homepage.
export const dynamicParams = false

export function generateStaticParams() {
  return markdownPaths().map((path) => ({ path }))
}

export async function GET(_request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  const body = markdownFor(path)
  if (body === null) return new Response("Not found\n", { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } })
  const page = path[0] === "index" ? "/" : "/" + path.join("/")
  return new Response(body, {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      // The HTML page stays canonical for search engines; this is its plain-text twin for agents.
      Link: `<${absoluteUrl(page)}>; rel="canonical"`,
    },
  })
}
