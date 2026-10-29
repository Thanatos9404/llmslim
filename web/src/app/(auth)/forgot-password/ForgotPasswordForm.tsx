"use client"

import Link from "next/link"
import { useState, type FormEvent } from "react"
import { Envelope } from "@/components/auth/Envelope"
import { Step } from "@/components/auth/motion"
import { Field, FormStatus, OfflineNotice, SubmitButton, type Status } from "@/components/auth/primitives"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import { describeError, OFFLINE_ERROR } from "@/lib/auth/messages"
import { validateEmail } from "@/lib/auth/validation"

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)
  const [sent, setSent] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldError = validateEmail(email)
    setError(fieldError)
    if (fieldError) return
    if (!navigator.onLine) return setStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(true)
    setStatus(null)
    const { error: requestError } = await authClient.requestPasswordReset({ email: email.trim(), redirectTo: "/reset-password" })
    setPending(false)
    if (requestError) return setStatus({ kind: "error", text: describeError(requestError, takeRetryAfter()) })
    // Identical whether or not the address has an account.
    setSent(true)
    setStatus({ kind: "success", text: "If an account uses that email, we have sent a link to reset the password. It works once and expires in 1 hour." })
  }

  return (
    <div className="auth-stack">
      <OfflineNotice />
      {sent ? <Step className="auth-sent"><Envelope id="forgot-envelope" /></Step> : null}
      <FormStatus status={status} id="forgot-status" />
      {sent ? (
        <p className="auth-footnote">
          <Link href="/sign-in" className="auth-link">
            Back to sign in
          </Link>
        </p>
      ) : (
        <form className="auth-form" onSubmit={onSubmit} noValidate aria-describedby="forgot-status">
          <Field label="Email" name="email" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false} value={email} onChange={(event) => { setEmail(event.target.value); if (error) setError(validateEmail(event.target.value)) }} onBlur={() => { if (email) setError(validateEmail(email)) }} error={error} required maxLength={254} />
          <SubmitButton pending={pending} pendingText="Sending…">
            Send reset link
          </SubmitButton>
          <p className="auth-footnote">
            Remembered it?{" "}
            <Link href="/sign-in" className="auth-link">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </div>
  )
}
