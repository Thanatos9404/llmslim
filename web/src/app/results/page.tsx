import { SiteFooter } from "@/components/site/SiteFooter"
import { SiteHeader } from "@/components/site/SiteHeader"
import { PageView } from "@/components/site/Telemetry"
import { ResultsStory } from "@/components/results/Story"
import { constructMetadata } from "@/lib/seo"
import "./story.css"

export const metadata = constructMetadata({
  title: "Results | LLMSlim",
  description: "What LLMSlim keeps and what it does to the answers: long chat memory, retrieval, long documents and agents, measured against full context, truncation, LLMLingua-2 and LongLLMLingua.",
  path: "/results",
  markdownPath: "/benchmarks.md",
  // The share images are results/opengraph-image.tsx and twitter-image.tsx.
  image: null,
})

export default function ResultsPage() {
  return <div className="slim-site rs-site"><PageView event="results_page_view" /><SiteHeader /><main id="main-content"><ResultsStory /></main><SiteFooter /></div>
}
