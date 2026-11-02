// Founding-list export for the founder: counts per plan, and a CSV of confirmed members. Read only.
//
// Usage, from web/ (the owner's or the llmslim_app connection string both work):
//   bash:        DATABASE_URL="postgresql://..." node scripts/founding-list-export.mjs > founding-list.csv
//   PowerShell:  $env:DATABASE_URL = "postgresql://..."; node scripts/founding-list-export.mjs > founding-list.csv
//                Remove-Item Env:DATABASE_URL
//
// The counts go to stderr, so they show in the terminal while the CSV goes to the file. Flags:
//   --counts   print the counts only, no CSV
//
// One read-only transaction; nothing is written. The connection string is never printed. Like the site
// (src/db/client.ts), TLS with certificate and host-name checks is required for every non-local host,
// whatever the URL's sslmode says. The CSV holds personal data: keep it off shared drives and delete it
// when you are done with it.
import { pathToFileURL } from "node:url"
import pg from "pg"

const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1", "[::1]"])
const TLS_PARAMS = ["sslmode", "ssl", "sslcert", "sslkey", "sslrootcert", "uselibpqcompat"]
const PLANS = ["free", "pro", "team", "business"]
const STATUSES = ["confirmed", "pending", "unsubscribed"]
const COLUMNS = ["email", "plan", "currency", "billing", "use_case", "source", "has_account", "joined_at", "confirmed_at"]

function connection(raw) {
  let url
  try {
    url = new URL(raw)
  } catch {
    throw new Error("DATABASE_URL is not a valid URL")
  }
  if (url.protocol !== "postgres:" && url.protocol !== "postgresql:") throw new Error("DATABASE_URL must be a postgres:// URL")
  const loopback = LOOPBACK.has(url.hostname)
  for (const param of TLS_PARAMS) url.searchParams.delete(param)
  return { connectionString: url.toString(), ssl: loopback ? false : { rejectUnauthorized: true }, max: 1, connectionTimeoutMillis: 10_000, statement_timeout: 30_000, application_name: "llmslim-founding-list-export" }
}

/** One CSV cell: quoted when needed, and a leading = + - @ (or tab, return) defused so spreadsheets do not run it as a formula. */
export function csvCell(value) {
  if (value === null || value === undefined) return ""
  let text = value instanceof Date ? value.toISOString() : String(value)
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function pad(text, width) {
  return String(text).padEnd(width)
}

async function main() {
  const countsOnly = process.argv.includes("--counts")
  const raw = process.env.DATABASE_URL
  if (!raw) {
    console.error("Set DATABASE_URL to the accounts database first (see the comment at the top of this file).")
    process.exit(1)
  }
  const client = new pg.Client(connection(raw))
  await client.connect()
  try {
    await client.query("begin read only")
    const counts = await client.query("select plan, status, count(*)::int as count from founding_list group by plan, status")
    const confirmedBy = await client.query(
      "select plan, currency, billing, count(*)::int as count from founding_list where status = 'confirmed' group by plan, currency, billing order by plan, currency, billing",
    )
    const members = countsOnly
      ? { rows: [] }
      : await client.query(
          "select email, plan, currency, billing, use_case, source, user_id is not null as has_account, created_at as joined_at, confirmed_at from founding_list where status = 'confirmed' order by confirmed_at, email",
        )
    await client.query("commit")

    const table = new Map(PLANS.map((plan) => [plan, Object.fromEntries(STATUSES.map((status) => [status, 0]))]))
    for (const { plan, status, count } of counts.rows) {
      if (!table.has(plan)) table.set(plan, Object.fromEntries(STATUSES.map((name) => [name, 0])))
      table.get(plan)[status] = count
    }
    const total = Object.fromEntries(STATUSES.map((status) => [status, [...table.values()].reduce((sum, row) => sum + (row[status] ?? 0), 0)]))
    const lines = ["Founding list, by plan", `${pad("plan", 10)}${STATUSES.map((status) => pad(status, 14)).join("")}`]
    for (const [plan, row] of [...table.entries(), ["total", total]]) lines.push(`${pad(plan, 10)}${STATUSES.map((status) => pad(row[status] ?? 0, 14)).join("")}`)
    lines.push("", "Confirmed, by plan, currency and billing")
    if (confirmedBy.rows.length === 0) lines.push("(none yet)")
    for (const { plan, currency, billing, count } of confirmedBy.rows) lines.push(`${pad(plan, 10)}${pad(currency, 6)}${pad(billing, 10)}${count}`)
    console.error(lines.join("\n"))

    if (!countsOnly) {
      const csv = [COLUMNS.join(","), ...members.rows.map((row) => COLUMNS.map((column) => csvCell(column === "has_account" ? (row[column] ? "yes" : "no") : row[column])).join(","))]
      process.stdout.write(`${csv.join("\r\n")}\r\n`)
      console.error(`\n${members.rows.length} confirmed ${members.rows.length === 1 ? "member" : "members"} written as CSV to standard output.`)
    }
  } finally {
    await client.end()
  }
}

// Run only as a script, so the CSV helper can be imported by tests.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    // Connection errors from pg name the host and user at most, never the password.
    console.error(`Export failed: ${error instanceof Error ? error.message : "unknown error"}`)
    process.exit(1)
  })
}
