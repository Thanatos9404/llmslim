/**
 * A per-mailbox budget for the emails anyone can make us send without signing in: verification
 * links, reset links and "you already have an account" notices.
 *
 * The per-path limits in rate-limits.ts stop one form from being repeated, but a stranger can still
 * point several forms (and sign-in attempts on an unverified account, which resend the
 * verification link) at someone else's address, from many networks, and with spellings that all
 * reach the same inbox: `name+1@gmail.com`, `n.ame@gmail.com`. This budget counts every such email
 * per mailbox, whatever the path, so our domain cannot be used to flood an inbox and the provider's
 * daily quota stays for real users. When it is spent the email is skipped and the response stays
 * the same, so the budget reveals nothing about which addresses have accounts.
 *
 * Notices that only a signed-in user can trigger (password changed, account deleted) are not
 * counted: they are already limited per account, and they must not be suppressed.
 */
import { hashIdentifier } from "./audit"
import type { Mail, MailKind } from "./email"
import { consume, type AnyPgDatabase } from "./rate-limit-store"
import type { Rule } from "./rate-limits"

export const MAIL_BUDGET = {
  hour: { window: 60 * 60, max: 5 },
  day: { window: 24 * 60 * 60, max: 10 },
} as const satisfies Record<string, Rule>

export const BUDGETED_MAIL: ReadonlySet<MailKind> = new Set<MailKind>(["verify-email", "reset-password", "existing-account"])

/** Providers that ignore dots in the local part and treat googlemail.com as gmail.com. */
const DOTLESS_DOMAINS = new Set(["gmail.com", "googlemail.com"])

/**
 * The inbox an address delivers to, as far as we can tell: lower case, NFKC, no `+tag`, no trailing
 * dot on the domain, and for Gmail no dots in the local part. Used only as a budget key; accounts
 * keep the address exactly as it was entered.
 */
export function mailbox(email: string): string {
  const value = email.normalize("NFKC").trim().toLowerCase()
  const at = value.lastIndexOf("@")
  if (at <= 0 || at === value.length - 1) return value
  let local = value.slice(0, at)
  let domain = value.slice(at + 1).replace(/\.+$/, "")
  const plus = local.indexOf("+")
  if (plus > 0) local = local.slice(0, plus)
  if (DOTLESS_DOMAINS.has(domain)) {
    domain = "gmail.com"
    local = local.replace(/\./g, "") || local
  }
  return `${local}@${domain}`
}

/**
 * Counts one email against its mailbox and says whether it may be sent. Kinds outside the budget
 * are always allowed and are not counted.
 */
export async function withinMailBudget(db: AnyPgDatabase, secret: string, mail: Pick<Mail, "to" | "kind">, now: number = Date.now()): Promise<boolean> {
  if (!BUDGETED_MAIL.has(mail.kind)) return true
  const key = `mail|${hashIdentifier(secret, "email", mailbox(mail.to))}`
  const hour = await consume(db, `${key}|hour`, MAIL_BUDGET.hour, now)
  if (!hour.allowed) return false
  const day = await consume(db, `${key}|day`, MAIL_BUDGET.day, now)
  return day.allowed
}
