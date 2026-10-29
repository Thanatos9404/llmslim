"use client"

import Link from "next/link"
import { useEffect, useState, type FormEvent } from "react"
import { NewPasswordField, SecretField } from "@/components/auth/PasswordField"
import { FormStatus, OfflineNotice, SubmitButton, type Status } from "@/components/auth/primitives"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import { describeError, OFFLINE_ERROR } from "@/lib/auth/messages"
import { validatePassword } from "@/lib/auth/validation"

export function ResetPasswordForm({ token }: { token: string }) {
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [errors, setErrors] = useState<{ password?: string | null; confirm?: string | null }>({})
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    // Keep the single-use token out of the address bar and history.
    window.history.replaceState(null, "", "/reset-password")
  }, [])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldErrors = { password: validatePassword(password), confirm: confirm === password ? null : "The passwords do not match." }
    setErrors(fieldErrors)
    if (fieldErrors.password || fieldErrors.confirm) return
    if (!navigator.onLine) return setStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(true)
    setStatus(null)
    const { error } = await authClient.resetPassword({ newPassword: password, token })
    setPending(false)
    if (error) {
      if (error.code === "PASSWORD_COMPROMISED" || error.code === "PASSWORD_TOO_SHORT" || error.code === "PASSWORD_TOO_LONG") {
        setErrors({ password: describeError(error) })
        return setStatus({ kind: "error", text: "Choose a different password." })
      }
      return setStatus({ kind: "error", text: describeError(error, takeRetryAfter()), action: error.code === "INVALID_TOKEN" ? <Link href="/forgot-password" className="auth-link">Request a new link</Link> : undefined })
    }
    setDone(true)
    setStatus({ kind: "success", text: "Your password has been changed and you have been signed out everywhere else." })
  }

  return (
    <div className="auth-stack">
      <OfflineNotice />
      <FormStatus status={status} id="reset-status" />
      {done ? (
        <Link href="/sign-in?reset=1" className="auth-button auth-button-primary" data-testid="reset-sign-in">
          Sign in
        </Link>
      ) : (
        <form className="auth-form" onSubmit={onSubmit} noValidate aria-describedby="reset-status">
          <NewPasswordField label="New password" value={password} onChange={setPassword} error={errors.password} />
          <SecretField label="Confirm new password" name="confirm-password" autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} error={errors.confirm} required maxLength={128} />
          <SubmitButton pending={pending} pendingText="Saving…">
            Change password
          </SubmitButton>
        </form>
      )}
    </div>
  )
}
