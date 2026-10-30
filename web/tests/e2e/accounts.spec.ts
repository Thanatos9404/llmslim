import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test"
import { randomBytes } from "node:crypto"
import { E2E } from "./env"
import { mailCount, waitForMail } from "./mail"

const run = randomBytes(4).toString("hex")
const email = `ada-${run}@example.com`
const name = "Ada Lovelace"
const password = `Analytical-Engine-${run}-1843`
const newPassword = `Difference-Engine-${run}-1822`
let ipCounter = 1

/** Each context gets its own client IP, so per-IP rate limits never couple unrelated tests. */
async function newContext(browser: Browser): Promise<BrowserContext> {
  return browser.newContext({ baseURL: E2E.baseURL, extraHTTPHeaders: { "x-real-ip": `198.51.100.${ipCounter++}` } })
}

function since(): Date {
  return new Date(Date.now() - 2_000)
}

async function signIn(page: Page, address: string, secret: string, next?: string) {
  await page.goto(next ? `/sign-in?next=${encodeURIComponent(next)}` : "/sign-in")
  await page.getByLabel("Email").fill(address)
  await page.getByLabel("Password", { exact: true }).fill(secret)
  await page.getByRole("button", { name: "Sign in", exact: true }).click()
}

test.describe.serial("accounts", () => {
  let context: BrowserContext
  let page: Page

  test.beforeAll(async ({ browser }) => {
    context = await newContext(browser)
    page = await context.newPage()
  })

  test.afterAll(async () => {
    await context.close()
  })

  test("/account redirects to sign-in when signed out", async () => {
    await page.goto("/account")
    await expect(page).toHaveURL(/\/sign-in\?next=(%2F|\/)account$/)
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible()
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/)
  })

  test("sign up with email shows field errors, strength feedback and a check-your-email state", async () => {
    await page.goto("/sign-up")
    await page.getByRole("button", { name: "Create account" }).click()
    await expect(page.getByTestId("field-error").first()).toBeVisible()
    await expect(page.getByText("Agree to the Terms of Service and Privacy Policy to continue.")).toBeVisible()

    await page.getByLabel("Name").fill(name)
    await page.getByLabel("Email").fill(email)
    await page.getByLabel("Password", { exact: true }).fill("short")
    await expect(page.getByTestId("password-strength")).toContainText("Too short")
    await page.getByLabel(/I agree to the/).check()
    if (process.env.AUTH_BREACHED_PASSWORD_CHECK !== "off") {
      // A password from known breaches is refused by the server (Have I Been Pwned range check).
      await page.getByLabel("Password", { exact: true }).fill("password1234")
      await page.getByRole("button", { name: "Create account" }).click()
      await expect(page.getByText("This password appears in a known data breach. Choose a different one.")).toBeVisible()
    }
    await page.getByLabel("Password", { exact: true }).fill(password)
    await expect(page.getByTestId("password-strength")).not.toContainText("Too short")
    const sent = since()
    await page.getByRole("button", { name: "Create account" }).click()
    await expect(page.getByTestId("check-email")).toBeVisible()
    await waitForMail(email, "verify-email", sent)
  })

  test("signing in before verifying is refused and sends a fresh link", async () => {
    const sent = since()
    await signIn(page, email, password)
    await expect(page.getByTestId("status-error")).toContainText("Confirm your email address first")
    await waitForMail(email, "verify-email", sent)
  })

  test("verify the email from the link in the mail sink; the link works once", async () => {
    const mail = await waitForMail(email, "verify-email", new Date(0))
    expect(mail.url).toMatch(new RegExp(`^${E2E.baseURL}/verify-email\\?token=`))
    await page.goto(mail.url!)
    await expect(page.getByTestId("status-success")).toContainText("Your email is confirmed")
    // The token is removed from the address bar once read.
    await expect(page).toHaveURL(`${E2E.baseURL}/verify-email`)
    await page.goto(mail.url!)
    await expect(page.getByTestId("status-error")).toContainText("already been used")
  })

  test("a wrong password and an unknown email give the same generic error", async () => {
    await signIn(page, email, "not-the-right-password")
    await expect(page.getByTestId("status-error")).toHaveText("The email or password is incorrect.")
    await signIn(page, `nobody-${run}@example.com`, "not-the-right-password")
    await expect(page.getByTestId("status-error")).toHaveText("The email or password is incorrect.")
  })

  test("sign in ignores an off-site ?next= and lands on the account page", async () => {
    await signIn(page, email, password, "https://evil.example/steal")
    await expect(page).toHaveURL(`${E2E.baseURL}/account`)
    await expect(page.getByTestId("account-email")).toContainText(email)
    await expect(page.getByTestId("session-item")).toHaveCount(1)
    await expect(page.getByTestId("password-state")).toHaveText("Password set")
  })

  test("sign out, then sign in again", async () => {
    await page.getByTestId("sign-out").click()
    await expect(page).toHaveURL(/\/sign-in\?signedOut=1$/)
    await expect(page.getByTestId("status-success")).toHaveText("You have signed out.")
    await page.goto("/account")
    await expect(page).toHaveURL(/\/sign-in\?next=(%2F|\/)account$/)
    await signIn(page, email, password, "/account")
    await expect(page).toHaveURL(`${E2E.baseURL}/account`)
  })

  test("the per-email limit stops guessing after five failed attempts", async ({ browser }) => {
    const attacker = await newContext(browser)
    const guessPage = await attacker.newPage()
    const target = `ratelimit-${run}@example.com`
    for (let attempt = 1; attempt <= 5; attempt++) {
      await signIn(guessPage, target, `wrong-password-${attempt}`)
      await expect(guessPage.getByTestId("status-error")).toHaveText("The email or password is incorrect.")
    }
    await signIn(guessPage, target, "wrong-password-6")
    await expect(guessPage.getByTestId("status-error")).toHaveText(/^Too many attempts\. Try again in \d+ minutes?\.$/)
    await attacker.close()
  })

  test("add a passkey with a virtual authenticator; after signing out, autofill (conditional UI) signs in with it", async () => {
    const cdp = await context.newCDPSession(page)
    await cdp.send("WebAuthn.enable")
    await cdp.send("WebAuthn.addVirtualAuthenticator", {
      options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
    })

    await page.goto("/account")
    await expect(page.getByTestId("no-passkeys")).toBeVisible()
    await page.getByLabel("Passkey name (optional)").fill("E2E laptop")
    await page.getByRole("button", { name: "Add a passkey" }).click()
    await expect(page.getByTestId("section-passkeys").getByTestId("status-success")).toContainText("Passkey “E2E laptop” added")
    await expect(page.getByTestId("passkey-name")).toHaveText("E2E laptop")

    // Conditional UI: the sign-in page offers passkeys through autofill as soon as it loads. The
    // virtual authenticator picks the only passkey, so the page signs in with no click at all.
    const signedOut = page.waitForResponse((response) => response.url().endsWith("/api/auth/sign-out") && response.status() === 200)
    const verified = page.waitForResponse((response) => response.url().endsWith("/api/auth/passkey/verify-authentication") && response.status() === 200)
    await page.getByTestId("sign-out").click()
    await signedOut
    await verified
    await expect(page).toHaveURL(`${E2E.baseURL}/account`)
    await expect(page.getByTestId("account-email")).toContainText(email)
  })

  test("sign in with the passkey button", async () => {
    // Turn conditional UI off for this page, so only the explicit button can start a ceremony.
    await page.addInitScript(() => {
      Object.defineProperty(window.PublicKeyCredential, "isConditionalMediationAvailable", { value: async () => false, configurable: true })
    })
    const signedOut = page.waitForResponse((response) => response.url().endsWith("/api/auth/sign-out") && response.status() === 200)
    await page.getByTestId("sign-out").click()
    await signedOut
    // A full page load, so the init script applies (sign-out navigates on the client).
    await page.goto("/sign-in")
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible()
    await page.getByTestId("passkey-sign-in").click()
    await expect(page).toHaveURL(`${E2E.baseURL}/account`)
    await expect(page.getByTestId("account-email")).toContainText(email)
  })

  test("rename and delete the passkey", async () => {
    await page.goto("/account")
    await page.getByRole("button", { name: "Rename passkey E2E laptop" }).click()
    await page.getByLabel("New name for E2E laptop").fill("Renamed key")
    await page.getByRole("button", { name: "Save", exact: true }).click()
    await expect(page.getByTestId("passkey-name")).toHaveText("Renamed key")

    await page.getByRole("button", { name: "Delete passkey Renamed key" }).click()
    await page.getByRole("button", { name: "Confirm delete" }).click()
    await expect(page.getByTestId("no-passkeys")).toBeVisible()
  })

  test("forgot and reset password revokes the other sessions", async ({ browser }) => {
    // `page` is signed in. Reset the password from a second browser.
    const other = await newContext(browser)
    const resetPage = await other.newPage()
    await resetPage.goto("/forgot-password")
    const sent = since()
    await resetPage.getByLabel("Email").fill(email)
    await resetPage.getByRole("button", { name: "Send reset link" }).click()
    await expect(resetPage.getByTestId("status-success")).toContainText("If an account uses that email")
    const mail = await waitForMail(email, "reset-password", sent)
    expect(mail.url).toMatch(new RegExp(`^${E2E.baseURL}/reset-password\\?token=`))

    await resetPage.goto(mail.url!)
    await expect(resetPage).toHaveURL(`${E2E.baseURL}/reset-password`)
    await resetPage.getByLabel("New password", { exact: true }).fill(newPassword)
    await resetPage.getByLabel("Confirm new password").fill(newPassword)
    await resetPage.getByRole("button", { name: "Change password" }).click()
    await expect(resetPage.getByTestId("status-success")).toContainText("signed out everywhere else")

    // The reset link is single use.
    await resetPage.goto(mail.url!)
    await resetPage.getByLabel("New password", { exact: true }).fill(`${newPassword}-again`)
    await resetPage.getByLabel("Confirm new password").fill(`${newPassword}-again`)
    await resetPage.getByRole("button", { name: "Change password" }).click()
    await expect(resetPage.getByTestId("status-error")).toContainText("invalid or has expired")
    await other.close()

    // The first browser's session was revoked by the reset.
    await page.goto("/account")
    await expect(page).toHaveURL(/\/sign-in\?next=(%2F|\/)account$/)
    await signIn(page, email, password)
    await expect(page.getByTestId("status-error")).toHaveText("The email or password is incorrect.")
    await signIn(page, email, newPassword, "/account")
    await expect(page).toHaveURL(`${E2E.baseURL}/account`)
  })

  test("signing up again with the same email reveals nothing and notifies the owner", async ({ browser }) => {
    const other = await newContext(browser)
    const signUpPage = await other.newPage()
    await signUpPage.goto("/sign-up")
    await signUpPage.getByLabel("Name").fill("Someone Else")
    await signUpPage.getByLabel("Email").fill(email)
    await signUpPage.getByLabel("Password", { exact: true }).fill(`Another-Password-${run}`)
    await signUpPage.getByLabel(/I agree to the/).check()
    const sent = since()
    await signUpPage.getByRole("button", { name: "Create account" }).click()
    await expect(signUpPage.getByTestId("check-email")).toBeVisible()
    await waitForMail(email, "existing-account", sent)
    await other.close()
  })

  test("delete the account after confirming the password", async () => {
    await page.goto("/account")
    await page.getByTestId("delete-open").click()
    await page.getByRole("button", { name: "Delete my account permanently" }).click()
    await expect(page.getByText("Enter your password to confirm.")).toBeVisible()
    await page.getByLabel("Password", { exact: true }).fill(newPassword)
    await page.getByLabel("I understand that my account will be deleted permanently.").check()
    await page.getByRole("button", { name: "Delete my account permanently" }).click()
    await expect(page).toHaveURL(/\/sign-in\?deleted=1$/)
    await expect(page.getByTestId("status-success")).toHaveText("Your account has been deleted.")
    await page.goto("/account")
    await expect(page).toHaveURL(/\/sign-in\?next=(%2F|\/)account$/)
    await signIn(page, email, newPassword)
    await expect(page.getByTestId("status-error")).toHaveText("The email or password is incorrect.")
    expect(mailCount(email, "account-deleted")).toBe(1)
  })
})
