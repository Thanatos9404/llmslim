/**
 * Rate-limit rules for the accounts API. Windows are in seconds.
 *
 * Two layers, both stored in Postgres (serverless instances share no memory):
 * - per client IP, enforced by Better Auth's limiter for every path below;
 * - per email address, enforced by the hooks in server.ts for the paths that take an email. The
 *   email is keyed by an HMAC, so the table never holds a readable address.
 *
 * Sign-in counts only failed attempts per email, so a person who signs in and out repeatedly is
 * never locked out, while guessing against one account stops after a handful of tries.
 */

export type Rule = { window: number; max: number }

const MINUTE = 60
const HOUR = 60 * MINUTE

/** Every request not listed below. */
export const DEFAULT_RULE: Rule = { window: MINUTE, max: 100 }

export const IP_RULES = {
  "/sign-in/email": { window: 15 * MINUTE, max: 20 },
  "/sign-up/email": { window: HOUR, max: 10 },
  "/request-password-reset": { window: 15 * MINUTE, max: 5 },
  "/send-verification-email": { window: 15 * MINUTE, max: 5 },
  "/reset-password": { window: 15 * MINUTE, max: 10 },
  "/reset-password/*": { window: 15 * MINUTE, max: 20 },
  "/verify-email": { window: 15 * MINUTE, max: 20 },
  "/change-password": { window: 15 * MINUTE, max: 10 },
  "/delete-user": { window: 15 * MINUTE, max: 10 },
  "/sign-in/social": { window: 5 * MINUTE, max: 20 },
  "/link-social": { window: 15 * MINUTE, max: 10 },
  "/unlink-account": { window: 15 * MINUTE, max: 10 },
  "/callback/*": { window: 5 * MINUTE, max: 30 },
  // Conditional UI asks for options on every sign-in page view, so this one is more generous.
  "/passkey/generate-authenticate-options": { window: 5 * MINUTE, max: 60 },
  "/passkey/verify-authentication": { window: 5 * MINUTE, max: 20 },
  "/passkey/generate-register-options": { window: 15 * MINUTE, max: 20 },
  "/passkey/verify-registration": { window: 15 * MINUTE, max: 20 },
  "/passkey/update-passkey": { window: 15 * MINUTE, max: 30 },
  "/passkey/delete-passkey": { window: 15 * MINUTE, max: 30 },
} as const satisfies Record<string, Rule>

export const EMAIL_RULES = {
  /** Failed attempts only. */
  "/sign-in/email": { window: 15 * MINUTE, max: 5 },
  "/sign-up/email": { window: HOUR, max: 3 },
  "/request-password-reset": { window: HOUR, max: 3 },
  "/send-verification-email": { window: HOUR, max: 3 },
} as const satisfies Record<string, Rule>

export type EmailLimitedPath = keyof typeof EMAIL_RULES

export function isEmailLimitedPath(path: string | undefined): path is EmailLimitedPath {
  return typeof path === "string" && Object.prototype.hasOwnProperty.call(EMAIL_RULES, path)
}

/** The message every rate-limited form shows, with the wait rounded up to whole minutes. */
export function rateLimitMessage(retryAfterSeconds: number | null | undefined): string {
  const seconds = Number.isFinite(retryAfterSeconds) && (retryAfterSeconds as number) > 0 ? (retryAfterSeconds as number) : 60
  const minutes = Math.max(1, Math.ceil(seconds / 60))
  return `Too many attempts. Try again in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`
}
