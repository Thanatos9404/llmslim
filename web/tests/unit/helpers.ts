import { PGlite } from "@electric-sql/pglite"
import { drizzle } from "drizzle-orm/pglite"
import { migrate } from "drizzle-orm/pglite/migrator"
import { fileURLToPath } from "node:url"
import { schema } from "@/db/schema"
import { resolveAuthConfig, type Env } from "@/lib/auth/config"
import type { Mail } from "@/lib/auth/email"
import type { AnyPgDatabase } from "@/lib/auth/rate-limit-store"
import { buildAuth } from "@/lib/auth/server"

export const ORIGIN = "http://localhost:3000"
export const SECRET = "unit-test-secret-0123456789abcdef0123456789abcdef"
const MIGRATIONS = fileURLToPath(new URL("../../drizzle", import.meta.url))

export async function testDatabase() {
  const client = new PGlite()
  const db = drizzle({ client, schema })
  await migrate(db, { migrationsFolder: MIGRATIONS })
  return { client, db: db as unknown as AnyPgDatabase }
}

export const baseEnv: Env = {
  NODE_ENV: "test",
  BETTER_AUTH_URL: ORIGIN,
  BETTER_AUTH_SECRET: SECRET,
  DATABASE_URL: "postgres://pglite.invalid/test",
  AUTH_BREACHED_PASSWORD_CHECK: "off",
  AUTH_DEV_MAIL: "log",
}

export async function testAuth(env: Env = {}) {
  const { client, db } = await testDatabase()
  const config = resolveAuthConfig({ ...baseEnv, ...env })
  const mails: Mail[] = []
  const pending: Promise<unknown>[] = []
  const auth = buildAuth(config, db, {
    background: (promise) => void pending.push(promise),
    mail: async (mail) => void mails.push(mail),
  })
  let ipCounter = 10
  const nextIp = () => `203.0.113.${ipCounter++ % 250}`

  async function settle() {
    while (pending.length) await Promise.allSettled(pending.splice(0))
  }

  async function call(path: string, init: { method?: string; body?: unknown; cookie?: string; ip?: string; origin?: string | null; query?: Record<string, string>; headers?: Record<string, string> } = {}) {
    const url = new URL(`/api/auth${path}`, ORIGIN)
    for (const [key, value] of Object.entries(init.query ?? {})) url.searchParams.set(key, value)
    const headers = new Headers({ "x-real-ip": init.ip ?? "203.0.113.1", "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0 Safari/537.36", ...init.headers })
    if (init.origin !== null) headers.set("origin", init.origin ?? ORIGIN)
    if (init.cookie) headers.set("cookie", init.cookie)
    if (init.body !== undefined) headers.set("content-type", "application/json")
    const response = await auth.handler(new Request(url, { method: init.method ?? (init.body === undefined ? "GET" : "POST"), headers, body: init.body === undefined ? undefined : JSON.stringify(init.body) }))
    await settle()
    const text = await response.text()
    let json: unknown = null
    try {
      json = text ? JSON.parse(text) : null
    } catch {
      json = text
    }
    return { response, status: response.status, json: json as Record<string, unknown> | null, cookie: sessionCookie(response) }
  }

  return { auth, db, client, config, mails, call, settle, nextIp }
}

/** The session cookie from a response, as a Cookie header value. */
export function sessionCookie(response: Response): string | undefined {
  const cookies = response.headers.getSetCookie()
  const session = cookies.find((cookie) => /session_token=/.test(cookie) && !/Max-Age=0/i.test(cookie))
  return session?.split(";")[0]
}

export function tokenFrom(mail: Mail | undefined): string {
  if (!mail?.url) throw new Error("no link in mail")
  const token = new URL(mail.url).searchParams.get("token")
  if (!token) throw new Error("no token in link")
  return token
}
