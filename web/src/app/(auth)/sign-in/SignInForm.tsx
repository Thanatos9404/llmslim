"use client"

import Link from "next/link"
import { useCallback, useState, type FormEvent } from "react"
import { Divider, Field, FormStatus, OfflineNotice, SubmitButton, type Status } from "@/components/auth/primitives"
import { SocialButtons } from "@/components/auth/SocialButtons"
import { usePasskeySignIn } from "@/components/auth/usePasskeySignIn"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import type { PublicAuthFeatures } from "@/lib/auth/config"
import { describeError, OFFLINE_ERROR } from "@/lib/auth/messages"
import { validateEmail } from "@/lib/auth/validation"

export function SignInForm({ features, next, initialStatus }: { features: PublicAuthFeatures; next: string; initialStatus: Status }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [errors, setErrors] = useState<{ email?: string | null; password?: string | null }>({})
  const [status, setStatus] = useState<Status>(initialStatus)
  const [pending, setPending] = useState(false)

  const finish = useCallback(() => {
    setStatus({ kind: "success", text: "Signed in. Redirecting…" })
    // A full navigation, so every server component sees the new session cookie.
    window.location.assign(next)
  }, [next])

  const passkey = usePasskeySignIn({ enabled: features.passkey, onSuccess: finish, onStatus: setStatus })

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldErrors = { email: validateEmail(email), password: password ? null : "Enter your password." }
    setErrors(fieldErrors)
    if (fieldErrors.email || fieldErrors.password) return
    if (!navigator.onLine) return setStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(true)
    setStatus(null)
    const { error } = await authClient.signIn.email({ email: email.trim(), password, rememberMe: true })
    if (!error) return finish()
    setPending(false)
    setStatus({ kind: "error", text: describeError(error, takeRetryAfter()) })
  }

  const busy = pending || passkey.pending

  return (
    <div className="auth-stack">
      <OfflineNotice />
      <FormStatus status={status} id="sign-in-status" />
      <SocialButtons google={features.google} github={features.github} callbackURL={next} errorCallbackURL="/sign-in" onStatus={setStatus} disabled={busy} />
      {features.passkey ? (
        <button type="button" className="auth-button auth-button-passkey" onClick={passkey.signIn} disabled={busy} aria-busy={passkey.pending || undefined} data-testid="passkey-sign-in">
          {passkey.pending ? <span className="auth-spinner" aria-hidden="true" /> : null}
          Sign in with a passkey
        </button>
      ) : null}
      {features.google || features.github || features.passkey ? <Divider>or use your email</Divider> : null}
      <form className="auth-form" onSubmit={onSubmit} noValidate aria-describedby="sign-in-status">
        <Field
          label="Email"
          name="email"
          type="email"
          inputMode="email"
          autoComplete="username webauthn"
          autoCapitalize="none"
          spellCheck={false}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={errors.email}
          required
          maxLength={254}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={errors.password}
          required
          maxLength={128}
        />
        <p className="auth-row-end">
          <Link href="/forgot-password" className="auth-link">
            Forgot password?
          </Link>
        </p>
        <SubmitButton pending={pending} pendingText="Signing in…" disabled={passkey.pending}>
          Sign in
        </SubmitButton>
      </form>
      <p className="auth-footnote">
        New to LLMSlim?{" "}
        <Link href={next === "/account" ? "/sign-up" : `/sign-up?next=${encodeURIComponent(next)}`} className="auth-link">
          Create an account
        </Link>
      </p>
    </div>
  )
}
