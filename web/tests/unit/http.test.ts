import { afterEach, describe, expect, it, vi } from "vitest"
import { crossOriginRejection, stripTokens, unavailableResponse, withoutSessionTokens } from "@/lib/auth/http"

const trusted = ["https://www.llmslim.app", "https://llmslim.app"]

function post(headers: Record<string, string>) {
  return new Request("https://www.llmslim.app/api/auth/sign-in/email", { method: "POST", headers })
}

describe("unavailableResponse", () => {
  it("is a 503 JSON error that is never cached", async () => {
    const response = unavailableResponse("database_not_configured")
    expect(response.status).toBe(503)
    expect(response.headers.get("content-type")).toContain("application/json")
    expect(response.headers.get("cache-control")).toBe("no-store")
    expect(await response.json()).toEqual({ error: "accounts_unavailable", code: "DATABASE_NOT_CONFIGURED", message: expect.stringContaining("database is not configured") })
  })
})

describe("the auth route without a database", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it("answers every request with 503 and a clear JSON error", async () => {
    vi.stubEnv("DATABASE_URL", "")
    vi.stubEnv("BETTER_AUTH_SECRET", "x".repeat(40))
    vi.resetModules()
    const route = await import("@/app/api/auth/[...all]/route")
    for (const response of [await route.GET(new Request("http://localhost:3000/api/auth/get-session")), await route.POST(new Request("http://localhost:3000/api/auth/sign-in/email", { method: "POST", body: "{}" }))]) {
      expect(response.status).toBe(503)
      expect(await response.json()).toMatchObject({ error: "accounts_unavailable", code: "DATABASE_NOT_CONFIGURED" })
    }
    expect(route.runtime).toBe("nodejs")
  })
})

describe("crossOriginRejection", () => {
  it("allows safe methods and our own origins", () => {
    expect(crossOriginRejection(new Request("https://www.llmslim.app/api/auth/get-session", { headers: { origin: "https://evil.example" } }), trusted)).toBeNull()
    expect(crossOriginRejection(post({ origin: "https://www.llmslim.app", "sec-fetch-site": "same-origin" }), trusted)).toBeNull()
    expect(crossOriginRejection(post({ origin: "https://llmslim.app" }), trusted)).toBeNull()
    expect(crossOriginRejection(post({}), trusted)).toBeNull()
  })

  it("rejects other origins, null origins, foreign referers and cross-site fetch metadata", async () => {
    const cases: Record<string, string>[] = [{ origin: "https://evil.example" }, { origin: "null" }, { referer: "https://evil.example/page" }, { "sec-fetch-site": "cross-site" }, { origin: "https://www.llmslim.app.evil.example" }]
    for (const headers of cases) {
      const response = crossOriginRejection(post(headers), trusted)
      expect(response?.status, JSON.stringify(headers)).toBe(403)
      expect(await response!.json()).toMatchObject({ code: "INVALID_ORIGIN" })
    }
  })
})

describe("session tokens never reach page scripts", () => {
  it("strips every token property", () => {
    expect(stripTokens({ token: "a", redirect: false, user: { id: "u" }, session: { token: "b", id: "s" }, list: [{ token: "c", id: 1 }] })).toEqual({ redirect: false, user: { id: "u" }, session: { id: "s" }, list: [{ id: 1 }] })
  })

  it("rewrites JSON responses and keeps cookies and status", async () => {
    const headers = new Headers({ "content-type": "application/json", "content-length": "99" })
    headers.append("set-cookie", "a=1; HttpOnly")
    headers.append("set-cookie", "b=2; HttpOnly")
    const response = await withoutSessionTokens(new Response(JSON.stringify({ token: "secret", user: { id: "u" } }), { status: 200, headers }))
    expect(await response.json()).toEqual({ user: { id: "u" } })
    expect(response.headers.getSetCookie()).toEqual(["a=1; HttpOnly", "b=2; HttpOnly"])
    expect(response.headers.get("content-length")).toBeNull()
  })

  it("leaves other responses alone", async () => {
    const redirect = new Response(null, { status: 302, headers: { location: "/account" } })
    expect(await withoutSessionTokens(redirect)).toBe(redirect)
  })
})
