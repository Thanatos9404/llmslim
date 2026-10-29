import { defineConfig, devices } from "@playwright/test"
import { E2E } from "./tests/e2e/env"

/**
 * End-to-end tests for accounts, against `next start` (run `npm run build` first) and a real
 * Postgres. Locally that can be PGlite over the Postgres wire protocol (`npm run db:local`); CI uses
 * a Postgres service container. Email goes to a file sink that the tests read.
 */
export default defineConfig({
  testDir: "tests/e2e",
  // One worker: the tests share a database and assert on rate limits.
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  globalSetup: "./tests/e2e/global-setup.ts",
  use: { baseURL: E2E.baseURL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `node node_modules/next/dist/bin/next start --port ${E2E.port}`,
    // A page that needs no database: the global setup migrates the database after the server starts.
    url: `${E2E.baseURL}/sign-in`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
    env: E2E.serverEnv,
  },
})
