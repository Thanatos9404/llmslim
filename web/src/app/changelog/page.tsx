import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { PageBackdrop } from "@/components/site/PageBackdrop";
import { BACKDROP_CODE } from "@/components/site/backdrop-code";
import { siteConfig } from "@/config/site";
import { releases } from "@/data/changelog";
import { constructMetadata } from "@/lib/seo";

export const metadata = constructMetadata({
  title: "LLMSlim release history | Changelog",
  description: "LLMSlim package history through v0.7.2, including planner relevance fixes and the cache-aware context runtime.",
  path: "/changelog", markdownPath: "/changelog.md"
});

export default function ChangelogPage() {
  return <div className="backdrop-clip flex min-h-screen flex-col"><SiteHeader /><main id="main-content" className="has-backdrop mx-auto w-full max-w-5xl flex-1 space-y-8 px-4 py-10 sm:px-6 lg:px-8"><PageBackdrop code={BACKDROP_CODE.upgrade(siteConfig.coreVersion)} /><header className="ch-head pt-16"><p className="p-kicker">Release history</p><h1>Changes with <span>consequences.</span></h1><p>LLMSlim releases document what shipped, what changed, and where the boundary remains.</p></header>{releases.map((release) => <Card key={release.version} className="glow-card"><CardHeader><div className="flex flex-wrap items-center gap-2"><Badge>{release.version}</Badge><Badge variant="outline">{release.date}</Badge></div><CardTitle className="mt-2 text-2xl">{release.theme}</CardTitle><CardDescription>{release.summary}</CardDescription></CardHeader><CardContent className="space-y-5"><div className="flex flex-wrap gap-2">{release.metrics.map((metric) => <Badge key={metric} variant="secondary">{metric}</Badge>)}</div><div className="space-y-4">{release.items.map((item) => { const Icon = item.icon; return <div key={item.title} className="flex gap-3"><Icon className="mt-0.5 size-5 shrink-0" /><div><p className="text-sm font-medium">{item.title}</p><p className="mt-1 text-sm leading-6 text-muted-foreground">{item.body}</p></div></div> })}</div></CardContent>{release.tag && <CardFooter><Button variant="outline" size="sm" render={<a href={release.tag} target="_blank" rel="noreferrer" />}>View verified source</Button></CardFooter>}</Card>)}</main><SiteFooter /></div>;
}
