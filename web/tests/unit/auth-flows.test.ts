/**
 * The real Better Auth configuration (buildAuth) against an in-process PGlite database: the
 * security properties that matter most, exercised through the HTTP handler.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { SESSION_MAX_AGE, safeAvatar } from "@/lib/auth/server"
import { ORIGIN, testAuth, tokenFrom } from "./helpers"

const PASSWORD = "correct horse battery staple"

async function verifiedUser(t: Awaited<ReturnType<typeof testAuth>>, email = "ada@example.com") {
  await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email, password: PASSWORD } })
  const mail = t.mails.filter((m) => m.kind === "verify-email" && m.to === email).pop()
  await t.call("/verify-email", { query: { token: tokenFrom(mail) } })
  const signIn = await t.call("/sign-in/email", { body: { email, password: PASSWORD } })
  expect(signIn.status).toBe(200)
  return { cookie: signIn.cookie!, userId: (signIn.json?.user as { id: string }).id }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("sign-up and verification", () => {
  it("requires a verified email before a password sign-in creates a session", async () => {
    const t = await testAuth()
    const up = await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "Ada@Example.com", password: PASSWORD } })
    expect(up.status).toBe(200)
    expect(up.cookie).toBeUndefined()
    const blocked = await t.call("/sign-in/email", { body: { email: "ada@example.com", password: PASSWORD } })
    expect(blocked.status).toBe(403)
    expect(blocked.json?.code).toBe("EMAIL_NOT_VERIFIED")
    expect(blocked.cookie).toBeUndefined()
  })

  it("links to the page (not the API), and the token works exactly once", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    const mail = t.mails.find((m) => m.kind === "verify-email")
    expect(mail?.url).toMatch(new RegExp(`^${ORIGIN}/verify-email\\?token=`))
    const first = await t.call("/verify-email", { query: { token: tokenFrom(mail) } })
    expect(first.status).toBe(200)
    expect(first.cookie).toBeUndefined()
    const second = await t.call("/verify-email", { query: { token: tokenFrom(mail) } })
    expect(second.status).toBe(400)
    expect(second.json?.code).toBe("TOKEN_ALREADY_USED")
  })

  it("rejects an expired verification token", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    vi.useFakeTimers({ now: Date.now() + 61 * 60 * 1000, toFake: ["Date"] })
    try {
      const late = await t.call("/verify-email", { query: { token: tokenFrom(t.mails.find((m) => m.kind === "verify-email")) } })
      expect(late.status).toBe(401)
      expect(late.json?.code).toBe("TOKEN_EXPIRED")
    } finally {
      vi.useRealTimers()
    }
  })

  it("validates the name and refuses an image URL or extra OAuth scopes", async () => {
    const t = await testAuth()
    expect((await t.call("/sign-up/email", { body: { name: "<script>", email: "x@example.com", password: PASSWORD } })).json?.code).toBe("INVALID_NAME")
    expect((await t.call("/sign-up/email", { body: { name: "Ada", email: "x@example.com", password: PASSWORD, image: "https://evil.example/x.png" } })).json?.code).toBe("IMAGE_NOT_ALLOWED")
    expect((await t.call("/sign-up/email", { body: { name: "Ada", email: "x@example.com", password: "short" } })).json?.code).toBe("PASSWORD_TOO_SHORT")
    expect((await t.call("/sign-up/email", { body: { name: "Ada", email: "x@example.com", password: "a".repeat(129) } })).json?.code).toBe("PASSWORD_TOO_LONG")
  })

  it("stores passwords as scrypt hashes, never in plain text", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    const rows = await t.client.query<{ password: string }>("select password from account where provider_id = 'credential'")
    expect(rows.rows[0].password).not.toContain(PASSWORD)
    expect(rows.rows[0].password).toMatch(/^[0-9a-f]{32}:[0-9a-f]{128}$/)
  })
})

describe("no account enumeration", () => {
  it("signs up an existing email with the same response shape, and tells the owner by email", async () => {
    const t = await testAuth()
    const fresh = await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    const again = await t.call("/sign-up/email", { body: { name: "Mallory", email: "ada@example.com", password: "another long password" } })
    expect(again.status).toBe(fresh.status)
    expect(Object.keys(again.json ?? {}).sort()).toEqual(Object.keys(fresh.json ?? {}).sort())
    expect(Object.keys((again.json?.user as object) ?? {}).sort()).toEqual(Object.keys((fresh.json?.user as object) ?? {}).sort())
    expect(t.mails.filter((m) => m.kind === "existing-account")).toHaveLength(1)
  })

  it("gives the same error for a wrong password and an unknown email", async () => {
    const t = await testAuth()
    await verifiedUser(t)
    const wrong = await t.call("/sign-in/email", { ip: "203.0.113.50", body: { email: "ada@example.com", password: "not the password" } })
    const unknown = await t.call("/sign-in/email", { ip: "203.0.113.51", body: { email: "nobody@example.com", password: "not the password" } })
    expect(wrong.status).toBe(401)
    expect(unknown.status).toBe(401)
    expect(wrong.json).toEqual(unknown.json)
  })

  it("answers forgot-password identically for known and unknown emails", async () => {
    const t = await testAuth()
    await verifiedUser(t)
    const known = await t.call("/request-password-reset", { body: { email: "ada@example.com", redirectTo: "/reset-password" } })
    const unknown = await t.call("/request-password-reset", { body: { email: "nobody@example.com", redirectTo: "/reset-password" } })
    expect(known.status).toBe(200)
    expect(known.json).toEqual(unknown.json)
    expect(t.mails.filter((m) => m.kind === "reset-password")).toHaveLength(1)
  })
})

describe("password reset", () => {
  it("uses a single-use token and revokes every session", async () => {
    const t = await testAuth()
    const { cookie } = await verifiedUser(t)
    await t.call("/request-password-reset", { body: { email: "ada@example.com", redirectTo: "/reset-password" } })
    const mail = t.mails.find((m) => m.kind === "reset-password")
    expect(mail?.url).toMatch(new RegExp(`^${ORIGIN}/reset-password\\?token=[A-Za-z0-9]+$`))
    const token = tokenFrom(mail)
    // Stored hashed: the raw token is nowhere in the database.
    const stored = await t.client.query<{ identifier: string }>("select identifier from verification")
    expect(stored.rows.some((row) => row.identifier.includes(token))).toBe(false)

    const reset = await t.call("/reset-password", { body: { token, newPassword: "a brand new passphrase" } })
    expect(reset.status).toBe(200)
    expect((await t.call("/get-session", { cookie })).json).toBeNull()
    const reuse = await t.call("/reset-password", { body: { token, newPassword: "yet another passphrase" } })
    expect(reuse.json?.code).toBe("INVALID_TOKEN")
    expect((await t.call("/sign-in/email", { body: { email: "ada@example.com", password: "a brand new passphrase" } })).status).toBe(200)
  })

  it("expires reset tokens after one hour", async () => {
    const t = await testAuth()
    await verifiedUser(t)
    await t.call("/request-password-reset", { body: { email: "ada@example.com", redirectTo: "/reset-password" } })
    const token = tokenFrom(t.mails.find((m) => m.kind === "reset-password"))
    const expiry = await t.client.query<{ seconds: number }>("select extract(epoch from (expires_at - now()))::int as seconds from verification order by created_at desc limit 1")
    expect(expiry.rows[0].seconds).toBeGreaterThan(3500)
    expect(expiry.rows[0].seconds).toBeLessThanOrEqual(3600)
    await t.client.query("update verification set expires_at = now() - interval '1 second'")
    expect((await t.call("/reset-password", { body: { token, newPassword: "a brand new passphrase" } })).json?.code).toBe("INVALID_TOKEN")
  })
})

describe("rate limiting", () => {
  it("blocks an email after five failed sign-ins, from any IP, with a Retry-After", async () => {
    const t = await testAuth()
    for (let attempt = 0; attempt < 5; attempt++) {
      expect((await t.call("/sign-in/email", { ip: t.nextIp(), body: { email: "victim@example.com", password: `guess-number-${attempt}` } })).status).toBe(401)
    }
    const blocked = await t.call("/sign-in/email", { ip: t.nextIp(), body: { email: "Victim@Example.com", password: "guess-number-6" } })
    expect(blocked.status).toBe(429)
    expect(blocked.json?.message).toBe("Too many attempts. Try again in 15 minutes.")
    expect(Number(blocked.response.headers.get("X-Retry-After"))).toBeGreaterThan(800)
    // The key is an HMAC: the table never holds the address.
    const keys = await t.client.query<{ key: string }>("select key from rate_limit")
    expect(keys.rows.some((row) => row.key.includes("victim"))).toBe(false)
  })

  it("limits each IP on sign-in and on passkey endpoints", async () => {
    const t = await testAuth()
    let last = 0
    for (let attempt = 0; attempt < 21; attempt++) {
      last = (await t.call("/sign-in/email", { ip: "203.0.113.99", body: { email: `user${attempt}@example.com`, password: "not the password" } })).status
    }
    expect(last).toBe(429)
    let passkeyStatus = 0
    for (let attempt = 0; attempt < 61; attempt++) passkeyStatus = (await t.call("/passkey/generate-authenticate-options", { ip: "203.0.113.98" })).status
    expect(passkeyStatus).toBe(429)
  })

  it("limits forgot-password per email", async () => {
    const t = await testAuth()
    const statuses: number[] = []
    for (let attempt = 0; attempt < 4; attempt++) statuses.push((await t.call("/request-password-reset", { ip: t.nextIp(), body: { email: "someone@example.com" } })).status)
    expect(statuses).toEqual([200, 200, 200, 429])
  })
})

describe("sessions, cookies and data minimisation", () => {
  it("issues an httpOnly SameSite=Lax cookie with a 7-day lifetime and no token in JSON from the route", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    await t.call("/verify-email", { query: { token: tokenFrom(t.mails.find((m) => m.kind === "verify-email")) } })
    const signIn = await t.call("/sign-in/email", { body: { email: "ada@example.com", password: PASSWORD } })
    const header = signIn.response.headers.getSetCookie().find((cookie) => cookie.includes("session_token="))!
    expect(header).toMatch(/^llmslim\.session_token=/)
    expect(header).toMatch(/HttpOnly/)
    expect(header).toMatch(/SameSite=Lax/)
    expect(header).toContain(`Max-Age=${SESSION_MAX_AGE}`)
  })

  it("uses the __Secure- prefix and Secure attribute over HTTPS", async () => {
    const t = await testAuth({ BETTER_AUTH_URL: "https://www.llmslim.app" })
    await t.call("/sign-up/email", { origin: "https://www.llmslim.app", body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    await t.call("/verify-email", { origin: "https://www.llmslim.app", query: { token: tokenFrom(t.mails.find((m) => m.kind === "verify-email")) } })
    const signIn = await t.call("/sign-in/email", { origin: "https://www.llmslim.app", body: { email: "ada@example.com", password: PASSWORD } })
    const header = signIn.response.headers.getSetCookie().find((cookie) => cookie.includes("session_token="))!
    expect(header).toMatch(/^__Secure-llmslim\.session_token=/)
    expect(header).toMatch(/; Secure/)
  })

  it("keeps no IP address on sessions, and audit rows hold only an IP hash", async () => {
    const t = await testAuth()
    await verifiedUser(t)
    const sessions = await t.client.query<{ ip_address: string | null; user_agent: string }>("select ip_address, user_agent from session")
    expect(sessions.rows[0].ip_address).toBeNull()
    expect(sessions.rows[0].user_agent).toContain("Chrome")
    const events = await t.client.query<Record<string, string | null>>("select * from auth_event order by created_at")
    expect(events.rows.map((row) => row.type)).toEqual(expect.arrayContaining(["sign_up", "email_verified", "sign_in_success"]))
    const dump = JSON.stringify(events.rows)
    expect(dump).not.toContain("203.0.113.1")
    expect(dump).not.toContain("ada@example.com")
    expect(dump).not.toContain(PASSWORD)
    expect(events.rows[0].ip_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it("drops OAuth access, refresh and ID tokens before they are stored", async () => {
    const t = await testAuth()
    const { userId } = await verifiedUser(t)
    const context = await t.auth.$context
    await context.internalAdapter.linkAccount({ userId, providerId: "github", accountId: "12345", accessToken: "gho_secret", refreshToken: "ghr_secret", idToken: "id.token.value" })
    const rows = await t.client.query<Record<string, string | null>>("select access_token, refresh_token, id_token from account where provider_id = 'github'")
    expect(rows.rows[0]).toEqual({ access_token: null, refresh_token: null, id_token: null })
  })

  it("keeps only Google and GitHub avatar URLs", () => {
    expect(safeAvatar("https://lh3.googleusercontent.com/a/abc")).toBe("https://lh3.googleusercontent.com/a/abc")
    expect(safeAvatar("https://avatars.githubusercontent.com/u/1?v=4")).toBe("https://avatars.githubusercontent.com/u/1?v=4")
    expect(safeAvatar("http://avatars.githubusercontent.com/u/1")).toBeNull()
    expect(safeAvatar("https://evil.example/x.png")).toBeNull()
    expect(safeAvatar("javascript:alert(1)")).toBeNull()
  })
})

describe("account deletion", () => {
  it("removes the user with their sessions, accounts and passkeys", async () => {
    const t = await testAuth()
    const { cookie, userId } = await verifiedUser(t)
    await t.client.query("insert into passkey (id, name, public_key, user_id, credential_id, counter, device_type, backed_up) values ('pk1', 'Laptop', 'pub', $1, 'cred1', 0, 'singleDevice', false)", [userId])
    const wrong = await t.call("/delete-user", { cookie, body: { password: "not the password" } })
    expect(wrong.status).toBe(400)
    const deleted = await t.call("/delete-user", { cookie, body: { password: PASSWORD } })
    expect(deleted.status).toBe(200)
    for (const table of ["\"user\"", "session", "account", "passkey"]) {
      const rows = await t.client.query<{ count: number }>(`select count(*)::int as count from ${table}`)
      expect(rows.rows[0].count, table).toBe(0)
    }
    const events = await t.client.query<{ type: string }>("select type from auth_event")
    expect(events.rows.map((row) => row.type)).toContain("account_deleted")
    expect(t.mails.some((m) => m.kind === "account-deleted")).toBe(true)
  })
})

describe("OAuth", () => {
  it("starts Google and GitHub with our callback URL, state and minimal scopes", async () => {
    const t = await testAuth({ GOOGLE_CLIENT_ID: "g-id", GOOGLE_CLIENT_SECRET: "g-secret", GITHUB_CLIENT_ID: "gh-id", GITHUB_CLIENT_SECRET: "gh-secret" })
    const google = new URL((await t.call("/sign-in/social", { body: { provider: "google", callbackURL: "/account", disableRedirect: true } })).json?.url as string)
    expect(google.hostname).toBe("accounts.google.com")
    expect(google.searchParams.get("redirect_uri")).toBe(`${ORIGIN}/api/auth/callback/google`)
    expect(google.searchParams.get("state")).toBeTruthy()
    expect(google.searchParams.get("scope")?.split(" ").sort()).toEqual(["email", "openid", "profile"])
    const github = new URL((await t.call("/sign-in/social", { body: { provider: "github", callbackURL: "/account", disableRedirect: true } })).json?.url as string)
    expect(`${github.origin}${github.pathname}`).toBe("https://github.com/login/oauth/authorize")
    expect(github.searchParams.get("redirect_uri")).toBe(`${ORIGIN}/api/auth/callback/github`)
    expect(github.searchParams.get("scope")).toBe("user:email")
  })

  it("refuses an off-site callback URL", async () => {
    const t = await testAuth({ GOOGLE_CLIENT_ID: "g-id", GOOGLE_CLIENT_SECRET: "g-secret" })
    const response = await t.call("/sign-in/social", { body: { provider: "google", callbackURL: "https://evil.example/", disableRedirect: true } })
    expect(response.status).toBe(403)
  })

  it("uses GitHub's primary email and its verified flag, and rejects unverified provider emails", async () => {
    const t = await testAuth({ GITHUB_CLIENT_ID: "gh-id", GITHUB_CLIENT_SECRET: "gh-secret" })
    const context = await t.auth.$context
    const github = context.socialProviders.find((provider) => provider.id === "github")!
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/user")) return Response.json({ id: 42, login: "ada", name: "Ada", email: "public@example.com", avatar_url: "https://avatars.githubusercontent.com/u/42" })
      return Response.json([{ email: "public@example.com", primary: false, verified: true }, { email: "Primary@Example.com", primary: true, verified: false }])
    }))
    const info = await github.getUserInfo({ accessToken: "token" } as never)
    expect(info?.user).toMatchObject({ email: "primary@example.com", emailVerified: false })
    const validate = (await t.auth.options).user?.validateUserInfo
    expect(await validate?.({ user: { email: "primary@example.com", emailVerified: false }, source: { action: "create-user", method: "oauth", oauth: { providerId: "github" } } } as never)).toMatchObject({ error: "email_not_verified" })
    expect(await validate?.({ user: { email: "primary@example.com", emailVerified: true }, source: { action: "link-account", method: "oauth", oauth: { providerId: "github" } } } as never)).toBeUndefined()
  })
})

describe("breached passwords", () => {
  it("rejects a password found by the Have I Been Pwned range API, sending only a 5-character prefix", async () => {
    const t = await testAuth({ AUTH_BREACHED_PASSWORD_CHECK: "on" })
    const { createHash } = await import("node:crypto")
    const sha1 = createHash("sha1").update(PASSWORD).digest("hex").toUpperCase()
    const requested: string[] = []
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      requested.push(String(input))
      return new Response(`${sha1.slice(5)}:3861493\r\n0000000000000000000000000000000000A:1`, { status: 200, headers: { "content-type": "text/plain" } })
    }))
    const response = await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    expect(response.status).toBe(400)
    expect(response.json?.code).toBe("PASSWORD_COMPROMISED")
    expect(requested).toEqual([`https://api.pwnedpasswords.com/range/${sha1.slice(0, 5)}`])
  })
})
