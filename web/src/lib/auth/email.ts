/**
 * Transactional email for accounts: verification links, password reset links and notices.
 *
 * Production sends through Resend's HTTPS API (no SDK needed). Development writes the message,
 * including the link, to the server log; end-to-end tests use the file sink. Neither development
 * transport can run on Vercel (see config.ts), so links never reach shared logs there.
 */
import { mkdir, writeFile } from "node:fs/promises"
import path from "node:path"
import { randomUUID } from "node:crypto"
import type { EmailTransport } from "./config"

export type MailKind = "verify-email" | "reset-password" | "existing-account" | "password-changed" | "account-deleted"

export type Mail = { to: string; subject: string; text: string; html: string; kind: MailKind; url?: string }

const BRAND = "LLMSlim"

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] as string)
}

function layout(heading: string, paragraphs: string[], action?: { label: string; url: string }): string {
  const body = paragraphs.map((text) => `<p style="margin:0 0 16px;line-height:1.5">${escapeHtml(text)}</p>`).join("")
  const button = action
    ? `<p style="margin:24px 0"><a href="${escapeHtml(action.url)}" style="background:#141413;color:#fbfbfa;padding:12px 18px;border-radius:8px;text-decoration:none;display:inline-block">${escapeHtml(action.label)}</a></p><p style="margin:0 0 16px;line-height:1.5;color:#6b6a65;font-size:13px">Or paste this link into your browser:<br><span style="word-break:break-all">${escapeHtml(action.url)}</span></p>`
    : ""
  return `<!doctype html><html><body style="margin:0;padding:24px;background:#fbfbfa;color:#141413;font-family:Arial,Helvetica,sans-serif"><div style="max-width:520px;margin:0 auto"><h1 style="font-size:20px;margin:0 0 16px">${escapeHtml(heading)}</h1>${body}${button}<p style="margin:32px 0 0;color:#6b6a65;font-size:12px">${BRAND} · https://www.llmslim.app</p></div></body></html>`
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
