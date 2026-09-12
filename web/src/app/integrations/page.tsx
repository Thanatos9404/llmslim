import Link from "next/link"
import { ExternalLink, PlugZap } from "lucide-react"
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { constructMetadata } from "@/lib/seo"
import { INTEGRATIONS_REGISTRY, INTEGRATION_CATEGORIES } from "@/data/integrations"

export const metadata = constructMetadata({ title: "Python Integrations | LLMSlim", description: "Use LLMSlim output with documented Python model-client examples." })

export default function IntegrationsIndexPage() {
  const integrations = Object.values(INTEGRATIONS_REGISTRY)
  return <div className="mx-auto max-w-5xl space-y-10"><header><Badge variant="secondary"><PlugZap /> Python client examples</Badge><h1 className="mt-4 text-4xl font-semibold tracking-tight">Output that fits your existing stack.</h1><p className="mt-3 max-w-3xl text-muted-foreground">Integration patterns for passing LLMSlim output into model clients. Provider calls remain your application’s responsibility.</p></header>{INTEGRATION_CATEGORIES.map((category) => { const entries = integrations.filter((item) => item.category === category); return entries.length ? <section key={category}><div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-semibold">{category}</h2><Badge variant="outline">{entries.length} examples</Badge></div><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{entries.map((item) => <Card key={item.slug}><CardHeader><div className="flex items-center justify-between"><IntegrationIcon iconKey={item.iconKey} className="size-6" /><Badge variant="secondary">{item.badgeText}</Badge></div><CardTitle className="mt-3">{item.name}</CardTitle><CardDescription>{item.tagline}</CardDescription></CardHeader><CardFooter><Button variant="outline" size="sm" render={<Link href={`/integrations/${item.slug}`} />}>Read guide <ExternalLink /></Button></CardFooter></Card>)}</div></section> : null })}</div>
}
