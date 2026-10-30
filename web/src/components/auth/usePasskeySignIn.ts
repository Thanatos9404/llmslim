"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import { describeError, OFFLINE_ERROR } from "@/lib/auth/messages"
import type { Status } from "./primitives"

const QUIET_CODES = new Set(["AUTH_CANCELLED", "ERROR_CEREMONY_ABORTED", "ERROR_ABORT", "ERROR_PASSTHROUGH_SEE_CAUSE_PROPERTY"])

/**
 * Passkey sign-in: an explicit button, plus conditional UI (passkeys offered in the email field's
 * autofill) where the browser supports it. Conditional UI starts as soon as the page is interactive,
 * so choosing a passkey from autofill signs in with no extra step.
 */
export function usePasskeySignIn({ enabled, onSuccess, onStatus }: { enabled: boolean; onSuccess: () => void; onStatus: (status: Status) => void }) {
  const [pending, setPending] = useState(false)
  const started = useRef(false)
  const mounted = useRef(false)
  const done = useRef(false)

  useEffect(() => {
    mounted.current = true
    if (enabled && !started.current) {
      // Started once per page view, even under React's development double-mount.
      started.current = true
      const credential = typeof window !== "undefined" ? window.PublicKeyCredential : undefined
      if (credential?.isConditionalMediationAvailable) {
        void credential
          .isConditionalMediationAvailable()
          .then(async (available) => {
            if (!available || !mounted.current) return
            const { data, error } = await authClient.signIn.passkey({ autoFill: true })
            if (!mounted.current || done.current) return
            if (data && !error) {
              done.current = true
              onSuccess()
            } else if (error && !QUIET_CODES.has("code" in error ? String(error.code) : "") && error.status !== 429) {
              // A failed autofill attempt is reported; a cancelled or superseded one is not.
              onStatus({ kind: "error", text: describeError(error, takeRetryAfter()) })
            }
          })
          .catch(() => undefined)
      }
    }
    return () => {
      mounted.current = false
    }
  }, [enabled, onSuccess, onStatus])

  const signIn = useCallback(async () => {
    if (!navigator.onLine) return onStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(true)
    onStatus(null)
    // Starting a new ceremony aborts a pending conditional one (SimpleWebAuthn handles this).
    const { data, error } = await authClient.signIn.passkey()
    if (data && !error) {
      done.current = true
      onSuccess()
      return
    }
    setPending(false)
    onStatus({ kind: "error", text: describeError(error, takeRetryAfter()) })
  }, [onStatus, onSuccess])

  return { pending, signIn }
}
