/**
 * Deletes rows that can no longer be used: expired verification values (email and reset tokens,
 * OAuth state, passkey challenges and the markers of used links) and expired sessions. Better Auth
 * removes some of these when they are next looked up; this catches the ones nobody looks up again,
 * such as OAuth sign-ins that were started and abandoned. It runs on a small sample of auth
 * requests (see server.ts), so no scheduled job is needed.
 */
import { sql } from "drizzle-orm"
import type { AnyPgDatabase } from "./rate-limit-store"

/** The share of auth requests that also run the clean-up. */
export const HOUSEKEEPING_SAMPLE = 0.005

export async function pruneExpired(db: AnyPgDatabase, now: number = Date.now()): Promise<void> {
  const cutoff = new Date(now).toISOString()
  await db.execute(sql`delete from verification where expires_at < ${cutoff}::timestamptz`)
  await db.execute(sql`delete from session where expires_at < ${cutoff}::timestamptz`)
}
