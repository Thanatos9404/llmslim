import Link from "next/link"
import { siteConfig } from "@/config/site"
import { DOCS_BY_VERSION, shipsAs } from "@/data/docs"
import { DEFAULT_DOCS_VERSION, docHref, docsHome, versionStatus, type DocsVersion } from "@/data/docs-versions"

/** The guide that says how to try a preview before it is released. */
const TRY_IT = { slug: "migrate-to-1-0", anchor: "#try-it" }

/** A notice at the top of every page of a preview or older version, so no one mistakes it for what pip installs. */
export function DocsVersionNotice({ version, slug }: { version: DocsVersion; slug?: string | null }) {
  const status = versionStatus(version)
  if (status === "current") return null
  const current = slug && DOCS_BY_VERSION[DEFAULT_DOCS_VERSION][slug] ? docHref(DEFAULT_DOCS_VERSION, slug) : docsHome(DEFAULT_DOCS_VERSION)
  const tryIt = status === "preview" && DOCS_BY_VERSION[version][TRY_IT.slug] ? docHref(version, TRY_IT.slug) + TRY_IT.anchor : null
  return <aside className={`docs-version-notice is-${status}`} aria-label={status === "preview" ? `Upcoming in ${version}` : `Docs for ${version}`}>
    <p className="docs-version-notice-label">{status === "preview" ? <>Upcoming in {version} <span>Preview</span></> : <>Docs for {version}</>}</p>
    {status === "preview"
      ? <p>These pages describe the main branch of LLMSlim Core, which becomes {shipsAs(version)}. <code className="doc-inline-code">pip install llmslim</code> installs {siteConfig.coreVersion} today, which doesn&apos;t have everything described here.</p>
      : <p>The current version is {DEFAULT_DOCS_VERSION}.</p>}
    <p className="docs-version-notice-links">
      {tryIt && <Link href={tryIt}>Try {version} now</Link>}
      <Link href={current}>{status === "preview" ? `Docs for ${DEFAULT_DOCS_VERSION}, what pip installs` : `Docs for ${DEFAULT_DOCS_VERSION}`}</Link>
    </p>
  </aside>
}
