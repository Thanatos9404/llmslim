/**
 * Security audit trail (the auth_event table).
 *
 * Each row holds the user id (when known), the event type, the sign-in method, an HMAC of the
 * client IP and a truncated user agent. Never a password, token, email address or raw IP. Writes are
 * best effort: a failed audit write is logged and never blocks sign-in.
 */
import { createHmac } from "node:crypto"
import { authEvent } from "@/db/schema"
import type { AnyPgDatabase } from "./rate-limit-store"

export type AuthEventType =
  | "sign_up"
  | "sign_in_success"
  | "sign_in_failure"
  | "sign_out"
  | "email_verified"
  | "password_reset"
  | "password_changed"
  | "password_set"
  | "passkey_added"
  | "passkey_renamed"
  | "passkey_removed"
  | "account_linked"
  | "account_unlinked"
  | "session_revoked"
  | "rate_limited"
  | "account_deleted"

export const AUDIT_RETENTION_DAYS = 180
const USER_AGENT_MAX = 256
/** Same order as Better Auth's ipAddressHeaders; Vercel overwrites both, so clients cannot spoof them there. */
export const IP_HEADERS = ["x-real-ip", "x-forwarded-for"] as const

/** The client IP from a single-valued forwarding header, or null. */
export function clientIp(headers: Headers | null | undefined): string | null {
  if (!headers) return null
  for (const name of IP_HEADERS) {
    const raw = headers.get(name)
    if (!raw) continue
    const parts = raw.split(",").map((part) => part.trim()).filter(Boolean)
    if (parts.length === 1 && /^[0-9a-fA-F:.]{2,45}$/.test(parts[0])) return parts[0].toLowerCase()
  }
  return null
}

/** Keyed hash, so the table cannot be reversed with a lookup over the IPv4 space. */
export function hashIdentifier(secret: string, purpose: "ip" | "email", value: string): string {
  return createHmac("sha256", secret).update(`${purpose}:${value}`).digest("hex")
}

export function truncateUserAgent(userAgent: string | null | undefined): string | null {
  if (!userAgent) return null
  const clean = userAgent.replace(/[\u0000-\u001f\u007f]/g, " ").trim()
  return clean ? clean.slice(0, USER_AGENT_MAX) : null
}

export type AuditInput = { type: AuthEventType; userId?: string | null; method?: string | null; headers?: Headers | null }

export async function recordAuthEvent(db: AnyPgDatabase, secret: string, input: AuditInput): Promise<void> {
  try {
    const ip = clientIp(input.headers)
    await db.insert(authEvent).values({
      type: input.type,
      userId: input.userId ?? null,
      method: input.method ?? null,
      ipHash: ip ? hashIdentifier(secret, "ip", ip) : null,
      userAgent: truncateUserAgent(input.headers?.get("user-agent")),
    })
  } catch (error) {
    console.error(`[accounts] could not record the ${input.type} audit event:`, error instanceof Error ? error.message : "unknown error")
  }
}
