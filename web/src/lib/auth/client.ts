"use client"

import { createAuthClient } from "better-auth/react"
import { passkeyClient } from "@better-auth/passkey/client"

let lastRetryAfter: number | null = null

/** Seconds from the most recent 429's X-Retry-After header, read once. */
export function takeRetryAfter(): number | null {
  const value = lastRetryAfter
  lastRetryAfter = null
  return value
}

export const authClient = createAuthClient({
  basePath: "/api/auth",
  plugins: [passkeyClient()],
  fetchOptions: {
    onError(context) {
      if (context.response?.status === 429) {
        const seconds = Number(context.response.headers.get("X-Retry-After"))
        lastRetryAfter = Number.isFinite(seconds) && seconds > 0 ? seconds : null
      }
    },
  },
})
