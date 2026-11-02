import { notFound } from "next/navigation"
import { DocArticle } from "@/components/docs/DocArticle"
import { DocsIndex, docsIndexMetadata } from "@/components/docs/DocsIndex"
import { DOCS_BY_VERSION } from "@/data/docs"
import { DEFAULT_DOCS_VERSION, DOCS_VERSIONS, docHref, isDocsVersion, versionStatus, type DocsVersion } from "@/data/docs-versions"
import { constructMetadata } from "@/lib/seo"

/**
 * Every docs page but the home: /docs/<slug> for the default version (src/data/docs-versions.ts), and /docs/<version>
 * and /docs/<version>/<slug> for the others. /docs/<default version>/... redirects to /docs/... (next.config.ts).
 */
export const dynamicParams = false

type Target = { version: DocsVersion; slug: string | null }

function target(path: string[]): Target | null {
  const [first, second, ...rest] = path
  if (rest.length > 0) return null
  if (second === undefined) {
    if (isDocsVersion(first)) return first === DEFAULT_DOCS_VERSION ? null : { version: first, slug: null }
    return DOCS_BY_VERSION[DEFAULT_DOCS_VERSION][first] ? { version: DEFAULT_DOCS_VERSION, slug: first } : null
  }
  if (!isDocsVersion(first) || first === DEFAULT_DOCS_VERSION) return null
  return DOCS_BY_VERSION[first][second] ? { version: first, slug: second } : null
}

export function generateStaticParams() {
  return [
    ...Object.keys(DOCS_BY_VERSION[DEFAULT_DOCS_VERSION]).map((slug) => ({ path: [slug] })),
    ...DOCS_VERSIONS.filter(({ id }) => id !== DEFAULT_DOCS_VERSION).flatMap(({ id }) => [
      { path: [id] },
      ...Object.keys(DOCS_BY_VERSION[id]).map((slug) => ({ path: [id, slug] })),
    ]),
  ]
}

export async function generateMetadata({ params }: { params: Promise<{ path: string[] }> }) {
  const found = target((await params).path)
  if (!found) return constructMetadata({ title: "Page Not Found | LLMSlim Docs", description: "Requested documentation guide not found.", noIndex: true })
  if (found.slug === null) return docsIndexMetadata(found.version)
  const doc = DOCS_BY_VERSION[found.version][found.slug]
  const status = versionStatus(found.version)
  const path = docHref(found.version, doc.slug)
  return constructMetadata({
    title: status === "current" ? `${doc.title} | LLMSlim Documentation` : `${doc.title} | LLMSlim ${found.version} Documentation${status === "preview" ? " (Preview)" : ""}`,
    description: status === "preview" ? `Upcoming in LLMSlim ${found.version}: ${doc.description}` : doc.description,
    path,
    markdownPath: `${path}.md`,
    type: "article",
    // Only the version pip installs is indexed: a preview describes unreleased code, and an old version is superseded.
    noIndex: status !== "current",
  })
}

export default async function DocsPathPage({ params }: { params: Promise<{ path: string[] }> }) {
  const found = target((await params).path)
  if (!found) notFound()
  if (found.slug === null) return <DocsIndex version={found.version} />
  return <DocArticle doc={DOCS_BY_VERSION[found.version][found.slug]} version={found.version} />
}
