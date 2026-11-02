"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { FormStatus, type Status } from "@/components/auth/primitives"
import { NETWORK_ERROR, OFFLINE_ERROR } from "@/lib/auth/messages"
import { rateLimitMessage } from "@/lib/auth/rate-limits"
import { describeChoice, type Choice } from "@/lib/founding-list/validation"

const INVALID = "This link is invalid or has expired, or a newer one was sent. Use the newest email, or join again from the pricing page."

/**
 * Confirms from a script, not on page load on the server: link scanners that fetch URLs from email
 * cannot confirm a place, as with the account's email confirmation.
 */
export function ConfirmFoundingList({ token }: { token: string | null }) {
  const [working, setWorking] = useState(token !== null)
  const [status, setStatus] = useState<Status>(token ? null : { kind: "error", text: INVALID })
  const started = useRef(false)

  useEffect(() => {
    if (!token || started.current) return
    started.current = true
    // Keep the token out of the address bar and history once it has been read.
    window.history.replaceState(null, "", "/founding-list/confirm")
    const run = async () => {
      if (!navigator.onLine) {
        setWorking(false)
        return setStatus({ kind: "error", text: OFFLINE_ERROR })
      }
      try {
        const response = await fetch("/api/founding-list/confirm", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token }), credentials: "same-origin" })
        const data = (await response.json().catch(() => ({}))) as Partial<Choice> & { status?: string }
        setWorking(false)
        if (response.ok && data.status === "confirmed" && data.plan && data.currency && data.billing) {
          return setStatus({ kind: "success", text: `You’re on the founding list for ${describeChoice(data as Choice)}. We’ll email you when LLMSlim Orbit opens. Nothing is charged.` })
        }
        if (response.status === 429) return setStatus({ kind: "error", text: rateLimitMessage(Number(response.headers.get("retry-after")) || null) })
        setStatus({ kind: "error", text: response.status === 400 ? INVALID : NETWORK_ERROR })
      } catch {
        setWorking(false)
        setStatus({ kind: "error", text: NETWORK_ERROR })
      }
    }
    void run()
  }, [token])

  return (
    <div className="auth-stack">
      {working ? (
        <p className="auth-status auth-status-info" role="status" aria-busy="true" data-testid="confirming">
          <span className="auth-spinner" aria-hidden="true" /> Confirming your place…
        </p>
      ) : null}
      <FormStatus status={status} id="founding-confirm-status" />
      <noscript>
        <p className="auth-description">Confirming needs JavaScript. Turn it on and open the link again.</p>
      </noscript>
      {!working ? (
        <Link href="/pricing" className="auth-button auth-button-primary" data-testid="founding-pricing">
          See the plans
        </Link>
      ) : null}
    </div>
  )
}
