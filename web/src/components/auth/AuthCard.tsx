import type { ReactNode } from "react"
import { PageBackdrop } from "@/components/site/PageBackdrop"
import { BACKDROP_CODE } from "@/components/site/backdrop-code"

/**
 * The page frame for every accounts page, in the site's style: a kicker, a two-tone heading whose
 * `accent` ends it in the serif italic, an optional description, and the content in a panel. The
 * founding-list confirm and unsubscribe pages use it too, with their own kicker.
 */
export function AuthCard({ title, accent, description, children, wide, kicker = "Account" }: { title: string; accent?: string; description?: ReactNode; children: ReactNode; wide?: boolean; kicker?: string }) {
  return (
    <main id="main-content" className="auth-page has-backdrop">
      <PageBackdrop code={BACKDROP_CODE.compress} layout="split" />
      <section className={`auth-card${wide ? " auth-card-wide" : ""}`} aria-labelledby="auth-title">
        <header className="auth-card-header">
          <p className="p-kicker auth-kicker">{kicker}</p>
          <h1 id="auth-title" className="auth-title">
            {title}
            {accent ? <> <span>{accent}</span></> : null}
          </h1>
          {description ? <p className="auth-description">{description}</p> : null}
        </header>
        <div className="auth-panel">{children}</div>
      </section>
    </main>
  )
}

export function UnavailableNotice({ what = "Accounts are" }: { what?: string }) {
  return (
    <div className="auth-status auth-status-info" role="status" data-testid="accounts-unavailable">
      <p>{what} not available on this deployment yet. Please try again later.</p>
    </div>
  )
}
