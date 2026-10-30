/**
 * Postgres access for the accounts system.
 *
 * Driver: node-postgres (`pg`) with a small pool, registered with Vercel's `attachDatabasePool` so
 * idle connections are closed before a Fluid compute instance is suspended. This is what Neon and
 * Vercel recommend for Fluid compute, and unlike Neon's HTTP driver it supports the interactive
 * transactions Better Auth uses (sign-up, password reset with session revocation).
 *
 * TLS is required for every host except loopback addresses (local Postgres, PGlite, CI service
 * containers). Any `sslmode` in the URL is removed and replaced by an explicit verify-full setting,
 * so a URL with `sslmode=disable` cannot switch TLS off in production.
 */
import { attachDatabasePool } from "@vercel/functions"
import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres"
import { Pool, type PoolConfig } from "pg"
import { schema } from "./schema"

export type Database = NodePgDatabase<typeof schema>

const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1", "[::1]"])
const TLS_PARAMS = ["sslmode", "ssl", "sslcert", "sslkey", "sslrootcert", "uselibpqcompat"]

export class DatabaseConfigError extends Error {}

/** Builds the pool settings for a connection string. Exported for tests. */
export function poolConfig(databaseUrl: string): PoolConfig {
  let url: URL
  try {
    url = new URL(databaseUrl)
  } catch {
    throw new DatabaseConfigError("DATABASE_URL is not a valid URL")
  }
  if (url.protocol !== "postgres:" && url.protocol !== "postgresql:") throw new DatabaseConfigError("DATABASE_URL must be a postgres:// URL")
  const loopback = LOOPBACK.has(url.hostname)
  for (const param of TLS_PARAMS) url.searchParams.delete(param)
  return {
    connectionString: url.toString(),
    // Certificate and hostname verified against the system CAs (Neon uses a public CA).
    ssl: loopback ? false : { rejectUnauthorized: true },
    max: 5,
    idleTimeoutMillis: 10_000,
    connectionTimeoutMillis: 5_000,
    // Bounds a stuck query instead of holding a serverless invocation open.
    statement_timeout: 10_000,
    application_name: "llmslim-web-accounts",
  }
}

export function createDatabase(databaseUrl: string): { db: Database; pool: Pool } {
  const pool = new Pool(poolConfig(databaseUrl))
  pool.on("error", (error) => console.error("[accounts] idle database client error:", error.message))
  attachDatabasePool(pool)
  return { db: drizzle({ client: pool, schema }), pool }
}
