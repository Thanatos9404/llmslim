/**
 * Abuse of the emails anyone can make us send: flooding someone else's inbox from our domain, and
 * writing your own words into those emails through the name field.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { greetingName, resetPasswordMail } from "@/lib/auth/email"
import { HOUSEKEEPING_INTERVAL_MS, housekeepingDue, pruneExpired } from "@/lib/auth/housekeeping"
import { BUDGETED_MAIL, MAIL_BUDGET, mailbox, withinMailBudget } from "@/lib/auth/mail-budget"
import { SECRET, testAuth, testDatabase, tokenFrom } from "./helpers"

const PASSWORD = "correct horse battery staple"
const BAIT = "Claim your refund at payout example dot com"
const HOUR = 60 * 60 * 1000

afterEach(() => {
  vi.useRealTimers()
})

function inbox(t: Awaited<ReturnType<typeof testAuth>>, address: string) {
  return t.mails.filter((mail) => mailbox(mail.to) === mailbox(address))
}

describe("mailbox", () => {
  it("maps the spellings that reach one inbox to one key", () => {
    expect(mailbox("Victim@Example.com")).toBe("victim@example.com")
    expect(mailbox("  victim+promo@example.com ")).toBe("victim@example.com")
    expect(mailbox("victim@example.com.")).toBe("victim@example.com")
    expect(mailbox("V.I.C.T.I.M+x@GoogleMail.com")).toBe("victim@gmail.com")
    expect(mailbox("v.ictim@gmail.com")).toBe("victim@gmail.com")
    expect(mailbox("ｖictim@gmail.com")).toBe("victim@gmail.com")
  })

  it("keeps dots outside Gmail, and leaves odd addresses usable as keys", () => {
    expect(mailbox("first.last@example.com")).toBe("first.last@example.com")
    expect(mailbox("+tag@example.com")).toBe("+tag@example.com")
    expect(mailbox("...@gmail.com")).toBe("...@gmail.com")
    expect(mailbox("no-at-sign")).toBe("no-at-sign")
    expect(mailbox("trailing@")).toBe("trailing@")
  })
})

describe("the per-mailbox email budget", () => {
  it("counts only the emails a stranger can trigger", async () => {
    const { db, client } = await testDatabase()
    expect([...BUDGETED_MAIL].sort()).toEqual(["existing-account", "reset-password", "verify-email"])
    for (let i = 0; i < 50; i++) expect(await withinMailBudget(db, SECRET, { to: "ada@example.com", kind: "password-changed" })).toBe(true)
    for (let i = 0; i < 50; i++) expect(await withinMailBudget(db, SECRET, { to: "ada@example.com", kind: "account-deleted" })).toBe(true)
    const rows = await client.query<{ count: number }>("select count(*)::int as count from rate_limit")
    expect(rows.rows[0].count).toBe(0)
  })

  it("allows five an hour and ten a day per mailbox, then resets", async () => {
    const { db } = await testDatabase()
    const start = Date.UTC(2026, 10, 1, 0, 0, 0)
    const send = (offset: number, to = "victim@example.com") => withinMailBudget(db, SECRET, { to, kind: "verify-email" }, start + offset)
    const firstHour = []
    for (let i = 0; i < 7; i++) firstHour.push(await send(i * 1000))
    expect(firstHour).toEqual([true, true, true, true, true, false, false])
    // Another mailbox has its own budget.
    expect(await send(8000, "someone-else@example.com")).toBe(true)
    // The hour resets; the day still counts the five already sent.
    const secondHour = []
    for (let i = 0; i < 6; i++) secondHour.push(await send(HOUR + 10_000 + i * 1000))
    expect(secondHour).toEqual([true, true, true, true, true, false])
    // Ten sent today: a third hour gets nothing until the day resets.
    expect(await send(2 * HOUR + 20_000)).toBe(false)
    expect(await send(24 * HOUR + 30_000)).toBe(true)
  })

  it("keys the budget by HMAC, so the table never holds an address", async () => {
    const { db, client } = await testDatabase()
    await withinMailBudget(db, SECRET, { to: "victim@example.com", kind: "reset-password" })
    const keys = await client.query<{ key: string }>("select key from rate_limit")
    expect(keys.rows.length).toBe(2)
    for (const row of keys.rows) {
      expect(row.key).toMatch(/^mail\|[0-9a-f]{64}\|(hour|day)$/)
      expect(row.key).not.toContain("victim")
    }
  })
})

describe("flooding an inbox through the accounts API", () => {
  it("stops repeated sign-ins on an unverified account from resending the link without limit", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { ip: t.nextIp(), body: { name: "Mallory", email: "victim@example.com", password: PASSWORD } })
    const statuses = new Set<number>()
    for (let attempt = 0; attempt < 20; attempt++) {
      // Each from a new network, so the per-IP limit never applies.
      statuses.add((await t.call("/sign-in/email", { ip: t.nextIp(), body: { email: "victim@example.com", password: PASSWORD } })).status)
    }
    // Every attempt still gets the same answer...
    expect([...statuses]).toEqual([403])
    // ...but the inbox gets at most the hourly budget.
    expect(inbox(t, "victim@example.com")).toHaveLength(MAIL_BUDGET.hour.max)
    const skipped = await t.client.query<{ method: string }>("select method from auth_event where type = 'rate_limited'")
    expect(skipped.rows.length).toBeGreaterThan(0)
    expect(skipped.rows.every((row) => row.method === "email:verify-email")).toBe(true)
  })

  it("treats plus tags and Gmail dots as the same inbox", async () => {
    const t = await testAuth()
    const spellings = ["victim@gmail.com", "victim+1@gmail.com", "v.ictim@gmail.com", "vi.ctim+2@gmail.com", "victim@googlemail.com", "VICTIM+3@gmail.com", "v.i.c.t.i.m@gmail.com", "victim+4@googlemail.com"]
    for (const email of spellings) {
      const up = await t.call("/sign-up/email", { ip: t.nextIp(), body: { name: "Mallory", email, password: PASSWORD } })
      // The response does not change when the email is skipped.
      expect(up.status).toBe(200)
    }
    expect(inbox(t, "victim@gmail.com")).toHaveLength(MAIL_BUDGET.hour.max)
  })

  it("shares one budget across sign-up, resend, reset and duplicate sign-up", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { ip: t.nextIp(), body: { name: "Mallory", email: "victim@example.com", password: PASSWORD } })
    for (let i = 0; i < 3; i++) await t.call("/send-verification-email", { ip: t.nextIp(), body: { email: `victim+${i}@example.com` } })
    for (let i = 0; i < 3; i++) await t.call("/request-password-reset", { ip: t.nextIp(), body: { email: "victim@example.com" } })
    for (let i = 0; i < 3; i++) await t.call("/sign-up/email", { ip: t.nextIp(), body: { name: "Mallory", email: "victim@example.com", password: "another long password" } })
    expect(inbox(t, "victim@example.com").length).toBeLessThanOrEqual(MAIL_BUDGET.hour.max)
  })

  it("still sends a real user their link", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    const mail = t.mails.find((m) => m.kind === "verify-email")
    expect((await t.call("/verify-email", { query: { token: tokenFrom(mail) } })).status).toBe(200)
    expect((await t.call("/sign-in/email", { body: { email: "ada@example.com", password: PASSWORD } })).status).toBe(200)
  })
})

describe("words a stranger can put in our email", () => {
  it("leaves the typed name out of every email to an address nobody has verified", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { ip: t.nextIp(), body: { name: BAIT, email: "victim@example.com", password: PASSWORD } })
    await t.call("/request-password-reset", { ip: t.nextIp(), body: { email: "victim@example.com" } })
    await t.call("/sign-up/email", { ip: t.nextIp(), body: { name: "Someone Else", email: "victim@example.com", password: "another long password" } })
    const kinds = t.mails.map((mail) => mail.kind).sort()
    expect(kinds).toEqual(["existing-account", "reset-password", "verify-email"])
    for (const mail of t.mails) {
      expect(mail.text, mail.kind).not.toContain("refund")
      expect(mail.html, mail.kind).not.toContain("refund")
      expect(mail.text.startsWith("Hi,\n"), mail.kind).toBe(true)
    }
  })

  it("greets a verified owner by name", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    await t.call("/verify-email", { query: { token: tokenFrom(t.mails.find((m) => m.kind === "verify-email")) } })
    await t.call("/request-password-reset", { ip: t.nextIp(), body: { email: "ada@example.com" } })
    const reset = t.mails.find((m) => m.kind === "reset-password")
    expect(reset?.text.startsWith("Hi Ada Lovelace,\n")).toBe(true)
  })

  it("decides the greeting from the verified flag alone", () => {
    expect(greetingName({ name: "Ada", emailVerified: true })).toBe("Ada")
    expect(greetingName({ name: "Ada", emailVerified: false })).toBeNull()
    expect(greetingName({ name: "Ada" })).toBeNull()
    expect(greetingName({ name: null, emailVerified: true })).toBeNull()
    expect(resetPasswordMail("a@example.com", greetingName({ name: BAIT, emailVerified: false }), "https://x.example/r").text).not.toContain(BAIT)
  })
})

describe("pruneExpired", () => {
  it("deletes expired verification values and sessions, and keeps live ones", async () => {
    const t = await testAuth()
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email: "ada@example.com", password: PASSWORD } })
    await t.call("/verify-email", { query: { token: tokenFrom(t.mails.find((m) => m.kind === "verify-email")) } })
    const signIn = await t.call("/sign-in/email", { body: { email: "ada@example.com", password: PASSWORD } })
    expect(signIn.status).toBe(200)
    const userId = (signIn.json?.user as { id: string }).id
    await t.client.query("insert into session (id, expires_at, token, user_id) values ('old-session', now() - interval '1 day', 'old-token', $1)", [userId])
    await t.client.query("insert into verification (id, identifier, value, expires_at) values ('old-state', 'state-1', 'x', now() - interval '1 minute'), ('live-state', 'state-2', 'y', now() + interval '10 minutes')")
    await pruneExpired(t.db)
    const sessions = await t.client.query<{ id: string }>("select id from session")
    expect(sessions.rows.map((row) => row.id)).not.toContain("old-session")
    expect(sessions.rows.length).toBe(1)
    const verifications = await t.client.query<{ id: string }>("select id from verification")
    const ids = verifications.rows.map((row) => row.id)
    expect(ids).toContain("live-state")
    expect(ids).not.toContain("old-state")
    // The live session still works after the clean-up.
    expect((await t.call("/get-session", { cookie: signIn.cookie })).json).not.toBeNull()
  })

  it("deletes security log entries past 180 days and counters whose window ended, as the privacy policy says", async () => {
    const t = await testAuth()
    const now = Date.now()
    await t.client.query("delete from auth_event")
    await t.client.query("delete from rate_limit")
    await t.client.query(
      "insert into auth_event (type, created_at) values ('sign_in_success', now() - interval '181 days'), ('sign_in_success', now() - interval '179 days')",
    )
    await t.client.query("insert into rate_limit (key, count, window_start, window_seconds) values ('ended', 1, $1, 86400), ('open', 1, $2, 86400)", [
      now - 24 * HOUR - 2 * HOUR,
      now - 23 * HOUR,
    ])
    await pruneExpired(t.db, now)
    const events = await t.client.query<{ age: number }>("select extract(day from now() - created_at)::int as age from auth_event")
    expect(events.rows.map((row) => row.age)).toEqual([179])
    const counters = await t.client.query<{ key: string }>("select key from rate_limit")
    expect(counters.rows.map((row) => row.key)).toEqual(["open"])
  })
})

describe("housekeepingDue", () => {
  it("runs on an instance's first request, then at most once per interval", () => {
    const start = 1_900_000_000_000
    housekeepingDue(start) // whatever an earlier test left, this instance has now run
    expect(housekeepingDue(start + 1)).toBe(false)
    expect(housekeepingDue(start + HOUSEKEEPING_INTERVAL_MS - 1)).toBe(false)
    expect(housekeepingDue(start + HOUSEKEEPING_INTERVAL_MS)).toBe(true)
    expect(housekeepingDue(start + HOUSEKEEPING_INTERVAL_MS + 1)).toBe(false)
  })
})
