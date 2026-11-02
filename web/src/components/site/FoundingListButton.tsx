"use client"

import { useEffect, useRef, useState, type FormEvent, type MouseEvent, type ReactNode } from "react"
import { track } from "@/lib/analytics"
import { rateLimitMessage } from "@/lib/auth/rate-limits"
import { EMAIL_MAX, validateEmail } from "@/lib/auth/validation"
import type { FoundingListFeatures } from "@/lib/founding-list/features"
import { CONFIRM_LINK_DAYS, USE_CASE_MAX, validateUseCase, type Choice } from "@/lib/founding-list/validation"

type Props = {
  choice: Choice
  planName: string
  /** The email link the button has always been: what runs before JavaScript loads, and the fallback after. */
  href: string
  className: string
  features: FoundingListFeatures
  children: ReactNode
}

type Phase =
  | { name: "idle"; notice?: string; error?: string }
  | { name: "joining" }
  | { name: "joined"; email: string; leaving?: boolean; error?: string }
  | { name: "form"; sending?: boolean; error?: string }
  | { name: "sent"; email: string }

const GENERIC = "Something went wrong."

/** An error under the button or form. The generic one offers the email link, which always works. */
function Problem({ text, href }: { text: string; href: string }) {
  return <p className="pr-join-error" role="alert">{text}{text === GENERIC && <> Try again, or <a href={href}>email us</a>.</>}</p>
}

async function call(method: "POST" | "DELETE", body?: unknown): Promise<{ status: number; data: Record<string, unknown>; retryAfter: number | null }> {
  const response = await fetch("/api/founding-list", {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  })
  const data = (await response.json().catch(() => ({}))) as Record<string, unknown>
  const retry = Number(response.headers.get("retry-after"))
  return { status: response.status, data, retryAfter: Number.isFinite(retry) && retry > 0 ? retry : null }
}

function failure(result: { status: number; data: Record<string, unknown>; retryAfter: number | null }): string {
  if (result.status === 429) return rateLimitMessage(result.retryAfter)
  if (result.status === 400 && typeof result.data.message === "string") return result.data.message
  return GENERIC
}

/**
 * "Join the founding list" on a plan card. Rendered as the email link it has always been, so it
 * works without JavaScript; once the page is interactive, a click joins in place instead:
 * - signed in: one click joins with the account's verified email, and can be undone;
 * - signed out: a small form (email, and optionally what it is for) that emails a confirmation link.
 * If this deployment has no accounts database, or no email transport for a signed-out visitor, the
 * click stays the email link.
 */
export function FoundingListButton({ choice, planName, href, className, features, children }: Props) {
  const [phase, setPhase] = useState<Phase>({ name: "idle" })
  const [email, setEmail] = useState("")
  const [useCase, setUseCase] = useState("")
  const [fieldErrors, setFieldErrors] = useState<{ email?: string | null; useCase?: string | null }>({})
  const result = useRef<HTMLDivElement>(null)

  // Moves focus to the outcome, since the button that was clicked is gone.
  useEffect(() => {
    if (phase.name === "joined" || phase.name === "sent") result.current?.focus()
  }, [phase.name])

  async function joinWithAccount() {
    setPhase({ name: "joining" })
    try {
      const response = await call("POST", { ...choice, source: "pricing" })
      if (response.status === 200 && typeof response.data.email === "string") return setPhase({ name: "joined", email: response.data.email })
      if (response.status === 401 && features.canEmail) return setPhase({ name: "form" })
      if (response.status === 401 || response.status === 503) {
        window.location.href = href
        return setPhase({ name: "idle" })
      }
      setPhase({ name: "idle", error: failure(response) })
    } catch {
      setPhase({ name: "idle", error: GENERIC })
    }
  }

  function onClick(event: MouseEvent<HTMLAnchorElement>) {
    track("pricing_cta_clicked", { plan: choice.plan, currency: choice.currency, billing: choice.billing })
    // Modified clicks (a new window, say) keep the link's own behaviour.
    if (!features.enabled || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return
    if (!features.signedIn && !features.canEmail) return
    event.preventDefault()
    if (features.signedIn) void joinWithAccount()
    else setPhase({ name: "form" })
  }

  async function leave() {
    if (phase.name !== "joined") return
    setPhase({ ...phase, leaving: true, error: undefined })
    try {
      const response = await call("DELETE")
      if (response.status === 200) return setPhase({ name: "idle", notice: "You have left the founding list." })
      setPhase({ ...phase, leaving: false, error: failure(response) })
    } catch {
      setPhase({ ...phase, leaving: false, error: GENERIC })
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const errors = { email: validateEmail(email), useCase: validateUseCase(useCase) }
    setFieldErrors(errors)
    if (errors.email || errors.useCase) return
    setPhase({ name: "form", sending: true })
    try {
      const response = await call("POST", { ...choice, source: "pricing", email: email.trim(), useCase: useCase.trim() || undefined })
      if (response.status === 200) return setPhase({ name: "sent", email: email.trim() })
      if (response.status === 503) {
        window.location.href = href
        return setPhase({ name: "form" })
      }
      if (response.data.code === "INVALID_EMAIL") {
        setFieldErrors({ email: String(response.data.message ?? "Enter a valid email address.") })
        return setPhase({ name: "form" })
      }
      if (response.data.code === "INVALID_USE_CASE") {
        setFieldErrors({ useCase: String(response.data.message ?? `Use ${USE_CASE_MAX} characters or fewer.`) })
        return setPhase({ name: "form" })
      }
      setPhase({ name: "form", error: failure(response) })
    } catch {
      setPhase({ name: "form", error: GENERIC })
    }
  }

  if (phase.name === "joining") {
    return <button type="button" className={className} disabled aria-busy="true">Joining…</button>
  }

  if (phase.name === "joined") {
    return <div ref={result} className="pr-join-done" role="status" tabIndex={-1} data-testid="founding-joined">
      <p>You’re on the founding list for {planName}. We’ll email {phase.email} when Orbit opens.</p>
      <button type="button" className="pr-join-link" onClick={leave} disabled={phase.leaving}>{phase.leaving ? "Leaving…" : "Leave the list"}</button>
      {phase.error && <Problem text={phase.error} href={href} />}
    </div>
  }

  if (phase.name === "sent") {
    return <div ref={result} className="pr-join-done" role="status" tabIndex={-1} data-testid="founding-sent">
      <p>Check {phase.email} for a link to confirm your place. It works for {CONFIRM_LINK_DAYS} days.</p>
      <p className="pr-join-note">Nothing there? Check your spam folder, or <a href={href}>email us</a>.</p>
    </div>
  }

  if (phase.name === "form") {
    const id = `founding-${choice.plan}`
    return <form className="pr-join" onSubmit={submit} noValidate aria-label={`Join the founding list for ${planName}`} data-testid="founding-form">
      <label htmlFor={`${id}-email`}>Email</label>
      <input id={`${id}-email`} name="email" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required maxLength={EMAIL_MAX}
        autoFocus value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={fieldErrors.email ? true : undefined} aria-describedby={fieldErrors.email ? `${id}-email-error` : undefined} />
      {fieldErrors.email && <p id={`${id}-email-error`} className="pr-join-error">{fieldErrors.email}</p>}
      <label htmlFor={`${id}-use`}>What will you use it for? <span>(optional)</span></label>
      <input id={`${id}-use`} name="useCase" maxLength={USE_CASE_MAX} value={useCase} onChange={(event) => setUseCase(event.target.value)}
        aria-invalid={fieldErrors.useCase ? true : undefined} aria-describedby={fieldErrors.useCase ? `${id}-use-error` : undefined} />
      {fieldErrors.useCase && <p id={`${id}-use-error`} className="pr-join-error">{fieldErrors.useCase}</p>}
      <button type="submit" className={className} disabled={phase.sending} aria-busy={phase.sending || undefined}>{phase.sending ? "Sending…" : children}</button>
      {phase.error && <Problem text={phase.error} href={href} />}
      <p className="pr-join-note">We’ll email you a link to confirm, and use your address only to write to you about Orbit. <a href="/privacy#founding-list">Privacy</a></p>
    </form>
  }

  return <>
    <a href={href} className={className} onClick={onClick}>{children}</a>
    {phase.notice && <p className="pr-join-note" role="status">{phase.notice}</p>}
    {phase.error && <Problem text={phase.error} href={href} />}
  </>
}
