/**
 * The versions of LLMSlim Core the docs describe, and which one /docs shows.
 *
 * This module imports nothing, so next.config.ts can read it too (the redirects of the default version's prefix).
 */

/** Newest first. Each version's pages live at /docs/<id>/<slug>; the default version's also at /docs/<slug>. */
export const DOCS_VERSIONS = [
  // `ships` says how a preview reaches PyPI, for the notice on its pages.
  { id: "1.0", label: "1.0", ships: "the 0.13 release candidate and then 1.0" },
  { id: "0.12", label: "0.12", ships: "0.12.0" },
] as const

export type DocsVersion = (typeof DOCS_VERSIONS)[number]["id"]

/**
 * The version /docs and /docs/<slug> show: what `pip install llmslim` installs. Until 1.0 is on PyPI that is 0.12, and
 * the 1.0 pages carry an "Upcoming in 1.0" notice. On release day, set it to "1.0": that is the only change. The 1.0
 * pages move to /docs/<slug>, the 0.12 pages stay at /docs/0.12/<slug> with a notice that 1.0 is current, and
 * /docs/1.0/... redirects to /docs/... (next.config.ts).
 */
export const DEFAULT_DOCS_VERSION: DocsVersion = "0.12"

export const isDocsVersion = (value: string): value is DocsVersion => DOCS_VERSIONS.some((version) => version.id === value)

/** "preview" for a version newer than the default, "current" for the default, "previous" for an older one. */
export type DocsVersionStatus = "preview" | "current" | "previous"

export function versionStatus(version: DocsVersion, current: DocsVersion = DEFAULT_DOCS_VERSION): DocsVersionStatus {
  const order = DOCS_VERSIONS.findIndex((item) => item.id === version)
  const base = DOCS_VERSIONS.findIndex((item) => item.id === current)
  return order === base ? "current" : order < base ? "preview" : "previous"
}

/** The docs home of a version: /docs for the default version, /docs/<version> for the others. */
export function docsHome(version: DocsVersion, current: DocsVersion = DEFAULT_DOCS_VERSION): string {
  return version === current ? "/docs" : `/docs/${version}`
}

/** The URL of a page in a version. */
export function docHref(version: DocsVersion, slug: string, current: DocsVersion = DEFAULT_DOCS_VERSION): string {
  return `${docsHome(version, current)}/${slug}`
}

/** The version and page a docs URL shows: /docs, /docs/<slug>, /docs/<version> or /docs/<version>/<slug>. */
export function parseDocsPath(pathname: string, current: DocsVersion = DEFAULT_DOCS_VERSION): { version: DocsVersion; slug: string | null } | null {
  const parts = pathname.replace(/\/+$/, "").split("/").filter(Boolean)
  if (parts[0] !== "docs" || parts.length > 3) return null
  if (parts.length === 1) return { version: current, slug: null }
  if (isDocsVersion(parts[1])) return parts.length === 2 ? { version: parts[1], slug: null } : { version: parts[1], slug: parts[2] }
  return parts.length === 2 ? { version: current, slug: parts[1] } : null
}

/**
 * Where a link in docs text goes. `doc:slug#anchor` is a guide in the version being read, `doc@1.0:slug` one in a
 * named version; site paths, in-page anchors and full URLs are kept as they are.
 */
export function resolveDocLink(href: string, version: DocsVersion, current: DocsVersion = DEFAULT_DOCS_VERSION): string {
  const match = href.match(/^doc(?:@([\d.]+))?:([a-z0-9-]+)(#[a-z0-9-]+)?$/)
  if (!match) return href
  const target = match[1] && isDocsVersion(match[1]) ? match[1] : version
  return docHref(target, match[2], current) + (match[3] ?? "")
}
