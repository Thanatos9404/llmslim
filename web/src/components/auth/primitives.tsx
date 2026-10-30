"use client"

/**
 * Small, unstyled-by-default building blocks for the accounts pages. All presentation lives in
 * src/app/(auth)/auth.css under `auth-` class names, so a redesign can restyle without touching
 * behaviour. Every field wires its label, hint and error to the input for screen readers.
 */
import { useEffect, useId, useState, type InputHTMLAttributes, type ReactNode } from "react"

export function useOnline(): boolean {
  const [online, setOnline] = useState(true)
  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    update()
    window.addEventListener("online", update)
    window.addEventListener("offline", update)
    return () => {
      window.removeEventListener("online", update)
      window.removeEventListener("offline", update)
    }
  }, [])
  return online
}

export function OfflineNotice() {
  const online = useOnline()
  if (online) return null
  return (
    <p className="auth-offline" role="status" data-testid="offline-notice">
      You are offline. Forms will work again when your connection returns.
    </p>
  )
}

export type Status = { kind: "error" | "success" | "info"; text: string; action?: ReactNode } | null

/** One live region per form: errors are announced assertively, success politely. */
export function FormStatus({ status, id }: { status: Status; id?: string }) {
  if (!status) return <div id={id} aria-live="polite" className="auth-status-empty" />
  return (
    <div id={id} className={`auth-status auth-status-${status.kind}`} role={status.kind === "error" ? "alert" : "status"} data-testid={`status-${status.kind}`}>
      <p>{status.text}</p>
      {status.action ? <div className="auth-status-action">{status.action}</div> : null}
    </div>
  )
}

type FieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  label: string
  error?: string | null
  hint?: ReactNode
  /** Rendered after the input, inside the field (for example a strength meter). */
  after?: ReactNode
  /** Rendered inside the input's box, at its end (for example a show-password button). */
  trailing?: ReactNode
}

export function Field({ label, error, hint, after, trailing, className, ...input }: FieldProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined
  return (
    <div className={`auth-field${error ? " auth-field-invalid" : ""}${className ? ` ${className}` : ""}`}>
      <label htmlFor={id} className="auth-label">
        {label}
      </label>
      {hint ? (
        <p id={hintId} className="auth-hint">
          {hint}
        </p>
      ) : null}
      {trailing ? (
        <div className="auth-input-wrap">
          <input id={id} className="auth-input" aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...input} />
          {trailing}
        </div>
      ) : (
        <input id={id} className="auth-input" aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...input} />
      )}
      {after}
      {error ? (
        <p id={errorId} className="auth-field-error" data-testid="field-error">
          {error}
        </p>
      ) : null}
    </div>
  )
}

export function SubmitButton({ pending, children, pendingText, disabled, className, ...rest }: { pending: boolean; children: ReactNode; pendingText: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="submit" className={`auth-button auth-button-primary${className ? ` ${className}` : ""}`} disabled={pending || disabled} aria-busy={pending || undefined} {...rest}>
      {pending ? (
        <>
          <span className="auth-spinner" aria-hidden="true" />
          {pendingText}
        </>
      ) : (
        children
      )}
    </button>
  )
}

export function Divider({ children }: { children: ReactNode }) {
  return (
    <div className="auth-divider" role="separator">
      <span>{children}</span>
    </div>
  )
}
