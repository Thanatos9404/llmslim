import { expect, test, type Browser, type BrowserContext } from "@playwright/test"
import { randomBytes } from "node:crypto"
import { Pool } from "pg"
import { E2E } from "./env"
import { waitForMail } from "./mail"

const run = randomBytes(4).toString("hex")
let ipCounter = 1

/** Each context gets its own client IP, so per-IP rate limits never couple unrelated tests. */
async function newContext(browser: Browser, options: { javaScriptEnabled?: boolean } = {}): Promise<BrowserContext> {
  return browser.newContext({ baseURL: E2E.baseURL, extraHTTPHeaders: { "x-real-ip": `198.51.100.${100 + ipCounter++}` }, ...options })
}

function since(): Date {
  return new Date(Date.now() - 2_000)
}

type Row = { email: string; user_id: string | null; plan: string; currency: string; billing: string; use_case: string | null; source: string; status: string; confirmed_at: Date | null }

// The owner's connection, to look at what the site stored.
const pool = new Pool({ connectionString: E2E.databaseUrl, max: 1 })
test.afterAll(async () => {
  await pool.end()
})

async function row(email: string): Promise<Row | undefined> {
  const { rows } = await pool.query<Row>("select email, user_id, plan, currency, billing, use_case, source, status, confirmed_at from founding_list where email = $1", [email])
  return rows[0]
}

function card(page: import("@playwright/test").Page, plan: string) {
  return page.locator(".pr-plan").filter({ has: page.getByRole("heading", { level: 3, name: plan, exact: true }) })
}

test.describe("founding list on /pricing", () => {
  test("the page renders as before: the email links stay, for visitors without JavaScript", async ({ browser }) => {
    const context = await newContext(browser, { javaScriptEnabled: false })
    const page = await context.newPage()
    await page.goto("/pricing?currency=inr&billing=monthly")
    const join = page.getByRole("link", { name: "Join the founding list" })
    await expect(join).toHaveCount(4)
    await expect(page.getByRole("link", { name: "Talk to us" })).toHaveCount(1)
    const pro = card(page, "Pro").getByRole("link", { name: "Join the founding list" })
    await expect(pro).toHaveClass("button button-outline")
    await expect(card(page, "Team").getByRole("link", { name: "Join the founding list" })).toHaveClass("button")
    const href = await pro.getAttribute("href")
    expect(href).toMatch(/^mailto:founder@llmslim\.app\?subject=/)
    expect(decodeURIComponent(href!)).toContain("Plan: Pro")
    // No public count unless the founder turns it on.
    await expect(page.getByText("on the founding list.")).toHaveCount(0)
    await context.close()
  })

  test("signed out: a small form, a confirmation email, the link confirms, and the unsubscribe link leaves", async ({ browser }) => {
    const context = await newContext(browser)
    const page = await context.newPage()
    const email = `lead-${run}@example.com`
    await page.goto("/pricing?currency=inr&billing=monthly")
    await card(page, "Pro").getByRole("link", { name: "Join the founding list" }).click()
    const form = page.getByTestId("founding-form")
    await expect(form).toBeVisible()
    await expect(form.getByLabel("Email")).toBeFocused()

    // The form's own check, with the accounts' wording.
    await form.getByLabel("Email").fill("not-an-email")
    await form.getByRole("button", { name: "Join the founding list" }).click()
    await expect(form.getByText("Enter a valid email address.")).toBeVisible()

    await form.getByLabel("Email").fill(email.toUpperCase())
    await form.getByLabel(/What will you use it for/).fill("Memory for a support agent")
    const sent = since()
    await form.getByRole("button", { name: "Join the founding list" }).click()
    await expect(page.getByTestId("founding-sent")).toContainText(`Check ${email.toUpperCase()} for a link to confirm`)
    expect(await row(email)).toMatchObject({ status: "pending", plan: "pro", currency: "inr", billing: "monthly", use_case: "Memory for a support agent", source: "pricing", user_id: null })

    const mail = await waitForMail(email, "founding-list-confirm", sent)
    expect(mail.url).toMatch(new RegExp(`^${E2E.baseURL}/founding-list/confirm\\?token=[A-Za-z0-9_-]{43}$`))
    expect(mail.unsubscribeUrl).toMatch(new RegExp(`^${E2E.baseURL}/founding-list/unsubscribe\\?token=`))
    expect(mail.text).toContain("Not you, or changed your mind? Unsubscribe:")
    expect(mail.text).not.toContain("support agent")

    const confirmPage = await page.goto(mail.url!)
    expect(confirmPage?.headers()["referrer-policy"]).toBe("no-referrer")
    await expect(page.getByTestId("status-success")).toContainText("You’re on the founding list for the Pro plan, in INR, billed monthly.")
    await expect(page).toHaveURL(`${E2E.baseURL}/founding-list/confirm`)
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/)
    const confirmed = await row(email)
    expect(confirmed?.status).toBe("confirmed")
    expect(confirmed?.confirmed_at).not.toBeNull()

    // Opening the link again is harmless.
    await page.goto(mail.url!)
    await expect(page.getByTestId("status-success")).toContainText("You’re on the founding list")

    await page.goto(mail.unsubscribeUrl!)
    await expect(page.getByTestId("status-success")).toContainText("You have left the founding list.")
    await expect(page).toHaveURL(`${E2E.baseURL}/founding-list/unsubscribe`)
    expect(await row(email)).toMatchObject({ status: "unsubscribed", use_case: null })
    await context.close()
  })

  test("signed out without JavaScript, the unsubscribe page still works with one button", async ({ browser }) => {
    const context = await newContext(browser)
    const email = `nojs-${run}@example.com`
    const sent = since()
    const response = await context.request.post("/api/founding-list", { data: { plan: "business", currency: "usd", billing: "annual", email }, headers: { origin: E2E.baseURL } })
    expect(await response.json()).toEqual({ status: "check_email" })
    const mail = await waitForMail(email, "founding-list-confirm", sent)
    await context.close()

    const noScript = await newContext(browser, { javaScriptEnabled: false })
    const page = await noScript.newPage()
    await page.goto(mail.unsubscribeUrl!)
    await page.getByRole("button", { name: "Leave the founding list" }).click()
    await expect(page).toHaveURL(`${E2E.baseURL}/founding-list/unsubscribe?result=done`)
    await expect(page.getByTestId("status-success")).toContainText("You have left the founding list.")
    expect(await row(email)).toMatchObject({ status: "unsubscribed" })
    await noScript.close()
  })

  test("signed in: one click joins with the account's email, again is idempotent, and Leave undoes it", async ({ browser }) => {
    const context = await newContext(browser)
    const page = await context.newPage()
    const email = `member-${run}@example.com`
    const password = `Founding-Member-${run}-2026`
    const sent = since()
    const signUp = await page.request.post("/api/auth/sign-up/email", { data: { name: "Grace Hopper", email, password }, headers: { origin: E2E.baseURL } })
    expect(signUp.status()).toBe(200)
    const verify = await waitForMail(email, "verify-email", sent)
    await page.goto(verify.url!)
    await expect(page.getByTestId("status-success")).toContainText("Your email is confirmed")
    const signIn = await page.request.post("/api/auth/sign-in/email", { data: { email, password }, headers: { origin: E2E.baseURL } })
    expect(signIn.status()).toBe(200)

    await page.goto("/pricing?currency=usd&billing=annual")
    await card(page, "Team").getByRole("link", { name: "Join the founding list" }).click()
    const joined = card(page, "Team").getByTestId("founding-joined")
    await expect(joined).toContainText(`You’re on the founding list for Team. We’ll email ${email} when Orbit opens.`)
    expect(await row(email)).toMatchObject({ status: "confirmed", plan: "team", currency: "usd", billing: "annual", source: "pricing" })
    expect((await row(email))?.user_id).toBeTruthy()

    // A second click, after a reload, updates the same row.
    await page.goto("/pricing?currency=usd&billing=monthly")
    await card(page, "Pro").getByRole("link", { name: "Join the founding list" }).click()
    await expect(card(page, "Pro").getByTestId("founding-joined")).toBeVisible()
    const { rows } = await pool.query<{ count: number }>("select count(*)::int as count from founding_list where email = $1", [email])
    expect(rows[0].count).toBe(1)
    expect(await row(email)).toMatchObject({ status: "confirmed", plan: "pro", billing: "monthly" })

    await card(page, "Pro").getByRole("button", { name: "Leave the list" }).click()
    await expect(card(page, "Pro").getByText("You have left the founding list.")).toBeVisible()
    await expect(card(page, "Pro").getByRole("link", { name: "Join the founding list" })).toBeVisible()
    expect(await row(email)).toMatchObject({ status: "unsubscribed" })
    await context.close()
  })

  test("another site cannot join or leave for a signed-in visitor", async ({ browser }) => {
    const context = await newContext(browser)
    const response = await context.request.post("/api/founding-list", { data: { plan: "pro", currency: "inr", billing: "monthly", email: `x-${run}@example.com` }, headers: { origin: "https://evil.example" } })
    expect(response.status()).toBe(403)
    expect((await response.json()).code).toBe("INVALID_ORIGIN")
    const leave = await context.request.delete("/api/founding-list", { headers: { origin: "https://evil.example" } })
    expect(leave.status()).toBe(403)
    await context.close()
  })
})
