import { Badge } from "@/components/ui/badge"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ClientStudioWrapper } from "@/components/studio/ClientStudioWrapper"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({ title: "LLMSlim Studio | Adaptive Context Planner", description: "Plan chat, RAG, memory, and tool context against a real model token budget and inspect every decision.", canonicalUrl: "https://www.llmslim.app/playground" })

export default function PlaygroundPage() {
  return <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 space-y-8 px-4 py-10 sm:px-6 lg:px-8"><header><Badge variant="secondary">Studio · v0.6.0</Badge><h1 className="mt-4 text-4xl font-semibold tracking-tight">Plan the whole context, not just one string.</h1><p className="mt-3 max-w-3xl text-muted-foreground">Allocate realistic conversation history, RAG evidence, memory, and authoritative tool schemas against a constrained model budget. Plan fully offline, use the protected quota-limited Sarvam demo, or provide a request-only Sarvam key.</p></header><ClientStudioWrapper /><div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><CardTitle>Real planner output</CardTitle><CardDescription>Token metrics and decisions are serialized directly from the Python <code>ContextPlan</code>. Compression occurs only when raw context exceeds the usable budget.</CardDescription></CardHeader></Card><Card><CardHeader><CardTitle>Explicit execution boundaries</CardTitle><CardDescription>LLMSlim never executes tools. Hosted mode keeps the project key server-side; BYOK credentials exist only for the current request and are never persisted.</CardDescription></CardHeader></Card></div></main>
}
