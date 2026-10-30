import { readFileSync, rmSync } from "node:fs"
import path from "node:path"
import { drizzle } from "drizzle-orm/node-postgres"
import { migrate } from "drizzle-orm/node-postgres/migrator"
import { Pool } from "pg"
import { E2E } from "./env"

const WEB = path.join(__dirname, "..", "..")

/**
 * Applies the checked-in migrations to the test database and starts from empty tables. With
 * `E2E_APP_DATABASE_URL` set it also grants the least-privilege role, as production does.
 */
export default async function globalSetup() {
  const pool = new Pool({ connectionString: E2E.databaseUrl, max: 1 })
  try {
    await migrate(drizzle({ client: pool }), { migrationsFolder: path.join(WEB, "drizzle") })
    if (E2E.appDatabaseUrl) await grantAppRole(pool, E2E.appDatabaseUrl)
    await pool.query(`truncate table "user", session, account, verification, passkey, rate_limit, auth_event cascade`)
  } finally {
    await pool.end()
  }
  rmSync(E2E.mailDir, { recursive: true, force: true })
}

/**
 * Runs scripts/db/app-role.sql as the owner, sets the role's test password, and fails when any table
 * the migrations created is missing a privilege every accounts table needs, naming the table.
 */
async function grantAppRole(pool: Pool, appDatabaseUrl: string) {
  const url = new URL(appDatabaseUrl)
  if (url.username !== "llmslim_app") throw new Error(`E2E_APP_DATABASE_URL must sign in as llmslim_app, not "${url.username}".`)
  await pool.query(readFileSync(path.join(WEB, "scripts", "db", "app-role.sql"), "utf8"))
  const client = await pool.connect()
  try {
    await client.query(`alter role llmslim_app with password ${client.escapeLiteral(decodeURIComponent(url.password))}`)
  } finally {
    client.release()
  }
  const { rows } = await pool.query<{ name: string; missing: string }>(`
    select c.relname as name, string_agg(p.privilege, ', ' order by p.privilege) as missing
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    cross join unnest(array['SELECT', 'INSERT', 'DELETE']) as p(privilege)
    where n.nspname = 'public' and c.relkind in ('r', 'p') and not has_table_privilege('llmslim_app', c.oid, p.privilege)
    group by c.relname
    union all
    select c.relname, 'USAGE'
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    -- CASE, because Postgres may evaluate has_sequence_privilege before the relkind test otherwise.
    where n.nspname = 'public' and case when c.relkind = 'S' then not has_sequence_privilege('llmslim_app', c.oid, 'USAGE') else false end
    order by 1`)
  if (rows.length > 0) {
    const list = rows.map((row) => `${row.name} (${row.missing})`).join(", ")
    throw new Error(`llmslim_app is missing privileges on ${list}. Grant them in web/scripts/db/app-role.sql and run it on production.`)
  }
}
