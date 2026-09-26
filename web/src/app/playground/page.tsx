import { Badge } from "@/components/ui/badge"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ClientStudioWrapper } from "@/components/studio/ClientStudioWrapper"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({ title: "LLMSlim Studio | Context Inspector", description: "Inspect provenance-aware agent context, quality gates, dependencies, token budgets, and trace decisions.", canonicalUrl: "https://www.llmslim.app/playground" })

export default function PlaygroundPage() {
  return <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 space-y-8 px-4 py-10 sm:px-6 lg:px-8"><header><Badge variant="secondary">Studio · Agent context</Badge><h1 className="mt-4 text-4xl font-semibold tracking-tight">Inspect the context each agent turn sees.</h1><p className="mt-3 max-w-3xl text-muted-foreground">Prepare conversation, RAG, memory, tool result, and schema context against a model budget. Inspect quality gates, dependencies, and a local trace. Use the Adaptive Planner tab to inspect an individual context plan.</p></header><ClientStudioWrapper /><div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><CardTitle>Real runtime output</CardTitle><CardDescription>Token metrics, decisions, quality gates, and graph edges come from the Python ContextRuntime. No model call occurs in the Context Inspector.</CardDescription></CardHeader></Card><Card><CardHeader><CardTitle>Explicit execution boundaries</CardTitle><CardDescription>LLMSlim prepares context but never authorizes or executes tools. Provider calls remain host-owned.</CardDescription></CardHeader></Card></div></main>
}
