import Link from "next/link"
import { notFound } from "next/navigation"
import { AlertTriangle, ArrowLeft, ArrowUpRight, BookOpen, CheckCircle2, Cpu, Layers, ShieldCheck, SlidersHorizontal, TriangleAlert, Zap } from "lucide-react"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { INTEGRATIONS_REGISTRY } from "@/data/integrations"
import { breadcrumbJsonLd, constructMetadata, faqJsonLd, jsonLdScript, techArticleJsonLd } from "@/lib/seo"

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) { const { slug } = await params; const item = INTEGRATIONS_REGISTRY[slug]; return item ? constructMetadata({ title: `LLMSlim + ${item.name} Integration Guide: Prompt & Context Compression`, description: item.description, path: `/integrations/${item.slug}`, markdownPath: `/integrations/${item.slug}.md`, type: "article" }) : constructMetadata({ title: "Integration Not Found | LLMSlim", description: "Requested platform integration not found." }) }
export async function generateStaticParams() { return Object.keys(INTEGRATIONS_REGISTRY).map((slug) => ({ slug })) }

export default async function IntegrationSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const item = INTEGRATIONS_REGISTRY[slug]; if (!item) notFound()
  const path = `/integrations/${item.slug}`
  const jsonLd = [
    techArticleJsonLd({ path, headline: `LLMSlim + ${item.name}`, description: item.description, section: item.category }),
    breadcrumbJsonLd([["Home", "/"], ["Integrations", "/integrations"], [item.name, path]]),
    ...(item.faqs.length > 0 ? [faqJsonLd(item.faqs.map((faq) => [faq.question, faq.answer] as const), path)] : []),
  ]
  // Numbered sections are counted as they render, so optional sections never leave a gap in the numbering.
  let section = 0
  const numbered = (title: string) => `${++section}. ${title}`
  // overflow-wrap:anywhere lets long identifiers (module paths, metadata keys) wrap on phones instead of widening the page.
  return <article className="mx-auto max-w-4xl space-y-8 [overflow-wrap:anywhere]"><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />
    <Button variant="ghost" size="sm" render={<Link href="/integrations" />}><ArrowLeft /> Back to integrations</Button>
    <header className="space-y-4"><div className="flex items-center gap-4"><Card className="p-3"><IntegrationIcon iconKey={item.iconKey} className="size-8" /></Card><div><div className="flex flex-wrap gap-2"><Badge>{item.category}</Badge><Badge variant="outline">{item.badgeText}</Badge></div><h1 className="mt-2 text-4xl font-semibold tracking-tight">LLMSlim + {item.name}</h1></div></div><p className="text-lg text-muted-foreground">{item.tagline}</p><p className="text-muted-foreground">{item.description}</p></header>
    <Guide title={numbered(item.setup ? "Installation and setup" : "Package installation")} icon={Zap}><p className="text-muted-foreground">{item.installNote ?? `Install LLMSlim and the official ${item.name} SDK using your package manager.`}</p><DocCodeBlock language="bash" filename="terminal" code={item.installation.command} />
      {/* Config files and wiring copied from the guide; each block spaces itself like the output block below. */}
      {item.setup?.map((step) => <div key={step.caption} className="mt-8">
        <p className="text-muted-foreground">{step.caption}</p>
        <DocCodeBlock language={step.language} filename={step.filename} code={step.code} />
      </div>)}
    </Guide>
    <Guide title={numbered("Architecture & execution flow")} icon={Layers}><Card><CardContent className="space-y-3">{item.architectureFlow.map((step, index) => <div key={step} className="flex gap-3"><Badge variant="secondary">{index + 1}</Badge><p className="text-sm text-muted-foreground">{step}</p></div>)}</CardContent></Card></Guide>
    <Guide title={numbered(item.output ? "Runnable example and its output" : "Production code pattern")} icon={Cpu}>
      <DocCodeBlock language={item.codeExample.language} filename={item.codeExample.filename} code={item.codeExample.code} />
      {/* .doc-code sets its own margins, so this block spaces itself instead of relying on space-y. */}
      {item.output && <div className="mt-8">
        <p className="text-sm text-muted-foreground">{item.output.caption}</p>
        <DocCodeBlock language="text" filename="output" code={item.output.text} wrap />
        <p className="mt-5 text-muted-foreground">{item.output.explanation}</p>
      </div>}
    </Guide>
    {/* Rows rather than a table: two columns on wide screens, stacked on phones, never a sideways scroll. */}
    {item.options && item.options.length > 0 && <Guide title={numbered("Options")} icon={SlidersHorizontal}><p className="text-muted-foreground">Keyword arguments, shown as <code className="font-mono text-sm">name = default</code>.</p><Card><CardContent><dl className="divide-y divide-border">{item.options.map((option) => <div key={option.name} className="grid gap-x-6 gap-y-1 py-3 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
      <dt className="font-mono text-xs leading-6">{option.name} <span className="text-muted-foreground">= {option.defaultValue}</span></dt>
      <dd className="text-sm leading-6 text-muted-foreground">{option.meaning}</dd>
    </div>)}</dl></CardContent></Card></Guide>}
    <Guide title={numbered("Deployment best practices")} icon={ShieldCheck}><Card><CardContent className="text-muted-foreground">{item.deploymentGuide}</CardContent></Card></Guide>
    <Guide title={numbered("Key optimization tips")} icon={CheckCircle2}><Card><CardContent><ul className="list-disc space-y-2 pl-5 text-muted-foreground">{item.optimizationTips.map((tip) => <li key={tip}>{tip}</li>)}</ul></CardContent></Card></Guide>
    {item.limitations && item.limitations.length > 0 && <Guide title={numbered("Limitations")} icon={TriangleAlert}><Card><CardContent><ul className="list-disc space-y-2 pl-5 text-muted-foreground">{item.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul></CardContent></Card></Guide>}
    {item.benchmarks.length > 0 && <Guide title={numbered("Performance metrics")}><Card><CardContent className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Metric</TableHead><TableHead>Uncompressed</TableHead><TableHead>LLMSlim</TableHead><TableHead>Impact</TableHead></TableRow></TableHeader><TableBody>{item.benchmarks.map((row) => <TableRow key={row.metric}><TableCell>{row.metric}</TableCell><TableCell>{row.uncompressed}</TableCell><TableCell>{row.compressed}</TableCell><TableCell>{row.impact}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card></Guide>}
    {item.faqs.length > 0 && <Guide title="Frequently asked questions"><Card><CardContent><Accordion>{item.faqs.map((faq) => <AccordionItem key={faq.question} value={faq.question}><AccordionTrigger>{faq.question}</AccordionTrigger><AccordionContent>{faq.answer}</AccordionContent></AccordionItem>)}</Accordion></CardContent></Card></Guide>}
    {item.troubleshooting.length > 0 && <Guide title="Troubleshooting" icon={AlertTriangle}>{item.troubleshooting.map((entry) => <Alert key={entry.issue}><AlertTriangle /><AlertTitle>{entry.issue}</AlertTitle><AlertDescription>{entry.solution}</AlertDescription></Alert>)}</Guide>}
    {item.links && item.links.length > 0 && <Guide title="Further reading" icon={BookOpen}><ul className="space-y-2">{item.links.map((link) => <li key={link.href}>{link.href.startsWith("/")
      ? <Link className="text-link" href={link.href}>{link.label} <ArrowUpRight size={14} aria-hidden="true" /></Link>
      : <a className="text-link" href={link.href} target="_blank" rel="noreferrer">{link.label} <ArrowUpRight size={14} aria-hidden="true" /></a>}</li>)}</ul></Guide>}
  </article>
}

function Guide({ title, icon: Icon, children }: { title: string; icon?: typeof Zap; children: React.ReactNode }) { return <section className="space-y-4 scroll-mt-24"><h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">{Icon && <Icon className="size-5" />}{title}</h2>{children}</section> }
