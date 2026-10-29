/**
 * Postgres schema for accounts. Migrations are generated from this file with drizzle-kit and
 * checked in under web/drizzle/.
 *
 * The first five tables follow Better Auth's core and passkey schemas (checked at runtime by
 * Better Auth's schema validation). Primary keys are 32-character random strings from Better Auth's
 * CSPRNG-backed generator, or random UUIDs for our own tables: never sequential, never guessable.
 *
 * Stored per user: name, email, email-verified flag, image URL, password hash (scrypt) for
 * email/password accounts, provider account ids, passkey public keys, and sessions (token, expiry,
 * user agent). OAuth access, refresh and ID tokens are not kept: the account hooks in
 * src/lib/auth/server.ts drop them before every write.
 */
import { bigint, boolean, index, integer, pgTable, text, timestamp, uniqueIndex, uuid } from "drizzle-orm/pg-core"

const timestamps = {
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().$onUpdate(() => new Date()).notNull(),
}

export const user = pgTable("user", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  email: text("email").notNull().unique(),
  emailVerified: boolean("email_verified").default(false).notNull(),
  image: text("image"),
  ...timestamps,
})

export const session = pgTable(
  "session",
  {
    id: text("id").primaryKey(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    token: text("token").notNull().unique(),
    ...timestamps,
    // Always null: the session hook drops the address (data minimisation). Kept for schema compatibility.
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    userId: text("user_id").notNull().references(() => user.id, { onDelete: "cascade" }),
  },
  (table) => [index("session_user_id_idx").on(table.userId)],
)

export const account = pgTable(
  "account",
  {
    id: text("id").primaryKey(),
    accountId: text("account_id").notNull(),
    providerId: text("provider_id").notNull(),
    userId: text("user_id").notNull().references(() => user.id, { onDelete: "cascade" }),
    // Always null for Google and GitHub (see the account hooks). Kept for schema compatibility.
    accessToken: text("access_token"),
    refreshToken: text("refresh_token"),
    idToken: text("id_token"),
    accessTokenExpiresAt: timestamp("access_token_expires_at", { withTimezone: true }),
    refreshTokenExpiresAt: timestamp("refresh_token_expires_at", { withTimezone: true }),
    scope: text("scope"),
    /** scrypt hash, credential accounts only. */
    password: text("password"),
    ...timestamps,
  },
  (table) => [
    index("account_user_id_idx").on(table.userId),
    uniqueIndex("account_provider_account_idx").on(table.providerId, table.accountId),
  ],
)

export const verification = pgTable(
  "verification",
  {
    id: text("id").primaryKey(),
    /** Stored hashed (verification.storeIdentifier = "hashed"), so a database leak exposes no live token. */
    identifier: text("identifier").notNull(),
    value: text("value").notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    ...timestamps,
  },
  (table) => [index("verification_identifier_idx").on(table.identifier)],
)

export const passkey = pgTable(
  "passkey",
  {
    id: text("id").primaryKey(),
    name: text("name"),
    publicKey: text("public_key").notNull(),
    userId: text("user_id").notNull().references(() => user.id, { onDelete: "cascade" }),
    credentialID: text("credential_id").notNull(),
    counter: integer("counter").notNull(),
    deviceType: text("device_type").notNull(),
    backedUp: boolean("backed_up").notNull(),
    transports: text("transports"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
    aaguid: text("aaguid"),
  },
  (table) => [index("passkey_user_id_idx").on(table.userId), uniqueIndex("passkey_credential_id_idx").on(table.credentialID)],
)

/**
 * Fixed-window counters for both rate-limit layers. One atomic upsert per request, so concurrent
 * requests on different serverless instances cannot slip past the limit. Keys are "ip|<path>" or
 * "email|<hmac>|<path>"; no raw email or IP is stored.
 */
export const rateLimit = pgTable(
  "rate_limit",
  {
    key: text("key").primaryKey(),
    count: integer("count").notNull(),
    windowStart: bigint("window_start", { mode: "number" }).notNull(),
    windowSeconds: integer("window_seconds").notNull(),
  },
  (table) => [index("rate_limit_window_start_idx").on(table.windowStart)],
)

/**
 * Security audit trail. No passwords, tokens or raw IP addresses, ever: the IP is an HMAC keyed by
 * the auth secret, and the user agent is truncated. `user_id` has no foreign key, so the record of
 * an account deletion outlives the account; rows older than 180 days are pruned.
 */
export const authEvent = pgTable(
  "auth_event",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: text("user_id"),
    type: text("type").notNull(),
    method: text("method"),
    ipHash: text("ip_hash"),
    userAgent: text("user_agent"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (table) => [index("auth_event_user_id_created_at_idx").on(table.userId, table.createdAt), index("auth_event_created_at_idx").on(table.createdAt)],
)

export const authSchema = { user, session, account, verification, passkey }
export const schema = { ...authSchema, rateLimit, authEvent }
