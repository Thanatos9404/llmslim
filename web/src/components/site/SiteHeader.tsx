"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { ArrowUpRight, Menu, Moon, Sun, X } from "lucide-react"
import { siteConfig } from "@/config/site"

const links = [["Documentation", "/docs"], ["Benchmarks", "/benchmarks"], ["Integrations", "/integrations"], ["Changelog", "/changelog"]] as const

export function Brand() {
  return <span className="brand"><span className="brand-symbol" aria-hidden="true" /><span>LLM<span className="brand-slim">Slim</span><span className="brand-period">.</span></span></span>
}

export function SiteHeader() {
  const [open, setOpen] = useState(false)
  const pathname = usePathname()
  const menuButton = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const close = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); menuButton.current?.focus() } }
    document.addEventListener("keydown", close)
    return () => document.removeEventListener("keydown", close)
  }, [])
  return <header className="site-header"><div className="site-header-inner">
    <Link href="/" aria-label="LLMSlim home" onClick={() => setOpen(false)}><Brand /></Link>
    <nav className="desktop-nav" aria-label="Primary navigation">{links.map(([label, href]) => <Link prefetch={false} key={href} href={href} aria-current={pathname.startsWith(href) ? "page" : undefined}>{label}</Link>)}</nav>
    <div className="header-actions"><button className="theme-toggle" data-theme-toggle aria-label="Switch color theme" title="Switch color theme"><Sun className="theme-sun" size={18} /><Moon className="theme-moon" size={18} /></button><a className="github-link" href={siteConfig.github} target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={15} /></a><Link prefetch={false} className="button button-small" href="/playground">Try Studio <ArrowUpRight size={15} /></Link><button ref={menuButton} className="mobile-menu-button" aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>{open ? <X size={21} /> : <Menu size={21} />}</button></div>
  </div><nav id="mobile-nav" className="mobile-nav" aria-label="Mobile navigation" hidden={!open}>{[...links, ["Engineering notes", "/articles"]].map(([label, href]) => <Link prefetch={false} key={href} href={href} onClick={() => setOpen(false)}>{label}<ArrowUpRight size={16} /></Link>)}</nav></header>
}
