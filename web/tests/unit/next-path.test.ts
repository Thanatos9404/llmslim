import { describe, expect, it } from "vitest"
import { DEFAULT_NEXT, sanitizeNext } from "@/lib/auth/next-path"

describe("sanitizeNext", () => {
  it.each([
    ["/account", "/account"],
    ["/docs/getting-started?tab=python#install", "/docs/getting-started?tab=python#install"],
    ["/playground", "/playground"],
    ["/sign-installer", "/sign-installer"],
  ])("keeps the same-origin path %s", (input, expected) => {
    expect(sanitizeNext(input)).toBe(expected)
  })

  it.each([
    "https://evil.example",
    "https://evil.example/account",
    "http://localhost:3000/account",
    "//evil.example",
    "//evil.example/account",
    "/\\evil.example",
    "\\\\evil.example",
    "/%2F%2Fevil.example",
    "/%2f/evil.example",
    "/%5Cevil.example",
    "%2F%2Fevil.example",
    "javascript:alert(1)",
    "data:text/html,hi",
    " //evil.example",
    "/account\nLocation: https://evil.example",
    "/%0d%0aSet-Cookie:x=1",
    "account",
    "",
    "/api/auth/sign-out",
    "/sign-in?next=/account",
    "/sign-up",
    "/reset-password?token=abc",
    "/_next/static/chunk.js",
    "/" + "a".repeat(600),
    "/%E0%A4%A",
  ])("rejects %j", (input) => {
    expect(sanitizeNext(input)).toBe(DEFAULT_NEXT)
  })

  it("rejects non-strings and uses the given fallback", () => {
    expect(sanitizeNext(undefined)).toBe(DEFAULT_NEXT)
    expect(sanitizeNext(["/account"])).toBe(DEFAULT_NEXT)
    expect(sanitizeNext(42, "/")).toBe("/")
  })
})
