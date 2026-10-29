import { getAuthConfig } from "@/lib/auth/config"
import { crossOriginRejection, unavailableResponse, withoutSessionTokens } from "@/lib/auth/http"
import { getAuth } from "@/lib/auth/server"

// Better Auth needs Node's crypto (scrypt) and a TCP database connection.
export const runtime = "nodejs"

async function handle(request: Request): Promise<Response> {
  const config = getAuthConfig()
  if (config.unavailable) return unavailableResponse(config.unavailable)
  const rejection = crossOriginRejection(request, config.trustedOrigins)
  if (rejection) return rejection
  const auth = getAuth()
  if (!auth) return unavailableResponse("database_not_configured")
  const response = await withoutSessionTokens(await auth.handler(request))
  const headers = new Headers(response.headers)
  headers.set("cache-control", "no-store")
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers })
}

export { handle as GET, handle as POST }
