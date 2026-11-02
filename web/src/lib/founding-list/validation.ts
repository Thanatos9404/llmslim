/**
 * Input rules for the LLMSlim Orbit founding list, shared by the pricing page's form and the API so
 * both reject the same input with the same words. The server is the authority.
 *
 * Email addresses use the accounts rules (src/lib/auth/validation.ts) and nothing else: no lookups,
 * no third-party checks.
 */
import { BILLINGS, CURRENCIES, type Billing, type Currency, type PlanId } from "@/data/pricing"
import { normalizeEmail, validateEmail, type FieldError } from "@/lib/auth/validation"

/** The plans the founding list takes. Enterprise is a conversation, not a list (its button emails us). */
export const FOUNDING_PLANS = ["free", "pro", "team", "business"] as const satisfies readonly PlanId[]
export type FoundingPlan = (typeof FOUNDING_PLANS)[number]

/** Where someone joined from. A fixed slug, never free text. */
export const FOUNDING_SOURCES = ["pricing"] as const
export type FoundingSource = (typeof FOUNDING_SOURCES)[number]

/** Counted in characters (code points), as Postgres's char_length counts them. */
export const USE_CASE_MAX = 280

/** How long an emailed confirmation link works. */
export const CONFIRM_LINK_DAYS = 7

export type Choice = { plan: FoundingPlan; currency: Currency; billing: Billing }

export type JoinRequest = {
  choice: Choice
  source: FoundingSource
  /** Lower-cased and trimmed. Null: join with the signed-in account's email. */
  email: string | null
  useCase: string | null
}

export type ParseResult = { ok: true; value: JoinRequest } | { ok: false; code: "INVALID_REQUEST" | "INVALID_EMAIL" | "INVALID_USE_CASE"; message: string }

function oneOf<T extends string>(value: unknown, options: readonly T[]): value is T {
  return typeof value === "string" && (options as readonly string[]).includes(value)
}

export function isFoundingPlan(value: unknown): value is FoundingPlan {
  return oneOf(value, FOUNDING_PLANS)
}

/**
 * Control characters, line breaks and invisible direction marks become spaces (the zero-width joiner
 * stays, for emoji), runs of spaces become one, ends are trimmed. Empty is null.
 */
export function cleanUseCase(value: string): string | null {
  const clean = value.normalize("NFC").replace(/[\u0000-\u001f\u007f-\u009f\u200b\u200e\u200f\u2028-\u202e\u2066-\u2069\ufeff]/g, " ").replace(/\s+/g, " ").trim()
  return clean ? clean : null
}

export function validateUseCase(value: string): FieldError {
  const clean = cleanUseCase(value)
  if (clean && Array.from(clean).length > USE_CASE_MAX) return `Use ${USE_CASE_MAX} characters or fewer.`
  return null
}

/** Parses the JSON body of a join request. Unknown fields are ignored. */
export function parseJoinRequest(body: unknown): ParseResult {
  const invalid = { ok: false, code: "INVALID_REQUEST", message: "Choose a plan, a currency and a billing period." } as const
  if (typeof body !== "object" || body === null || Array.isArray(body)) return invalid
  const input = body as Record<string, unknown>
  if (!isFoundingPlan(input.plan) || !oneOf(input.currency, CURRENCIES) || !oneOf(input.billing, BILLINGS)) return invalid
  const source = input.source === undefined ? "pricing" : input.source
  if (!oneOf(source, FOUNDING_SOURCES)) return invalid

  let email: string | null = null
  if (input.email !== undefined && input.email !== null) {
    if (typeof input.email !== "string") return { ok: false, code: "INVALID_EMAIL", message: "Enter a valid email address." }
    const error = validateEmail(input.email)
    if (error) return { ok: false, code: "INVALID_EMAIL", message: error }
    email = normalizeEmail(input.email)
  }

  let useCase: string | null = null
  if (input.useCase !== undefined && input.useCase !== null) {
    if (typeof input.useCase !== "string" || input.useCase.length > USE_CASE_MAX * 8) return { ok: false, code: "INVALID_USE_CASE", message: `Use ${USE_CASE_MAX} characters or fewer.` }
    const error = validateUseCase(input.useCase)
    if (error) return { ok: false, code: "INVALID_USE_CASE", message: error }
    useCase = cleanUseCase(input.useCase)
  }

  return { ok: true, value: { choice: { plan: input.plan, currency: input.currency, billing: input.billing }, source, email, useCase } }
}

/** How a choice reads in a sentence: "the Pro plan, in INR, billed monthly", or "the Free plan". Fixed words only. */
export function describeChoice(choice: Choice): string {
  const plan = `the ${choice.plan.charAt(0).toUpperCase()}${choice.plan.slice(1)} plan`
  if (choice.plan === "free") return plan
  return `${plan}, in ${choice.currency.toUpperCase()}, billed ${choice.billing === "annual" ? "annually" : "monthly"}`
}
