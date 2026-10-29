import type { Metadata } from "next"
import { SiteFooter } from "@/components/site/SiteFooter"
import { SiteHeader } from "@/components/site/SiteHeader"
import "../lp-base.css"
import "./auth.css"

// Every accounts page is kept out of search results, whatever the page sets.
export const metadata: Metadata = {
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    // `lp` brings the home page's theme tokens and glass (lp-base.css); `premium` floats the header over the sky.
    <div className="premium lp auth-shell flex min-h-screen flex-col">
      <SiteHeader />
      {children}
      <SiteFooter />
    </div>
  )
}
