"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { ArrowRight, Menu, Moon, Sun, X } from "lucide-react"
import { siteConfig } from "@/config/site"
import { TrackedLink } from "./TrackedLink"

const links = [["Docs", "/docs"], ["Platform", "/platform"], ["Benchmarks", "/benchmarks"], ["Integrations", "/integrations"], ["Changelog", "/changelog"]] as const

export function Brand() {
  return <span className="brand"><span className="brand-symbol" aria-hidden="true" /><span>LLM<span className="brand-slim">Slim</span></span></span>
}

function GitHubMark() {
  return <svg viewBox="0 0 16 16" width="17" height="17" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" /></svg>
}

/** A floating glass bar: transparent over the hero, firmer once the page scrolls. */
export function SiteHeader() {
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const pathname = usePathname()
  const menuButton = useRef<HTMLButtonElement>(null)
  const bar = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); menuButton.current?.focus() } }
    const outside = (event: PointerEvent) => { if (bar.current && !bar.current.contains(event.target as Node)) setOpen(false) }
    let frame = 0
    const scroll = () => { if (!frame) frame = requestAnimationFrame(() => { frame = 0; setScrolled(window.scrollY > 16) }) }
    scroll()
    document.addEventListener("keydown", close)
    document.addEventListener("pointerdown", outside)
    window.addEventListener("scroll", scroll, { passive: true })
    return () => { cancelAnimationFrame(frame); document.removeEventListener("keydown", close); document.removeEventListener("pointerdown", outside); window.removeEventListener("scroll", scroll) }
  }, [])
  return <header className="site-header" data-scrolled={scrolled || open ? "" : undefined}>
    <div ref={bar} className="site-header-bar">
      <Link className="site-header-brand" href="/" aria-label="LLMSlim home" onClick={() => setOpen(false)}><Brand /></Link>
      <nav className="desktop-nav" aria-label="Primary navigation">{links.map(([label, href]) => <Link prefetch={false} key={href} href={href} aria-current={pathname.startsWith(href) ? "page" : undefined}>{label}</Link>)}</nav>
      <div className="header-actions">
        <a className="header-icon" href={siteConfig.github} target="_blank" rel="noreferrer" aria-label="LLMSlim on GitHub" title="GitHub"><GitHubMark /></a>
        <button className="header-icon theme-toggle" data-theme-toggle aria-label="Switch color theme" title="Switch color theme"><Sun className="theme-sun" size={16} /><Moon className="theme-moon" size={16} /></button>
        <TrackedLink prefetch={false} className="button button-small" href="/playground" event="studio_clicked" properties={{ location: "header" }}>Try Studio <ArrowRight size={14} /></TrackedLink>
        <button ref={menuButton} className="header-icon mobile-menu-button" aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>{open ? <X size={18} /> : <Menu size={18} />}</button>
      </div>
      <nav id="mobile-nav" className="mobile-nav" aria-label="Mobile navigation" hidden={!open}>{[...links, ["Engineering notes", "/articles"]].map(([label, href]) => <Link prefetch={false} key={href} href={href} onClick={() => setOpen(false)}>{label}<ArrowRight size={15} /></Link>)}</nav>
    </div>
  </header>
}
