"use client"
import { useMemo, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { m, useReducedMotion } from "framer-motion"
import { Search } from "lucide-react"
import { DocsVersionSwitch } from "@/components/docs/DocsVersionSwitch"
import { DEFAULT_DOCS_VERSION, docHref, docsHome, parseDocsPath, type DocsVersion } from "@/data/docs-versions"

/** One guide as the server lists it; `filter` is the lowercase text the filter box matches, `badge` a short marker. */
export interface DocNavItem { slug: string; title: string; filter: string; badge?: "New" | "Experimental" }
/** One category of guides as the server lists them. */
export interface DocNavGroup { category: string; items: DocNavItem[] }

/** Grouped guides of the version being read, with the version switch and a filter. The highlight slides to the current page. */
export function DocSidebar({ className, nav }: { className?: string; nav: Record<DocsVersion, DocNavGroup[]> }) {
  const pathname = usePathname() ?? "/docs"
  const here = parseDocsPath(pathname) ?? { version: DEFAULT_DOCS_VERSION, slug: null }
  const [query, setQuery] = useState("")
  const reduced = useReducedMotion()
  const groups = nav[here.version]
  const slugs = useMemo(() => Object.fromEntries(Object.entries(nav).map(([version, list]) => [version, list.flatMap((group) => group.items.map((item) => item.slug))])) as Record<DocsVersion, string[]>, [nav])
  const shown = useMemo(() => {
    const needle = query.toLowerCase().trim()
    return groups.map((group) => ({ ...group, items: group.items.filter((item) => item.filter.includes(needle)) }))
  }, [groups, query])
  return <aside aria-label="Documentation navigation" className={className}>
    <DocsVersionSwitch slugs={slugs} />
    <label className="docs-search">
      <Search size={14} aria-hidden="true" />
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter guides" aria-label="Filter guides" />
    </label>
    <nav className="docs-nav" aria-label={`Guides for ${here.version}`}>
      <Link href={docsHome(here.version)} className="docs-nav-home" aria-current={here.slug === null ? "page" : undefined}>Overview</Link>
      {shown.map(({ category, items }) => {
        return items.length ? <div key={category} className="docs-nav-group">
          <p className="docs-nav-label">{category}</p>
          <ul>{items.map((item) => <li key={item.slug}>
            <Link href={docHref(here.version, item.slug)} aria-current={here.slug === item.slug ? "page" : undefined}>
              {here.slug === item.slug && <m.span layoutId="docs-nav-on" className="docs-nav-on" transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} />}
              <span>{item.title}</span>
              {item.badge && <span className={`docs-nav-badge is-${item.badge.toLowerCase()}`}>{item.badge}</span>}
            </Link>
          </li>)}</ul>
        </div> : null
      })}
      {shown.every((group) => group.items.length === 0) && <p className="docs-nav-empty">No guide matches “{query}”.</p>}
    </nav>
  </aside>
}
