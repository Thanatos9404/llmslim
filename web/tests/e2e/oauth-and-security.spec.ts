import { expect, test } from "@playwright/test"
import { E2E } from "./env"

test.use({ extraHTTPHeaders: { "x-real-ip": "198.51.100.200" } })

test.describe("OAuth start, without real credentials", () => {
  test("Google: the start endpoint returns Google's authorize URL with our callback, state, PKCE and scopes", async ({ request }) => {
    const response = await request.post("/api/auth/sign-in/social", { data: { provider: "google", callbackURL: "/account", disableRedirect: true }, headers: { origin: E2E.baseURL } })
    expect(response.status()).toBe(200)
    const { url } = (await response.json()) as { url: string }
    const authorize = new URL(url)
    expect(authorize.origin).toBe("https://accounts.google.com")
    expect(authorize.searchParams.get("client_id")).toBe(E2E.googleClientId)
    expect(authorize.searchParams.get("redirect_uri")).toBe(`${E2E.baseURL}/api/auth/callback/google`)
    expect(authorize.searchParams.get("response_type")).toBe("code")
    expect(authorize.searchParams.get("state")).toMatch(/^.{16,}$/)
    expect(authorize.searchParams.get("code_challenge_method")).toBe("S256")
    expect(authorize.searchParams.get("code_challenge")).toBeTruthy()
    expect((authorize.searchParams.get("scope") ?? "").split(" ").sort()).toEqual(["email", "openid", "profile"])
  })

  test("GitHub: the start endpoint returns GitHub's authorize URL with only the user:email scope", async ({ request }) => {
    const response = await request.post("/api/auth/sign-in/social", { data: { provider: "github", callbackURL: "/account", disableRedirect: true }, headers: { origin: E2E.baseURL } })
    expect(response.status()).toBe(200)
    const { url } = (await response.json()) as { url: string }
    const authorize = new URL(url)
    expect(`${authorize.origin}${authorize.pathname}`).toBe("https://github.com/login/oauth/authorize")
    expect(authorize.searchParams.get("client_id")).toBe(E2E.githubClientId)
    expect(authorize.searchParams.get("redirect_uri")).toBe(`${E2E.baseURL}/api/auth/callback/github`)
    expect(authorize.searchParams.get("state")).toMatch(/^.{16,}$/)
    expect(authorize.searchParams.get("scope")).toBe("user:email")
  })

  test("the buttons on the sign-in page send the browser to each provider", async ({ page }) => {
    // Stub the providers so the test never leaves the machine.
    await page.route("https://accounts.google.com/**", (route) => route.fulfill({ status: 200, contentType: "text/html", body: "<title>google stub</title>" }))
    await page.route("https://github.com/**", (route) => route.fulfill({ status: 200, contentType: "text/html", body: "<title>github stub</title>" }))
    await page.goto("/sign-in")
    await page.getByRole("button", { name: "Continue with Google" }).click()
    await page.waitForURL(/^https:\/\/accounts\.google\.com\//)
    expect(new URL(page.url()).searchParams.get("redirect_uri")).toBe(`${E2E.baseURL}/api/auth/callback/google`)
    await page.goto("/sign-in")
    await page.getByRole("button", { name: "Continue with GitHub" }).click()
    await page.waitForURL(/^https:\/\/github\.com\/login\/oauth\/authorize/)
    expect(new URL(page.url()).searchParams.get("redirect_uri")).toBe(`${E2E.baseURL}/api/auth/callback/github`)
  })

  test("extra scopes cannot be requested", async ({ request }) => {
    const response = await request.post("/api/auth/sign-in/social", { data: { provider: "github", scopes: ["repo"], disableRedirect: true }, headers: { origin: E2E.baseURL } })
    expect(response.status()).toBe(400)
  })
})

test.describe("request safety", () => {
  test("a state-changing request from another origin is rejected", async ({ request }) => {
    const response = await request.post("/api/auth/sign-in/email", { data: { email: "x@example.com", password: "whatever-password" }, headers: { origin: "https://evil.example" } })
    expect(response.status()).toBe(403)
    expect((await response.json()).code).toBe("INVALID_ORIGIN")
  })

  test("accounts API responses are never cached", async ({ request }) => {
    const response = await request.get("/api/auth/get-session")
    expect(response.headers()["cache-control"]).toContain("no-store")
  })
})

test.describe("security headers and the rest of the site", () => {
  const pages = ["/", "/playground", "/docs", "/docs/getting-started", "/results", "/benchmarks", "/integrations", "/articles", "/changelog", "/platform", "/compare/llmlingua", "/privacy", "/sign-in", "/sign-up", "/forgot-password", "/verify-email", "/reset-password"]

  for (const path of pages) {
    test(`${path} loads with the CSP and no policy violations`, async ({ page }) => {
      const violations: string[] = []
      page.on("console", (message) => {
        // Chrome reports every blocked resource as "... violates the following Content Security Policy directive".
        if (/Content Security Policy/i.test(message.text())) violations.push(message.text())
      })
      const response = await page.goto(path)
      expect(response?.status()).toBe(200)
      const headers = response!.headers()
      expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'")
      expect(headers["content-security-policy"]).toContain("object-src 'none'")
      expect(headers["x-content-type-options"]).toBe("nosniff")
      expect(headers["referrer-policy"]).toBe(["/verify-email", "/reset-password"].includes(path) ? "no-referrer" : "strict-origin-when-cross-origin")
      expect(headers["x-frame-options"]).toBe("DENY")
      await page.waitForLoadState("load")
      // Give hydration and client-side fetches a moment to run.
      await page.waitForTimeout(1_500)
      expect(violations).toEqual([])
    })
  }

  test("token pages send no referrer and are not cached", async ({ request }) => {
    for (const path of ["/verify-email", "/reset-password"]) {
      const response = await request.get(path)
      expect(response.headers()["referrer-policy"]).toBe("no-referrer")
      expect(response.headers()["cache-control"]).toContain("no-store")
    }
  })

  test("the Studio page still renders its heading and editor", async ({ page }) => {
    await page.goto("/playground")
    await expect(page.locator("main")).toBeVisible()
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible()
  })
})
