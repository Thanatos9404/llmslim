import { and, asc, desc, eq, gt, sql } from "drizzle-orm"
import { getAuthenticatorName } from "@better-auth/passkey"
import { account, passkey, session } from "@/db/schema"
import { describeDevice } from "@/lib/auth/device"
import type { AnyPgDatabase } from "@/lib/auth/rate-limit-store"

export type AccountView = {
  user: { name: string; email: string; emailVerified: boolean; image: string | null }
  hasPassword: boolean
  /** Account row ids of connected providers (what unlinking takes), or null. */
  linked: { google: string | null; github: string | null }
  available: { google: boolean; github: boolean; passkey: boolean }
  /** Signed in recently enough for sensitive changes without signing in again. */
  fresh: boolean
  passkeys: { id: string; name: string; createdAt: string | null; authenticator: string | null; synced: boolean }[]
  sessions: { id: string; device: string; createdAt: string; lastActiveAt: string; current: boolean }[]
}

/** Whether a session was created within the last `maxAgeSeconds`. */
export function isFresh(createdAt: Date | string, maxAgeSeconds: number, now: number = Date.now()): boolean {
  return now - new Date(createdAt).getTime() < maxAgeSeconds * 1000
}

/** Everything the account page shows, read straight from the database and scoped to one user. */
export async function loadAccountView(db: AnyPgDatabase, userId: string, currentSessionId: string) {
  const [accounts, passkeys, sessions] = await Promise.all([
    // Only whether a password exists: the hash never leaves the database.
    db.select({ id: account.id, providerId: account.providerId, hasPassword: sql<boolean>`${account.password} is not null` }).from(account).where(eq(account.userId, userId)),
    db.select({ id: passkey.id, name: passkey.name, createdAt: passkey.createdAt, aaguid: passkey.aaguid, backedUp: passkey.backedUp }).from(passkey).where(eq(passkey.userId, userId)).orderBy(asc(passkey.createdAt)),
    db.select({ id: session.id, userAgent: session.userAgent, createdAt: session.createdAt, updatedAt: session.updatedAt }).from(session).where(and(eq(session.userId, userId), gt(session.expiresAt, new Date()))).orderBy(desc(session.updatedAt)),
  ])
  return {
    hasPassword: accounts.some((row) => row.providerId === "credential" && Boolean(row.hasPassword)),
    linked: { google: accounts.find((row) => row.providerId === "google")?.id ?? null, github: accounts.find((row) => row.providerId === "github")?.id ?? null },
    passkeys: passkeys.map((row) => ({
      id: row.id,
      name: row.name?.trim() || "Passkey",
      createdAt: row.createdAt ? row.createdAt.toISOString() : null,
      authenticator: getAuthenticatorName(row.aaguid) ?? null,
      synced: row.backedUp,
    })),
    sessions: sessions.map((row) => ({
      id: row.id,
      device: describeDevice(row.userAgent),
      createdAt: row.createdAt.toISOString(),
      lastActiveAt: row.updatedAt.toISOString(),
      current: row.id === currentSessionId,
    })),
  }
}
