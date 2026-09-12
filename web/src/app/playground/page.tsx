import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ClientStudioWrapper } from "@/components/studio/ClientStudioWrapper"
import { constructMetadata } from "@/lib/seo"

export const metadata = constructMetadata({ title: "LLMSlim Studio | Live Python Compression", description: "Run live extractive compression with the repository LLMSlim Python package and inspect its returned token metrics.", canonicalUrl: "https://www.llmslim.app/playground" })

export default function PlaygroundPage() {
  return <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 space-y-8 px-4 py-10 sm:px-6 lg:px-8"><header><Badge variant="secondary">Studio</Badge><h1 className="mt-4 text-4xl font-semibold tracking-tight">Inspect the shape of context.</h1><p className="mt-3 max-w-3xl text-muted-foreground">Run live extractive compression with the shipped LLMSlim Python package. Output and token metrics come from the returned <code>CompressionResult</code>.</p></header><ClientStudioWrapper /><div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><CardTitle>Run extractive live</CardTitle><CardDescription>The public Studio runs the offline extractive path through its same-origin Python function.</CardDescription></CardHeader></Card><Card><CardHeader><CardTitle>Bring a provider for rewrite</CardTitle><CardDescription>Rewrite and hybrid require a caller-supplied provider and are not exposed by the public endpoint.</CardDescription></CardHeader></Card></div></main>
}
