import { headers } from "next/headers"
import { getAuth } from "./server"

export type CurrentSession = NonNullable<Awaited<ReturnType<NonNullable<ReturnType<typeof getAuth>>["api"]["getSession"]>>>

/** The signed-in session for this request, or null. Never throws: a database outage reads as signed out. */
export async function getCurrentSession(): Promise<CurrentSession | null> {
  const auth = getAuth()
  if (!auth) return null
  try {
    return await auth.api.getSession({ headers: await headers() })
  } catch (error) {
    console.error("[accounts] could not read the session:", error instanceof Error ? error.message : "unknown error")
    return null
  }
}
