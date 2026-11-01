/**
 * The Better Auth instance for llmslim.app accounts.
 *
 * `buildAuth` takes a resolved configuration and a Drizzle database, so unit tests can run the real
 * configuration against an in-process PGlite database. `getAuth` builds the production instance
 * lazily on the first request: importing this module never touches the network or the environment,
 * which keeps `next build` working with no auth variables at all.
 */
import { betterAuth } from "better-auth"
import { drizzleAdapter } from "better-auth/adapters/drizzle"
import { APIError, createAuthMiddleware, getSessionFromCtx, isAPIError } from "better-auth/api"
import { nextCookies } from "better-auth/next-js"
import { haveIBeenPwned } from "better-auth/plugins/haveibeenpwned"
import type { GithubProfile } from "better-auth/social-providers"
import { passkey } from "@better-auth/passkey"
import { waitUntil } from "@vercel/functions"
import { sql } from "drizzle-orm"
import { authSchema } from "@/db/schema"
import { createDatabase } from "@/db/client"
import { recordAuthEvent, hashIdentifier, type AuthEventType } from "./audit"
import { getAuthConfig, type AuthConfig } from "./config"
import { accountDeletedMail, existingAccountMail, greetingName, passwordChangedMail, resetPasswordMail, sendMail, verificationMail, type Mail } from "./email"
import { housekeepingDue, pruneExpired } from "./housekeeping"
import { withinMailBudget } from "./mail-budget"
import { consume, peek, type AnyPgDatabase } from "./rate-limit-store"
import { DEFAULT_RULE, EMAIL_RULES, IP_RULES, isEmailLimitedPath, rateLimitMessage } from "./rate-limits"
import { NAME_MAX, PASSWORD_MAX, PASSWORD_MIN, normalizeEmail, validateEmail, validateName, validatePasskeyName } from "./validation"

export const SESSION_MAX_AGE = 7 * 24 * 60 * 60
export const SESSION_UPDATE_AGE = 24 * 60 * 60
/** Adding a passkey, unlinking a provider, setting a password or deleting without a password needs a sign-in this recent. */
export const FRESH_SESSION_AGE = 30 * 60
export const TOKEN_TTL = 60 * 60

/** Hosts whose avatar URLs we keep. Anything else is dropped, which also keeps the CSP's img-src short. */
export const AVATAR_HOSTS = ["lh3.googleusercontent.com", "avatars.githubusercontent.com"] as const

const PASSWORD_PATHS = ["/sign-up/email", "/change-password", "/reset-password"]
const USED_VERIFICATION_PREFIX = "used-email-verification:"

export type BuildOptions = {
  /** Where background work goes. Defaults to Vercel's waitUntil; tests pass a collector. */
  background?: (promise: Promise<unknown>) => void
  /** Overrides the mail transport (tests). */
  mail?: (mail: Mail) => Promise<void>
}

export function safeAvatar(url: unknown): string | null {
  if (typeof url !== "string" || url.length > 2048) return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === "https:" && (AVATAR_HOSTS as readonly string[]).includes(parsed.hostname) ? parsed.toString() : null
  } catch {
    return null
  }
}

function cleanName(name: unknown, email: unknown): string {
  const raw = typeof name === "string" ? name.replace(/[\u0000-\u001f\u007f<>]/g, " ").replace(/\s+/g, " ").trim() : ""
  if (raw) return Array.from(raw).slice(0, NAME_MAX).join("")
  return typeof email === "string" ? email.split("@")[0].slice(0, NAME_MAX) : "LLMSlim user"
}

/** The sign-in method behind a new session, from the endpoint that created it. */
export function methodFromPath(path: string | undefined, params?: Record<string, string> | undefined): string | null {
  if (!path) return null
  if (path === "/sign-in/email") return "password"
  if (path === "/passkey/verify-authentication") return "passkey"
  if (path.startsWith("/callback/")) return params?.id ?? path.slice("/callback/".length)
  return null
}

async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value))
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")
}

type GitHubEmail = { email: string; primary: boolean; verified: boolean }

/** GitHub sign-in uses the primary email and its verified flag from the API, never a public profile email. */
async function githubUserInfo(token: { accessToken?: string }) {
  if (!token.accessToken) return null
  const headers = { authorization: `Bearer ${token.accessToken}`, accept: "application/vnd.github+json", "user-agent": "llmslim-accounts", "x-github-api-version": "2022-11-28" }
  const [profileResponse, emailsResponse] = await Promise.all([
    fetch("https://api.github.com/user", { headers, signal: AbortSignal.timeout(10_000) }),
    fetch("https://api.github.com/user/emails", { headers, signal: AbortSignal.timeout(10_000) }),
  ])
  if (!profileResponse.ok || !emailsResponse.ok) return null
  const profile = (await profileResponse.json()) as GithubProfile
  const emails = (await emailsResponse.json()) as GitHubEmail[]
  const primary = Array.isArray(emails) ? emails.find((entry) => entry.primary) : undefined
  if (!primary?.email) return null
  return {
    // The account id comes from profile.id through the provider's accountSubject.
    user: {
      name: profile.name || profile.login,
      email: primary.email.toLowerCase(),
      image: profile.avatar_url,
      emailVerified: primary.verified === true,
    },
    data: profile,
  }
}

export function buildAuth(config: AuthConfig, db: AnyPgDatabase, options: BuildOptions = {}) {
  if (config.unavailable || !config.secret) throw new Error(`Accounts are unavailable: ${config.unavailable ?? "secret_not_configured"}`)
  const secret = config.secret
  const background = options.background ?? ((promise: Promise<unknown>) => waitUntil(promise))
  const deliver = options.mail ?? ((mail: Mail) => sendMail(config.email, mail))
  const site = config.baseURL

  const audit = (type: AuthEventType, userId: string | null | undefined, headers: Headers | null | undefined, method?: string | null) =>
    recordAuthEvent(db, secret, { type, userId, headers, method })

  const sendSafely = async (mail: Mail) => {
    try {
      if (!(await withinMailBudget(db, secret, mail))) {
        console.warn(`[accounts] skipped a ${mail.kind} email: its mailbox reached the email limit`)
        await audit("rate_limited", null, null, `email:${mail.kind}`)
        return
      }
      await deliver(mail)
    } catch (error) {
      // The address is not logged; the kind is enough to find the failure.
      console.error(`[accounts] could not send the ${mail.kind} email:`, error instanceof Error ? error.message : "unknown error")
    }
  }

  const emailKey = (email: string, path: string) => `email|${hashIdentifier(secret, "email", normalizeEmail(email))}|${path}`

  const tooManyRequests = (retryAfter: number | null) =>
    new APIError("TOO_MANY_REQUESTS", { message: rateLimitMessage(retryAfter), code: "RATE_LIMITED" }, { "X-Retry-After": String(retryAfter ?? 60), "Retry-After": String(retryAfter ?? 60) })

  const badRequest = (code: string, message: string) => new APIError("BAD_REQUEST", { code, message })

  const socialProviders: Parameters<typeof betterAuth>[0]["socialProviders"] = {}
  if (config.google) {
    socialProviders.google = {
      clientId: config.google.clientId,
      clientSecret: config.google.clientSecret,
      // openid, email and profile only: the defaults, and all we need.
      prompt: "select_account",
    }
  }
  if (config.github) {
    socialProviders.github = {
      clientId: config.github.clientId,
      clientSecret: config.github.clientSecret,
      // user:email lists the account's emails with their verified flags; the public profile needs no scope.
      disableDefaultScope: true,
      scope: ["user:email"],
      getUserInfo: githubUserInfo,
    }
  }

  const passkeyPlugin = passkey({
    rpID: config.passkey.rpID,
    rpName: config.passkey.rpName,
    origin: config.passkey.origins,
    // Discoverable credentials make username-less sign-in and autofill work; user verification is enforced below.
    authenticatorSelection: { residentKey: "required", userVerification: "required" },
    registration: {
      requireSession: true,
      afterVerification: ({ verification }) => {
        if (!verification.registrationInfo?.userVerified) throw new APIError("BAD_REQUEST", { code: "USER_VERIFICATION_REQUIRED", message: "Your device must confirm it is you (PIN, fingerprint or face) to add a passkey." })
      },
    },
    authentication: {
      afterVerification: ({ verification }) => {
        if (!verification.authenticationInfo.userVerified) throw new APIError("UNAUTHORIZED", { code: "USER_VERIFICATION_REQUIRED", message: "Your device must confirm it is you (PIN, fingerprint or face) to sign in." })
      },
    },
  })

  return betterAuth({
    appName: "LLMSlim",
    baseURL: config.baseURL,
    basePath: "/api/auth",
    secret,
    telemetry: { enabled: false },
    logger: { level: config.production ? "warn" : "info" },
    database: drizzleAdapter(db, { provider: "pg", schema: authSchema, transaction: true }),
    trustedOrigins: config.trustedOrigins,
    disabledPaths: ["/get-access-token", "/refresh-token", "/account-info", "/change-email", "/update-session", "/delete-user/callback", "/reset-password/:token"],

    emailAndPassword: {
      enabled: true,
      // Fail closed: without an email transport, new accounts could never verify their address.
      disableSignUp: config.email.mode === "disabled",
      requireEmailVerification: true,
      autoSignIn: false,
      minPasswordLength: PASSWORD_MIN,
      maxPasswordLength: PASSWORD_MAX,
      resetPasswordTokenExpiresIn: TOKEN_TTL,
      revokeSessionsOnPasswordReset: true,
      sendResetPassword: async ({ user, token }) => {
        await sendSafely(resetPasswordMail(user.email, greetingName(user), `${site}/reset-password?token=${encodeURIComponent(token)}`))
      },
      onPasswordReset: async ({ user }, request) => {
        await audit("password_reset", user.id, request?.headers)
      },
      onExistingUserSignUp: async ({ user }) => {
        await sendSafely(existingAccountMail(user.email, greetingName(user), `${site}/sign-in`, `${site}/forgot-password`))
      },
    },

    emailVerification: {
      sendOnSignUp: true,
      sendOnSignIn: true,
      autoSignInAfterVerification: false,
      expiresIn: TOKEN_TTL,
      sendVerificationEmail: async ({ user, token }) => {
        // Links to the page, not the API: the page verifies with a script, so link scanners that
        // prefetch URLs cannot use up the token.
        await sendSafely(verificationMail(user.email, greetingName(user), `${site}/verify-email?token=${encodeURIComponent(token)}`))
      },
      afterEmailVerification: async (user, request) => {
        await audit("email_verified", user.id, request?.headers)
      },
    },

    socialProviders,

    account: {
      // Tokens are dropped by the account hooks below; encryption is a second line of defence.
      encryptOAuthTokens: true,
      storeStateStrategy: "database",
      accountLinking: {
        enabled: true,
        // No provider is trusted blindly: linking needs a verified email at the provider and here.
        trustedProviders: [],
        allowDifferentEmails: false,
        allowUnlinkingAll: false,
        updateUserInfoOnLink: false,
      },
    },

    session: {
      expiresIn: SESSION_MAX_AGE,
      updateAge: SESSION_UPDATE_AGE,
      freshAge: FRESH_SESSION_AGE,
      cookieCache: { enabled: false },
    },

    verification: { storeIdentifier: "hashed" },

    user: {
      changeEmail: { enabled: false },
      deleteUser: {
        enabled: true,
        afterDelete: async (user, request) => {
          await db.execute(sql`delete from verification where value = ${user.id}`)
          await audit("account_deleted", user.id, request?.headers)
          await sendSafely(accountDeletedMail(user.email, greetingName(user)))
        },
      },
      validateUserInfo: ({ user, source }) => {
        if (source.method === "oauth" && user.emailVerified !== true) {
          return { error: "email_not_verified", errorDescription: "Verify your email address with the provider, then try again." }
        }
      },
    },

    rateLimit: {
      enabled: true,
      window: DEFAULT_RULE.window,
      max: DEFAULT_RULE.max,
      customRules: IP_RULES,
      // Better Auth's key holds the client IP; only a keyed hash of it is stored.
      customStorage: { consume: (key, rule) => consume(db, `ip|${hashIdentifier(secret, "ip", key)}`, rule) },
    },

    advanced: {
      useSecureCookies: config.secureCookies,
      // Explicit, so origin and CSRF checks also run when NODE_ENV=test (Better Auth skips them there by default).
      disableOriginCheck: false,
      disableCSRFCheck: false,
      cookiePrefix: "llmslim",
      defaultCookieAttributes: { httpOnly: true, sameSite: "lax", secure: config.secureCookies, path: "/" },
      ipAddress: { ipAddressHeaders: ["x-real-ip", "x-forwarded-for"], ipv6Subnet: 64 },
      backgroundTasks: { handler: background },
    },

    onAPIError: { errorURL: "/sign-in" },

    databaseHooks: {
      user: {
        create: {
          before: async (user) => ({ data: { ...user, name: cleanName(user.name, user.email), image: safeAvatar(user.image) } }),
          after: async (user, context) => {
            await audit("sign_up", user.id, context?.request?.headers ?? context?.headers, context?.path === "/sign-up/email" ? "password" : methodFromPath(context?.path, context?.params as Record<string, string> | undefined))
          },
        },
        update: {
          before: async (user) => {
            const data: Record<string, unknown> = { ...user }
            if ("image" in data) data.image = safeAvatar(data.image)
            if ("name" in data && data.name !== undefined) data.name = cleanName(data.name, undefined)
            return { data }
          },
        },
      },
      session: {
        create: {
          // Data minimisation: the session list shows device and time, so the IP is not kept.
          before: async (session) => ({ data: { ...session, ipAddress: null, userAgent: session.userAgent ? String(session.userAgent).slice(0, 512) : null } }),
          after: async (session, context) => {
            const method = methodFromPath(context?.path, context?.params as Record<string, string> | undefined)
            if (method) await audit("sign_in_success", session.userId, context?.request?.headers ?? context?.headers, method)
          },
        },
      },
      account: {
        create: {
          before: async (account) => ({ data: { ...account, accessToken: null, refreshToken: null, idToken: null, accessTokenExpiresAt: null, refreshTokenExpiresAt: null } }),
          after: async (account, context) => {
            if (account.providerId !== "credential") await audit("account_linked", account.userId, context?.request?.headers ?? context?.headers, account.providerId)
          },
        },
        update: {
          before: async (account) => {
            const data: Record<string, unknown> = { ...account }
            for (const field of ["accessToken", "refreshToken", "idToken", "accessTokenExpiresAt", "refreshTokenExpiresAt"]) if (field in data) data[field] = null
            return { data }
          },
        },
      },
    },

    hooks: {
      before: createAuthMiddleware(async (ctx) => {
        const path = ctx.path
        const body = (ctx.body ?? {}) as Record<string, unknown>
        const headers = ctx.request?.headers ?? ctx.headers

        if (housekeepingDue()) {
          background(pruneExpired(db).catch((error) => console.error("[accounts] could not prune expired rows:", error instanceof Error ? error.message : "unknown error")))
        }

        if (path === "/sign-up/email") {
          const nameError = validateName(typeof body.name === "string" ? body.name : "")
          if (nameError) throw badRequest("INVALID_NAME", nameError)
          const emailError = validateEmail(typeof body.email === "string" ? body.email : "")
          if (emailError) throw badRequest("INVALID_EMAIL", emailError)
          if (body.image !== undefined) throw badRequest("IMAGE_NOT_ALLOWED", "A profile image cannot be set here.")
        }
        if (path === "/update-user") {
          if (body.image !== undefined) throw badRequest("IMAGE_NOT_ALLOWED", "A profile image cannot be set here.")
          if (body.name !== undefined) {
            const nameError = validateName(typeof body.name === "string" ? body.name : "")
            if (nameError) throw badRequest("INVALID_NAME", nameError)
          }
        }
        if ((path === "/sign-in/social" || path === "/link-social") && (body.scopes !== undefined || body.idToken !== undefined)) {
          // Only the configured minimal scopes, and only the redirect flow.
          throw badRequest("UNSUPPORTED_OPTION", "This sign-in option is not supported.")
        }
        if ((path === "/passkey/verify-registration" || path === "/passkey/update-passkey") && body.name !== undefined) {
          const nameError = validatePasskeyName(typeof body.name === "string" ? body.name : "")
          if (nameError) throw badRequest("INVALID_PASSKEY_NAME", nameError)
        }

        if (isEmailLimitedPath(path) && typeof body.email === "string" && body.email.length <= 320) {
          const rule = EMAIL_RULES[path]
          const key = emailKey(body.email, path)
          // Sign-in counts failures only (in the after hook); the rest count every request.
          const decision = path === "/sign-in/email" ? await peek(db, key, rule) : await consume(db, key, rule)
          if (!decision.allowed) {
            await audit("rate_limited", null, headers, path)
            throw tooManyRequests(decision.retryAfter)
          }
        }

        if (path === "/verify-email") {
          const token = typeof ctx.query?.token === "string" ? ctx.query.token : ""
          if (token) {
            const used = await ctx.context.internalAdapter.findVerificationValue(`${USED_VERIFICATION_PREFIX}${await sha256Hex(token)}`)
            if (used) throw new APIError("BAD_REQUEST", { code: "TOKEN_ALREADY_USED", message: "This link has already been used." })
          }
        }
      }),

      after: createAuthMiddleware(async (ctx) => {
        const path = ctx.path
        const returned = ctx.context.returned
        const failed = isAPIError(returned)
        const headers = ctx.request?.headers ?? ctx.headers
        const body = (ctx.body ?? {}) as Record<string, unknown>

        if (path === "/sign-in/email" && failed) {
          if (returned.statusCode === 401 && typeof body.email === "string" && body.email.length <= 320) {
            await consume(db, emailKey(body.email, path), EMAIL_RULES[path])
          }
          if (returned.statusCode === 401) await audit("sign_in_failure", null, headers, "password")
          return
        }
        if (path === "/passkey/verify-authentication" && failed) {
          await audit("sign_in_failure", null, headers, "passkey")
          return
        }
        if (failed) return

        if (path === "/verify-email") {
          const token = typeof ctx.query?.token === "string" ? ctx.query.token : ""
          if (token) {
            await ctx.context.internalAdapter.createVerificationValue({
              identifier: `${USED_VERIFICATION_PREFIX}${await sha256Hex(token)}`,
              value: "used",
              expiresAt: new Date(Date.now() + 2 * TOKEN_TTL * 1000),
            })
          }
          return
        }

        const sessionEvents: Record<string, AuthEventType> = {
          "/passkey/verify-registration": "passkey_added",
          "/passkey/update-passkey": "passkey_renamed",
          "/passkey/delete-passkey": "passkey_removed",
          "/change-password": "password_changed",
          "/unlink-account": "account_unlinked",
          "/revoke-session": "session_revoked",
          "/revoke-other-sessions": "session_revoked",
          "/revoke-sessions": "session_revoked",
          "/sign-out": "sign_out",
        }
        const type = sessionEvents[path ?? ""]
        if (!type) return
        const response = returned as { user?: { id?: string; email?: string; name?: string; emailVerified?: boolean }; userId?: string } | undefined
        let userId = response?.user?.id ?? response?.userId ?? ctx.context.session?.user.id ?? null
        let user = response?.user ?? ctx.context.session?.user ?? null
        if (!userId && path !== "/sign-out") {
          const session = await getSessionFromCtx(ctx).catch(() => null)
          userId = session?.user.id ?? null
          user = session?.user ?? user
        }
        await audit(type, userId, headers)
        if (type === "password_changed" && user?.email) {
          background(sendSafely(passwordChangedMail(user.email, greetingName(user), `${site}/forgot-password`)))
        }
      }),
    },

    plugins: [
      passkeyPlugin,
      haveIBeenPwned({
        enabled: config.breachedPasswordCheck,
        paths: PASSWORD_PATHS,
        customPasswordCompromisedMessage: "This password appears in a known data breach. Choose a different one.",
      }),
      // Must be last: lets server actions set cookies and stops RSC renders from refreshing sessions.
      nextCookies(),
    ],
  })
}

export type Auth = ReturnType<typeof buildAuth>

type Instance = { auth: Auth; db: AnyPgDatabase }
const globalStore = globalThis as typeof globalThis & { __llmslimAccounts?: Instance }

/** The accounts instance, or null when this deployment is not configured for accounts. */
export function getAuthInstance(): Instance | null {
  const config = getAuthConfig()
  if (config.unavailable || !config.databaseUrl) return null
  if (!globalStore.__llmslimAccounts) {
    const { db } = createDatabase(config.databaseUrl)
    globalStore.__llmslimAccounts = { auth: buildAuth(config, db as unknown as AnyPgDatabase), db: db as unknown as AnyPgDatabase }
  }
  return globalStore.__llmslimAccounts
}

export function getAuth(): Auth | null {
  return getAuthInstance()?.auth ?? null
}
