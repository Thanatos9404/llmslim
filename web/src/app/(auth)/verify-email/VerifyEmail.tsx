"use client"

import Link from "next/link"
import { useEffect, useRef, useState, type FormEvent } from "react"
import { Field, FormStatus, OfflineNotice, SubmitButton, type Status } from "@/components/auth/primitives"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import { describeError, OFFLINE_ERROR } from "@/lib/auth/messages"
import { validateEmail } from "@/lib/auth/validation"

type Phase = "verifying" | "verified" | "failed" | "idle"

export function VerifyEmail({ token, malformed, canResend }: { token: string | null; malformed: boolean; canResend: boolean }) {
  const [phase, setPhase] = useState<Phase>(token ? "verifying" : malformed ? "failed" : "idle")
  const [result, setResult] = useState<Status>(malformed ? { kind: "error", text: describeError({ code: "INVALID_TOKEN", status: 400 }) } : null)
  const started = useRef(false)

  useEffect(() => {
    if (!token || started.current) return
    started.current = true
    // Keep the token out of the address bar and history once it has been read.
    window.history.replaceState(null, "", "/verify-email")
    const run = async () => {
      if (!navigator.onLine) {
        setPhase("failed")
        return setResult({ kind: "error", text: OFFLINE_ERROR })
      }
      const { error } = await authClient.verifyEmail({ query: { token } })
      if (!error) {
        setPhase("verified")
        return setResult({ kind: "success", text: "Your email is confirmed. You can now sign in." })
      }
      setPhase("failed")
      setResult({ kind: "error", text: describeError(error, takeRetryAfter()) })
    }
    void run()
  }, [token])

  return (
    <div className="auth-stack">
      <OfflineNotice />
      {phase === "verifying" ? (
        <p className="auth-status auth-status-info" role="status" aria-busy="true" data-testid="verifying">
          <span className="auth-spinner" aria-hidden="true" /> Confirming your email…
        </p>
      ) : null}
      <FormStatus status={result} id="verify-status" />
      {phase === "verified" ? (
        <Link href="/sign-in" className="auth-button auth-button-primary" data-testid="verified-sign-in">
          Sign in
        </Link>
      ) : null}
      {phase === "idle" ? <p className="auth-description">Open the link in the email we sent you to confirm your address. Didn&apos;t get it? Request a new one below.</p> : null}
      {(phase === "failed" || phase === "idle") && canResend ? <ResendForm /> : null}
    </div>
  )
}

function ResendForm() {
  const [email, setEmail] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldError = validateEmail(email)
    setError(fieldError)
    if (fieldError) return
    if (!navigator.onLine) return setStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(true)
    setStatus(null)
    const { error: requestError } = await authClient.sendVerificationEmail({ email: email.trim() })
    setPending(false)
    setStatus(requestError ? { kind: "error", text: describeError(requestError, takeRetryAfter()) } : { kind: "success", text: "If that address has an account waiting for confirmation, a new link is on its way. It expires in 1 hour." })
  }

  return (
    <form className="auth-form" onSubmit={onSubmit} noValidate aria-describedby="resend-status">
      <h2 className="auth-subtitle">Send a new link</h2>
      <FormStatus status={status} id="resend-status" />
      <Field label="Email" name="email" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false} value={email} onChange={(event) => setEmail(event.target.value)} error={error} required maxLength={254} />
      <SubmitButton pending={pending} pendingText="Sending…">
        Send link
      </SubmitButton>
    </form>
  )
}
