import Link from "next/link";
import { siteConfig } from "@/config/site";

export function Footer() {
  return <footer className="site-footer"><div className="site-footer__inner">
    <div className="site-footer__identity">
      <span>© {new Date().getFullYear()} LLMSlim · MIT licensed</span>
      <a href="https://www.producthunt.com/products/llmslim/reviews/new?utm_source=badge-product_review&utm_medium=badge&utm_source=badge-llmslim" target="_blank" rel="noreferrer" aria-label="Review LLMSlim on Product Hunt">
        <img src="https://api.producthunt.com/widgets/embed-image/v1/product_review.svg?product_id=1270622&theme=dark" alt="LLMSlim — Semantic prompt compression that never drops instructions | Product Hunt" width="250" height="54" />
      </a>
    </div>
    <nav aria-label="Footer"><Link href="/docs">Docs</Link><Link href="/benchmarks">Benchmarks</Link><Link href="/changelog">Changelog</Link><a href={siteConfig.pypi} target="_blank" rel="noreferrer">PyPI</a><a href={siteConfig.productHunt} target="_blank" rel="noreferrer">Product Hunt</a><a href={siteConfig.linkedin} target="_blank" rel="noreferrer">LinkedIn</a><a href={siteConfig.github} target="_blank" rel="noreferrer">GitHub</a></nav>
  </div></footer>;
}
