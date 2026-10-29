import { rmSync } from "node:fs"
import path from "node:path"
import { drizzle } from "drizzle-orm/node-postgres"
import { migrate } from "drizzle-orm/node-postgres/migrator"
import { Pool } from "pg"
import { E2E } from "./env"

/** Applies the checked-in migrations to the test database and starts from empty tables. */
export default async function globalSetup() {
  const pool = new Pool({ connectionString: E2E.databaseUrl, max: 1 })
  try {
    await migrate(drizzle({ client: pool }), { migrationsFolder: path.join(__dirname, "..", "..", "drizzle") })
    await pool.query(`truncate table "user", session, account, verification, passkey, rate_limit, auth_event cascade`)
  } finally {
    await pool.end()
  }
  rmSync(E2E.mailDir, { recursive: true, force: true })
}
