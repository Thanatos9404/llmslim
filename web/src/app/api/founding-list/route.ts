import { handleFoundingList } from "@/lib/founding-list/server"

// Better Auth (for the session) needs Node's crypto and a TCP database connection.
export const runtime = "nodejs"

/** Join the founding list: one click when signed in, or start the email confirmation. */
export function POST(request: Request): Promise<Response> {
  return handleFoundingList(request, (handlers) => handlers.join)
}

/** Leave the founding list (signed in). */
export function DELETE(request: Request): Promise<Response> {
  return handleFoundingList(request, (handlers) => handlers.leave)
}
