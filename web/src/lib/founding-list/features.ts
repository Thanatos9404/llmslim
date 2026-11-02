/**
 * What the pricing page's "Join the founding list" buttons can do on this deployment and for this
 * visitor. Pure and cheap: no database, no session lookup, so the page stays as fast as it was.
 */
import { getSessionCookie } from "better-auth/cookies"
import { COOKIE_PREFIX, type AuthConfig } from "@/lib/auth/config"

export type FoundingListFeatures = {
  /** The database and secret are configured. Without them every button stays the email link it was. */
  enabled: boolean
  /** An email transport is configured, so visitors who are not signed in can confirm by email. */
  canEmail: boolean
  /**
   * The request carries a session cookie, so a click tries the one-click join first. Only a hint:
   * the API checks the session, and a stale cookie falls back to the email form.
   */
  signedIn: boolean
}

export function foundingListFeatures(config: AuthConfig, requestHeaders: Headers): FoundingListFeatures {
  const enabled = config.unavailable === null
  return {
    enabled,
    canEmail: enabled && config.email.mode !== "disabled",
    signedIn: enabled && getSessionCookie(requestHeaders, { cookiePrefix: COOKIE_PREFIX }) !== null,
  }
}
