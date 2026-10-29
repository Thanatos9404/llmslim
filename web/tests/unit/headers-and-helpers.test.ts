import { describe, expect, it, vi } from "vitest"
import { contentSecurityPolicy, securityHeaders, tokenPageHeaders } from "../../security-headers"
import { poolConfig } from "@/db/client"
import { clientIp, hashIdentifier, truncateUserAgent } from "@/lib/auth/audit"
import { describeDevice } from "@/lib/auth/device"
import { resetPasswordMail, verificationMail } from "@/lib/auth/email"
import { describeError, messageForCode } from "@/lib/auth/messages"
import { methodFromPath } from "@/lib/auth/server"

function directives(policy: string): Record<string, string[]> {
  return Object.fromEntries(policy.split(";").map((part) => part.trim().split(/\s+/)).map(([name, ...sources]) => [name, sources]))
}

describe("Content Security Policy", () => {
  const production = directives(contentSecurityPolicy({ NODE_ENV: "production", VERCEL: "1", VERCEL_ENV: "production" }))

  it("forbids framing, plugins, foreign forms and base tags", () => {
    expect(production["frame-ancestors"]).toEqual(["'none'"])
    expect(production["object-src"]).toEqual(["'none'"])
    expect(production["form-action"]).toEqual(["'self'"])
    expect(production["base-uri"]).toEqual(["'self'"])
    expect(production["default-src"]).toEqual(["'self'"])
    expect(production["frame-src"]).toEqual(["'none'"])
    expect(production).toHaveProperty("upgrade-insecure-requests")
  })

  it("allows no eval in production, and no wildcard script hosts", () => {
    expect(production["script-src"]).not.toContain("'unsafe-eval'")
    expect(production["script-src"].some((source) => source.includes("*"))).toBe(false)
    expect(directives(contentSecurityPolicy({ NODE_ENV: "development" }))["script-src"]).toContain("'unsafe-eval'")
  })

  it("allows the avatar hosts the account page shows, and the Sentry host only when configured", () => {
    expect(production["img-src"]).toEqual(expect.arrayContaining(["https://lh3.googleusercontent.com", "https://avatars.githubusercontent.com"]))
    expect(production["connect-src"].some((source) => source.includes("sentry"))).toBe(false)
    const withSentry = directives(contentSecurityPolicy({ NODE_ENV: "production", NEXT_PUBLIC_SENTRY_DSN: "https://key@o123.ingest.us.sentry.io/456" }))
    expect(withSentry["connect-src"]).toContain("https://o123.ingest.us.sentry.io")
  })

  it("allows the Vercel Toolbar on previews only, and never upgrades requests on localhost", () => {
    const preview = directives(contentSecurityPolicy({ NODE_ENV: "production", VERCEL: "1", VERCEL_ENV: "preview" }))
    expect(preview["script-src"]).toContain("https://vercel.live")
    expect(preview["frame-src"]).toEqual(["https://vercel.live"])
    expect(production["script-src"]).not.toContain("https://vercel.live")
    expect(directives(contentSecurityPolicy({ NODE_ENV: "production" }))).not.toHaveProperty("upgrade-insecure-requests")
  })

  it("sends the companion headers, and no-referrer on token pages", () => {
    const headers = Object.fromEntries(securityHeaders({ NODE_ENV: "production" }).map(({ key, value }) => [key, value]))
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin")
    expect(headers["X-Content-Type-Options"]).toBe("nosniff")
    expect(headers["X-Frame-Options"]).toBe("DENY")
    expect(Object.fromEntries(tokenPageHeaders().map(({ key, value }) => [key, value]))["Referrer-Policy"]).toBe("no-referrer")
  })
})

describe("database connection settings", () => {
  it("requires verified TLS for remote hosts, whatever sslmode the URL asks for", () => {
    const config = poolConfig("postgresql://app:pw@ep-cool-123-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=disable&channel_binding=require")
    expect(config.ssl).toEqual({ rejectUnauthorized: true })
    expect(config.connectionString).not.toContain("sslmode")
    expect(config.connectionString).toContain("channel_binding=require")
    expect(config.max).toBeLessThanOrEqual(10)
  })

  it("skips TLS only for loopback databases", () => {
    expect(poolConfig("postgres://postgres:postgres@127.0.0.1:5433/postgres").ssl).toBe(false)
    expect(poolConfig("postgres://postgres:postgres@localhost:5432/test").ssl).toBe(false)
  })

  it("refuses URLs that are not Postgres", () => {
    expect(() => poolConfig("mysql://x@y/z")).toThrow()
    expect(() => poolConfig("not a url")).toThrow()
  })
})

describe("audit helpers", () => {
  it("reads a single-valued forwarding header and ignores spoofable chains", () => {
    expect(clientIp(new Headers({ "x-real-ip": "203.0.113.7" }))).toBe("203.0.113.7")
    expect(clientIp(new Headers({ "x-forwarded-for": "203.0.113.7" }))).toBe("203.0.113.7")
    expect(clientIp(new Headers({ "x-forwarded-for": "1.2.3.4, 203.0.113.7" }))).toBeNull()
    expect(clientIp(new Headers({ "x-real-ip": "<script>" }))).toBeNull()
    expect(clientIp(null)).toBeNull()
  })

  it("hashes with a key, and truncates user agents", () => {
    expect(hashIdentifier("a".repeat(32), "ip", "203.0.113.7")).not.toBe(hashIdentifier("b".repeat(32), "ip", "203.0.113.7"))
    expect(hashIdentifier("a".repeat(32), "ip", "x")).not.toBe(hashIdentifier("a".repeat(32), "email", "x"))
    expect(truncateUserAgent("x".repeat(1000))).toHaveLength(256)
    expect(truncateUserAgent("a\u0000b")).toBe("a b")
  })

  it("names the sign-in method from the endpoint", () => {
    expect(methodFromPath("/sign-in/email")).toBe("password")
    expect(methodFromPath("/passkey/verify-authentication")).toBe("passkey")
    expect(methodFromPath("/callback/:id", { id: "github" })).toBe("github")
    expect(methodFromPath("/change-password")).toBeNull()
  })
})

describe("device labels", () => {
  it.each([
    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36", "Chrome on Windows"],
    ["Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15", "Safari on macOS"],
    ["Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1", "Safari on iOS"],
    ["Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0", "Firefox on Linux"],
    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0", "Edge on Windows"],
    ["Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36", "Chrome on Android"],
    [null, "Unknown device"],
  ])("%s", (userAgent, label) => {
    expect(describeDevice(userAgent)).toBe(label)
  })
})

describe("emails", () => {
  it("escape names and carry the link", () => {
    const mail = verificationMail("ada@example.com", "<b>Ada</b>", "https://www.llmslim.app/verify-email?token=a.b.c")
    expect(mail.html).not.toContain("<b>Ada</b>")
    expect(mail.html).toContain("&lt;b&gt;Ada&lt;/b&gt;")
    expect(mail.text).toContain("https://www.llmslim.app/verify-email?token=a.b.c")
    expect(resetPasswordMail("ada@example.com", null, "https://www.llmslim.app/reset-password?token=abc").text).toContain("expires in 1 hour")
  })
})

describe("messages", () => {
  it("map error codes to plain wording, with rate limits in minutes", () => {
    expect(messageForCode("INVALID_EMAIL_OR_PASSWORD")).toBe("The email or password is incorrect.")
    expect(messageForCode("email_not_verified")).toMatch(/not verified/)
    expect(describeError({ status: 429 }, 125)).toBe("Too many attempts. Try again in 3 minutes.")
    expect(describeError({ status: 503 })).toMatch(/not available/)
    expect(describeError({ code: "SOMETHING_NEW", status: 400 })).toBe("Something went wrong. Please try again.")
  })
})

describe("mail transports", () => {
  it("writes the link to the server log in development", async () => {
    const { sendMail } = await import("@/lib/auth/email")
    const lines: string[] = []
    const spy = vi.spyOn(console, "info").mockImplementation((line: string) => void lines.push(line))
    await sendMail({ mode: "log" }, verificationMail("ada@example.com", "Ada", "http://localhost:3000/verify-email?token=a.b.c"))
    spy.mockRestore()
    expect(lines.join("\n")).toContain("http://localhost:3000/verify-email?token=a.b.c")
  })

  it("refuses to send when no transport is configured", async () => {
    const { sendMail, EmailNotConfiguredError } = await import("@/lib/auth/email")
    await expect(sendMail({ mode: "disabled" }, verificationMail("ada@example.com", "Ada", "https://x"))).rejects.toBeInstanceOf(EmailNotConfiguredError)
  })

  it("sends through Resend's API with the key as a bearer token", async () => {
    const { sendMail } = await import("@/lib/auth/email")
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }))
    vi.stubGlobal("fetch", fetchMock)
    await sendMail({ mode: "resend", apiKey: "re_test_key", from: "LLMSlim <accounts@llmslim.app>" }, verificationMail("ada@example.com", "Ada", "https://www.llmslim.app/verify-email?token=a.b.c"))
    vi.unstubAllGlobals()
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe("https://api.resend.com/emails")
    expect((init.headers as Record<string, string>).authorization).toBe("Bearer re_test_key")
    expect(JSON.parse(String(init.body))).toMatchObject({ from: "LLMSlim <accounts@llmslim.app>", to: ["ada@example.com"] })
  })
})
