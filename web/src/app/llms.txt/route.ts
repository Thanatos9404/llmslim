import { llmsTxt } from "@/lib/agent-content"

export const dynamic = "force-static"

export function GET() {
  return new Response(llmsTxt(), { headers: { "Content-Type": "text/plain; charset=utf-8", "X-Robots-Tag": "noindex" } })
}
