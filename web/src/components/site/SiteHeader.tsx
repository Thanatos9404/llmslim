"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { AnimatePresence, m, useMotionValueEvent, useReducedMotion, useScroll } from "framer-motion"
import { ArrowRight, ArrowUpRight, Moon, Sun } from "lucide-react"
import { siteConfig } from "@/config/site"
import { LogoMark } from "@/components/brand/LogoMark"
import { TrackedLink } from "./TrackedLink"

const links = [["Docs", "/docs"], ["Vault", "/vault"], ["Pricing", "/pricing"], ["Results", "/results"], ["Integrations", "/integrations"], ["Changelog", "/changelog"]] as const
const menu = [
  ["Docs", "/docs", "Install, compress, integrate"],
  ["Vault", "/vault", "Self-hosted, in your own cloud"],
  ["Pricing", "/pricing", "Plans for LLMSlim 1.0"],
  ["Results", "/results", "Every benchmark, measured"],
  ["Integrations", "/integrations", "Frameworks and providers"],
  ["Studio", "/playground", "Try it in the browser"],
  ["Changelog", "/changelog", "What shipped, and when"],
  ["About", "/about", "Who builds LLMSlim"],
] as const
const SPRING = { type: "spring", stiffness: 420, damping: 36, mass: 0.8 } as const

/** The mark: five strands of context converging into three, in the brand gradient. */
export function Mark({ size = 22 }: { size?: number }) {
  return <LogoMark size={size} className="mark" />
}

export function Brand() {
  return <span className="brand"><Mark size={24} /><span className="brand-word">LLM<span className="brand-slim">Slim</span></span></span>
}

export function GitHubMark() {
  return <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" /></svg>
}

function isActive(pathname: string, href: string) {
  if (href === "/results") return pathname.startsWith("/results") || pathname.startsWith("/benchmarks")
  return pathname.startsWith(href)
}

/** A floating island. Full at the top of the page; folds into a small capsule while you read down, and opens
 *  again when you scroll up or reach for it. The menu grows out of the capsule. */
export function SiteHeader() {
  const [open, setOpen] = useState(false)
  const [folded, setFolded] = useState(false)
  const [reaching, setReaching] = useState(false)
  const [hover, setHover] = useState<string | null>(null)
  const pathname = usePathname()
  const reduced = useReducedMotion()
  const header = useRef<HTMLElement>(null)
  const menuButton = useRef<HTMLButtonElement>(null)
  const { scrollY } = useScroll()
  useMotionValueEvent(scrollY, "change", (y) => {
    const previous = scrollY.getPrevious() ?? 0
    if (y < 120) setFolded(false)
    else if (Math.abs(y - previous) > 6) setFolded(y > previous)
  })
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if (event.key === "Escape" && open) { setOpen(false); menuButton.current?.focus() } }
    const away = (event: PointerEvent) => { if (open && header.current && !header.current.contains(event.target as Node)) setOpen(false) }
    document.addEventListener("keydown", key)
    document.addEventListener("pointerdown", away)
    return () => { document.removeEventListener("keydown", key); document.removeEventListener("pointerdown", away) }
  }, [open])

  const compact = folded && !reaching && !open
  const current = links.find(([, href]) => isActive(pathname, href))?.[0]
  const spring = reduced ? { duration: 0 } : SPRING
  const fade = reduced ? { duration: 0 } : { duration: 0.22 }

  return <header ref={header} className="site-header" data-compact={compact ? "" : undefined} data-where={current ? "" : undefined} data-open={open ? "" : undefined}
    onPointerEnter={(event) => { if (event.pointerType === "mouse") setReaching(true) }} onPointerLeave={() => setReaching(false)}
    onFocus={() => setReaching(true)} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setReaching(false) }}>
    <m.div className="island" layout transition={spring} style={{ borderRadius: 16 }}>
      <m.div layout="position" transition={spring}>
        <Link className="island-brand" href="/" aria-label="LLMSlim home" onClick={() => setOpen(false)}><Brand /></Link>
      </m.div>

      <AnimatePresence initial={false} mode="popLayout">
        {compact ? current && <m.span key="where" className="island-where" layout="position" initial={{ opacity: 0, filter: "blur(4px)" }} animate={{ opacity: 1, filter: "blur(0px)" }} exit={{ opacity: 0, filter: "blur(4px)" }} transition={fade}>
          {current}
        </m.span> : <m.nav key="links" className="island-links" aria-label="Primary navigation" onMouseLeave={() => setHover(null)}
          initial={{ opacity: 0, filter: "blur(6px)" }} animate={{ opacity: 1, filter: "blur(0px)" }} exit={{ opacity: 0, filter: "blur(6px)" }} transition={fade}>
          {links.map(([label, href]) => {
            const active = isActive(pathname, href)
            return <Link prefetch={false} key={href} href={href} aria-current={active ? "page" : undefined} onMouseEnter={() => setHover(href)} onFocus={() => setHover(href)} onBlur={() => setHover(null)}>
              {hover === href && <m.span layoutId="island-hover" className="island-hover" transition={spring} />}
              {active && <span className="island-active" aria-hidden="true" />}
              <span className="island-label">{label}</span>
            </Link>
          })}
        </m.nav>}
      </AnimatePresence>

      <m.div className="island-actions" layout="position" transition={spring}>
        {!compact && <a className="island-icon island-github" href={siteConfig.github} target="_blank" rel="noreferrer" aria-label="LLMSlim on GitHub" title="GitHub"><GitHubMark /></a>}
        <button className="island-icon" data-theme-toggle aria-label="Switch color theme" title="Switch color theme"><Sun className="theme-sun" size={15} /><Moon className="theme-moon" size={15} /></button>
        <button ref={menuButton} className="island-menu" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="site-menu" onClick={() => setOpen(!open)}>
          <span className="island-menu-lines" aria-hidden="true"><i /><i /></span>
        </button>
        <TrackedLink prefetch={false} className="island-cta" href="/playground" event="studio_clicked" properties={{ location: "header" }} aria-label="Try Studio"><span>Try Studio</span><ArrowRight size={14} /></TrackedLink>
      </m.div>
    </m.div>

    <AnimatePresence>{open && <m.div id="site-menu" className="island-panel" role="dialog" aria-label="Site menu"
      initial={reduced ? { opacity: 0 } : { opacity: 0, y: -10, scale: 0.97, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
      exit={reduced ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.98, filter: "blur(4px)" }} transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 460, damping: 34 }}>
      <ul className="island-grid">{menu.map(([label, href, note], index) => <m.li key={href} initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reduced ? 0 : 0.04 + index * 0.03, duration: 0.3 }}>
        <Link prefetch={false} href={href} onClick={() => setOpen(false)} aria-current={isActive(pathname, href) ? "page" : undefined}>
          <span className="island-grid-label">{label}<ArrowRight size={13} /></span><span className="island-grid-note">{note}</span>
        </Link>
      </m.li>)}</ul>
      <div className="island-panel-foot">
        <a href={siteConfig.github} target="_blank" rel="noreferrer"><GitHubMark /> GitHub <ArrowUpRight size={13} /></a>
        <a href={siteConfig.pypi} target="_blank" rel="noreferrer">PyPI <ArrowUpRight size={13} /></a>
        <Link prefetch={false} href="/articles" onClick={() => setOpen(false)}>Engineering notes <ArrowUpRight size={13} /></Link>
      </div>
    </m.div>}</AnimatePresence>
  </header>
}
