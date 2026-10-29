/**
 * Request gate in front of Better Auth's handler: the 503 when accounts are not configured, and a
 * strict origin check on every state-changing request (Better Auth itself checks origins only when
 * cookies are present).
 */
import type { UnavailableReason } from "./config"

const NO_STORE = { "cache-control": "no-store", "content-type": "application/json; charset=utf-8" } as const

const UNAVAILABLE_MESSAGES: Record<UnavailableReason, string> = {
  database_not_configured: "Accounts are not available on this deployment: the database is not configured.",
  secret_not_configured: "Accounts are not available on this deployment: the auth secret is not configured.",
  secret_too_short: "Accounts are not available on this deployment: the auth secret is too short.",
  base_url_invalid: "Accounts are not available on this deployment: the auth URL is not valid.",
}

export function unavailableResponse(reason: UnavailableReason): Response {
  return new Response(JSON.stringify({ error: "accounts_unavailable", code: reason.toUpperCase(), message: UNAVAILABLE_MESSAGES[reason] }), {
    status: 503,
    headers: { ...NO_STORE, "retry-after": "300" },
  })
}

/**
 * Removes every `token` property from a JSON body. Better Auth returns the session token in JSON for
 * bearer-token clients; this site only uses the httpOnly cookie, so page scripts never see it.
 */
export function stripTokens(value: unknown, depth = 0): unknown {
  if (depth > 6 || value === null || typeof value !== "object") return value
  if (Array.isArray(value)) return value.map((item) => stripTokens(item, depth + 1))
  const out: Record<string, unknown> = {}
  for (const [key, inner] of Object.entries(value)) if (key !== "token") out[key] = stripTokens(inner, depth + 1)
  return out
}

export async function withoutSessionTokens(response: Response): Promise<Response> {
  const type = response.headers.get("content-type") ?? ""
  if (!type.includes("application/json") || response.status === 204) return response
  const text = await response.text()
  let body: unknown
  try {
    body = JSON.parse(text)
  } catch {
    return new Response(text, { status: response.status, statusText: response.statusText, headers: response.headers })
  }
  const headers = new Headers(response.headers)
  headers.delete("content-length")
  return new Response(JSON.stringify(stripTokens(body)), { status: response.status, statusText: response.statusText, headers })
}

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"])

/**
 * Rejects a state-changing request from another site: a cross-site Fetch Metadata header, or an
 * Origin (or, without one, a Referer) that is not one of ours. Requests from non-browser clients
 * carry neither header and pass through to Better Auth's own checks.
 */
export function crossOriginRejection(request: Request, trustedOrigins: readonly string[]): Response | null {
  if (SAFE_METHODS.has(request.method.toUpperCase())) return null
  const site = request.headers.get("sec-fetch-site")
  const origin = request.headers.get("origin")
  let source = origin && origin !== "null" ? origin : null
  if (!source) {
    const referer = request.headers.get("referer")
    if (referer) {
      try {
        source = new URL(referer).origin
      } catch {
        source = "invalid"
      }
    }
  }
  const forbidden = site === "cross-site" || origin === "null" || (source !== null && !trustedOrigins.includes(source))
  if (!forbidden) return null
  return new Response(JSON.stringify({ code: "INVALID_ORIGIN", message: "This request came from a site that is not allowed to use LLMSlim accounts." }), { status: 403, headers: NO_STORE })
}
