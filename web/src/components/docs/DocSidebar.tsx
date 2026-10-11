"use client"
import { useMemo, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion, useReducedMotion } from "framer-motion"
import { Search } from "lucide-react"
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs"

/** Grouped guides with a filter. The highlight slides to the current page. */
export function DocSidebar({ className }: { className?: string }) {
  const pathname = usePathname()
  const [query, setQuery] = useState("")
  const reduced = useReducedMotion()
  const current = pathname?.split("/").pop() || ""
  const docs = useMemo(() => Object.values(DOCS_REGISTRY).filter((doc) => `${doc.title} ${doc.description} ${doc.searchIntent}`.toLowerCase().includes(query.toLowerCase().trim())), [query])
  return <aside aria-label="Documentation navigation" className={className}>
    <label className="docs-search">
      <Search size={14} aria-hidden="true" />
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter guides" aria-label="Filter guides" />
    </label>
    <nav className="docs-nav">
      <Link href="/docs" className="docs-nav-home" aria-current={pathname === "/docs" ? "page" : undefined}>Overview</Link>
      {DOC_CATEGORIES.map((category) => {
        const items = docs.filter((doc) => doc.category === category)
        return items.length ? <div key={category} className="docs-nav-group">
          <p className="docs-nav-label">{category}</p>
          <ul>{items.map((item) => <li key={item.slug}>
            <Link href={`/docs/${item.slug}`} aria-current={current === item.slug ? "page" : undefined}>
              {current === item.slug && <motion.span layoutId="docs-nav-on" className="docs-nav-on" transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }} />}
              <span>{item.title}</span>
            </Link>
          </li>)}</ul>
        </div> : null
      })}
      {docs.length === 0 && <p className="docs-nav-empty">No guide matches “{query}”.</p>}
    </nav>
  </aside>
}
