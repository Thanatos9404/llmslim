/**
 * Transactional email for accounts and the founding list: verification links, password reset links,
 * founding-list confirmations and notices.
 *
 * Production sends through Resend's HTTPS API (no SDK needed). Development writes the message,
 * including the link, to the server log; end-to-end tests use the file sink. Neither development
 * transport can run on Vercel (see config.ts), so links never reach shared logs there.
 */
import { mkdir, writeFile } from "node:fs/promises"
import path from "node:path"
import { randomUUID } from "node:crypto"
import { describeChoice, type Choice } from "@/lib/founding-list/validation"
import type { EmailTransport } from "./config"

export type MailKind = "verify-email" | "reset-password" | "existing-account" | "password-changed" | "account-deleted" | "founding-list-confirm" | "founding-list-member"

export type Mail = { to: string; subject: string; text: string; html: string; kind: MailKind; url?: string; unsubscribeUrl?: string }

const BRAND = "LLMSlim"
const UNSUBSCRIBE_LINE = "Not you, or changed your mind?"

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] as string)
}

function layout(heading: string, paragraphs: string[], action?: { label: string; url: string }, unsubscribeUrl?: string): string {
  const body = paragraphs.map((text) => `<p style="margin:0 0 16px;line-height:1.5">${escapeHtml(text)}</p>`).join("")
  const button = action
    ? `<p style="margin:24px 0"><a href="${escapeHtml(action.url)}" style="background:#141413;color:#fbfbfa;padding:12px 18px;border-radius:8px;text-decoration:none;display:inline-block">${escapeHtml(action.label)}</a></p><p style="margin:0 0 16px;line-height:1.5;color:#6b6a65;font-size:13px">Or paste this link into your browser:<br><span style="word-break:break-all">${escapeHtml(action.url)}</span></p>`
    : ""
  const unsubscribe = unsubscribeUrl ? `<p style="margin:32px 0 0;color:#6b6a65;font-size:12px">${UNSUBSCRIBE_LINE} <a href="${escapeHtml(unsubscribeUrl)}" style="color:#6b6a65">Unsubscribe</a></p>` : ""
  return `<!doctype html><html><body style="margin:0;padding:24px;background:#fbfbfa;color:#141413;font-family:Arial,Helvetica,sans-serif"><div style="max-width:520px;margin:0 auto"><h1 style="font-size:20px;margin:0 0 16px">${escapeHtml(heading)}</h1>${body}${button}${unsubscribe}<p style="margin:${unsubscribe ? 8 : 32}px 0 0;color:#6b6a65;font-size:12px">${BRAND} · https://www.llmslim.app</p></div></body></html>`
}

/**
 * The name an email may greet its reader by. Until the address is verified, the name on the
 * account was typed by whoever signed up, who may not own the address: putting it in our email
 * would let a stranger write a line of their own (a fake offer, a link-like domain) into a message
 * that arrives from llmslim.app.
 */
export function greetingName(user: { name?: string | null; emailVerified?: boolean | null }): string | null {
  return user.emailVerified === true ? (user.name ?? null) : null
}

function greeting(name: string | null | undefined): string {
  const trimmed = name?.trim()
  return trimmed ? `Hi ${trimmed},` : "Hi,"
}

export function verificationMail(to: string, name: string | null | undefined, url: string): Mail {
  const lines = [greeting(name), `Confirm your email address to finish creating your ${BRAND} account. The link works once and expires in 1 hour.`, "If you did not create an account, you can ignore this email."]
  return { to, kind: "verify-email", url, subject: `Confirm your ${BRAND} email`, text: `${lines.join("\n\n")}\n\n${url}\n`, html: layout("Confirm your email", lines, { label: "Confirm email", url }) }
}

export function resetPasswordMail(to: string, name: string | null | undefined, url: string): Mail {
  const lines = [greeting(name), `Someone asked to reset the password for your ${BRAND} account. The link works once and expires in 1 hour. Resetting signs you out everywhere else.`, "If this was not you, ignore this email: your password stays the same."]
  return { to, kind: "reset-password", url, subject: `Reset your ${BRAND} password`, text: `${lines.join("\n\n")}\n\n${url}\n`, html: layout("Reset your password", lines, { label: "Choose a new password", url }) }
}

export function existingAccountMail(to: string, name: string | null | undefined, signInUrl: string, resetUrl: string): Mail {
  const lines = [greeting(name), `Someone tried to create a new ${BRAND} account with this email address, which already has an account. Nothing was changed.`, `To sign in, go to ${signInUrl}. If you forgot your password, reset it at ${resetUrl}.`, "If this was not you, you can ignore this email."]
  return { to, kind: "existing-account", subject: `You already have a ${BRAND} account`, text: `${lines.join("\n\n")}\n`, html: layout("You already have an account", lines, { label: "Sign in", url: signInUrl }) }
}

export function passwordChangedMail(to: string, name: string | null | undefined, resetUrl: string, change: "changed" | "added" = "changed"): Mail {
  const what =
    change === "added"
      ? `A password was just added to your ${BRAND} account, so you can now also sign in with your email and password.`
      : `The password for your ${BRAND} account was just changed, and your other sessions were signed out.`
  const lines = [greeting(name), what, `If this was not you, reset your password now at ${resetUrl} and review the sessions on your account page.`]
  const heading = change === "added" ? "A password was added to your account" : "Your password was changed"
  return { to, kind: "password-changed", subject: change === "added" ? `A password was added to your ${BRAND} account` : `Your ${BRAND} password was changed`, text: `${lines.join("\n\n")}\n`, html: layout(heading, lines) }
}

export function accountDeletedMail(to: string, name: string | null | undefined): Mail {
  const lines = [greeting(name), `Your ${BRAND} account and its sign-in methods, passkeys and sessions have been deleted.`, "If this was not you, reply to this email straight away."]
  return { to, kind: "account-deleted", subject: `Your ${BRAND} account was deleted`, text: `${lines.join("\n\n")}\n`, html: layout("Your account was deleted", lines) }
}

/**
 * The founding-list confirmation (double opt-in). Whoever typed the address may not own it, so the
 * email carries only fixed words and the plan chosen, never the free-text use case.
 */
export function foundingListConfirmMail(to: string, choice: Choice, url: string, unsubscribeUrl: string, ttlDays: number): Mail {
  const lines = [
    "Hi,",
    `Confirm that you want to join the founding list for ${BRAND} Orbit, the hosted edition that opens with ${BRAND} 1.0. We will email you when it opens. You chose ${describeChoice(choice)}; nothing is charged.`,
    `The link works for ${ttlDays} days. If you did not ask for this, ignore this email and you will not hear from us.`,
  ]
  return {
    to,
    kind: "founding-list-confirm",
    url,
    unsubscribeUrl,
    subject: `Confirm your place on the ${BRAND} founding list`,
    text: `${lines.join("\n\n")}\n\n${url}\n\n${UNSUBSCRIBE_LINE} Unsubscribe: ${unsubscribeUrl}\n`,
    html: layout("Confirm your place on the founding list", lines, { label: "Confirm and join", url }, unsubscribeUrl),
  }
}

/** Sent instead of a new link when the address is already confirmed: nothing was changed. */
export function foundingListMemberMail(to: string, choice: Choice, pricingUrl: string, unsubscribeUrl: string, contact: string): Mail {
  const lines = [
    "Hi,",
    `Someone asked to join the ${BRAND} Orbit founding list with this email address, which is already on it, for ${describeChoice(choice)}. Nothing was changed.`,
    `To change your plan, sign in with this address and choose it at ${pricingUrl}, or email ${contact}. If this was not you, you can ignore this email.`,
  ]
  return {
    to,
    kind: "founding-list-member",
    unsubscribeUrl,
    subject: `You are already on the ${BRAND} founding list`,
    text: `${lines.join("\n\n")}\n\n${UNSUBSCRIBE_LINE} Unsubscribe: ${unsubscribeUrl}\n`,
    html: layout("You are already on the founding list", lines, undefined, unsubscribeUrl),
  }
}

export class EmailNotConfiguredError extends Error {
  constructor() {
    super("No email transport is configured")
  }
}

export async function sendMail(transport: EmailTransport, mail: Mail): Promise<void> {
  switch (transport.mode) {
    case "resend": {
      const response = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: { authorization: `Bearer ${transport.apiKey}`, "content-type": "application/json", "idempotency-key": randomUUID() },
        body: JSON.stringify({ from: transport.from, to: [mail.to], subject: mail.subject, html: mail.html, text: mail.text }),
        signal: AbortSignal.timeout(10_000),
      })
      // The response body is not logged: it can echo the recipient.
      if (!response.ok) throw new Error(`Resend rejected the ${mail.kind} email with HTTP ${response.status}`)
      return
    }
    case "log": {
      console.info(`[accounts] development email (${mail.kind}) to ${mail.to}: ${mail.subject}${mail.url ? `\n[accounts] link: ${mail.url}` : ""}`)
      return
    }
    case "file": {
      await mkdir(transport.dir, { recursive: true })
      const name = `${Date.now()}-${randomUUID()}.json`
      await writeFile(path.join(transport.dir, name), JSON.stringify({ ...mail, sentAt: new Date().toISOString() }), "utf8")
      console.info(`[accounts] development email (${mail.kind}) to ${mail.to} written to ${path.join(transport.dir, name)}`)
      return
    }
    case "disabled":
      throw new EmailNotConfiguredError()
  }
}
