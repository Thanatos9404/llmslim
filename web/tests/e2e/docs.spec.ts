import { expect, test, type Page } from "@playwright/test"

/** The docs' version switch, notice, redirects and Markdown twins, on the production build. No database is touched. */

const PAGES = [
  "/docs", "/docs/quickstart-python", "/docs/quickstart-http", "/docs/api-llmslim-memory",
  "/docs/1.0", "/docs/1.0/quickstart-mcp", "/docs/1.0/import-history", "/docs/1.0/explain", "/docs/1.0/openai-compatible-endpoint",
  "/docs/1.0/storage-backends", "/docs/1.0/remote-mcp", "/docs/1.0/migrate-to-1-0", "/docs/1.0/api-llmslim",
]

const switcher = (page: Page) => page.locator(".docs-side .docs-version-switch")
const robots = (page: Page) => page.locator('meta[name="robots"]').getAttribute("content")

test.describe("docs versions", () => {
  test("/docs is 0.12, what pip installs, with no preview notice, and indexable", async ({ page }) => {
    await page.goto("/docs/quickstart-python")
    await expect(page.locator("h1")).toHaveText("Python quickstart")
    await expect(page.locator(".docs-version-notice")).toHaveCount(0)
    await expect(switcher(page).getByRole("link", { name: /Docs for 0\.12/ })).toHaveAttribute("aria-current", "true")
    expect(await robots(page)).toContain("index")
    expect(await robots(page)).not.toContain("noindex")
  })

  test("switching to 1.0 keeps the guide, shows the notice and is not indexed", async ({ page }) => {
    await page.goto("/docs/quickstart-python")
    await switcher(page).getByRole("link", { name: /Docs for 1\.0/ }).click()
    await expect(page).toHaveURL(/\/docs\/1\.0\/quickstart-python$/)
    const notice = page.locator(".docs-version-notice")
    await expect(notice).toContainText("Upcoming in 1.0")
    await expect(notice).toContainText("pip install llmslim installs 0.12.0 today")
    expect(await robots(page)).toContain("noindex")
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://www.llmslim.app/docs/1.0/quickstart-python")
  })

  test("a 1.0-only guide switches to the 0.12 docs home, and doesn't exist at /docs/<slug>", async ({ page, request }) => {
    await page.goto("/docs/1.0/import-history")
    await expect(page.locator(".doc-badge.is-new")).toHaveText("New in 1.0")
    await switcher(page).getByRole("link", { name: /Docs for 0\.12/ }).click()
    await expect(page).toHaveURL(/\/docs$/)
    expect((await request.get("/docs/import-history", { maxRedirects: 0 })).status()).toBe(404)
  })

  test("the default version's own prefix redirects to /docs", async ({ request }) => {
    const page = await request.get("/docs/0.12/quickstart-mcp", { maxRedirects: 0 })
    expect(page.status()).toBe(307)
    expect(page.headers()["location"]).toBe("/docs/quickstart-mcp")
    expect((await request.get("/docs/0.12", { maxRedirects: 0 })).headers()["location"]).toBe("/docs")
  })

  test("Markdown twins carry the version, and the preview says so first", async ({ request }) => {
    const preview = await request.get("/docs/1.0/remote-mcp.md")
    expect(preview.headers()["content-type"]).toContain("text/markdown")
    const text = await preview.text()
    expect(text.split("\n").slice(0, 3).join("\n")).toContain("Upcoming in 1.0 (preview)")
    expect(text).toContain("Version: 1.0")
    expect(await (await request.get("/docs/1.0.md")).text()).toContain("# LLMSlim documentation 1.0")
    expect(await (await request.get("/docs/quickstart-mcp.md")).text()).not.toContain("Upcoming in")
  })

  test("experimental guides are marked as such", async ({ page }) => {
    for (const slug of ["openai-compatible-endpoint", "remote-mcp"]) {
      await page.goto(`/docs/1.0/${slug}`)
      await expect(page.locator(".doc-badge.is-experimental")).toBeVisible()
      await expect(page.locator(".doc-callout-label", { hasText: "Experimental" })).toBeVisible()
    }
  })
})

test.describe("docs on a phone", () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test("no page scrolls sideways, and the version switch is on screen", async ({ page }) => {
    for (const path of PAGES) {
      await page.goto(path)
      const { scroll, width } = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: window.innerWidth }))
      expect(scroll, path).toBeLessThanOrEqual(width)
      await expect(page.locator(".docs-mobilebar .docs-version-switch"), path).toBeVisible()
    }
  })

  test("the switch works on a phone too", async ({ page }) => {
    await page.goto("/docs/quickstart-http")
    await page.locator(".docs-mobilebar").getByRole("link", { name: /Docs for 1\.0/ }).click()
    await expect(page).toHaveURL(/\/docs\/1\.0\/quickstart-http$/)
    await expect(page.locator(".docs-mobilebar-home")).toHaveAttribute("href", "/docs/1.0")
  })
})
