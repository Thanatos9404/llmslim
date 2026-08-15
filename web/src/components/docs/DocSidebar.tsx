"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search } from "lucide-react";
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs";

export function DocSidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const currentSlug = pathname?.split("/").pop() || "getting-started";
  const docList = useMemo(() => Object.values(DOCS_REGISTRY).filter((doc) => `${doc.title} ${doc.description} ${doc.searchIntent}`.toLowerCase().includes(query.toLowerCase().trim())), [query]);

  return <aside aria-label="Documentation navigation" className={`docs-sidebar ${className || ""}`}>
    <div className="docs-sidebar__head"><span>LLMSlim Docs</span><small>Python API</small></div>
    <label className="docs-sidebar__search"><Search size={14} /><span className="sr-only">Search documentation</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search docs" /></label>
    <div className="docs-sidebar__list">{DOC_CATEGORIES.map((category) => {
      const items = docList.filter((doc) => doc.category === category);
      if (!items.length) return null;
      return <section key={category}><h2>{category}</h2><ul>{items.map((item) => <li key={item.slug}><Link href={`/docs/${item.slug}`} data-active={currentSlug === item.slug || undefined}>{item.title}</Link></li>)}</ul></section>;
    })}{docList.length === 0 && <p className="docs-sidebar__empty">No published guide matches that search.</p>}</div>
  </aside>;
}
