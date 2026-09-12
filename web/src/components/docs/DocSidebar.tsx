"use client"
import { useMemo, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Search } from "lucide-react"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs"

export function DocSidebar({ className }: { className?: string }) {
  const pathname = usePathname(); const [query, setQuery] = useState(""); const currentSlug = pathname?.split("/").pop() || "getting-started"
  const docs = useMemo(() => Object.values(DOCS_REGISTRY).filter((doc) => `${doc.title} ${doc.description} ${doc.searchIntent}`.toLowerCase().includes(query.toLowerCase().trim())), [query])
  return <aside aria-label="Documentation navigation" className={className}><div className="relative mb-3"><Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search docs" className="pl-8" /></div><ScrollArea className="h-[calc(100vh-10rem)] pr-3"><Accordion defaultValue={Array.from(DOC_CATEGORIES)} multiple>{DOC_CATEGORIES.map((category) => { const items = docs.filter((doc) => doc.category === category); return items.length ? <AccordionItem key={category} value={category}><AccordionTrigger>{category}</AccordionTrigger><AccordionContent className="grid gap-1">{items.map((item) => <Link key={item.slug} href={`/docs/${item.slug}`} className={`rounded-md px-2 py-1.5 text-sm ${currentSlug === item.slug ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"}`}>{item.title}</Link>)}</AccordionContent></AccordionItem> : null })}</Accordion></ScrollArea></aside>
}
