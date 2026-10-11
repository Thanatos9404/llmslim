import { StudioLab } from "@/components/studio/Lab"
import { constructMetadata } from "@/lib/seo"
import "./studio.css"

export const metadata = constructMetadata({
  title: "Studio | LLMSlim",
  description: "Pick a scenario, ask a question and watch LLMSlim cut an agent's context down to what answers it, next to plain truncation to the same size.",
  path: "/playground",
})

export default function PlaygroundPage() {
  return <main id="main-content" className="slim-site lab-site"><StudioLab /></main>
}
