/**
 * Deletes rows past their use or their retention period: expired verification values (email and
 * reset tokens, OAuth state, passkey challenges and the markers of used links), expired sessions,
 * rate-limit counters whose window has ended, and security log entries older than 180 days. Better
 * Auth removes some of these when they are next looked up; this catches the ones nobody looks up
 * again, such as OAuth sign-ins that were started and abandoned.
 *
 * Each server instance runs it on its first auth request and then at most every 10 minutes (see
 * server.ts), so the retention periods in the privacy policy hold whenever the site is in use,
 * without a scheduled job.
 */
import { sql } from "drizzle-orm"
import { AUDIT_RETENTION_DAYS } from "./audit"
import { prune as pruneRateLimits, type AnyPgDatabase } from "./rate-limit-store"

export const HOUSEKEEPING_INTERVAL_MS = 10 * 60 * 1000

let lastRun = Number.NEGATIVE_INFINITY

/** Whether this instance is due to run the clean-up; a true answer counts as the run. */
export function housekeepingDue(now: number = Date.now()): boolean {
  if (now - lastRun < HOUSEKEEPING_INTERVAL_MS) return false
  lastRun = now
  return true
}

export async function pruneExpired(db: AnyPgDatabase, now: number = Date.now()): Promise<void> {
  const cutoff = new Date(now).toISOString()
  await db.execute(sql`delete from verification where expires_at < ${cutoff}::timestamptz`)
  await db.execute(sql`delete from session where expires_at < ${cutoff}::timestamptz`)
  await pruneRateLimits(db, now)
  await db.execute(sql`delete from auth_event where created_at < ${cutoff}::timestamptz - make_interval(days => ${AUDIT_RETENTION_DAYS})`)
}
