import Link from "next/link"
import { BookOpen, Code2, ExternalLink, Sparkles } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { constructMetadata } from "@/lib/seo"
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs"

export const metadata = constructMetadata({ title: "Documentation — LLMSlim Prompt & Context Compression", description: "Released developer documentation for LLMSlim." })

export default function DocsIndexPage() {
  const docs = Object.values(DOCS_REGISTRY)
  return <div className="mx-auto max-w-5xl space-y-10"><header><Badge variant="secondary"><BookOpen /> Released Python documentation</Badge><h1 className="mt-4 text-4xl font-semibold tracking-tight">Build with the released engine.</h1><p className="mt-3 max-w-3xl text-muted-foreground">Concise guides for context roles, pipelines, token accounting, and the safety boundaries that ship in LLMSlim.</p></header><div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><Sparkles className="size-5" /><CardTitle className="mt-3">Overview & philosophy</CardTitle><CardDescription>Understand what runs locally, what needs a provider, and where the trust boundary sits.</CardDescription></CardHeader><CardFooter><Button variant="outline" render={<Link href="/docs/getting-started" />}>Start here <ExternalLink /></Button></CardFooter></Card><Card><CardHeader><Code2 className="size-5" /><CardTitle className="mt-3">Python SDK integration</CardTitle><CardDescription>Make one real extraction call, then choose the correct role and counter for your workflow.</CardDescription></CardHeader><CardFooter><Button variant="outline" render={<Link href="/docs/getting-started" />}>Quick start <ExternalLink /></Button></CardFooter></Card></div>{DOC_CATEGORIES.map((category) => { const items = docs.filter((doc) => doc.category === category); return items.length ? <section key={category}><div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-semibold">{category}</h2><Badge variant="outline">{items.length} guides</Badge></div><div className="grid gap-3">{items.map((doc) => <Card key={doc.slug} size="sm"><CardHeader><CardTitle>{doc.title}</CardTitle><CardDescription>{doc.description}</CardDescription></CardHeader><CardFooter><Button variant="ghost" size="sm" render={<Link href={`/docs/${doc.slug}`} />}>{doc.readingTime} <ExternalLink /></Button></CardFooter></Card>)}</div></section> : null })}</div>
}
