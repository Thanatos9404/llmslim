"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { DEFAULT_DOCS_VERSION, DOCS_VERSIONS, docHref, docsHome, parseDocsPath, versionStatus, type DocsVersion } from "@/data/docs-versions"

/**
 * Two links, one per version. Each keeps you on the same guide when the other version has it, and goes to that
 * version's docs home when it doesn't. Plain links, so it works before scripts load and for crawlers.
 */
export function DocsVersionSwitch({ slugs, className }: { slugs: Record<DocsVersion, string[]>; className?: string }) {
  const here = parseDocsPath(usePathname() ?? "/docs") ?? { version: DEFAULT_DOCS_VERSION, slug: null }
  return <nav className={`docs-version-switch${className ? ` ${className}` : ""}`} aria-label="Documentation version">
    <span className="docs-version-switch-label" aria-hidden="true">Version</span>
    <span className="docs-version-switch-options">
      {DOCS_VERSIONS.map(({ id }) => {
        const href = here.slug && slugs[id].includes(here.slug) ? docHref(id, here.slug) : docsHome(id)
        const status = versionStatus(id)
        const on = id === here.version
        return <Link key={id} href={href} className="docs-version-option" aria-current={on ? "true" : undefined}
          aria-label={`Docs for ${id}${status === "preview" ? " (preview, not on PyPI yet)" : status === "current" ? " (what pip installs)" : ""}`}>
          {id}{status === "preview" && <span className="docs-version-tag">preview</span>}
        </Link>
      })}
    </span>
  </nav>
}

/** Below 960px the sidebar is hidden: this bar keeps the version switch and a way back to the version's guides. */
export function DocsMobileBar({ slugs }: { slugs: Record<DocsVersion, string[]> }) {
  const here = parseDocsPath(usePathname() ?? "/docs") ?? { version: DEFAULT_DOCS_VERSION, slug: null }
  return <div className="docs-mobilebar">
    <DocsVersionSwitch slugs={slugs} />
    {here.slug && <Link href={docsHome(here.version)} className="docs-mobilebar-home">All guides</Link>}
  </div>
}
