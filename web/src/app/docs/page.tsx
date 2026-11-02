import { DocsIndex, docsIndexMetadata } from "@/components/docs/DocsIndex"
import { DEFAULT_DOCS_VERSION } from "@/data/docs-versions"

export const metadata = docsIndexMetadata(DEFAULT_DOCS_VERSION)

export default function DocsIndexPage() {
  return <DocsIndex version={DEFAULT_DOCS_VERSION} />
}
