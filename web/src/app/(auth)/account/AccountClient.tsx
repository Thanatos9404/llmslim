"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { DeviceIcon, KeyIcon, MailIcon } from "@/components/auth/icons"
import { NewPasswordField, SecretField } from "@/components/auth/PasswordField"
import { ProviderMark } from "@/components/auth/SocialButtons"
import { Field, FormStatus, OfflineNotice, SubmitButton, type Status } from "@/components/auth/primitives"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import { describeDevice } from "@/lib/auth/device"
import { describeError, OFFLINE_ERROR, REAUTH_MESSAGE, type ErrorLike } from "@/lib/auth/messages"
import { PASSKEY_NAME_MAX, validateName, validatePasskeyName, validatePassword } from "@/lib/auth/validation"
import { revokeSessionAction, setPasswordAction } from "./actions"
import type { AccountView } from "./data"

const REAUTH_HREF = "/sign-in?reauth=1&next=%2Faccount"
const REAUTH_CODES = new Set(["SESSION_NOT_FRESH", "SESSION_EXPIRED"])

function reauthLink(): ReactNode {
  return (
    <Link href={REAUTH_HREF} className="auth-link" data-testid="reauth-link">
      Sign in again
    </Link>
  )
}

/** Turns a client error into a status, with a sign-in link when the session is too old. */
function errorStatus(error: ErrorLike): Status {
  if (error?.code && REAUTH_CODES.has(error.code)) return { kind: "error", text: REAUTH_MESSAGE, action: reauthLink() }
  if (error?.status === 401) return { kind: "error", text: "Your session has ended. Sign in again.", action: reauthLink() }
  return { kind: "error", text: describeError(error, takeRetryAfter()) }
}

function offline(): Status | null {
  return typeof navigator !== "undefined" && !navigator.onLine ? { kind: "error", text: OFFLINE_ERROR } : null
}

const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC", timeZoneName: "short" })

function When({ iso }: { iso: string | null }) {
  if (!iso) return <span>unknown</span>
  return (
    <time dateTime={iso} suppressHydrationWarning>
      {dateFormat.format(new Date(iso))}
    </time>
  )
}

function relative(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000)
  if (minutes < 2) return "just now"
  if (minutes < 60) return `${minutes} minutes ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `about ${hours} ${hours === 1 ? "hour" : "hours"} ago`
  const days = Math.round(hours / 24)
  return `${days} ${days === 1 ? "day" : "days"} ago`
}

function Section({ id, title, description, children, danger }: { id: string; title: string; description?: ReactNode; children: ReactNode; danger?: boolean }) {
  return (
    <section className={`auth-section lp-glass${danger ? " is-danger" : ""}`} aria-labelledby={`${id}-title`} id={id} data-testid={`section-${id}`}>
      <h2 id={`${id}-title`} className="auth-subtitle">
        {title}
      </h2>
      {description ? <p className="auth-description">{description}</p> : null}
      {children}
    </section>
  )
}

export function AccountClient({ view, notice }: { view: AccountView; notice: string | null }) {
  return (
    <div className="auth-stack auth-account">
      <OfflineNotice />
      {notice ? (
        <div className="auth-status auth-status-error" role="alert">
          <p>{notice}</p>
        </div>
      ) : null}
      <ProfileSection view={view} />
      <MethodsSection view={view} />
      {view.available.passkey ? <PasskeysSection view={view} /> : null}
      <PasswordSection view={view} />
      <SessionsSection view={view} />
      <SignOutSection />
      <DeleteSection view={view} />
    </div>
  )
}

function ProfileSection({ view }: { view: AccountView }) {
  const router = useRouter()
  const [name, setName] = useState(view.user.name)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldError = validateName(name)
    setError(fieldError)
    if (fieldError) return
    const off = offline()
    if (off) return setStatus(off)
    setPending(true)
    const { error: requestError } = await authClient.updateUser({ name: name.trim() })
    setPending(false)
    if (requestError) return setStatus(errorStatus(requestError))
    setStatus({ kind: "success", text: "Your name has been updated." })
    router.refresh()
  }

  return (
    <Section id="profile" title="Profile">
      <div className="auth-profile">
        {view.user.image ? (
          // eslint-disable-next-line @next/next/no-img-element -- provider avatars, allowed hosts only, no optimisation needed
          <img src={view.user.image} alt="" width={56} height={56} className="auth-avatar" referrerPolicy="no-referrer" />
        ) : (
          <span className="auth-avatar auth-monogram" aria-hidden="true">{Array.from(view.user.name.trim() || view.user.email)[0]?.toUpperCase()}</span>
        )}
        <dl className="auth-facts">
          <dt>Email</dt>
          <dd data-testid="account-email">
            {view.user.email} {view.user.emailVerified ? <span className="auth-badge">Verified</span> : <span className="auth-badge auth-badge-warn">Not verified</span>}
          </dd>
        </dl>
      </div>
      <FormStatus status={status} id="profile-status" />
      <form className="auth-form auth-form-inline" onSubmit={onSubmit} noValidate aria-describedby="profile-status">
        <Field label="Name" name="name" autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} error={error} required maxLength={80} />
        <SubmitButton pending={pending} pendingText="Saving…" className="auth-button-secondary">
          Save name
        </SubmitButton>
      </form>
    </Section>
  )
}

function MethodsSection({ view }: { view: AccountView }) {
  const router = useRouter()
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState<string | null>(null)
  const providers = (["google", "github"] as const).filter((provider) => view.available[provider] || view.linked[provider])
  const methodCount = (view.hasPassword ? 1 : 0) + (view.linked.google ? 1 : 0) + (view.linked.github ? 1 : 0)
  const labels = { google: "Google", github: "GitHub" } as const

  async function link(provider: "google" | "github") {
    const off = offline()
    if (off) return setStatus(off)
    setPending(provider)
    setStatus(null)
    const { data, error } = await authClient.linkSocial({ provider, callbackURL: "/account", errorCallbackURL: "/account", disableRedirect: true })
    if (error || !data?.url) {
      setPending(null)
      return setStatus(errorStatus(error))
    }
    window.location.assign(data.url)
  }

  async function unlink(provider: "google" | "github") {
    const off = offline()
    if (off) return setStatus(off)
    setPending(provider)
    setStatus(null)
    const accountId = view.linked[provider]
    if (!accountId) return setPending(null)
    const { error } = await authClient.unlinkAccount({ accountId })
    setPending(null)
    if (error) return setStatus(errorStatus(error))
    setStatus({ kind: "success", text: `${labels[provider]} has been disconnected.` })
    router.refresh()
  }

  return (
    <Section id="methods" title="Ways to sign in" description="Connect Google or GitHub with the same verified email address as this account.">
      <FormStatus status={status} />
      <ul className="auth-list">
        <li className="auth-list-item">
          <span className="auth-list-icon" aria-hidden="true"><MailIcon /></span>
          <span className="auth-list-main">Email and password</span>
          <span className="auth-list-meta" data-testid="password-state">
            {view.hasPassword ? "Password set" : "No password"}
          </span>
        </li>
        {providers.map((provider) => {
          const linked = Boolean(view.linked[provider])
          const canUnlink = linked && methodCount > 1
          return (
            <li key={provider} className="auth-list-item" data-testid={`provider-${provider}`}>
              <span className="auth-list-icon" aria-hidden="true"><ProviderMark provider={provider} /></span>
              <span className="auth-list-main">{labels[provider]}</span>
              <span className={`auth-list-meta${linked ? " is-on" : ""}`}>{linked ? "Connected" : "Not connected"}</span>
              <span className="auth-list-actions">
                {linked ? (
                  canUnlink ? (
                    <button type="button" className="auth-button auth-button-secondary" onClick={() => unlink(provider)} disabled={pending !== null} aria-busy={pending === provider || undefined}>
                      Disconnect {labels[provider]}
                    </button>
                  ) : (
                    <span className="auth-hint">Add a password or another provider before disconnecting.</span>
                  )
                ) : view.available[provider] ? (
                  <button type="button" className="auth-button auth-button-secondary" onClick={() => link(provider)} disabled={pending !== null} aria-busy={pending === provider || undefined}>
                    Connect {labels[provider]}
                  </button>
                ) : null}
              </span>
            </li>
          )
        })}
      </ul>
    </Section>
  )
}

function PasskeysSection({ view }: { view: AccountView }) {
  const router = useRouter()
  const [status, setStatus] = useState<Status>(null)
  const [name, setName] = useState("")
  const [nameError, setNameError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const label = name.trim() || describeDevice(navigator.userAgent)
    const fieldError = validatePasskeyName(label)
    setNameError(fieldError)
    if (fieldError) return
    const off = offline()
    if (off) return setStatus(off)
    setAdding(true)
    setStatus(null)
    const result = await authClient.passkey.addPasskey({ name: label })
    setAdding(false)
    if (result?.error) return setStatus(errorStatus(result.error))
    setName("")
    setStatus({ kind: "success", text: `Passkey “${label}” added. You can now sign in with it.` })
    router.refresh()
  }

  return (
    <Section id="passkeys" title="Passkeys" description="Sign in with your fingerprint, face or device PIN instead of a password. Passkeys cannot be phished.">
      <FormStatus status={status} />
      {view.passkeys.length > 0 ? (
        <ul className="auth-list" data-testid="passkey-list">
          {view.passkeys.map((item) => (
            <PasskeyRow key={item.id} item={item} onStatus={setStatus} />
          ))}
        </ul>
      ) : (
        <p className="auth-hint" data-testid="no-passkeys">
          No passkeys yet.
        </p>
      )}
      {view.fresh ? (
        <form className="auth-form auth-form-inline" onSubmit={add} noValidate>
          <Field label="Passkey name (optional)" name="passkey-name" autoComplete="off" value={name} onChange={(event) => setName(event.target.value)} error={nameError} maxLength={PASSKEY_NAME_MAX} placeholder="For example: Work laptop" />
          <SubmitButton pending={adding} pendingText="Waiting for your device…" className="auth-button-secondary">
            Add a passkey
          </SubmitButton>
        </form>
      ) : (
        <div className="auth-status auth-status-info" role="status">
          <p>To add a passkey, confirm it is you first.</p>
          <div className="auth-status-action">{reauthLink()}</div>
        </div>
      )}
    </Section>
  )
}

function PasskeyRow({ item, onStatus }: { item: AccountView["passkeys"][number]; onStatus: (status: Status) => void }) {
  const router = useRouter()
  const [mode, setMode] = useState<"view" | "rename" | "delete">("view")
  const [name, setName] = useState(item.name)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldError = validatePasskeyName(name)
    setError(fieldError)
    if (fieldError) return
    const off = offline()
    if (off) return onStatus(off)
    setPending(true)
    const { error: requestError } = await authClient.passkey.updatePasskey({ id: item.id, name: name.trim() })
    setPending(false)
    if (requestError) return onStatus(errorStatus(requestError))
    setMode("view")
    onStatus({ kind: "success", text: "Passkey renamed." })
    router.refresh()
  }

  async function remove() {
    const off = offline()
    if (off) return onStatus(off)
    setPending(true)
    const { error: requestError } = await authClient.passkey.deletePasskey({ id: item.id })
    setPending(false)
    if (requestError) return onStatus(errorStatus(requestError))
    onStatus({ kind: "success", text: `Passkey “${item.name}” deleted.` })
    router.refresh()
  }

  return (
    <li className="auth-list-item" data-testid="passkey-item">
      {mode === "rename" ? (
        <form className="auth-form auth-form-inline" onSubmit={rename} noValidate>
          <Field label={`New name for ${item.name}`} name="passkey-rename" autoComplete="off" value={name} onChange={(event) => setName(event.target.value)} error={error} maxLength={PASSKEY_NAME_MAX} autoFocus />
          <SubmitButton pending={pending} pendingText="Saving…" className="auth-button-secondary">
            Save
          </SubmitButton>
          <button type="button" className="auth-button auth-button-quiet" onClick={() => setMode("view")}>
            Cancel
          </button>
        </form>
      ) : (
        <>
          <span className="auth-list-icon" aria-hidden="true"><KeyIcon /></span>
          <span className="auth-list-main" data-testid="passkey-name">
            {item.name}
          </span>
          <span className="auth-list-meta">
            {item.authenticator ? `${item.authenticator} · ` : ""}
            {item.synced ? "Synced · " : ""}Added <When iso={item.createdAt} />
          </span>
          <span className="auth-list-actions">
            {mode === "delete" ? (
              <>
                <span className="auth-hint">Delete this passkey?</span>
                <button type="button" className="auth-button auth-button-danger" onClick={remove} disabled={pending} aria-busy={pending || undefined}>
                  Confirm delete
                </button>
                <button type="button" className="auth-button auth-button-quiet" onClick={() => setMode("view")}>
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button type="button" className="auth-button auth-button-secondary" onClick={() => setMode("rename")} aria-label={`Rename passkey ${item.name}`}>
                  Rename
                </button>
                <button type="button" className="auth-button auth-button-secondary" onClick={() => setMode("delete")} aria-label={`Delete passkey ${item.name}`}>
                  Delete
                </button>
              </>
            )}
          </span>
        </>
      )}
    </li>
  )
}

function PasswordSection({ view }: { view: AccountView }) {
  const router = useRouter()
  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [errors, setErrors] = useState<{ current?: string | null; password?: string | null; confirm?: string | null }>({})
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldErrors = {
      current: view.hasPassword && !current ? "Enter your current password." : null,
      password: validatePassword(password),
      confirm: confirm === password ? null : "The passwords do not match.",
    }
    setErrors(fieldErrors)
    if (Object.values(fieldErrors).some(Boolean)) return
    const off = offline()
    if (off) return setStatus(off)
    setPending(true)
    setStatus(null)
    if (view.hasPassword) {
      const { error } = await authClient.changePassword({ currentPassword: current, newPassword: password, revokeOtherSessions: true })
      setPending(false)
      if (error) {
        if (error.code === "INVALID_PASSWORD") return setErrors({ current: describeError(error) })
        if (error.code === "PASSWORD_COMPROMISED") return setErrors({ password: describeError(error) })
        return setStatus(errorStatus(error))
      }
      setStatus({ kind: "success", text: "Your password has been changed. Your other sessions have been signed out." })
    } else {
      const result = await setPasswordAction(password)
      setPending(false)
      if (!result.ok) {
        if (result.code === "PASSWORD_COMPROMISED" || result.code === "INVALID_PASSWORD") return setErrors({ password: result.error })
        return setStatus(result.code === "SESSION_NOT_FRESH" ? { kind: "error", text: result.error, action: reauthLink() } : { kind: "error", text: result.error })
      }
      setStatus({ kind: "success", text: "Your password has been set. You can now sign in with your email and password." })
    }
    setCurrent("")
    setPassword("")
    setConfirm("")
    router.refresh()
  }

  return (
    <Section id="password" title={view.hasPassword ? "Change password" : "Set a password"} description={view.hasPassword ? "Changing your password signs you out on every other device." : "Add a password so you can also sign in with your email address."}>
      <FormStatus status={status} id="password-status" />
      <form className="auth-form" onSubmit={onSubmit} noValidate aria-describedby="password-status">
        {/* Lets password managers attach the new password to the right account. */}
        <input type="email" name="username" autoComplete="username" value={view.user.email} readOnly hidden />
        {view.hasPassword ? <SecretField label="Current password" name="current-password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} error={errors.current} required maxLength={128} /> : null}
        <NewPasswordField label="New password" name="new-password" value={password} onChange={setPassword} error={errors.password} context={[view.user.name, view.user.email.split("@")[0] ?? ""]} />
        <SecretField label="Confirm new password" name="confirm-password" autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} error={errors.confirm} required maxLength={128} />
        <SubmitButton pending={pending} pendingText="Saving…" className="auth-button-secondary">
          {view.hasPassword ? "Change password" : "Set password"}
        </SubmitButton>
      </form>
    </Section>
  )
}

function SessionsSection({ view }: { view: AccountView }) {
  const router = useRouter()
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState<string | null>(null)
  const others = view.sessions.filter((item) => !item.current).length

  async function revoke(id: string) {
    const off = offline()
    if (off) return setStatus(off)
    setPending(id)
    const result = await revokeSessionAction(id)
    setPending(null)
    if (!result.ok) return setStatus({ kind: "error", text: result.error })
    setStatus({ kind: "success", text: "That session has been signed out." })
    router.refresh()
  }

  async function revokeOthers() {
    const off = offline()
    if (off) return setStatus(off)
    setPending("others")
    const { error } = await authClient.revokeOtherSessions()
    setPending(null)
    if (error) return setStatus(errorStatus(error))
    setStatus({ kind: "success", text: "All other sessions have been signed out." })
    router.refresh()
  }

  return (
    <Section id="sessions" title="Active sessions" description="Devices signed in to your account. Times are approximate and shown in UTC.">
      <FormStatus status={status} />
      <ul className="auth-list" data-testid="session-list">
        {view.sessions.map((item) => (
          <li key={item.id} className="auth-list-item" data-testid="session-item">
            <span className="auth-list-icon" aria-hidden="true"><DeviceIcon /></span>
            <span className="auth-list-main">
              {item.device}
              {item.current ? <span className="auth-badge">This device</span> : null}
            </span>
            <span className="auth-list-meta">
              Signed in <When iso={item.createdAt} /> · active <span suppressHydrationWarning>{relative(item.lastActiveAt)}</span>
            </span>
            <span className="auth-list-actions">
              {item.current ? null : (
                <button type="button" className="auth-button auth-button-secondary" onClick={() => revoke(item.id)} disabled={pending !== null} aria-busy={pending === item.id || undefined} aria-label={`Sign out ${item.device}`}>
                  Sign out
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {others > 0 ? (
        <button type="button" className="auth-button auth-button-secondary" onClick={revokeOthers} disabled={pending !== null} aria-busy={pending === "others" || undefined}>
          Sign out all other sessions
        </button>
      ) : null}
    </Section>
  )
}

function SignOutSection() {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [status, setStatus] = useState<Status>(null)

  async function signOut() {
    const off = offline()
    if (off) return setStatus(off)
    setPending(true)
    const { error } = await authClient.signOut()
    if (error) {
      setPending(false)
      return setStatus(errorStatus(error))
    }
    router.replace("/sign-in?signedOut=1")
    router.refresh()
  }

  return (
    <Section id="sign-out" title="Sign out" description="Sign out of LLMSlim on this device.">
      <FormStatus status={status} />
      <button type="button" className="auth-button auth-button-secondary" onClick={signOut} disabled={pending} aria-busy={pending || undefined} data-testid="sign-out">
        {pending ? "Signing out…" : "Sign out"}
      </button>
    </Section>
  )
}

function DeleteSection({ view }: { view: AccountView }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState("")
  const [understood, setUnderstood] = useState(false)
  const [errors, setErrors] = useState<{ password?: string | null; understood?: string | null }>({})
  const [status, setStatus] = useState<Status>(null)
  const [pending, setPending] = useState(false)
  const needsReauth = !view.hasPassword && !view.fresh
  const dialog = useRef<HTMLDialogElement>(null)
  const opener = useRef<HTMLButtonElement>(null)

  // The confirmation is a modal dialog: focus moves into it, the page behind is inert, and Escape closes it.
  useEffect(() => {
    const element = dialog.current
    if (open && element && !element.open) element.showModal()
  }, [open])

  function close() {
    if (pending) return
    dialog.current?.close()
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fieldErrors = {
      password: view.hasPassword && !password ? "Enter your password to confirm." : null,
      understood: understood ? null : "Confirm that you understand this cannot be undone.",
    }
    setErrors(fieldErrors)
    if (fieldErrors.password || fieldErrors.understood) return
    const off = offline()
    if (off) return setStatus(off)
    setPending(true)
    setStatus(null)
    const { error } = await authClient.deleteUser(view.hasPassword ? { password } : {})
    if (error) {
      setPending(false)
      if (error.code === "INVALID_PASSWORD") return setErrors({ password: "That password is incorrect." })
      return setStatus(errorStatus(error))
    }
    router.replace("/sign-in?deleted=1")
    router.refresh()
  }

  return (
    <Section id="delete" title="Delete account" description="Permanently delete your account, sign-in methods, passkeys and sessions. This cannot be undone." danger>
      <button ref={opener} type="button" className="auth-button auth-button-danger" onClick={() => setOpen(true)} data-testid="delete-open" aria-haspopup="dialog">
        Delete account…
      </button>
      {open ? (
        <dialog
          ref={dialog}
          className="auth-dialog lp-glass"
          aria-labelledby="delete-dialog-title"
          onClose={() => {
            setOpen(false)
            opener.current?.focus()
          }}
          onCancel={(event) => {
            if (pending) event.preventDefault()
          }}
        >
          <h3 id="delete-dialog-title" className="auth-subtitle">
            Delete your account?
          </h3>
          <p className="auth-description">Your account, sign-in methods, passkeys and sessions are deleted at once. This cannot be undone.</p>
          <FormStatus status={status} id="delete-status" />
          {needsReauth ? (
            <div className="auth-stack">
              <div className="auth-status auth-status-info" role="status">
                <p>To delete your account, confirm it is you first.</p>
                <div className="auth-status-action">{reauthLink()}</div>
              </div>
              <div className="auth-row auth-dialog-actions">
                <button type="button" className="auth-button auth-button-quiet" onClick={close}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <form className="auth-form" onSubmit={onSubmit} noValidate aria-describedby="delete-status">
              <input type="email" name="username" autoComplete="username" value={view.user.email} readOnly hidden />
              {view.hasPassword ? <SecretField label="Password" name="delete-password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} error={errors.password} required maxLength={128} /> : null}
              <div className={`auth-field auth-checkbox${errors.understood ? " auth-field-invalid" : ""}`}>
                <input id="delete-understood" type="checkbox" checked={understood} onChange={(event) => setUnderstood(event.target.checked)} aria-invalid={errors.understood ? true : undefined} aria-describedby={errors.understood ? "delete-understood-error" : undefined} />
                <label htmlFor="delete-understood">I understand that my account will be deleted permanently.</label>
                {errors.understood ? (
                  <p id="delete-understood-error" className="auth-field-error">
                    {errors.understood}
                  </p>
                ) : null}
              </div>
              <div className="auth-row auth-dialog-actions">
                <button type="button" className="auth-button auth-button-quiet" onClick={close} disabled={pending}>
                  Cancel
                </button>
                <SubmitButton pending={pending} pendingText="Deleting…" className="auth-button-danger">
                  Delete my account permanently
                </SubmitButton>
              </div>
            </form>
          )}
        </dialog>
      ) : null}
    </Section>
  )
}
