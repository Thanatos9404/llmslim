import { describe, expect, it } from "vitest"
import { DEV_SECRET, publicFeatures, resolveAuthConfig } from "@/lib/auth/config"

const SECRET = "x".repeat(48)
const production = { NODE_ENV: "production", VERCEL: "1", VERCEL_ENV: "production", BETTER_AUTH_URL: "https://www.llmslim.app", BETTER_AUTH_SECRET: SECRET, DATABASE_URL: "postgres://u:p@db.example.com/neondb" }

describe("provider visibility", () => {
  it("hides Google and GitHub when their variables are missing", () => {
    const features = publicFeatures(resolveAuthConfig(production))
    expect(features.google).toBe(false)
    expect(features.github).toBe(false)
  })

  it("hides a provider configured with only one of its two variables", () => {
    const config = resolveAuthConfig({ ...production, GOOGLE_CLIENT_ID: "id", GITHUB_CLIENT_SECRET: "secret" })
    expect(config.google).toBeNull()
    expect(config.github).toBeNull()
  })

  it("shows a provider when both variables are set, and treats blank values as missing", () => {
    const features = publicFeatures(resolveAuthConfig({ ...production, GOOGLE_CLIENT_ID: "id", GOOGLE_CLIENT_SECRET: "secret", GITHUB_CLIENT_ID: "  ", GITHUB_CLIENT_SECRET: "secret" }))
    expect(features.google).toBe(true)
    expect(features.github).toBe(false)
  })

  it("hides every provider when accounts are unavailable", () => {
    const features = publicFeatures(resolveAuthConfig({ ...production, DATABASE_URL: undefined, GOOGLE_CLIENT_ID: "id", GOOGLE_CLIENT_SECRET: "secret" }))
    expect(features).toMatchObject({ available: false, google: false, github: false, passkey: false, emailSignUp: false })
  })
})

describe("fail closed", () => {
  it("reports a missing database first", () => {
    expect(resolveAuthConfig({ ...production, DATABASE_URL: "" }).unavailable).toBe("database_not_configured")
  })

  it("refuses to run in production without a secret, or with a short one", () => {
    expect(resolveAuthConfig({ ...production, BETTER_AUTH_SECRET: undefined }).unavailable).toBe("secret_not_configured")
    expect(resolveAuthConfig({ ...production, BETTER_AUTH_SECRET: "short" }).unavailable).toBe("secret_too_short")
  })

  it("uses a development secret only outside production", () => {
    const config = resolveAuthConfig({ NODE_ENV: "development", DATABASE_URL: "postgres://localhost/dev" })
    expect(config.secret).toBe(DEV_SECRET)
    expect(config.unavailable).toBeNull()
  })

  it("disables email/password sign-up and reset in production without an email provider", () => {
    const config = resolveAuthConfig(production)
    expect(config.email.mode).toBe("disabled")
    const features = publicFeatures(config)
    expect(features.emailSignUp).toBe(false)
    expect(features.passwordReset).toBe(false)
    // Existing accounts can still sign in with their password.
    expect(features.emailPassword).toBe(true)
  })

  it("never uses the log or file mail transports on Vercel, even when asked", () => {
    expect(resolveAuthConfig({ ...production, AUTH_DEV_MAIL: "file" }).email.mode).toBe("disabled")
    expect(resolveAuthConfig({ ...production, VERCEL_ENV: "preview", AUTH_DEV_MAIL: "log" }).email.mode).toBe("disabled")
  })

  it("logs links in development and uses Resend only when both of its variables are set", () => {
    expect(resolveAuthConfig({ NODE_ENV: "development", DATABASE_URL: "postgres://localhost/dev" }).email.mode).toBe("log")
    expect(resolveAuthConfig({ ...production, RESEND_API_KEY: "re_test" }).email.mode).toBe("disabled")
    expect(resolveAuthConfig({ ...production, RESEND_API_KEY: "re_test", AUTH_EMAIL_FROM: "LLMSlim <accounts@llmslim.app>" }).email).toEqual({ mode: "resend", apiKey: "re_test", from: "LLMSlim <accounts@llmslim.app>" })
  })

  it("keeps the breached-password check on whenever the app runs on Vercel", () => {
    expect(resolveAuthConfig({ ...production, AUTH_BREACHED_PASSWORD_CHECK: "off" }).breachedPasswordCheck).toBe(true)
    expect(resolveAuthConfig({ NODE_ENV: "test", AUTH_BREACHED_PASSWORD_CHECK: "off" }).breachedPasswordCheck).toBe(false)
  })
})

describe("origins, cookies and passkeys", () => {
  it("trusts www and the apex in production, with secure cookies and the apex as RP ID", () => {
    const config = resolveAuthConfig(production)
    expect(config.trustedOrigins).toEqual(["https://www.llmslim.app", "https://llmslim.app"])
    expect(config.secureCookies).toBe(true)
    expect(config.passkey.rpID).toBe("llmslim.app")
    expect(config.passkey.origins).toEqual(["https://www.llmslim.app", "https://llmslim.app"])
  })

  it("trusts only this preview deployment's own hosts, never a wildcard", () => {
    const config = resolveAuthConfig({ NODE_ENV: "production", VERCEL: "1", VERCEL_ENV: "preview", VERCEL_URL: "llmslim-abc123-team.vercel.app", VERCEL_BRANCH_URL: "llmslim-git-feature-team.vercel.app", BETTER_AUTH_SECRET: SECRET, DATABASE_URL: "postgres://u:p@db.example.com/x" })
    expect(config.baseURL).toBe("https://llmslim-git-feature-team.vercel.app")
    expect([...config.trustedOrigins].sort()).toEqual(["https://llmslim-abc123-team.vercel.app", "https://llmslim-git-feature-team.vercel.app"])
    expect(config.trustedOrigins.some((origin) => origin.includes("*"))).toBe(false)
    expect(config.passkey.rpID).toBe("llmslim-git-feature-team.vercel.app")
    expect(config.passkey.origins).toEqual(["https://llmslim-git-feature-team.vercel.app"])
  })

  it("uses localhost, plain cookies and RP ID localhost for local development", () => {
    const config = resolveAuthConfig({ NODE_ENV: "development", DATABASE_URL: "postgres://localhost/dev" })
    expect(config.baseURL).toBe("http://localhost:3000")
    expect(config.trustedOrigins).toEqual(["http://localhost:3000"])
    expect(config.secureCookies).toBe(false)
    expect(config.passkey.rpID).toBe("localhost")
  })

  it("honours an explicit RP ID and drops origins it cannot cover", () => {
    const config = resolveAuthConfig({ ...production, PASSKEY_RP_ID: "www.llmslim.app" })
    expect(config.passkey.rpID).toBe("www.llmslim.app")
    expect(config.passkey.origins).toEqual(["https://www.llmslim.app"])
  })

  it("rejects an unusable BETTER_AUTH_URL", () => {
    expect(resolveAuthConfig({ ...production, BETTER_AUTH_URL: "javascript:alert(1)" }).unavailable).toBe("base_url_invalid")
  })
})
