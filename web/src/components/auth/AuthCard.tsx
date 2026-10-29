import type { ReactNode } from "react"
import { MarkImage } from "@/components/landing/home/MarkImage"

/**
 * The page frame for every accounts page: the home page's sky (navy night or pale day), one glass card with the
 * heading, and on wide screens an optional quiet product moment beside it. `wide` (the account page) drops the outer
 * glass so its sections can be glass panels of their own.
 */
export function AuthCard({ title, description, children, wide, aside }: { title: string; description?: ReactNode; children: ReactNode; wide?: boolean; aside?: ReactNode }) {
  return (
    <main id="main-content" className={`auth-page${aside ? " has-aside" : ""}${wide ? " is-wide" : ""}`}>
      <div className="auth-sky" aria-hidden="true">
        <div className="lp-aurora" />
        <div className="lp-stars" />
        <div className="lp-horizon" />
      </div>
      <div className="auth-frame">
        <section className={`auth-card${wide ? " auth-card-wide" : " lp-glass"}`} aria-labelledby="auth-title">
          <header className="auth-card-header">
            {wide ? null : <MarkImage size={20} className="auth-card-mark" />}
            <h1 id="auth-title" className="auth-title">
              {title}
            </h1>
            {description ? <p className="auth-description">{description}</p> : null}
          </header>
          {children}
        </section>
        {aside ? <div className="auth-aside">{aside}</div> : null}
      </div>
    </main>
  )
}

export function UnavailableNotice() {
  return (
    <div className="auth-status auth-status-info" role="status" data-testid="accounts-unavailable">
      <p>Accounts are not available on this deployment yet. Please try again later.</p>
    </div>
  )
}
