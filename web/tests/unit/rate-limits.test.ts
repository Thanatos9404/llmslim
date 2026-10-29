import { afterAll, beforeAll, describe, expect, it } from "vitest"
import { consume, peek, prune } from "@/lib/auth/rate-limit-store"
import { DEFAULT_RULE, EMAIL_RULES, IP_RULES, isEmailLimitedPath, rateLimitMessage } from "@/lib/auth/rate-limits"
import { testDatabase } from "./helpers"

describe("rate-limit configuration", () => {
  it("limits every sensitive endpoint per IP, more strictly than the default", () => {
    const sensitive = ["/sign-in/email", "/sign-up/email", "/request-password-reset", "/send-verification-email", "/reset-password", "/verify-email", "/change-password", "/delete-user", "/passkey/generate-authenticate-options", "/passkey/verify-authentication", "/passkey/generate-register-options", "/passkey/verify-registration"] as const
    for (const path of sensitive) {
      const rule = IP_RULES[path]
      expect(rule, path).toBeDefined()
      expect(rule.max / rule.window, path).toBeLessThan(DEFAULT_RULE.max / DEFAULT_RULE.window)
    }
  })

  it("limits sign-in, sign-up, forgot-password and resend per email", () => {
    expect(EMAIL_RULES["/sign-in/email"]).toEqual({ window: 900, max: 5 })
    expect(EMAIL_RULES["/sign-up/email"].max).toBeLessThanOrEqual(3)
    expect(EMAIL_RULES["/request-password-reset"].max).toBeLessThanOrEqual(3)
    expect(EMAIL_RULES["/send-verification-email"].max).toBeLessThanOrEqual(3)
    for (const path of Object.keys(EMAIL_RULES)) expect(IP_RULES, path).toHaveProperty(path)
    expect(isEmailLimitedPath("/sign-in/email")).toBe(true)
    expect(isEmailLimitedPath("/get-session")).toBe(false)
    expect(isEmailLimitedPath(undefined)).toBe(false)
  })

  it("words the wait in whole minutes", () => {
    expect(rateLimitMessage(30)).toBe("Too many attempts. Try again in 1 minute.")
    expect(rateLimitMessage(61)).toBe("Too many attempts. Try again in 2 minutes.")
    expect(rateLimitMessage(900)).toBe("Too many attempts. Try again in 15 minutes.")
    expect(rateLimitMessage(null)).toBe("Too many attempts. Try again in 1 minute.")
    expect(rateLimitMessage(Number.NaN)).toBe("Too many attempts. Try again in 1 minute.")
  })
})

describe("Postgres-backed counters", () => {
  let database: Awaited<ReturnType<typeof testDatabase>>
  beforeAll(async () => {
    database = await testDatabase()
  })
  afterAll(async () => {
    await database.client.close()
  })

  it("allows max requests per window, then refuses with the seconds left", async () => {
    const rule = { window: 60, max: 3 }
    const now = 1_000_000
    for (let index = 0; index < 3; index++) expect((await consume(database.db, "k1", rule, now + index)).allowed).toBe(true)
    const refused = await consume(database.db, "k1", rule, now + 10_000)
    expect(refused).toEqual({ allowed: false, retryAfter: 50 })
    // A new window starts once the old one has passed.
    expect((await consume(database.db, "k1", rule, now + 60_000)).allowed).toBe(true)
  })

  it("is atomic under concurrent requests", async () => {
    const rule = { window: 60, max: 5 }
    const results = await Promise.all(Array.from({ length: 20 }, () => consume(database.db, "k-concurrent", rule, 2_000_000)))
    expect(results.filter((result) => result.allowed)).toHaveLength(5)
  })

  it("peeks without counting", async () => {
    const rule = { window: 60, max: 2 }
    expect((await peek(database.db, "k-peek", rule, 3_000_000)).allowed).toBe(true)
    await consume(database.db, "k-peek", rule, 3_000_000)
    expect((await peek(database.db, "k-peek", rule, 3_000_001)).allowed).toBe(true)
    await consume(database.db, "k-peek", rule, 3_000_002)
    expect(await peek(database.db, "k-peek", rule, 3_000_003)).toEqual({ allowed: false, retryAfter: 60 })
  })

  it("prunes counters whose window ended over an hour ago", async () => {
    await consume(database.db, "k-old", { window: 60, max: 1 }, 1)
    await prune(database.db, 10_000_000)
    const rows = await database.client.query<{ key: string }>("select key from rate_limit where key = 'k-old'")
    expect(rows.rows).toHaveLength(0)
  })
})
