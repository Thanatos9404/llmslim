"use client"
import { useMemo, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { m, useReducedMotion } from "framer-motion"
import { Search } from "lucide-react"

/** One category of guides as the server lists them; `filter` is the lowercase text the filter box matches. */
export interface DocNavGroup { category: string; items: { slug: string; title: string; filter: string }[] }

/** Grouped guides with a filter. The highlight slides to the current page. */
export function DocSidebar({ className, groups }: { className?: string; groups: DocNavGroup[] }) {
  const pathname = usePathname()
  const [query, setQuery] = useState("")
  const reduced = useReducedMotion()
  const current = pathname?.split("/").pop() || ""
  const shown = useMemo(() => {
    const needle = query.toLowerCase().trim()
    return groups.map((group) => ({ ...group, items: group.items.filter((item) => item.filter.includes(needle)) }))
  }, [groups, query])
  return <aside aria-label="Documentation navigation" className={className}>
    <label className="docs-search">
      <Search size={14} aria-hidden="true" />
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter guides" aria-label="Filter guides" />
    </label>
    <nav className="docs-nav">
      <Link href="/docs" className="docs-nav-home" aria-current={pathname === "/docs" ? "page" : undefined}>Overview</Link>
      {shown.map(({ category, items }) => {
        return items.length ? <div key={category} className="docs-nav-group">
          <p className="docs-nav-label">{category}</p>
          <ul>{items.map((item) => <li key={item.slug}>
            <Link href={`/docs/${item.slug}`} aria-current={current === item.slug ? "page" : undefined}>
              {current === item.slug && <m.span layoutId="docs-nav-on" className="docs-nav-on" transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} />}
              <span>{item.title}</span>
            </Link>
          </li>)}</ul>
        </div> : null
      })}
      {shown.every((group) => group.items.length === 0) && <p className="docs-nav-empty">No guide matches “{query}”.</p>}
    </nav>
  </aside>
}
