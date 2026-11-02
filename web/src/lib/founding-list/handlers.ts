/**
 * HTTP handlers for the founding list (src/app/api/founding-list). They take their configuration,
 * database and Better Auth instance as arguments, so unit tests run them against PGlite.
 *
 * Abuse protection reuses the accounts machinery: the same origin gate as /api/auth, the same
 * Postgres rate-limit store with HMAC keys, the same per-mailbox email budget, and the audit trail
 * for refused requests. A request that emails a link always gets the same answer, whether the
 * address is new, waiting for confirmation, already confirmed or unsubscribed, and the email is sent
 * after the response, so neither the answer nor its timing says which.
 */
import { getIP } from "better-auth/api"
import { waitUntil } from "@vercel/functions"
import { siteConfig } from "@/config/site"
import { hashIdentifier, recordAuthEvent } from "@/lib/auth/audit"
import type { AuthConfig } from "@/lib/auth/config"
import { foundingListConfirmMail, foundingListMemberMail, sendMail, type Mail } from "@/lib/auth/email"
import { crossOriginRejection } from "@/lib/auth/http"
import { housekeepingDue, pruneExpired } from "@/lib/auth/housekeeping"
import { withinMailBudget } from "@/lib/auth/mail-budget"
import { consume, type AnyPgDatabase } from "@/lib/auth/rate-limit-store"
import { FOUNDING_LIST_RULES, rateLimitMessage, type Rule } from "@/lib/auth/rate-limits"
import type { Auth } from "@/lib/auth/server"
import { confirmByToken, joinWithAccount, leaveWithAccount, requestByEmail, unsubscribeByToken, type EmailRequestOutcome } from "./store"
import { CONFIRM_TOKEN_TTL_DAYS, isConfirmToken, unsubscribeToken } from "./tokens"
import { parseJoinRequest } from "./validation"

export type HandlerOptions = {
  /** Where background work goes. Defaults to Vercel's waitUntil; tests pass a collector. */
  background?: (promise: Promise<unknown>) => void
  /** Overrides the mail transport (tests). */
  mail?: (mail: Mail) => Promise<void>
}

const NO_STORE = { "cache-control": "no-store", "content-type": "application/json; charset=utf-8" } as const
const MAX_BODY = 4096
const PATH = "/founding-list"
export const UNSUBSCRIBE_PAGE = "/founding-list/unsubscribe"

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { ...NO_STORE, ...headers } })
}

function tooMany(retryAfter: number | null): Response {
  const seconds = String(retryAfter ?? 60)
  return json(429, { code: "RATE_LIMITED", message: rateLimitMessage(retryAfter) }, { "retry-after": seconds })
}

/** Requests that act on the session cookie must name a trusted origin; a missing Origin is not enough. */
function cookieOriginRejection(request: Request, trustedOrigins: readonly string[]): Response | null {
  const origin = request.headers.get("origin")
  if (origin && trustedOrigins.includes(origin)) return null
  return json(403, { code: "INVALID_ORIGIN", message: "This request was blocked because it did not come from llmslim.app." })
}

/**
 * The confirm and unsubscribe pages carry a token in their URL, so they send no referrer, and a
 * browser may then post from them with `Origin: null` (a plain form always does). Sec-Fetch-Site,
 * which no page can set, still shows the request came from this site. For these two the token is
 * the credential, not a cookie, so a request from elsewhere could do no more than one sent directly.
 */
function tokenPageOriginRejection(request: Request, trustedOrigins: readonly string[]): Response | null {
  if (request.headers.get("origin") === "null" && request.headers.get("sec-fetch-site") === "same-origin") return null
  return crossOriginRejection(request, trustedOrigins)
}

type Body = { ok: true; value: unknown } | { ok: false; response: Response }

async function readJson(request: Request): Promise<Body> {
  const type = (request.headers.get("content-type") ?? "").toLowerCase()
  if (!type.startsWith("application/json")) return { ok: false, response: json(415, { code: "UNSUPPORTED_MEDIA_TYPE", message: "Send JSON." }) }
  const text = await request.text()
  if (text.length > MAX_BODY) return { ok: false, response: json(413, { code: "TOO_LARGE", message: "That request is too large." }) }
  try {
    return { ok: true, value: JSON.parse(text) }
  } catch {
    return { ok: false, response: json(400, { code: "INVALID_REQUEST", message: "That request could not be read." }) }
  }
}

export function foundingListHandlers(config: AuthConfig, db: AnyPgDatabase, auth: Auth, options: HandlerOptions = {}) {
  if (!config.secret) throw new Error("The founding list needs the auth secret")
  const secret = config.secret
  const site = config.baseURL
  const background = options.background ?? ((promise: Promise<unknown>) => waitUntil(promise))
  const deliver = options.mail ?? ((mail: Mail) => sendMail(config.email, mail))

  const limit = async (key: string, rule: Rule, request: Request): Promise<Response | null> => {
    const decision = await consume(db, key, rule)
    if (decision.allowed) return null
    await recordAuthEvent(db, secret, { type: "rate_limited", method: PATH, headers: request.headers })
    return tooMany(decision.retryAfter)
  }

  /** Per network, the way Better Auth keys its own limits (IPv6 per /64). No IP: no network limit. */
  const limitByIp = (request: Request, action: string, rule: Rule) => {
    const ip = getIP(request, auth.options)
    return ip ? limit(`ip|${hashIdentifier(secret, "ip", `${ip}|${PATH}/${action}`)}`, rule, request) : Promise.resolve(null)
  }

  const session = async (request: Request) => {
    try {
      return await auth.api.getSession({ headers: request.headers })
    } catch (error) {
      console.error("[founding-list] could not read the session:", error instanceof Error ? error.message : "unknown error")
      return null
    }
  }

  const sendSafely = async (mail: Mail) => {
    try {
      if (!(await withinMailBudget(db, secret, mail))) {
        console.warn(`[founding-list] skipped a ${mail.kind} email: its mailbox reached the email limit`)
        await recordAuthEvent(db, secret, { type: "rate_limited", method: `email:${mail.kind}` })
        return
      }
      await deliver(mail)
    } catch (error) {
      // The address is not logged; the kind is enough to find the failure.
      console.error(`[founding-list] could not send the ${mail.kind} email:`, error instanceof Error ? error.message : "unknown error")
    }
  }

  const mailFor = (email: string, outcome: EmailRequestOutcome): Mail => {
    const unsubscribeUrl = `${site}${UNSUBSCRIBE_PAGE}?token=${encodeURIComponent(unsubscribeToken(secret, outcome.id))}`
    if (outcome.kind === "already-confirmed") return foundingListMemberMail(email, outcome.choice, `${site}/pricing`, unsubscribeUrl, siteConfig.founderEmail)
    return foundingListConfirmMail(email, outcome.choice, `${site}/founding-list/confirm?token=${encodeURIComponent(outcome.token)}`, unsubscribeUrl, CONFIRM_TOKEN_TTL_DAYS)
  }

  /**
   * POST: join. Without an email, joins with the signed-in account (401 EMAIL_REQUIRED when signed
   * out); with one, starts the double opt-in for that address.
   */
  async function join(request: Request): Promise<Response> {
    const rejected = crossOriginRejection(request, config.trustedOrigins)
    if (rejected) return rejected
    const body = await readJson(request)
    if (!body.ok) return body.response
    const parsed = parseJoinRequest(body.value)
    if (!parsed.ok) return json(400, { code: parsed.code, message: parsed.message })
    const { choice, source, email, useCase } = parsed.value

    if (housekeepingDue()) {
      background(pruneExpired(db).catch((error) => console.error("[founding-list] could not prune expired rows:", error instanceof Error ? error.message : "unknown error")))
    }
    const limited = await limitByIp(request, "join", FOUNDING_LIST_RULES.join)
    if (limited) return limited

    if (email === null) {
      const originRejected = cookieOriginRejection(request, config.trustedOrigins)
      if (originRejected) return originRejected
      const current = await session(request)
      // Accounts start verified, so this always holds; an unverified address goes through the email link instead.
      if (!current || current.user.emailVerified !== true) return json(401, { code: "EMAIL_REQUIRED", message: "Enter your email address to join." })
      const accountLimited = await limit(`user|${current.user.id}|founding-list`, FOUNDING_LIST_RULES.account, request)
      if (accountLimited) return accountLimited
      const joined = await joinWithAccount(db, current.user, choice, source)
      return json(200, { status: "joined", ...joined })
    }

    if (config.email.mode === "disabled") return json(503, { code: "EMAIL_UNAVAILABLE", message: "Joining by email is not available right now." })
    const emailLimited = await limit(`email|${hashIdentifier(secret, "email", email)}|${PATH}`, FOUNDING_LIST_RULES.email, request)
    if (emailLimited) return emailLimited
    const outcome = await requestByEmail(db, secret, { email, choice, useCase, source })
    background(sendSafely(mailFor(email, outcome)))
    return json(200, { status: "check_email" })
  }

  /** DELETE: a signed-in member leaves the list. */
  async function leave(request: Request): Promise<Response> {
    const rejected = crossOriginRejection(request, config.trustedOrigins) ?? cookieOriginRejection(request, config.trustedOrigins)
    if (rejected) return rejected
    const current = await session(request)
    if (!current) return json(401, { code: "UNAUTHORIZED", message: "Your session has ended. Sign in again." })
    const limited = await limit(`user|${current.user.id}|founding-list`, FOUNDING_LIST_RULES.account, request)
    if (limited) return limited
    await leaveWithAccount(db, current.user)
    return json(200, { status: "left" })
  }

  /** POST { token }: follows a confirm link (the confirm page sends it, so link scanners cannot). */
  async function confirm(request: Request): Promise<Response> {
    const rejected = tokenPageOriginRejection(request, config.trustedOrigins)
    if (rejected) return rejected
    const body = await readJson(request)
    if (!body.ok) return body.response
    const limited = await limitByIp(request, "link", FOUNDING_LIST_RULES.link)
    if (limited) return limited
    const token = (body.value as { token?: unknown } | null)?.token
    const choice = isConfirmToken(token) ? await confirmByToken(db, secret, token) : null
    if (!choice) return json(400, { code: "INVALID_TOKEN", message: "This link is invalid or has expired." })
    return json(200, { status: "confirmed", ...choice })
  }

  /**
   * POST { token }: follows an unsubscribe link. Takes JSON from the unsubscribe page's script, or a
   * plain form post from its no-JavaScript fallback, which is answered with a redirect back to it.
   */
  async function unsubscribe(request: Request): Promise<Response> {
    const rejected = tokenPageOriginRejection(request, config.trustedOrigins)
    if (rejected) return rejected
    const form = (request.headers.get("content-type") ?? "").toLowerCase().startsWith("application/x-www-form-urlencoded")
    let token: unknown
    if (form) {
      const text = await request.text()
      token = text.length <= MAX_BODY ? new URLSearchParams(text).get("token") : null
    } else {
      const body = await readJson(request)
      if (!body.ok) return body.response
      token = (body.value as { token?: unknown } | null)?.token
    }
    const limited = await limitByIp(request, "link", FOUNDING_LIST_RULES.link)
    if (limited) return form ? Response.redirect(`${site}${UNSUBSCRIBE_PAGE}?result=limited`, 303) : limited
    const done = await unsubscribeByToken(db, secret, token)
    if (form) return Response.redirect(`${site}${UNSUBSCRIBE_PAGE}?result=${done ? "done" : "invalid"}`, 303)
    if (!done) return json(400, { code: "INVALID_TOKEN", message: "This link is invalid." })
    return json(200, { status: "unsubscribed" })
  }

  return { join, leave, confirm, unsubscribe }
}

export type FoundingListHandlers = ReturnType<typeof foundingListHandlers>
