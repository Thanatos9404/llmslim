import Link from "next/link"
import { notFound } from "next/navigation"
import { ArrowLeft, Clock3, ExternalLink } from "lucide-react"
import { DocCallout } from "@/components/docs/DocCallout"
import { DocCodeBlock } from "@/components/docs/DocCodeBlock"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { DOCS_REGISTRY } from "@/data/docs"
import { siteConfig } from "@/config/site"
import { constructMetadata } from "@/lib/seo"

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) { const { slug } = await params; const doc = DOCS_REGISTRY[slug]; return doc ? constructMetadata({ title: `${doc.title} — LLMSlim Documentation`, description: doc.description }) : constructMetadata({ title: "Page Not Found | LLMSlim Docs", description: "Requested documentation guide not found." }) }
export async function generateStaticParams() { return Object.keys(DOCS_REGISTRY).map((slug) => ({ slug })) }

export default async function DocSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params; const doc = DOCS_REGISTRY[slug]; if (!doc) notFound()
  const jsonLd = { "@context": "https://schema.org", "@type": "TechArticle", headline: doc.title, description: doc.description, url: `${siteConfig.url}/docs/${doc.slug}` }
  return <article className="mx-auto max-w-3xl space-y-8"><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} /><Button variant="ghost" size="sm" render={<Link href="/docs" />}><ArrowLeft /> All documentation</Button><header><div className="flex flex-wrap gap-2"><Badge>{doc.category}</Badge><Badge variant="outline"><Clock3 /> {doc.readingTime}</Badge><Badge variant="outline">Updated {doc.lastUpdated}</Badge></div><h1 className="mt-4 text-4xl font-semibold tracking-tight">{doc.title}</h1><p className="mt-3 text-lg text-muted-foreground">{doc.subtitle}</p></header><div className="space-y-10">{doc.sections.map((section) => <section id={section.id} key={section.id} className="scroll-mt-24"><h2 className="text-2xl font-semibold tracking-tight">{section.title}</h2><p className="mt-3 leading-7 text-muted-foreground">{section.content}</p>{section.callout && <DocCallout callout={section.callout} />}{section.codeSnippet && <DocCodeBlock language={section.codeSnippet.language} filename={section.codeSnippet.filename} code={section.codeSnippet.code} />}</section>)}</div>{doc.faqs.length > 0 && <Card><CardHeader><CardTitle>Frequently asked questions</CardTitle></CardHeader><CardContent><Accordion>{doc.faqs.map((faq) => <AccordionItem key={faq.question} value={faq.question}><AccordionTrigger>{faq.question}</AccordionTrigger><AccordionContent>{faq.answer}</AccordionContent></AccordionItem>)}</Accordion></CardContent></Card>}{doc.relatedPages.length > 0 && <Card><CardHeader><CardTitle>Continue reading</CardTitle></CardHeader><CardContent className="flex flex-wrap gap-2">{doc.relatedPages.map((item) => <Button key={item.slug} variant="outline" size="sm" render={<Link href={`/docs/${item.slug}`} />}>{item.title} <ExternalLink /></Button>)}</CardContent></Card>}</article>
}
