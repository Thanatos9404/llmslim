import type { ReactNode } from "react"

/** The page frame for every accounts page: one heading, an optional description, the content. */
export function AuthCard({ title, description, children, wide }: { title: string; description?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <main id="main-content" className="auth-page">
      <section className={`auth-card${wide ? " auth-card-wide" : ""}`} aria-labelledby="auth-title">
        <header className="auth-card-header">
          <h1 id="auth-title" className="auth-title">
            {title}
          </h1>
          {description ? <p className="auth-description">{description}</p> : null}
        </header>
        {children}
      </section>
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
