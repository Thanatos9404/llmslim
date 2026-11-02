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
import { sql } from "drizzle-orm"
import { bigint, boolean, check, index, integer, pgTable, text, timestamp, uniqueIndex, uuid } from "drizzle-orm/pg-core"

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
 * requests on different serverless instances cannot slip past the limit. Keys are "ip|<hmac>" (of the
 * IP and path) or "email|<hmac>|<path>"; no raw email or IP is stored.
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

/**
 * The LLMSlim Orbit founding list: people who asked to hear when Orbit opens, and which plan they
 * looked at. One row per address (`email` is trimmed and lower-cased). Signed-in members join with
 * their verified account email and start confirmed; everyone else is `pending` until they follow the
 * link we email them. Only a keyed hash of that link's token is stored, and an unconfirmed row is
 * deleted once its link expires. Deleting an account deletes the row it joined with.
 */
export const foundingList = pgTable(
  "founding_list",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    userId: text("user_id").references(() => user.id, { onDelete: "cascade" }),
    email: text("email").notNull(),
    plan: text("plan", { enum: ["free", "pro", "team", "business"] }).notNull(),
    currency: text("currency", { enum: ["inr", "usd"] }).notNull(),
    billing: text("billing", { enum: ["monthly", "annual"] }).notNull(),
    /** Optional, typed by the visitor: what they will use Orbit for. Capped at 280 characters. */
    useCase: text("use_case"),
    /** Where they joined, a fixed slug such as "pricing". */
    source: text("source").notNull(),
    status: text("status", { enum: ["pending", "confirmed", "unsubscribed"] }).default("pending").notNull(),
    /** HMAC of the confirmation link's token; null once confirmed. */
    tokenHash: text("token_hash"),
    tokenExpiresAt: timestamp("token_expires_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    confirmedAt: timestamp("confirmed_at", { withTimezone: true }),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().$onUpdate(() => new Date()).notNull(),
  },
  (table) => [
    uniqueIndex("founding_list_email_idx").on(table.email),
    uniqueIndex("founding_list_token_hash_idx").on(table.tokenHash),
    index("founding_list_user_id_idx").on(table.userId),
    check("founding_list_plan_check", sql`${table.plan} in ('free', 'pro', 'team', 'business')`),
    check("founding_list_currency_check", sql`${table.currency} in ('inr', 'usd')`),
    check("founding_list_billing_check", sql`${table.billing} in ('monthly', 'annual')`),
    check("founding_list_status_check", sql`${table.status} in ('pending', 'confirmed', 'unsubscribed')`),
    check("founding_list_email_check", sql`char_length(${table.email}) <= 254`),
    check("founding_list_use_case_check", sql`char_length(${table.useCase}) <= 280`),
    check("founding_list_source_check", sql`${table.source} ~ '^[a-z0-9_-]{1,40}$'`),
  ],
)

export const authSchema = { user, session, account, verification, passkey }
export const schema = { ...authSchema, rateLimit, authEvent, foundingList }
