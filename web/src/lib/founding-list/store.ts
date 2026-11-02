/**
 * Database steps for the founding list. Each is one statement, so concurrent requests cannot leave a
 * row half-changed, and every step can be repeated safely: joining twice keeps one row, confirming or
 * unsubscribing twice changes nothing more.
 */
import { sql } from "drizzle-orm"
import { normalizeEmail } from "@/lib/auth/validation"
import type { AnyPgDatabase } from "@/lib/auth/rate-limit-store"
import { CONFIRM_TOKEN_TTL_SECONDS, confirmTokenHash, newConfirmToken, readUnsubscribeToken } from "./tokens"
import type { Choice, FoundingSource } from "./validation"

export type Status = "pending" | "confirmed" | "unsubscribed"

type Row = Record<string, unknown>

function rowsOf(result: unknown): Row[] {
  const rows = (result as { rows?: unknown }).rows
  return Array.isArray(rows) ? (rows as Row[]) : []
}

function choiceOf(row: Row): Choice {
  return { plan: row.plan, currency: row.currency, billing: row.billing } as Choice
}

/**
 * A signed-in member joins, or changes their plan, with their account's verified email. The row is
 * confirmed at once: the address was verified when the account was made.
 */
export async function joinWithAccount(db: AnyPgDatabase, user: { id: string; email: string }, choice: Choice, source: FoundingSource): Promise<Choice & { email: string }> {
  const email = normalizeEmail(user.email)
  const result = await db.execute(sql`
    insert into founding_list (user_id, email, plan, currency, billing, source, status, confirmed_at)
    values (${user.id}, ${email}, ${choice.plan}, ${choice.currency}, ${choice.billing}, ${source}, 'confirmed', now())
    on conflict (email) do update set
      user_id = excluded.user_id,
      plan = excluded.plan,
      currency = excluded.currency,
      billing = excluded.billing,
      status = 'confirmed',
      confirmed_at = case when founding_list.status = 'confirmed' then founding_list.confirmed_at else now() end,
      token_hash = null,
      token_expires_at = null,
      updated_at = now()
    returning email, plan, currency, billing`)
  const row = rowsOf(result)[0]
  return { ...choiceOf(row), email: String(row.email) }
}

/** A signed-in member leaves the list. True when they were on it. */
export async function leaveWithAccount(db: AnyPgDatabase, user: { id: string; email: string }): Promise<boolean> {
  const result = await db.execute(sql`
    update founding_list set status = 'unsubscribed', use_case = null, token_hash = null, token_expires_at = null, updated_at = now()
    where (email = ${normalizeEmail(user.email)} or user_id = ${user.id}) and status <> 'unsubscribed'
    returning id`)
  return rowsOf(result).length > 0
}

export type EmailRequestOutcome =
  /** Send the confirmation email with this token: a new address, an unconfirmed one, or one that left and asks again. */
  | { kind: "confirm"; id: string; token: string; choice: Choice }
  /** Already confirmed: nothing is changed, and the address gets a short notice instead of a link. */
  | { kind: "already-confirmed"; id: string; choice: Choice }

/**
 * Someone who is not signed in asks to join with an email address. Nobody has shown they own the
 * address yet, so a confirmed row is never changed. Any other row gets the new choice and a new
 * confirm token, which replaces (and so invalidates) the previous one; it stays unconfirmed until
 * the link is followed. The caller answers the same way in every case.
 */
export async function requestByEmail(db: AnyPgDatabase, secret: string, input: { email: string; choice: Choice; useCase: string | null; source: FoundingSource }): Promise<EmailRequestOutcome> {
  const token = newConfirmToken()
  const hash = confirmTokenHash(secret, token)
  const result = await db.execute(sql`
    insert into founding_list (email, plan, currency, billing, use_case, source, status, token_hash, token_expires_at)
    values (${normalizeEmail(input.email)}, ${input.choice.plan}, ${input.choice.currency}, ${input.choice.billing}, ${input.useCase}, ${input.source}, 'pending', ${hash}, now() + make_interval(secs => ${CONFIRM_TOKEN_TTL_SECONDS}))
    on conflict (email) do update set
      plan = case when founding_list.status = 'confirmed' then founding_list.plan else excluded.plan end,
      currency = case when founding_list.status = 'confirmed' then founding_list.currency else excluded.currency end,
      billing = case when founding_list.status = 'confirmed' then founding_list.billing else excluded.billing end,
      use_case = case when founding_list.status = 'confirmed' then founding_list.use_case else coalesce(excluded.use_case, founding_list.use_case) end,
      token_hash = case when founding_list.status = 'confirmed' then founding_list.token_hash else excluded.token_hash end,
      token_expires_at = case when founding_list.status = 'confirmed' then founding_list.token_expires_at else excluded.token_expires_at end,
      updated_at = case when founding_list.status = 'confirmed' then founding_list.updated_at else now() end
    returning id, status, plan, currency, billing`)
  const row = rowsOf(result)[0]
  const id = String(row.id)
  if (row.status === "confirmed") return { kind: "already-confirmed", id, choice: choiceOf(row) }
  return { kind: "confirm", id, token, choice: choiceOf(row) }
}

/**
 * Follows a confirm link. The token keeps working until it expires, so opening the link twice
 * answers "confirmed" both times; unsubscribing clears it, so an old link cannot undo that.
 */
export async function confirmByToken(db: AnyPgDatabase, secret: string, token: string): Promise<Choice | null> {
  const result = await db.execute(sql`
    update founding_list set
      status = 'confirmed',
      confirmed_at = coalesce(case when status = 'confirmed' then confirmed_at end, now()),
      updated_at = now()
    where token_hash = ${confirmTokenHash(secret, token)} and token_expires_at > now()
    returning plan, currency, billing`)
  const row = rowsOf(result)[0]
  return row ? choiceOf(row) : null
}

/**
 * Follows an unsubscribe link. Null when the token is not one we made; true otherwise, also when the
 * row is gone (an expired request, or a deleted account): either way the address is off the list.
 * The free-text use case is dropped with the subscription.
 */
export async function unsubscribeByToken(db: AnyPgDatabase, secret: string, token: unknown): Promise<true | null> {
  const id = readUnsubscribeToken(secret, token)
  if (!id) return null
  await db.execute(sql`
    update founding_list set status = 'unsubscribed', use_case = null, token_hash = null, token_expires_at = null, updated_at = now()
    where id = ${id} and status <> 'unsubscribed'`)
  return true
}

/** Confirmed members, for the optional public counter (off by default). */
export async function countConfirmed(db: AnyPgDatabase): Promise<number> {
  const result = await db.execute(sql`select count(*)::int as count from founding_list where status = 'confirmed'`)
  return Number(rowsOf(result)[0]?.count ?? 0)
}

/**
 * Deletes requests whose confirm link expired unconfirmed (nobody showed they own the address), and
 * forgets expired tokens on the other rows, with the use case typed by whoever asked to rejoin an
 * unsubscribed address and never confirmed. Run by the accounts clean-up.
 */
export async function pruneFoundingList(db: AnyPgDatabase, now: number = Date.now()): Promise<void> {
  const cutoff = new Date(now).toISOString()
  await db.execute(sql`delete from founding_list where status = 'pending' and token_expires_at < ${cutoff}::timestamptz`)
  await db.execute(sql`
    update founding_list set token_hash = null, token_expires_at = null, use_case = case when status = 'unsubscribed' then null else use_case end
    where status <> 'pending' and token_expires_at < ${cutoff}::timestamptz`)
}
