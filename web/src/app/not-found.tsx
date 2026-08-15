import Link from "next/link";
import { ArrowRight, Compass, FileQuestion } from "lucide-react";
import { Footer } from "@/components/landing/Footer";
import { Navbar } from "@/components/landing/Navbar";

export default function NotFound() {
  return <div className="site-shell"><Navbar /><main id="main-content" className="not-found-page"><div className="not-found-page__code">404</div><span className="eyebrow">Signal not found</span><h1>That context path<br /><span>does not exist.</span></h1><p>The page may have moved, or the URL may be incomplete. Start with the Studio, documentation, or the benchmark report.</p><div><Link href="/" className="button button--primary"><Compass size={16} /> Return home</Link><Link href="/docs" className="button">Browse docs <ArrowRight size={16} /></Link></div><FileQuestion className="not-found-page__mark" size={150} aria-hidden="true" /></main><Footer /></div>;
}
