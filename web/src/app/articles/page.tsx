import Link from "next/link"
import { Clock3, ExternalLink, FileText, Sigma } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { constructMetadata } from "@/lib/seo"
import { ARTICLES_REGISTRY, ARTICLE_CATEGORIES } from "@/data/articles"

export const metadata = constructMetadata({ title: "Engineering Articles & Research Papers — LLMSlim", description: "Technical writing about prompt compression, context safety, and evaluation." })

export default function ArticlesIndexPage() {
  const articles = Object.values(ARTICLES_REGISTRY); const featured = articles[0]
  return <div className="mx-auto max-w-5xl space-y-10"><header><Badge variant="secondary"><FileText /> Engineering notes & research</Badge><h1 className="mt-4 text-4xl font-semibold tracking-tight">Context, examined in public.</h1><p className="mt-3 max-w-3xl text-muted-foreground">Technical explorations of graph centrality, token economics, attention saliency, and provenance-aware compression.</p></header><Card><CardHeader><Badge variant="outline" className="w-fit">Featured paper · {featured.readingTime}</Badge><CardTitle className="mt-3 text-2xl">{featured.title}</CardTitle><CardDescription>{featured.subtitle} — {featured.abstract}</CardDescription><p className="flex items-center gap-2 text-sm text-muted-foreground"><Sigma className="size-4" /> {featured.mathIntuitionSummary}</p></CardHeader><CardFooter><Button render={<Link href={`/articles/${featured.slug}`} />}>Read article <ExternalLink /></Button></CardFooter></Card>{ARTICLE_CATEGORIES.map((category) => { const items = articles.filter((article) => article.category === category); return items.length ? <section key={category}><div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-semibold">{category}</h2><Badge variant="outline">{items.length} papers</Badge></div><div className="grid gap-3">{items.map((article) => <Card key={article.slug} size="sm"><CardHeader><CardTitle>{article.title}</CardTitle><CardDescription>{article.subtitle}</CardDescription></CardHeader><CardFooter><Button variant="ghost" size="sm" render={<Link href={`/articles/${article.slug}`} />}><Clock3 /> {article.readingTime} <ExternalLink /></Button></CardFooter></Card>)}</div></section> : null })}</div>
}
