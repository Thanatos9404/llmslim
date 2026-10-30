/**
 * User-facing wording for every error the accounts API can return. Messages stay generic where
 * detail would reveal whether an account exists.
 */
import { rateLimitMessage } from "./rate-limits"

export const GENERIC_ERROR = "Something went wrong. Please try again."
export const OFFLINE_ERROR = "You appear to be offline. Check your connection and try again."
export const NETWORK_ERROR = "We could not reach LLMSlim. Check your connection and try again."
export const REAUTH_MESSAGE = "For your security, sign in again to do this."

const BY_CODE: Record<string, string> = {
  INVALID_EMAIL_OR_PASSWORD: "The email or password is incorrect.",
  EMAIL_NOT_VERIFIED: "Confirm your email address first. We have sent you a new link.",
  INVALID_EMAIL: "Enter a valid email address.",
  INVALID_NAME: "Use letters, numbers, spaces, hyphens and apostrophes only.",
  PASSWORD_TOO_SHORT: "Use at least 10 characters.",
  PASSWORD_TOO_LONG: "Use 128 characters or fewer.",
  PASSWORD_COMPROMISED: "This password appears in a known data breach. Choose a different one.",
  INVALID_PASSWORD: "Your current password is incorrect.",
  INVALID_TOKEN: "This link is invalid or has expired. Request a new one.",
  TOKEN_EXPIRED: "This link has expired. Request a new one.",
  TOKEN_ALREADY_USED: "This link has already been used. If your email is confirmed, sign in.",
  USER_NOT_FOUND: "This link is invalid or has expired. Request a new one.",
  SESSION_NOT_FRESH: "For your security, sign in again to do this.",
  SESSION_EXPIRED: "For your security, sign in again to do this.",
  UNAUTHORIZED: "Your session has ended. Sign in again.",
  CREDENTIAL_ACCOUNT_NOT_FOUND: "This account has no password. Set one first.",
  FAILED_TO_UNLINK_LAST_ACCOUNT: "Add another way to sign in before removing this one.",
  ACCOUNT_NOT_FOUND: "That sign-in method is not connected.",
  EMAIL_PASSWORD_SIGN_UP_DISABLED: "New accounts with email and password are not available right now. Continue with Google or GitHub instead.",
  RESET_PASSWORD_DISABLED: "Password reset by email is not available right now.",
  VERIFICATION_EMAIL_NOT_ENABLED: "Email confirmation is not available right now.",
  INVALID_ORIGIN: "This request was blocked because it did not come from llmslim.app.",
  MISSING_OR_NULL_ORIGIN: "This request was blocked because it did not come from llmslim.app.",
  ACCOUNTS_UNAVAILABLE: "Accounts are not available on this deployment yet.",
  RATE_LIMITED: "Too many attempts. Try again in a few minutes.",
  // Passkeys
  AUTH_CANCELLED: "The passkey request was cancelled or timed out.",
  ERROR_CEREMONY_ABORTED: "The passkey request was cancelled or timed out.",
  REGISTRATION_CANCELLED: "Adding the passkey was cancelled or timed out.",
  PREVIOUSLY_REGISTERED: "This passkey is already saved to your account.",
  ERROR_AUTHENTICATOR_PREVIOUSLY_REGISTERED: "This passkey is already saved to your account.",
  PASSKEY_NOT_FOUND: "This passkey is not registered with LLMSlim. Sign in another way, then add it from your account page.",
  AUTHENTICATION_FAILED: "We could not verify that passkey. Try again.",
  CHALLENGE_NOT_FOUND: "The passkey request expired. Try again.",
  USER_VERIFICATION_REQUIRED: "Your device must confirm it is you (PIN, fingerprint or face) to use a passkey.",
  YOU_ARE_NOT_ALLOWED_TO_REGISTER_THIS_PASSKEY: "This passkey cannot be added to your account.",
  FAILED_TO_VERIFY_REGISTRATION: "We could not verify that passkey. Try again.",
  INVALID_PASSKEY_NAME: "Use 60 characters or fewer, without < or >.",
  // OAuth callback errors (query parameter `error` on /sign-in and /account)
  email_not_verified: "Your email address is not verified with that provider. Verify it there, then try again.",
  account_not_linked: "An account with this email already exists. Sign in with your password or a passkey, then connect this provider from your account page.",
  unable_to_link_account: "We could not connect that account. Try again.",
  "email_doesn't_match": "That account uses a different email address from your LLMSlim account.",
  account_already_linked_to_different_user: "That account is already connected to a different LLMSlim account.",
  signup_disabled: "New accounts are not available right now.",
  state_mismatch: "The sign-in request expired. Try again.",
  please_restart_the_process: "The sign-in request expired. Try again.",
  invalid_code: "The sign-in request expired. Try again.",
  access_denied: "You cancelled signing in with that provider.",
}

export type ErrorLike = { code?: string | null; message?: string | null; status?: number | null } | null | undefined

export function messageForCode(code: string | null | undefined): string | null {
  if (!code) return null
  return BY_CODE[code] ?? BY_CODE[code.toUpperCase()] ?? null
}

/** Picks the message for a Better Auth client error. */
export function describeError(error: ErrorLike, retryAfter?: number | null): string {
  if (!error) return GENERIC_ERROR
  if (error.status === 429) return rateLimitMessage(retryAfter ?? null)
  if (error.status === 503) return BY_CODE.ACCOUNTS_UNAVAILABLE
  const known = messageForCode(error.code)
  if (known) return known
  if (error.status === 0 || error.status === undefined) {
    if (typeof navigator !== "undefined" && navigator.onLine === false) return OFFLINE_ERROR
    return NETWORK_ERROR
  }
  if (error.status && error.status >= 500) return GENERIC_ERROR
  return GENERIC_ERROR
}
