"use client"

import Link from "next/link"
import { useRef, useState, type FormEvent } from "react"
import { NewPasswordField } from "@/components/auth/PasswordField"
import { Divider, Field, FormStatus, OfflineNotice, SubmitButton, type Status } from "@/components/auth/primitives"
import { SocialButtons } from "@/components/auth/SocialButtons"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import type { PublicAuthFeatures } from "@/lib/auth/config"
import { describeError, OFFLINE_ERROR } from "@/lib/auth/messages"
import { validateEmail, validateName, validatePassword } from "@/lib/auth/validation"

type Errors = { name?: string | null; email?: string | null; password?: string | null; consent?: string | null }

const CONSENT_ERROR = "Agree to the Terms of Service and Privacy Policy to continue."

export function SignUpForm({ features, next }: { features: PublicAuthFeatures; next: string }) {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [consent, setConsent] = useState(false)
  const [errors, setErrors] = useState<Errors>({})
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)
  const [sentTo, setSentTo] = useState<string | null>(null)
  const consentRef = useRef<HTMLInputElement>(null)

  function requireConsent(): boolean {
    if (consent) return true
    setErrors((current) => ({ ...current, consent: CONSENT_ERROR }))
    consentRef.current?.focus()
    return false
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldErrors: Errors = {
      name: validateName(name),
      email: validateEmail(email),
      password: validatePassword(password),
      consent: consent ? null : CONSENT_ERROR,
    }
    setErrors(fieldErrors)
    if (Object.values(fieldErrors).some(Boolean)) return
    if (!navigator.onLine) return setStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(true)
    setStatus(null)
    const { error } = await authClient.signUp.email({ name: name.trim(), email: email.trim(), password })
    setPending(false)
    if (error) {
      // Password problems belong next to the password field.
      if (error.code === "PASSWORD_COMPROMISED" || error.code === "PASSWORD_TOO_SHORT" || error.code === "PASSWORD_TOO_LONG") {
        setErrors((current) => ({ ...current, password: describeError(error) }))
        return setStatus({ kind: "error", text: "Choose a different password." })
      }
      return setStatus({ kind: "error", text: describeError(error, takeRetryAfter()) })
    }
    // The same answer whether or not the address already has an account.
    setSentTo(email.trim())
    setPassword("")
  }

  if (sentTo) return <CheckEmail email={sentTo} />

  return (
    <div className="auth-stack">
      <OfflineNotice />
      <FormStatus status={status} id="sign-up-status" />
      <SocialButtons google={features.google} github={features.github} callbackURL={next} errorCallbackURL="/sign-up" onStatus={setStatus} beforeStart={requireConsent} disabled={pending} />
      {features.emailSignUp ? (
        <>
          {features.google || features.github ? <Divider>or sign up with email</Divider> : null}
          <form className="auth-form" onSubmit={onSubmit} noValidate aria-describedby="sign-up-status">
            <Field label="Name" name="name" type="text" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} error={errors.name} required maxLength={80} />
            <Field label="Email" name="email" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false} value={email} onChange={(event) => setEmail(event.target.value)} error={errors.email} required maxLength={254} />
            <NewPasswordField value={password} onChange={setPassword} error={errors.password} context={[name, email.split("@")[0] ?? ""]} />
            <ConsentField consent={consent} setConsent={setConsent} error={errors.consent} inputRef={consentRef} />
            <SubmitButton pending={pending} pendingText="Creating account…">
              Create account
            </SubmitButton>
          </form>
        </>
      ) : (
        <>
          {features.google || features.github ? <ConsentField consent={consent} setConsent={setConsent} error={errors.consent} inputRef={consentRef} /> : null}
          <div className="auth-status auth-status-info" role="status" data-testid="email-sign-up-disabled">
            <p>{features.google || features.github ? "Signing up with email and password is not available right now. Continue with Google or GitHub instead." : "Signing up is not available right now. Please try again later."}</p>
          </div>
        </>
      )}
      <p className="auth-footnote">
        Already have an account?{" "}
        <Link href={next === "/account" ? "/sign-in" : `/sign-in?next=${encodeURIComponent(next)}`} className="auth-link">
          Sign in
        </Link>
      </p>
    </div>
  )
}

function ConsentField({ consent, setConsent, error, inputRef }: { consent: boolean; setConsent: (value: boolean) => void; error?: string | null; inputRef: React.RefObject<HTMLInputElement | null> }) {
  return (
    <div className={`auth-field auth-checkbox${error ? " auth-field-invalid" : ""}`}>
      <input
        ref={inputRef}
        id="sign-up-consent"
        type="checkbox"
        checked={consent}
        onChange={(event) => setConsent(event.target.checked)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? "sign-up-consent-error" : undefined}
        required
      />
      <label htmlFor="sign-up-consent">
        I agree to the{" "}
        <Link href="/terms" className="auth-link" target="_blank" rel="noopener">
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link href="/privacy" className="auth-link" target="_blank" rel="noopener">
          Privacy Policy
        </Link>
        .
      </label>
      {error ? (
        <p id="sign-up-consent-error" className="auth-field-error" data-testid="field-error">
          {error}
        </p>
      ) : null}
    </div>
  )
}

function CheckEmail({ email }: { email: string }) {
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)

  async function resend() {
    if (!navigator.onLine) return setStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(true)
    const { error } = await authClient.sendVerificationEmail({ email })
    setPending(false)
    setStatus(error ? { kind: "error", text: describeError(error, takeRetryAfter()) } : { kind: "success", text: "If that address needs confirming, a new link is on its way." })
  }

  return (
    <div className="auth-stack" data-testid="check-email">
      <div className="auth-status auth-status-success" role="status">
        <p>
          Check your email. If <strong>{email}</strong> can be used for a new account, we have sent a link to confirm it. The link expires in 1 hour.
        </p>
      </div>
      <FormStatus status={status} />
      <button type="button" className="auth-button auth-button-secondary" onClick={resend} disabled={pending} aria-busy={pending || undefined}>
        {pending ? "Sending…" : "Send the link again"}
      </button>
      <p className="auth-footnote">
        Confirmed already?{" "}
        <Link href="/sign-in" className="auth-link">
          Sign in
        </Link>
      </p>
    </div>
  )
}
