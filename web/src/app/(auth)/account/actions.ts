"use server"

/**
 * Account actions that Better Auth does not expose over HTTP, or exposes in a way that would hand
 * session tokens to the browser. Next.js checks the Origin of every server action request.
 */
import { and, eq } from "drizzle-orm"
import { headers } from "next/headers"
import { isPasswordCompromised } from "better-auth/plugins/haveibeenpwned"
import { account, session as sessionTable } from "@/db/schema"
import { recordAuthEvent } from "@/lib/auth/audit"
import { getAuthConfig } from "@/lib/auth/config"
import { greetingName, passwordChangedMail, sendMail } from "@/lib/auth/email"
import { GENERIC_ERROR, REAUTH_MESSAGE } from "@/lib/auth/messages"
import { consume } from "@/lib/auth/rate-limit-store"
import { rateLimitMessage } from "@/lib/auth/rate-limits"
import { FRESH_SESSION_AGE, getAuthInstance } from "@/lib/auth/server"
import { validatePassword } from "@/lib/auth/validation"

export type ActionResult = { ok: true } | { ok: false; error: string; code?: string }

const SESSION_ID = /^[A-Za-z0-9]{16,64}$/

async function signedIn() {
  const instance = getAuthInstance()
  if (!instance) return null
  const requestHeaders = await headers()
  const current = await instance.auth.api.getSession({ headers: requestHeaders }).catch(() => null)
  if (!current) return null
  return { ...instance, current, requestHeaders }
}

export async function revokeSessionAction(sessionId: unknown): Promise<ActionResult> {
  const context = await signedIn()
  if (!context) return { ok: false, code: "UNAUTHORIZED", error: "Your session has ended. Sign in again." }
  if (typeof sessionId !== "string" || !SESSION_ID.test(sessionId)) return { ok: false, error: "That session was not found." }
  if (sessionId === context.current.session.id) return { ok: false, error: "To end this session, use Sign out." }
  const deleted = await context.db
    .delete(sessionTable)
    .where(and(eq(sessionTable.id, sessionId), eq(sessionTable.userId, context.current.user.id)))
    .returning({ id: sessionTable.id })
  if (deleted.length === 0) return { ok: false, error: "That session was not found. It may have ended already." }
  await recordAuthEvent(context.db, getAuthConfig().secret ?? "", { type: "session_revoked", userId: context.current.user.id, headers: context.requestHeaders })
  return { ok: true }
}

/** Adds a password to an account that signs in only with Google, GitHub or a passkey. */
export async function setPasswordAction(newPassword: unknown): Promise<ActionResult> {
  const context = await signedIn()
  if (!context) return { ok: false, code: "UNAUTHORIZED", error: "Your session has ended. Sign in again." }
  const config = getAuthConfig()
  const userId = context.current.user.id
  if (typeof newPassword !== "string") return { ok: false, error: GENERIC_ERROR }
  const invalid = validatePassword(newPassword)
  if (invalid) return { ok: false, code: "INVALID_PASSWORD", error: invalid }
  const createdAt = new Date(context.current.session.createdAt).getTime()
  if (Date.now() - createdAt >= FRESH_SESSION_AGE * 1000) return { ok: false, code: "SESSION_NOT_FRESH", error: REAUTH_MESSAGE }
  const existing = await context.db.select({ id: account.id }).from(account).where(and(eq(account.userId, userId), eq(account.providerId, "credential")))
  if (existing.length > 0) return { ok: false, error: "Your account already has a password. Use Change password instead." }
  const limit = await consume(context.db, `user|${userId}|set-password`, { window: 15 * 60, max: 5 })
  if (!limit.allowed) return { ok: false, code: "RATE_LIMITED", error: rateLimitMessage(limit.retryAfter) }
  if (config.breachedPasswordCheck) {
    try {
      if (await isPasswordCompromised(newPassword)) return { ok: false, code: "PASSWORD_COMPROMISED", error: "This password appears in a known data breach. Choose a different one." }
    } catch {
      return { ok: false, error: "We could not check that password right now. Please try again." }
    }
  }
  try {
    await context.auth.api.setPassword({ body: { newPassword }, headers: context.requestHeaders })
  } catch (error) {
    console.error("[accounts] set password failed:", error instanceof Error ? error.message : "unknown error")
    return { ok: false, error: GENERIC_ERROR }
  }
  await recordAuthEvent(context.db, config.secret ?? "", { type: "password_set", userId, headers: context.requestHeaders })
  try {
    await sendMail(config.email, passwordChangedMail(context.current.user.email, greetingName(context.current.user), `${config.baseURL}/forgot-password`, "added"))
  } catch {
    // A notice, not a requirement.
  }
  return { ok: true }
}
