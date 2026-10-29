import path from "node:path"

const port = Number(process.env.E2E_PORT ?? 3100)
const baseURL = `http://localhost:${port}`

/** Settings shared by the Playwright config, the global setup and the tests. No real credentials. */
export const E2E = {
  port,
  baseURL,
  databaseUrl: process.env.E2E_DATABASE_URL ?? "postgres://postgres:postgres@127.0.0.1:5433/postgres",
  mailDir: path.resolve(process.env.E2E_MAIL_DIR ?? ".e2e-mail"),
  googleClientId: "e2e-google-client-id.apps.googleusercontent.com",
  githubClientId: "e2e-github-client-id",
  get serverEnv(): Record<string, string> {
    return {
      DATABASE_URL: this.databaseUrl,
      BETTER_AUTH_URL: baseURL,
      BETTER_AUTH_SECRET: "e2e-only-secret-0123456789abcdefghijklmnopqrstuvwxyz",
      AUTH_DEV_MAIL: "file",
      AUTH_DEV_MAIL_DIR: this.mailDir,
      // Dummy OAuth clients: the tests check the redirect to each provider and never complete a flow.
      GOOGLE_CLIENT_ID: this.googleClientId,
      GOOGLE_CLIENT_SECRET: "e2e-google-client-secret",
      GITHUB_CLIENT_ID: this.githubClientId,
      GITHUB_CLIENT_SECRET: "e2e-github-client-secret",
      AUTH_BREACHED_PASSWORD_CHECK: process.env.AUTH_BREACHED_PASSWORD_CHECK ?? "on",
    }
  },
}
