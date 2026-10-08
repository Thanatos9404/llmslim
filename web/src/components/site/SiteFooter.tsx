import Link from "next/link"
import { ArrowUpRight } from "lucide-react"
import { siteConfig } from "@/config/site"
import { Brand } from "./SiteHeader"

export function SiteFooter() {
  return <footer className="site-footer"><div className="site-width footer-top"><div><Link href="/" aria-label="LLMSlim home"><Brand /></Link><p>The context layer for production AI agents.<br />Open-source core. Private platform.</p><span className="eyebrow">BUILT IN INDIA.</span></div><nav aria-label="Footer navigation"><span className="eyebrow">BUILD</span><Link href="/docs">Documentation</Link><Link href="/playground" prefetch={false}>Compression Studio</Link><Link href="/integrations">Integrations</Link><Link href="/benchmarks">Benchmarks</Link><Link href="/platform">Platform beta</Link></nav><nav aria-label="Project links"><span className="eyebrow">EXPLORE</span><Link href="/articles">Engineering notes</Link><Link href="/changelog">Changelog</Link><a href={siteConfig.github} target="_blank" rel="noreferrer">GitHub <ArrowUpRight size={14} /></a><a href={siteConfig.pypi} target="_blank" rel="noreferrer">PyPI <ArrowUpRight size={14} /></a></nav></div><div className="site-width footer-bottom"><span>© {new Date().getFullYear()} LLMSlim</span><a href="https://snyk.io/" target="_blank" rel="noreferrer">Open-source security tools by Snyk <ArrowUpRight size={13} /></a><Link href="/privacy">Privacy</Link><a href={siteConfig.license} target="_blank" rel="noreferrer">Core: MIT License <ArrowUpRight size={13} /></a></div></footer>
}
