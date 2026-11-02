import Image from "next/image"
import { MemoryGlyph } from "@/components/brand/MemoryGlyph"
import { IntegrationRows } from "@/components/integrations/IntegrationRows"
import { StackDiagram } from "@/components/integrations/StackDiagram"
import { Reveal } from "@/components/motion/Reveal"
import { PageBackdrop } from "@/components/site/PageBackdrop"
import { BACKDROP_CODE } from "@/components/site/backdrop-code"
import { constructMetadata } from "@/lib/seo"
import { INTEGRATIONS_REGISTRY, INTEGRATION_CATEGORIES } from "@/data/integrations"
import "./integrations.css"

export const metadata = constructMetadata({ title: "Python Integrations | LLMSlim", description: "Use LLMSlim in LangChain, LlamaIndex, Haystack, gptme, Hermes Agent and Pydantic AI, or with your Python model client: install lines, runnable examples and their real output.", path: "/integrations", markdownPath: "/integrations.md" })

export default function IntegrationsIndexPage() {
  const integrations = Object.values(INTEGRATIONS_REGISTRY)
  return <div className="int-page int-v2 has-backdrop">
    <PageBackdrop code={BACKDROP_CODE.langchain} low />
    <header className="int-hero">
      <div className="int-hero-copy">
        <p className="p-kicker cmp-kicker"><MemoryGlyph size={14} />Python integrations</p>
        <h1>Output that fits <span>your existing stack.</span></h1>
        <p>Drop LLMSlim into a LangChain, LlamaIndex or Haystack pipeline, let it fit a gptme, Hermes Agent or Pydantic AI history into a token budget, or pass its output straight into the model client you already use. Provider calls stay in your application.</p>
      </div>
      <div className="int-stage on-dark">
        {/* A still photo here (the compare plates drift): this page already carries the pixel backdrop. */}
        <div className="px-photo" aria-hidden="true"><div className="px-photo-media">
          {/* Eager: the stage is the largest thing in the first screen on desktop and on most phones. */}
          <Image src="/media/stock/laptop-code.webp" alt="" fill loading="eager" sizes="(max-width: 980px) 100vw, 560px" style={{ objectPosition: "50% 40%" }} />
        </div></div>
        <div className="int-stage-veil" aria-hidden="true" />
        <StackDiagram />
      </div>
    </header>
    {INTEGRATION_CATEGORIES.map((category) => {
      const entries = integrations.filter((item) => item.category === category)
      return entries.length ? <section key={category} className="int-group" aria-label={category}>
        {/* A still glyph here: SVG transforms are not composited, and four animated glyphs cost this page's phone score. */}
        <Reveal className="int-group-head"><MemoryGlyph size={14} /><h2>{category}</h2></Reveal>
        <IntegrationRows items={entries.map(({ slug, name, badgeText, tagline, iconKey }) => ({ slug, name, badgeText, tagline, iconKey }))} />
      </section> : null
    })}
  </div>
}
