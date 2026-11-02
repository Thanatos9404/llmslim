/**
 * The two links in a founding-list email.
 *
 * - Confirm: 32 random bytes. The database keeps only an HMAC of it (keyed by the auth secret), so a
 *   leaked table cannot be turned into working links. It expires after 7 days, and asking again
 *   replaces it, so only the newest link works.
 * - Unsubscribe: the row's id and an HMAC of it. Nothing is stored and it never expires, so the link
 *   keeps working for as long as the row exists. Rotating the auth secret invalidates both kinds.
 */
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto"
import { CONFIRM_LINK_DAYS } from "./validation"

export const CONFIRM_TOKEN_TTL_DAYS = CONFIRM_LINK_DAYS
export const CONFIRM_TOKEN_TTL_SECONDS = CONFIRM_LINK_DAYS * 24 * 60 * 60

const CONFIRM_TOKEN = /^[A-Za-z0-9_-]{43}$/
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const SIGNATURE = /^[A-Za-z0-9_-]{43}$/

function hmac(secret: string, purpose: string, value: string): Buffer {
  return createHmac("sha256", secret).update(`founding-list:${purpose}:${value}`).digest()
}

export function newConfirmToken(): string {
  return randomBytes(32).toString("base64url")
}

/** Whether a value has the shape of a confirm token; anything else is not worth a database lookup. */
export function isConfirmToken(value: unknown): value is string {
  return typeof value === "string" && CONFIRM_TOKEN.test(value)
}

/** What the database stores for a confirm token. */
export function confirmTokenHash(secret: string, token: string): string {
  return hmac(secret, "confirm", token).toString("hex")
}

export function unsubscribeToken(secret: string, id: string): string {
  return `${id}.${hmac(secret, "unsubscribe", id).toString("base64url")}`
}

/** The row id an unsubscribe token was made for, or null when the token is malformed or not ours. */
export function readUnsubscribeToken(secret: string, token: unknown): string | null {
  if (typeof token !== "string" || token.length > 100) return null
  const [id, signature, ...rest] = token.split(".")
  if (rest.length > 0 || !id || !signature || !UUID.test(id) || !SIGNATURE.test(signature)) return null
  const expected = hmac(secret, "unsubscribe", id)
  const given = Buffer.from(signature, "base64url")
  return given.length === expected.length && timingSafeEqual(given, expected) ? id : null
}
