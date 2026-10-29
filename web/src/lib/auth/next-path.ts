/**
 * Sanitises the `?next=` redirect target used after sign-in.
 *
 * Only same-origin paths are accepted: a single leading slash, no scheme, no protocol-relative
 * `//host`, no backslashes (browsers treat `/\host` as `//host`), no control characters, and nothing
 * that resolves to another origin. Anything else falls back to the account page.
 */

export const DEFAULT_NEXT = "/account"
// Where a redirect after sign-in would be pointless or loop: API routes and the auth pages themselves.
const BLOCKED_SEGMENTS = ["/api", "/_next", "/sign-in", "/sign-up", "/forgot-password", "/reset-password", "/verify-email"]
const PLACEHOLDER_ORIGIN = "https://next-path.invalid"

export function sanitizeNext(raw: unknown, fallback: string = DEFAULT_NEXT): string {
  if (typeof raw !== "string") return fallback
  const candidate = raw.trim()
  if (!candidate || candidate.length > 512) return fallback
  if (!candidate.startsWith("/") || candidate.startsWith("//")) return fallback
  if (/[\\\u0000-\u001f\u007f]/.test(candidate)) return fallback
  let decoded: string
  try {
    decoded = decodeURIComponent(candidate)
  } catch {
    return fallback
  }
  // Encoded slashes or backslashes can turn into "//" or "/\" after a later decode.
  if (decoded.startsWith("//") || /[\\\u0000-\u001f\u007f]/.test(decoded)) return fallback
  let url: URL
  try {
    url = new URL(candidate, PLACEHOLDER_ORIGIN)
  } catch {
    return fallback
  }
  if (url.origin !== PLACEHOLDER_ORIGIN) return fallback
  const path = `${url.pathname}${url.search}${url.hash}`
  const lowered = url.pathname.toLowerCase()
  if (BLOCKED_SEGMENTS.some((segment) => lowered === segment || lowered.startsWith(`${segment}/`))) return fallback
  return path
}
