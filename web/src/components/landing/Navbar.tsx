"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, Menu, Moon, Sun, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { MagneticLink } from "@/components/landing/MagneticLink";
import { siteConfig } from "@/config/site";

const links = [
  { name: "Docs", href: "/docs" },
  { name: "Studio", href: "/playground" },
  { name: "Benchmarks", href: "/benchmarks" },
  { name: "Articles", href: "/articles" },
  { name: "Changelog", href: "/changelog" },
];

function ThemeToggle() {
  return <button type="button" className="theme-toggle" data-theme-toggle aria-label="Switch to light mode" aria-pressed="false" title="Toggle color theme" suppressHydrationWarning>
    <span className="theme-toggle__thumb" aria-hidden="true" />
    <Sun aria-hidden="true" />
    <Moon aria-hidden="true" />
  </button>;
}

export function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  return <header className="site-nav">
    <div className="site-nav__surface">
      <div className="site-nav__inner">
        <Link className="brand" href="/" aria-label="LLMSlim homepage">
          <Image src="/llmslim_logo.png" alt="" width={31} height={31} priority />
          <span>LLMSlim</span><span className="brand__version">v0.3.1</span>
        </Link>
        <nav className="nav-links" aria-label="Main navigation">
          {links.map((link) => <Link key={link.href} href={link.href} data-active={pathname === link.href || pathname.startsWith(`${link.href}/`) || undefined}>{link.name}</Link>)}
        </nav>
        <div className="nav-actions">
          <a className="nav-github" href={siteConfig.github} target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={13} /></a>
          <ThemeToggle />
          <MagneticLink className="button--primary nav-studio-cta" href="/playground">Try Studio</MagneticLink>
          <button type="button" className="icon-button mobile-only" onClick={() => setOpen((value) => !value)} aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="mobile-site-navigation">{open ? <X /> : <Menu />}</button>
        </div>
      </div>
      <nav id="mobile-site-navigation" className="mobile-nav" aria-label="Mobile navigation" hidden={!open}>
        {links.map((link) => <Link key={link.href} href={link.href} data-active={pathname === link.href || pathname.startsWith(`${link.href}/`) || undefined} onClick={() => setOpen(false)}>{link.name}</Link>)}
        <a href={siteConfig.github} target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={14} /></a>
      </nav>
    </div>
  </header>;
}
