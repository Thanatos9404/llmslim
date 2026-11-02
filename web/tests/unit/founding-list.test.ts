/**
 * The founding list: input rules, the two kinds of link token, idempotent database steps, and the
 * HTTP handlers (no enumeration, origin checks, rate limits and the per-mailbox email budget),
 * against an in-process PGlite database with the real Better Auth configuration.
 */
import { describe, expect, it } from "vitest"
import { foundingListConfirmMail, foundingListMemberMail, type Mail } from "@/lib/auth/email"
import { foundingListFeatures } from "@/lib/founding-list/features"
import { foundingListHandlers } from "@/lib/founding-list/handlers"
import { confirmByToken, countConfirmed, joinWithAccount, leaveWithAccount, pruneFoundingList, requestByEmail, unsubscribeByToken } from "@/lib/founding-list/store"
import { confirmTokenHash, isConfirmToken, newConfirmToken, readUnsubscribeToken, unsubscribeToken } from "@/lib/founding-list/tokens"
import { USE_CASE_MAX, cleanUseCase, describeChoice, parseJoinRequest, validateUseCase, type Choice } from "@/lib/founding-list/validation"
import { resolveAuthConfig } from "@/lib/auth/config"
import { csvCell } from "../../scripts/founding-list-export.mjs"
import { ORIGIN, SECRET, baseEnv, testAuth, testDatabase, tokenFrom } from "./helpers"

const PRO: Choice = { plan: "pro", currency: "inr", billing: "monthly" }
const TEAM: Choice = { plan: "team", currency: "usd", billing: "annual" }
const PASSWORD = "correct horse battery staple"
const DAY = 24 * 60 * 60 * 1000

type Row = { id: string; email: string; user_id: string | null; plan: string; currency: string; billing: string; use_case: string | null; source: string; status: string; token_hash: string | null; confirmed_at: Date | null }

async function rows(client: { query: <T>(sql: string, params?: unknown[]) => Promise<{ rows: T[] }> }): Promise<Row[]> {
  return (await client.query<Row>("select * from founding_list order by created_at")).rows
}

describe("validation", () => {
  it("accepts a plan choice, trims and lower-cases the email, and defaults the source to pricing", () => {
    const parsed = parseJoinRequest({ ...PRO, email: "  Ada@Example.COM ", useCase: "  Memory for a\nsupport agent  " })
    expect(parsed).toEqual({ ok: true, value: { choice: PRO, source: "pricing", email: "ada@example.com", useCase: "Memory for a support agent" } })
    expect(parseJoinRequest({ ...TEAM })).toEqual({ ok: true, value: { choice: TEAM, source: "pricing", email: null, useCase: null } })
  })

  it("refuses Enterprise, unknown values, unknown sources and bodies that are not objects", () => {
    for (const body of [{ ...PRO, plan: "enterprise" }, { ...PRO, currency: "eur" }, { ...PRO, billing: "weekly" }, { ...PRO, source: "https://evil.example" }, { plan: "pro" }, null, [], "pro", 42]) {
      expect(parseJoinRequest(body)).toMatchObject({ ok: false, code: "INVALID_REQUEST" })
    }
  })

  it("rejects malformed emails with the accounts' own rule and words, and nothing else", () => {
    for (const email of ["", "   ", "ada", "ada@", "@example.com", "ada@example", "a b@example.com", "ada@@example.com", `${"a".repeat(250)}@example.com`, 42]) {
      expect(parseJoinRequest({ ...PRO, email })).toMatchObject({ ok: false, code: "INVALID_EMAIL" })
    }
    expect(parseJoinRequest({ ...PRO, email: "ada" })).toMatchObject({ message: "Enter a valid email address." })
    // No disposable-domain list and no lookups: a well-formed address is accepted.
    expect(parseJoinRequest({ ...PRO, email: "someone@mailinator.com" })).toMatchObject({ ok: true })
  })

  it("caps the use case at 280 characters, counting an emoji as one, after cleaning", () => {
    expect(validateUseCase("x".repeat(USE_CASE_MAX))).toBeNull()
    expect(validateUseCase("😀".repeat(USE_CASE_MAX))).toBeNull()
    expect(validateUseCase("x".repeat(USE_CASE_MAX + 1))).toBe("Use 280 characters or fewer.")
    expect(validateUseCase(`  ${"x".repeat(USE_CASE_MAX)}  \n\n `)).toBeNull()
    expect(parseJoinRequest({ ...PRO, email: "ada@example.com", useCase: "y".repeat(USE_CASE_MAX + 1) })).toMatchObject({ ok: false, code: "INVALID_USE_CASE" })
    expect(parseJoinRequest({ ...PRO, email: "ada@example.com", useCase: 7 })).toMatchObject({ ok: false, code: "INVALID_USE_CASE" })
    expect(cleanUseCase("a\u0000b‮c d\t e​f")).toBe("a b c d e f")
    expect(cleanUseCase("family \u{1F468}‍\u{1F469}‍\u{1F467}")).toBe("family \u{1F468}‍\u{1F469}‍\u{1F467}")
    expect(cleanUseCase(" \n\t ﻿")).toBeNull()
  })

  it("describes a choice in fixed words", () => {
    expect(describeChoice(PRO)).toBe("the Pro plan, in INR, billed monthly")
    expect(describeChoice(TEAM)).toBe("the Team plan, in USD, billed annually")
    expect(describeChoice({ plan: "free", currency: "usd", billing: "annual" })).toBe("the Free plan")
  })
})

describe("tokens", () => {
  it("makes 256-bit confirm tokens and stores only a keyed hash of them", () => {
    const token = newConfirmToken()
    expect(isConfirmToken(token)).toBe(true)
    expect(newConfirmToken()).not.toBe(token)
    for (const bad of ["", "short", `${token}x`, token.replace(/.$/, "="), null, 42]) expect(isConfirmToken(bad)).toBe(false)
    const hash = confirmTokenHash(SECRET, token)
    expect(hash).toMatch(/^[0-9a-f]{64}$/)
    expect(hash).toBe(confirmTokenHash(SECRET, token))
    expect(hash).not.toBe(confirmTokenHash(`${SECRET}-rotated`, token))
    expect(hash).not.toContain(token)
  })

  it("signs unsubscribe tokens, and refuses tampered, foreign or malformed ones", () => {
    const id = "6f1c2a52-8d0e-4c43-9a7b-2f0f5d1e9c11"
    const token = unsubscribeToken(SECRET, id)
    expect(readUnsubscribeToken(SECRET, token)).toBe(id)
    const [, signature] = token.split(".")
    const otherId = "6f1c2a52-8d0e-4c43-9a7b-2f0f5d1e9c12"
    expect(readUnsubscribeToken(SECRET, `${otherId}.${signature}`)).toBeNull()
    expect(readUnsubscribeToken(SECRET, `${id}.${signature.slice(0, -2)}AA`)).toBeNull()
    expect(readUnsubscribeToken(`${SECRET}-other`, token)).toBeNull()
    for (const bad of [undefined, null, 42, "", id, `${id}.`, `${token}.extra`, `NOT-A-UUID.${signature}`, "x".repeat(500)]) expect(readUnsubscribeToken(SECRET, bad)).toBeNull()
  })
})

describe("the founding_list table", () => {
  it("refuses values outside the allowed sets, and a second row for the same address", async () => {
    const { client } = await testDatabase()
    const insert = (values: string) => client.query(`insert into founding_list (email, plan, currency, billing, source) values ${values}`)
    await insert("('ada@example.com', 'pro', 'inr', 'monthly', 'pricing')")
    await expect(insert("('ada@example.com', 'team', 'usd', 'annual', 'pricing')")).rejects.toThrow()
    await expect(insert("('b@example.com', 'enterprise', 'inr', 'monthly', 'pricing')")).rejects.toThrow()
    await expect(insert("('b@example.com', 'pro', 'eur', 'monthly', 'pricing')")).rejects.toThrow()
    await expect(insert("('b@example.com', 'pro', 'inr', 'weekly', 'pricing')")).rejects.toThrow()
    await expect(insert("('b@example.com', 'pro', 'inr', 'monthly', 'Pricing Page')")).rejects.toThrow()
    await expect(client.query(`insert into founding_list (email, plan, currency, billing, source, use_case) values ('c@example.com', 'pro', 'inr', 'monthly', 'pricing', $1)`, ["x".repeat(281)])).rejects.toThrow()
    await expect(client.query(`update founding_list set status = 'maybe'`)).rejects.toThrow()
    expect((await rows(client)).map((row) => row.status)).toEqual(["pending"])
  })
})

describe("database steps are idempotent", () => {
  it("asking twice keeps one row, replaces the token and keeps the newest choice", async () => {
    const { db, client } = await testDatabase()
    const first = await requestByEmail(db, SECRET, { email: "Ada@Example.com", choice: PRO, useCase: "support agent", source: "pricing" })
    expect(first.kind).toBe("confirm")
    const second = await requestByEmail(db, SECRET, { email: "ada@example.com", choice: TEAM, useCase: null, source: "pricing" })
    expect(second.kind).toBe("confirm")
    expect(second.id).toBe(first.id)
    const [row] = await rows(client)
    expect(await rows(client)).toHaveLength(1)
    expect(row).toMatchObject({ email: "ada@example.com", plan: "team", currency: "usd", billing: "annual", use_case: "support agent", status: "pending", user_id: null })
    if (first.kind !== "confirm" || second.kind !== "confirm") throw new Error("expected confirm outcomes")
    // Only a keyed hash is stored, and only the newest link works.
    expect(row.token_hash).toBe(confirmTokenHash(SECRET, second.token))
    expect(JSON.stringify(row)).not.toContain(second.token)
    expect(await confirmByToken(db, SECRET, first.token)).toBeNull()
    expect(await confirmByToken(db, SECRET, second.token)).toEqual(TEAM)
  })

  it("confirming twice answers the same and keeps the first confirmation time", async () => {
    const { db, client } = await testDatabase()
    const outcome = await requestByEmail(db, SECRET, { email: "ada@example.com", choice: PRO, useCase: null, source: "pricing" })
    if (outcome.kind !== "confirm") throw new Error("expected a confirm outcome")
    expect(await confirmByToken(db, SECRET, outcome.token)).toEqual(PRO)
    const [confirmed] = await rows(client)
    expect(confirmed.status).toBe("confirmed")
    expect(await confirmByToken(db, SECRET, outcome.token)).toEqual(PRO)
    const [again] = await rows(client)
    expect(again.confirmed_at?.toISOString()).toBe(confirmed.confirmed_at?.toISOString())
    expect(await confirmByToken(db, SECRET, newConfirmToken())).toBeNull()
  })

  it("never changes a confirmed row for someone who has not shown they own the address", async () => {
    const { db, client } = await testDatabase()
    const outcome = await requestByEmail(db, SECRET, { email: "ada@example.com", choice: PRO, useCase: "agents", source: "pricing" })
    if (outcome.kind !== "confirm") throw new Error("expected a confirm outcome")
    await confirmByToken(db, SECRET, outcome.token)
    const [before] = await rows(client)
    const again = await requestByEmail(db, SECRET, { email: "ada@example.com", choice: TEAM, useCase: "something else", source: "pricing" })
    expect(again).toEqual({ kind: "already-confirmed", id: outcome.id, choice: PRO })
    const [after] = await rows(client)
    expect(after).toEqual(before)
  })

  it("unsubscribing twice is fine, drops the use case, and an old confirm link cannot undo it", async () => {
    const { db, client } = await testDatabase()
    const outcome = await requestByEmail(db, SECRET, { email: "ada@example.com", choice: PRO, useCase: "agents", source: "pricing" })
    if (outcome.kind !== "confirm") throw new Error("expected a confirm outcome")
    await confirmByToken(db, SECRET, outcome.token)
    const token = unsubscribeToken(SECRET, outcome.id)
    expect(await unsubscribeByToken(db, SECRET, token)).toBe(true)
    expect(await unsubscribeByToken(db, SECRET, token)).toBe(true)
    expect(await unsubscribeByToken(db, SECRET, `${token.slice(0, -1)}A`)).toBeNull()
    expect(await rows(client)).toMatchObject([{ status: "unsubscribed", use_case: null, token_hash: null }])
    expect(await confirmByToken(db, SECRET, outcome.token)).toBeNull()
    expect((await rows(client))[0].status).toBe("unsubscribed")
  })

  it("someone who left can ask again; they stay off the list until they follow the new link", async () => {
    const { db, client } = await testDatabase()
    const first = await requestByEmail(db, SECRET, { email: "ada@example.com", choice: PRO, useCase: null, source: "pricing" })
    await unsubscribeByToken(db, SECRET, unsubscribeToken(SECRET, first.id))
    const again = await requestByEmail(db, SECRET, { email: "ada@example.com", choice: TEAM, useCase: null, source: "pricing" })
    if (again.kind !== "confirm") throw new Error("expected a confirm outcome")
    expect((await rows(client))[0]).toMatchObject({ status: "unsubscribed", plan: "team" })
    expect(await countConfirmed(db)).toBe(0)
    expect(await confirmByToken(db, SECRET, again.token)).toEqual(TEAM)
    expect((await rows(client))[0].status).toBe("confirmed")
    expect(await countConfirmed(db)).toBe(1)
  })

  it("a signed-in join is confirmed at once; joining again updates the plan and keeps one row", async () => {
    const { db, client } = await testDatabase()
    await client.query(`insert into "user" (id, name, email, email_verified) values ('u1', 'Ada', 'ada@example.com', true)`)
    // An unconfirmed request for the same address is taken over by the account.
    await requestByEmail(db, SECRET, { email: "ada@example.com", choice: PRO, useCase: "agents", source: "pricing" })
    expect(await joinWithAccount(db, { id: "u1", email: "Ada@example.com" }, PRO, "pricing")).toEqual({ ...PRO, email: "ada@example.com" })
    const [first] = await rows(client)
    expect(first).toMatchObject({ user_id: "u1", status: "confirmed", token_hash: null, use_case: "agents" })
    expect(await joinWithAccount(db, { id: "u1", email: "ada@example.com" }, TEAM, "pricing")).toEqual({ ...TEAM, email: "ada@example.com" })
    const all = await rows(client)
    expect(all).toHaveLength(1)
    expect(all[0]).toMatchObject({ plan: "team", currency: "usd", billing: "annual", status: "confirmed" })
    expect(all[0].confirmed_at?.toISOString()).toBe(first.confirmed_at?.toISOString())

    expect(await leaveWithAccount(db, { id: "u1", email: "ada@example.com" })).toBe(true)
    expect(await leaveWithAccount(db, { id: "u1", email: "ada@example.com" })).toBe(false)
    expect(await rows(client)).toMatchObject([{ status: "unsubscribed", use_case: null }])
    // Joining again after leaving confirms again.
    await joinWithAccount(db, { id: "u1", email: "ada@example.com" }, PRO, "pricing")
    expect(await rows(client)).toMatchObject([{ status: "confirmed", plan: "pro" }])
    // Deleting the account deletes the row it joined with.
    await client.query(`delete from "user" where id = 'u1'`)
    expect(await rows(client)).toHaveLength(0)
  })

  it("the clean-up deletes requests whose link expired unconfirmed and forgets expired tokens", async () => {
    const { db, client } = await testDatabase()
    await requestByEmail(db, SECRET, { email: "stale@example.com", choice: PRO, useCase: "x", source: "pricing" })
    await requestByEmail(db, SECRET, { email: "live@example.com", choice: PRO, useCase: null, source: "pricing" })
    const confirmed = await requestByEmail(db, SECRET, { email: "member@example.com", choice: PRO, useCase: null, source: "pricing" })
    if (confirmed.kind !== "confirm") throw new Error("expected a confirm outcome")
    await confirmByToken(db, SECRET, confirmed.token)
    const left = await requestByEmail(db, SECRET, { email: "left@example.com", choice: PRO, useCase: null, source: "pricing" })
    await unsubscribeByToken(db, SECRET, unsubscribeToken(SECRET, left.id))
    await requestByEmail(db, SECRET, { email: "left@example.com", choice: PRO, useCase: "typed by a stranger", source: "pricing" })
    await client.query(`update founding_list set token_expires_at = now() - interval '1 minute' where email in ('stale@example.com', 'member@example.com', 'left@example.com')`)
    await pruneFoundingList(db)
    const after = await rows(client)
    expect(after.map((row) => row.email).sort()).toEqual(["left@example.com", "live@example.com", "member@example.com"])
    expect(after.find((row) => row.email === "member@example.com")).toMatchObject({ status: "confirmed", token_hash: null })
    expect(after.find((row) => row.email === "left@example.com")).toMatchObject({ status: "unsubscribed", token_hash: null, use_case: null })
    expect(after.find((row) => row.email === "live@example.com")?.token_hash).toMatch(/^[0-9a-f]{64}$/)
    // A confirm link stops working once it expires.
    const late = await requestByEmail(db, SECRET, { email: "late@example.com", choice: PRO, useCase: null, source: "pricing" })
    if (late.kind !== "confirm") throw new Error("expected a confirm outcome")
    await client.query(`update founding_list set token_expires_at = now() - interval '1 second' where email = 'late@example.com'`)
    expect(await confirmByToken(db, SECRET, late.token)).toBeNull()
    await pruneFoundingList(db, Date.now() + DAY)
    expect((await rows(client)).map((row) => row.email)).not.toContain("late@example.com")
  })
})

describe("emails", () => {
  it("carry fixed words and the plan, never the use case, with a one-line unsubscribe link and no images", () => {
    const confirm = foundingListConfirmMail("ada@example.com", PRO, `${ORIGIN}/founding-list/confirm?token=abc`, `${ORIGIN}/founding-list/unsubscribe?token=def`, 7)
    expect(confirm.kind).toBe("founding-list-confirm")
    expect(confirm.text).toContain("the Pro plan, in INR, billed monthly")
    expect(confirm.text).toContain(`Not you, or changed your mind? Unsubscribe: ${ORIGIN}/founding-list/unsubscribe?token=def`)
    expect(confirm.html).toContain(`href="${ORIGIN}/founding-list/unsubscribe?token=def"`)
    expect(confirm.html).not.toMatch(/<img|tracking|pixel/i)
    const member = foundingListMemberMail("ada@example.com", PRO, `${ORIGIN}/pricing`, `${ORIGIN}/founding-list/unsubscribe?token=def`, "founder@llmslim.app")
    expect(member.kind).toBe("founding-list-member")
    expect(member.url).toBeUndefined()
    expect(member.text).toContain("Nothing was changed.")
    expect(member.html).not.toMatch(/<img/i)
  })
})

describe("the export script's CSV", () => {
  it("quotes what needs quoting and defuses spreadsheet formulas typed into the use case", () => {
    expect(csvCell("ada@example.com")).toBe("ada@example.com")
    expect(csvCell(null)).toBe("")
    expect(csvCell('Memory, "fast"\nplease')).toBe('"Memory, ""fast""\nplease"')
    expect(csvCell("=HYPERLINK(\"https://evil.example\")")).toBe("\"'=HYPERLINK(\"\"https://evil.example\"\")\"")
    for (const start of ["+", "-", "@", "\t"]) expect(csvCell(`${start}1`).startsWith("'")).toBe(true)
    expect(csvCell(new Date("2026-11-02T10:00:00Z"))).toBe("2026-11-02T10:00:00.000Z")
  })
})

describe("what the pricing page offers", () => {
  it("keeps the email link when there is no database, and needs an email transport for the form", () => {
    const signedOut = new Headers()
    const signedIn = new Headers({ cookie: "llmslim.session_token=abc.def" })
    const secure = new Headers({ cookie: "__Secure-llmslim.session_token=abc.def" })
    const full = resolveAuthConfig(baseEnv)
    expect(foundingListFeatures(full, signedOut)).toEqual({ enabled: true, canEmail: true, signedIn: false })
    expect(foundingListFeatures(full, signedIn).signedIn).toBe(true)
    expect(foundingListFeatures(full, secure).signedIn).toBe(true)
    expect(foundingListFeatures(resolveAuthConfig({ ...baseEnv, DATABASE_URL: undefined }), signedIn)).toEqual({ enabled: false, canEmail: false, signedIn: false })
    const noMail = resolveAuthConfig({ ...baseEnv, NODE_ENV: "production", AUTH_DEV_MAIL: undefined, VERCEL: "1", BETTER_AUTH_SECRET: SECRET })
    expect(foundingListFeatures(noMail, signedOut)).toEqual({ enabled: true, canEmail: false, signedIn: false })
  })
})

async function setup() {
  const t = await testAuth()
  const mails: Mail[] = []
  const pending: Promise<unknown>[] = []
  const handlers = foundingListHandlers(t.config, t.db, t.auth, { background: (promise) => void pending.push(promise), mail: async (mail) => void mails.push(mail) })
  let ip = 1
  async function request(handler: keyof typeof handlers, init: { method?: string; body?: unknown; form?: string; origin?: string | null; cookie?: string; ip?: string; contentType?: string; headers?: Record<string, string> } = {}) {
    const headers = new Headers({ "x-real-ip": init.ip ?? `198.51.100.${ip++}`, "user-agent": "Mozilla/5.0 Chrome/140.0", ...init.headers })
    if (init.origin !== null) headers.set("origin", init.origin ?? ORIGIN)
    if (init.cookie) headers.set("cookie", init.cookie)
    let body: string | undefined
    if (init.form !== undefined) {
      headers.set("content-type", "application/x-www-form-urlencoded")
      body = init.form
    } else if (init.body !== undefined) {
      headers.set("content-type", init.contentType ?? "application/json")
      body = typeof init.body === "string" ? init.body : JSON.stringify(init.body)
    }
    const path = handler === "join" || handler === "leave" ? "/api/founding-list" : `/api/founding-list/${handler}`
    const response = await handlers[handler](new Request(new URL(path, ORIGIN), { method: init.method ?? (handler === "leave" ? "DELETE" : "POST"), headers, body }))
    while (pending.length) await Promise.allSettled(pending.splice(0))
    const text = await response.text()
    let json: Record<string, unknown> | null = null
    try {
      json = text ? (JSON.parse(text) as Record<string, unknown>) : null
    } catch {
      json = null
    }
    return { response, status: response.status, json }
  }
  async function signedIn(email = "ada@example.com") {
    await t.call("/sign-up/email", { body: { name: "Ada Lovelace", email, password: PASSWORD } })
    await t.call("/verify-email", { query: { token: tokenFrom(t.mails.filter((m) => m.kind === "verify-email" && m.to === email).pop()) } })
    const signIn = await t.call("/sign-in/email", { body: { email, password: PASSWORD } })
    expect(signIn.status).toBe(200)
    return signIn.cookie!
  }
  return { ...t, foundingMails: mails, request, signedIn }
}

describe("the join handler, signed out (double opt-in)", () => {
  it("emails a confirm link and an unsubscribe link; following them confirms, then unsubscribes", async () => {
    const t = await setup()
    const joined = await t.request("join", { body: { ...PRO, email: "Ada@Example.com", useCase: "Memory for <b>zebra</b> agents" } })
    expect(joined.status).toBe(200)
    expect(joined.json).toEqual({ status: "check_email" })
    expect(joined.response.headers.get("cache-control")).toBe("no-store")
    const [mail] = t.foundingMails
    expect(mail).toMatchObject({ to: "ada@example.com", kind: "founding-list-confirm" })
    expect(mail.url).toMatch(new RegExp(`^${ORIGIN}/founding-list/confirm\\?token=[A-Za-z0-9_-]{43}$`))
    expect(mail.unsubscribeUrl).toMatch(new RegExp(`^${ORIGIN}/founding-list/unsubscribe\\?token=`))
    expect(`${mail.subject}${mail.text}${mail.html}`).not.toContain("zebra")

    const confirmed = await t.request("confirm", { body: { token: tokenFrom(mail) } })
    expect(confirmed.status).toBe(200)
    expect(confirmed.json).toEqual({ status: "confirmed", ...PRO })
    expect(await rows(t.client)).toMatchObject([{ status: "confirmed", use_case: "Memory for <b>zebra</b> agents" }])

    const unsubscribe = new URL(mail.unsubscribeUrl!).searchParams.get("token")
    const left = await t.request("unsubscribe", { body: { token: unsubscribe } })
    expect(left.json).toEqual({ status: "unsubscribed" })
    expect(await rows(t.client)).toMatchObject([{ status: "unsubscribed" }])
  })

  it("answers the same for a new, a waiting, a confirmed and an unsubscribed address", async () => {
    const t = await setup()
    const answers: string[] = []
    const ask = async (email: string) => {
      const result = await t.request("join", { body: { ...PRO, email } })
      answers.push(JSON.stringify([result.status, result.json]))
    }
    const last = (email: string) => t.foundingMails.filter((mail) => mail.to === email).at(-1)!
    await ask("waiting@example.com")
    await ask("confirmed@example.com")
    await t.request("confirm", { body: { token: tokenFrom(last("confirmed@example.com")) } })
    await ask("left@example.com")
    await t.request("unsubscribe", { body: { token: new URL(last("left@example.com").unsubscribeUrl!).searchParams.get("token") } })
    for (const email of ["new@example.com", "waiting@example.com", "confirmed@example.com", "left@example.com"]) await ask(email)
    expect(new Set(answers)).toEqual(new Set([JSON.stringify([200, { status: "check_email" }])]))
    // What differs is only what arrives in the inbox: a confirmed address gets a notice, not a link.
    expect(["new", "waiting", "confirmed", "left"].map((name) => last(`${name}@example.com`).kind)).toEqual(["founding-list-confirm", "founding-list-confirm", "founding-list-member", "founding-list-confirm"])
  })

  it("rejects bad input with the same words as the form, and refuses other sites and non-JSON bodies", async () => {
    const t = await setup()
    expect((await t.request("join", { body: { ...PRO, email: "not-an-email" } })).json).toEqual({ code: "INVALID_EMAIL", message: "Enter a valid email address." })
    expect((await t.request("join", { body: { ...PRO, email: "ada@example.com", useCase: "z".repeat(300) } })).json).toEqual({ code: "INVALID_USE_CASE", message: "Use 280 characters or fewer." })
    expect((await t.request("join", { body: { ...PRO, plan: "enterprise", email: "ada@example.com" } })).status).toBe(400)
    expect((await t.request("join", { body: "{not json" })).status).toBe(400)
    expect((await t.request("join", { body: "plan=pro", contentType: "text/plain" })).status).toBe(415)
    expect((await t.request("join", { body: JSON.stringify({ ...PRO, email: "ada@example.com", pad: "x".repeat(5000) }) })).status).toBe(413)
    const foreign = await t.request("join", { body: { ...PRO, email: "ada@example.com" }, origin: "https://evil.example" })
    expect(foreign.status).toBe(403)
    expect(foreign.json?.code).toBe("INVALID_ORIGIN")
    expect(t.foundingMails).toHaveLength(0)
    expect(await rows(t.client)).toHaveLength(0)
  })

  it("limits requests per address and per network, and records the refusals", async () => {
    const t = await setup()
    for (let i = 0; i < 3; i++) expect((await t.request("join", { body: { ...PRO, email: "victim@example.com" } })).status).toBe(200)
    const limited = await t.request("join", { body: { ...PRO, email: "VICTIM@example.com" } })
    expect(limited.status).toBe(429)
    expect(limited.json?.message).toMatch(/^Too many attempts\. Try again in \d+ minutes?\.$/)
    expect(Number(limited.response.headers.get("retry-after"))).toBeGreaterThan(0)
    for (let i = 0; i < 10; i++) expect((await t.request("join", { body: { ...PRO, email: `n${i}@example.com` }, ip: "203.0.113.77" })).status).toBe(200)
    expect((await t.request("join", { body: { ...PRO, email: "n10@example.com" }, ip: "203.0.113.77" })).status).toBe(429)
    const events = await t.client.query<{ method: string; ip_hash: string | null }>("select method, ip_hash from auth_event where type = 'rate_limited'")
    expect(events.rows.map((row) => row.method)).toEqual(["/founding-list", "/founding-list"])
    const keys = await t.client.query<{ key: string }>("select key from rate_limit")
    for (const { key } of keys.rows) expect(key).not.toMatch(/victim|203\.0\.113/)
  })

  it("shares the per-mailbox email budget with the accounts emails", async () => {
    const t = await setup()
    // Different spellings of one inbox get past the per-address limit, but not the mailbox budget.
    for (let i = 0; i < 7; i++) expect((await t.request("join", { body: { ...PRO, email: `victim+${i}@example.com` } })).json).toEqual({ status: "check_email" })
    expect(t.foundingMails).toHaveLength(5)
    const skipped = await t.client.query<{ method: string }>("select method from auth_event where type = 'rate_limited'")
    expect(skipped.rows.map((row) => row.method)).toEqual(["email:founding-list-confirm", "email:founding-list-confirm"])
  })

  it("follows unsubscribe links from the no-JavaScript form with a redirect back to the page", async () => {
    const t = await setup()
    await t.request("join", { body: { ...PRO, email: "ada@example.com" } })
    const token = new URL(t.foundingMails[0].unsubscribeUrl!).searchParams.get("token")!
    const done = await t.request("unsubscribe", { form: new URLSearchParams({ token }).toString() })
    expect(done.status).toBe(303)
    expect(done.response.headers.get("location")).toBe(`${ORIGIN}/founding-list/unsubscribe?result=done`)
    // The pages send no referrer, so a browser may post from them with `Origin: null`; Sec-Fetch-Site still says same-origin.
    const join = await t.request("join", { body: { ...PRO, email: "grace@example.com" } })
    expect(join.status).toBe(200)
    const grace = new URL(t.foundingMails[1].unsubscribeUrl!).searchParams.get("token")!
    const sameSite = { "sec-fetch-site": "same-origin" }
    expect((await t.request("confirm", { body: { token: tokenFrom(t.foundingMails[1]) }, origin: "null", headers: sameSite })).json).toEqual({ status: "confirmed", ...PRO })
    const nullOrigin = await t.request("unsubscribe", { form: new URLSearchParams({ token: grace }).toString(), origin: "null", headers: sameSite })
    expect(nullOrigin.response.headers.get("location")).toBe(`${ORIGIN}/founding-list/unsubscribe?result=done`)
    for (const headers of [{ "sec-fetch-site": "cross-site" }, {}] as Record<string, string>[]) {
      expect((await t.request("unsubscribe", { form: new URLSearchParams({ token: grace }).toString(), origin: "null", headers })).status).toBe(403)
      expect((await t.request("confirm", { body: { token: tokenFrom(t.foundingMails[1]) }, origin: "null", headers })).status).toBe(403)
    }
    // The cookie-based actions never accept a null Origin.
    expect((await t.request("leave", { origin: "null", headers: sameSite })).status).toBe(403)
    const invalid = await t.request("unsubscribe", { form: "token=nope" })
    expect(invalid.response.headers.get("location")).toBe(`${ORIGIN}/founding-list/unsubscribe?result=invalid`)
    expect((await t.request("unsubscribe", { body: { token: "nope" } })).status).toBe(400)
    expect((await t.request("confirm", { body: { token: "nope" } })).status).toBe(400)
    expect((await t.request("confirm", { body: { token: newConfirmToken() } })).json).toEqual({ code: "INVALID_TOKEN", message: "This link is invalid or has expired." })
  })
})

describe("the join handler, signed in (one click)", () => {
  it("joins with the account's verified email, idempotently, and leaves", async () => {
    const t = await setup()
    const cookie = await t.signedIn("ada@example.com")
    const joined = await t.request("join", { body: PRO, cookie })
    expect(joined.status).toBe(200)
    expect(joined.json).toEqual({ status: "joined", ...PRO, email: "ada@example.com" })
    expect((await t.request("join", { body: TEAM, cookie })).json).toEqual({ status: "joined", ...TEAM, email: "ada@example.com" })
    const all = await rows(t.client)
    expect(all).toHaveLength(1)
    expect(all[0]).toMatchObject({ status: "confirmed", plan: "team" })
    expect(all[0].user_id).toBeTruthy()
    // No email is sent for a one-click join.
    expect(t.foundingMails).toHaveLength(0)

    expect((await t.request("leave", { cookie })).json).toEqual({ status: "left" })
    expect(await rows(t.client)).toMatchObject([{ status: "unsubscribed" }])
  })

  it("asks for an email when signed out, and needs our Origin to act on the session cookie", async () => {
    const t = await setup()
    const cookie = await t.signedIn("ada@example.com")
    expect((await t.request("join", { body: PRO })).json).toEqual({ code: "EMAIL_REQUIRED", message: "Enter your email address to join." })
    expect((await t.request("join", { body: PRO, cookie: "llmslim.session_token=forged" })).status).toBe(401)
    expect((await t.request("join", { body: PRO, cookie, origin: null })).status).toBe(403)
    expect((await t.request("join", { body: PRO, cookie, origin: "https://evil.example" })).status).toBe(403)
    expect((await t.request("leave", { cookie, origin: null })).status).toBe(403)
    expect((await t.request("leave", {})).status).toBe(401)
    expect(await rows(t.client)).toHaveLength(0)
  })
})
