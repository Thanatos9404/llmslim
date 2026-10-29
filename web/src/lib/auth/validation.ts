/**
 * Field rules shared by the browser forms and the server, so both reject the same input with the
 * same words. The server is still the authority: Better Auth enforces the password length and the
 * breached-password check, and the hooks in server.ts enforce the name and email rules.
 */

export const PASSWORD_MIN = 10
export const PASSWORD_MAX = 128
export const NAME_MAX = 80
export const EMAIL_MAX = 254
export const PASSKEY_NAME_MAX = 60

// Deliberately simple: one "@", a dot in the domain, no spaces or control characters.
const EMAIL_PATTERN = /^[^\s@\u0000-\u001f\u007f]+@[^\s@\u0000-\u001f\u007f]+\.[^\s@\u0000-\u001f\u007f]+$/
// Letters, marks, numbers, spaces and a little punctuation; no angle brackets, URLs or control characters.
const NAME_PATTERN = /^[\p{L}\p{M}\p{N} .,'’\-]+$/u

export type FieldError = string | null

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase()
}

export function validateEmail(email: string): FieldError {
  const value = email.trim()
  if (!value) return "Enter your email address."
  if (value.length > EMAIL_MAX || !EMAIL_PATTERN.test(value)) return "Enter a valid email address."
  return null
}

export function validateName(name: string): FieldError {
  const value = name.trim()
  if (!value) return "Enter your name."
  if (value.length > NAME_MAX) return `Use ${NAME_MAX} characters or fewer.`
  if (!NAME_PATTERN.test(value) || /https?:|www\./i.test(value)) return "Use letters, numbers, spaces, hyphens and apostrophes only."
  return null
}

/** Counted in UTF-16 code units, exactly as Better Auth counts on the server, so the two always agree. */
export function passwordLength(password: string): number {
  return password.length
}

export function validatePassword(password: string): FieldError {
  if (!password) return "Enter a password."
  const length = passwordLength(password)
  if (length < PASSWORD_MIN) return `Use at least ${PASSWORD_MIN} characters.`
  if (length > PASSWORD_MAX) return `Use ${PASSWORD_MAX} characters or fewer.`
  return null
}

export function validatePasskeyName(name: string): FieldError {
  const value = name.trim()
  if (!value) return "Enter a name for this passkey."
  if (Array.from(value).length > PASSKEY_NAME_MAX) return `Use ${PASSKEY_NAME_MAX} characters or fewer.`
  if (/[\u0000-\u001f\u007f<>]/.test(value)) return "Use letters, numbers, spaces and punctuation only."
  return null
}

export type PasswordStrength = { score: 0 | 1 | 2 | 3 | 4; label: string; hint: string | null }

const COMMON_FRAGMENTS = ["password", "passw0rd", "qwerty", "123456", "letmein", "welcome", "admin", "llmslim", "iloveyou", "abc123", "monkey", "dragon"]

/**
 * A quick, offline estimate for feedback while typing. It is not a security control: the server
 * rejects passwords found in known breaches, whatever this score says.
 */
export function passwordStrength(password: string, context: string[] = []): PasswordStrength {
  if (!password) return { score: 0, label: "Too short", hint: `Use at least ${PASSWORD_MIN} characters.` }
  const length = passwordLength(password)
  if (length < PASSWORD_MIN) return { score: 0, label: "Too short", hint: `Use at least ${PASSWORD_MIN} characters.` }
  const lower = password.toLowerCase()
  const personal = context.map((part) => part.trim().toLowerCase()).filter((part) => part.length >= 3)
  if (personal.some((part) => lower.includes(part))) return { score: 1, label: "Weak", hint: "Avoid your name or email address." }
  if (COMMON_FRAGMENTS.some((fragment) => lower.includes(fragment))) return { score: 1, label: "Weak", hint: "Avoid common words and sequences." }
  if (/^(.)\1+$/.test(password)) return { score: 1, label: "Weak", hint: "Avoid repeating one character." }
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((pattern) => pattern.test(password)).length
  const unique = new Set(Array.from(password)).size
  let score = 1
  if (length >= 12) score += 1
  if (length >= 16) score += 1
  if (classes >= 3 || length >= 20) score += 1
  if (unique < 6) score = Math.min(score, 2)
  const bounded = Math.max(1, Math.min(4, score)) as 1 | 2 | 3 | 4
  const labels = { 1: "Weak", 2: "Fair", 3: "Good", 4: "Strong" } as const
  const hint = bounded >= 3 ? null : length < 16 ? "A longer passphrase of four or more words is stronger." : "Mix in more varied characters."
  return { score: bounded, label: labels[bounded], hint }
}
