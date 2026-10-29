/**
 * Postgres-backed fixed-window rate limiting, shared by every serverless instance.
 *
 * `consume` is a single INSERT ... ON CONFLICT DO UPDATE ... RETURNING statement, so the read, the
 * window reset and the increment are one atomic step: concurrent requests cannot all pass a stale
 * read. Better Auth's limiter uses it through `rateLimit.customStorage`; the per-email limits in
 * server.ts call it directly.
 */
import { sql } from "drizzle-orm"
import type { PgDatabase, PgQueryResultHKT } from "drizzle-orm/pg-core"
import type { Rule } from "./rate-limits"

// Any Postgres driver Drizzle supports: node-postgres in production, PGlite in unit tests.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type AnyPgDatabase = PgDatabase<PgQueryResultHKT, any>

export type Decision = { allowed: boolean; retryAfter: number | null }

type Row = { count: number | string; window_start: number | string; window_seconds: number | string }

function rowsOf(result: unknown): Row[] {
  const rows = (result as { rows?: unknown }).rows
  return Array.isArray(rows) ? (rows as Row[]) : []
}

function decide(row: Row | undefined, max: number, now: number): Decision {
  if (!row) return { allowed: true, retryAfter: null }
  const count = Number(row.count)
  const end = Number(row.window_start) + Number(row.window_seconds) * 1000
  if (end <= now) return { allowed: true, retryAfter: null }
  return count <= max ? { allowed: true, retryAfter: null } : { allowed: false, retryAfter: Math.max(1, Math.ceil((end - now) / 1000)) }
}

export async function consume(db: AnyPgDatabase, key: string, rule: Rule, now: number = Date.now()): Promise<Decision> {
  const result = await db.execute(sql`
    insert into rate_limit (key, count, window_start, window_seconds)
    values (${key}, 1, ${now}, ${rule.window})
    on conflict (key) do update set
      count = case when rate_limit.window_start + rate_limit.window_seconds * 1000 <= ${now} then 1 else rate_limit.count + 1 end,
      window_start = case when rate_limit.window_start + rate_limit.window_seconds * 1000 <= ${now} then ${now} else rate_limit.window_start end,
      window_seconds = case when rate_limit.window_start + rate_limit.window_seconds * 1000 <= ${now} then ${rule.window} else greatest(rate_limit.window_seconds, ${rule.window}) end
    returning count, window_start, window_seconds`)
  if (Math.random() < 0.01) void prune(db, now).catch(() => undefined)
  return decide(rowsOf(result)[0], rule.max, now)
}

/** Whether the next request would be refused, without counting it. */
export async function peek(db: AnyPgDatabase, key: string, rule: Rule, now: number = Date.now()): Promise<Decision> {
  const result = await db.execute(sql`select count, window_start, window_seconds from rate_limit where key = ${key}`)
  const row = rowsOf(result)[0]
  if (!row) return { allowed: true, retryAfter: null }
  // The next attempt would make the count one higher.
  return decide({ ...row, count: Number(row.count) + 1 }, rule.max, now)
}

/** Drops counters whose window ended more than an hour ago. */
export async function prune(db: AnyPgDatabase, now: number = Date.now()): Promise<void> {
  await db.execute(sql`delete from rate_limit where window_start + window_seconds * 1000 < ${now - 3_600_000}`)
}
