/**
 * Accounts configuration, resolved from environment variables only.
 *
 * Pure and synchronous so it can be unit tested: no I/O, no secrets logged, no defaults that would
 * weaken security in production. Every optional feature fails closed: a provider without both of its
 * variables is hidden, and email/password sign-up is disabled when no email transport is configured.
 */

export type Env = Readonly<Record<string, string | undefined>>

export type EmailTransport =
  | { mode: "resend"; apiKey: string; from: string }
  | { mode: "log" }
  | { mode: "file"; dir: string }
  | { mode: "disabled" }

export type OAuthClient = { clientId: string; clientSecret: string }

export type UnavailableReason = "database_not_configured" | "secret_not_configured" | "secret_too_short" | "base_url_invalid"

export interface AuthConfig {
  /** A deployed build (NODE_ENV=production): local `next start`, Vercel preview or Vercel production. */
  production: boolean
  /** Running on Vercel (the `VERCEL` system variable). Development-only mail transports never run there. */
  onVercel: boolean
  vercelEnv: "production" | "preview" | "development" | null
  baseURL: string
  secret: string | null
  databaseUrl: string | null
  trustedOrigins: string[]
  secureCookies: boolean
  passkey: { rpID: string; rpName: string; origins: string[] }
  google: OAuthClient | null
  github: OAuthClient | null
  email: EmailTransport
  /** Have I Been Pwned range check on new passwords. Only switchable off outside Vercel (offline tests). */
  breachedPasswordCheck: boolean
  /** Why the accounts API cannot run, or null when it can. */
  unavailable: UnavailableReason | null
}

/** Canonical production origins. Both work: www is canonical, the apex redirects or serves the same app. */
export const PRODUCTION_ORIGINS = ["https://www.llmslim.app", "https://llmslim.app"] as const
export const PRODUCTION_RP_ID = "llmslim.app"
export const MIN_SECRET_LENGTH = 32
/** Development and test only. Never used when NODE_ENV=production. */
export const DEV_SECRET = "llmslim-development-secret-never-use-in-production"

function value(env: Env, key: string): string | null {
  const raw = env[key]
  if (typeof raw !== "string") return null
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : null
}

function originOf(url: string): string | null {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null
    return parsed.origin
  } catch {
    return null
  }
}

function hostUrl(host: string | null): string | null {
  if (!host) return null
  return originOf(`https://${host.replace(/^https?:\/\//, "").replace(/\/+$/, "")}`)
}

/** True when `hostname` equals `rpID` or is a subdomain of it, the WebAuthn rule for a valid RP ID. */
export function hostMatchesRpId(hostname: string, rpID: string): boolean {
  const host = hostname.toLowerCase()
  const rp = rpID.toLowerCase()
  return host === rp || host.endsWith(`.${rp}`)
}

function resolveBaseURL(env: Env, vercelEnv: AuthConfig["vercelEnv"]): string | null {
  const explicit = value(env, "BETTER_AUTH_URL")
  if (explicit) return originOf(explicit)
  if (vercelEnv === "preview") return hostUrl(value(env, "VERCEL_BRANCH_URL") ?? value(env, "VERCEL_URL"))
  if (vercelEnv === "production") return hostUrl(value(env, "VERCEL_PROJECT_PRODUCTION_URL")) ?? PRODUCTION_ORIGINS[0]
  const port = value(env, "PORT") ?? "3000"
  return `http://localhost:${/^\d{1,5}$/.test(port) ? port : "3000"}`
}

function resolveEmail(env: Env, production: boolean, onVercel: boolean): EmailTransport {
  const apiKey = value(env, "RESEND_API_KEY")
  const from = value(env, "AUTH_EMAIL_FROM")
  if (apiKey && from) return { mode: "resend", apiKey, from }
  // Development transports: an explicit opt-in, and never on Vercel, where logs are shared.
  const dev = value(env, "AUTH_DEV_MAIL")
  if (!onVercel && dev === "file") return { mode: "file", dir: value(env, "AUTH_DEV_MAIL_DIR") ?? ".auth-mail" }
  if (!onVercel && dev === "log") return { mode: "log" }
  if (!production && !onVercel) return { mode: "log" }
  return { mode: "disabled" }
}

function oauth(env: Env, prefix: "GOOGLE" | "GITHUB"): OAuthClient | null {
  const clientId = value(env, `${prefix}_CLIENT_ID`)
  const clientSecret = value(env, `${prefix}_CLIENT_SECRET`)
  return clientId && clientSecret ? { clientId, clientSecret } : null
}

export function resolveAuthConfig(env: Env): AuthConfig {
  const production = env.NODE_ENV === "production"
  const onVercel = Boolean(value(env, "VERCEL"))
  const rawVercelEnv = value(env, "VERCEL_ENV")
  const vercelEnv = rawVercelEnv === "production" || rawVercelEnv === "preview" || rawVercelEnv === "development" ? rawVercelEnv : null

  const resolvedBase = resolveBaseURL(env, vercelEnv)
  const baseURL = resolvedBase ?? PRODUCTION_ORIGINS[0]
  const baseHost = new URL(baseURL).hostname
  const isProductionSite = vercelEnv === "production" || hostMatchesRpId(baseHost, PRODUCTION_RP_ID)

  const origins = new Set<string>([new URL(baseURL).origin])
  if (isProductionSite) for (const origin of PRODUCTION_ORIGINS) origins.add(origin)
  if (vercelEnv === "preview") {
    // The exact hosts of this preview deployment, not a *.vercel.app wildcard: another team's
    // project can be given a name that matches any "<project>-*-<scope>.vercel.app" pattern.
    for (const host of [value(env, "VERCEL_URL"), value(env, "VERCEL_BRANCH_URL")]) {
      const origin = hostUrl(host)
      if (origin) origins.add(origin)
    }
  }
  const trustedOrigins = [...origins].filter((origin) => !production || !onVercel || origin.startsWith("https://"))

  const rpID = (value(env, "PASSKEY_RP_ID") ?? (isProductionSite ? PRODUCTION_RP_ID : baseHost)).toLowerCase()
  const passkeyOrigins = trustedOrigins.filter((origin) => hostMatchesRpId(new URL(origin).hostname, rpID))

  let secret = value(env, "BETTER_AUTH_SECRET")
  if (!secret && !production) secret = DEV_SECRET

  let unavailable: UnavailableReason | null = null
  const databaseUrl = value(env, "DATABASE_URL")
  if (!resolvedBase) unavailable = "base_url_invalid"
  else if (!databaseUrl) unavailable = "database_not_configured"
  else if (!secret) unavailable = "secret_not_configured"
  else if (production && secret.length < MIN_SECRET_LENGTH) unavailable = "secret_too_short"

  return {
    production,
    onVercel,
    vercelEnv,
    baseURL,
    secret,
    databaseUrl,
    trustedOrigins,
    secureCookies: baseURL.startsWith("https://"),
    passkey: { rpID, rpName: value(env, "PASSKEY_RP_NAME") ?? "LLMSlim", origins: passkeyOrigins },
    google: oauth(env, "GOOGLE"),
    github: oauth(env, "GITHUB"),
    email: resolveEmail(env, production, onVercel),
    breachedPasswordCheck: onVercel || value(env, "AUTH_BREACHED_PASSWORD_CHECK") !== "off",
    unavailable,
  }
}

/** What the sign-in and sign-up pages may offer. Safe to send to the browser: no secrets. */
export interface PublicAuthFeatures {
  available: boolean
  unavailableReason: UnavailableReason | null
  google: boolean
  github: boolean
  passkey: boolean
  emailPassword: boolean
  /** New email/password accounts need a working email transport for verification. */
  emailSignUp: boolean
  passwordReset: boolean
}

export function publicFeatures(config: AuthConfig): PublicAuthFeatures {
  const available = config.unavailable === null
  const canEmail = config.email.mode !== "disabled"
  return {
    available,
    unavailableReason: config.unavailable,
    google: available && config.google !== null,
    github: available && config.github !== null,
    passkey: available && config.passkey.origins.length > 0,
    emailPassword: available,
    emailSignUp: available && canEmail,
    passwordReset: available && canEmail,
  }
}

let cached: AuthConfig | null = null

/** The configuration for this process. Environment variables do not change at runtime. */
export function getAuthConfig(): AuthConfig {
  cached ??= resolveAuthConfig(process.env)
  return cached
}
