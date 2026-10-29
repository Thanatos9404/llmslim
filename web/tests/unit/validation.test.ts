import { describe, expect, it } from "vitest"
import { passwordStrength, validateEmail, validateName, validatePasskeyName, validatePassword, PASSWORD_MAX, PASSWORD_MIN } from "@/lib/auth/validation"

describe("validatePassword mirrors the server (10 to 128 characters)", () => {
  it("accepts the bounds and rejects outside them", () => {
    expect(PASSWORD_MIN).toBe(10)
    expect(PASSWORD_MAX).toBe(128)
    expect(validatePassword("a".repeat(9))).toMatch(/at least 10/)
    expect(validatePassword("a".repeat(10))).toBeNull()
    expect(validatePassword("a".repeat(128))).toBeNull()
    expect(validatePassword("a".repeat(129))).toMatch(/128 characters or fewer/)
    expect(validatePassword("")).toBe("Enter a password.")
  })

  it("counts length the way Better Auth does (UTF-16 code units)", () => {
    expect(validatePassword("\u{1F510}".repeat(5))).toBeNull()
  })
})

describe("validateEmail", () => {
  it.each(["ada@example.com", "a.b+tag@sub.example.co.uk"])("accepts %s", (email) => expect(validateEmail(email)).toBeNull())
  it.each(["", "ada", "ada@", "@example.com", "ada@example", "a b@example.com", `${"a".repeat(250)}@example.com`])("rejects %j", (email) => expect(validateEmail(email)).not.toBeNull())
})

describe("validateName", () => {
  it.each(["Ada Lovelace", "José Núñez-O’Brien", "李小龙", "R2 D2"])("accepts %s", (name) => expect(validateName(name)).toBeNull())
  it.each(["", "   ", "<script>", "Visit https://evil.example", "www.evil.example", "a".repeat(81)])("rejects %j", (name) => expect(validateName(name)).not.toBeNull())
})

describe("validatePasskeyName", () => {
  it("accepts normal names and rejects markup, blanks and long names", () => {
    expect(validatePasskeyName("Work laptop")).toBeNull()
    expect(validatePasskeyName("<b>")).not.toBeNull()
    expect(validatePasskeyName("x".repeat(61))).not.toBeNull()
    expect(validatePasskeyName(" ")).not.toBeNull()
  })
})

describe("passwordStrength", () => {
  it("scores short, common and personal passwords low, and passphrases high", () => {
    expect(passwordStrength("short").score).toBe(0)
    expect(passwordStrength("password12345").score).toBe(1)
    expect(passwordStrength("adalovelace99!", ["Ada Lovelace", "adalovelace"]).score).toBe(1)
    expect(passwordStrength("aaaaaaaaaaaa").score).toBe(1)
    expect(passwordStrength("correct-horse-battery-staple").score).toBeGreaterThanOrEqual(3)
    expect(passwordStrength("Tr0ub4dor&3-Xyz").label).toMatch(/Good|Strong/)
  })
})
