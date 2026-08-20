import { constructMetadata } from "@/lib/seo";
import { ClientStudioWrapper } from "@/components/studio/ClientStudioWrapper";

export const metadata = constructMetadata({
  title: "LLMSlim Studio | Live Python Compression",
  description: "Run live extractive compression with the repository LLMSlim Python package and inspect its returned token metrics.",
  canonicalUrl: "https://www.llmslim.app/playground",
});

export default function PlaygroundPage() {
  return <main id="main-content" className="studio-page">
    <div className="studio-intro">
      <div><span className="eyebrow">Studio</span><h1>Inspect the shape of context.</h1></div>
      <p>Run live extractive compression with the same LLMSlim Python package shipped from this repository. Output and token metrics come from the returned <code>CompressionResult</code>.</p>
    </div>
    <ClientStudioWrapper />
    <section className="product-section" style={{ paddingBottom: 0 }}>
      <div><span className="section-label">Live engine boundary</span><h2>Python execution, with the right limits.</h2></div>
      <div><p>Set the correct context role when you know the provenance. RAG, tool, and assistant text are treated differently from system and developer text in the v0.4.0 safety boundary.</p><div className="method-list"><div className="method"><span className="method__number">01</span><div><h3>Run extractive live</h3><p>The public Studio runs the offline extractive path through its same-origin Python function.</p></div></div><div className="method"><span className="method__number">02</span><div><h3>Bring a provider for rewrite</h3><p>Rewrite and hybrid require a caller-supplied provider and are not exposed by the public endpoint.</p></div></div></div></div>
    </section>
  </main>;
}
