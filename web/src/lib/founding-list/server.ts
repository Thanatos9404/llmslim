/**
 * The founding-list handlers for this deployment, built once per server instance on the accounts
 * database, and the optional public count. Nothing here runs at import time, so `next build` needs
 * no database.
 */
import { getAuthConfig } from "@/lib/auth/config"
import { unavailableResponse } from "@/lib/auth/http"
import { getAuthInstance } from "@/lib/auth/server"
import { foundingListHandlers, type FoundingListHandlers } from "./handlers"
import { countConfirmed } from "./store"

const globalStore = globalThis as typeof globalThis & { __llmslimFoundingList?: FoundingListHandlers }

/** Runs one handler, or answers 503 when this deployment has no accounts database. */
export async function handleFoundingList(request: Request, pick: (handlers: FoundingListHandlers) => (request: Request) => Promise<Response>): Promise<Response> {
  const config = getAuthConfig()
  if (config.unavailable) return unavailableResponse(config.unavailable)
  const instance = getAuthInstance()
  if (!instance) return unavailableResponse("database_not_configured")
  globalStore.__llmslimFoundingList ??= foundingListHandlers(config, instance.db, instance.auth)
  try {
    return await pick(globalStore.__llmslimFoundingList)(request)
  } catch (error) {
    // For example a database outage, or a deployment that is ahead of its migration. The button then offers the email link.
    console.error("[founding-list] request failed:", error instanceof Error ? error.message : "unknown error")
    return new Response(JSON.stringify({ code: "SERVER_ERROR", message: "Something went wrong." }), { status: 500, headers: { "cache-control": "no-store", "content-type": "application/json; charset=utf-8" } })
  }
}

/** Confirmed members, or null when there is no database or the count is below `minimum`. Never throws. */
export async function publicFoundingCount(minimum: number): Promise<number | null> {
  const instance = getAuthInstance()
  if (!instance) return null
  try {
    const count = await countConfirmed(instance.db)
    return count >= minimum ? count : null
  } catch (error) {
    console.error("[founding-list] could not count members:", error instanceof Error ? error.message : "unknown error")
    return null
  }
}
