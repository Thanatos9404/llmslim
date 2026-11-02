"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { FormStatus, type Status } from "@/components/auth/primitives"
import { siteConfig } from "@/config/site"
import { NETWORK_ERROR, OFFLINE_ERROR } from "@/lib/auth/messages"
import { rateLimitMessage } from "@/lib/auth/rate-limits"

export type Outcome = "done" | "invalid" | "limited"

const DONE = "You have left the founding list. We won’t email you about Orbit again."
const INVALID = `This link is not valid. To leave the founding list, email ${siteConfig.founderEmail} and we will take you off it.`

function statusFor(outcome: Outcome | null): Status {
  if (outcome === "done") return { kind: "success", text: DONE }
  if (outcome === "invalid") return { kind: "error", text: INVALID }
  if (outcome === "limited") return { kind: "error", text: rateLimitMessage(null) }
  return null
}

/**
 * Unsubscribes from a script, like the confirm page, so link scanners cannot. Without JavaScript the
 * page shows a one-button form that posts the same token and comes back here with the outcome.
 */
export function UnsubscribeFoundingList({ token, outcome }: { token: string | null; outcome: Outcome | null }) {
  const [working, setWorking] = useState(token !== null && outcome === null)
  const [status, setStatus] = useState<Status>(statusFor(outcome))
  const started = useRef(false)

  useEffect(() => {
    if (!token || outcome !== null || started.current) return
    started.current = true
    window.history.replaceState(null, "", "/founding-list/unsubscribe")
    const run = async () => {
      if (!navigator.onLine) {
        setWorking(false)
        return setStatus({ kind: "error", text: OFFLINE_ERROR })
      }
      try {
        const response = await fetch("/api/founding-list/unsubscribe", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ token }), credentials: "same-origin" })
        setWorking(false)
        if (response.ok) return setStatus(statusFor("done"))
        if (response.status === 429) return setStatus({ kind: "error", text: rateLimitMessage(Number(response.headers.get("retry-after")) || null) })
        setStatus(response.status === 400 ? statusFor("invalid") : { kind: "error", text: NETWORK_ERROR })
      } catch {
        setWorking(false)
        setStatus({ kind: "error", text: NETWORK_ERROR })
      }
    }
    void run()
  }, [token, outcome])

  return (
    <div className="auth-stack">
      {working ? (
        <p className="auth-status auth-status-info" role="status" aria-busy="true" data-testid="unsubscribing">
          <span className="auth-spinner" aria-hidden="true" /> Taking you off the list…
        </p>
      ) : null}
      <FormStatus status={status} id="founding-unsubscribe-status" />
      {token && outcome === null ? (
        <noscript>
          <form className="auth-form" method="post" action="/api/founding-list/unsubscribe">
            <input type="hidden" name="token" value={token} />
            <button type="submit" className="auth-button auth-button-primary">Leave the founding list</button>
          </form>
        </noscript>
      ) : null}
      {status?.kind === "success" ? (
        <Link href="/pricing" className="auth-button auth-button-primary auth-button-secondary" data-testid="founding-rejoin">
          Changed your mind? See the plans
        </Link>
      ) : null}
    </div>
  )
}
