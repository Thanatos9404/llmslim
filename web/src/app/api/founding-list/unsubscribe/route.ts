import { handleFoundingList } from "@/lib/founding-list/server"

export const runtime = "nodejs"

/** Leaves the founding list from the emailed unsubscribe link's token (JSON, or a plain form post without JavaScript). */
export function POST(request: Request): Promise<Response> {
  return handleFoundingList(request, (handlers) => handlers.unsubscribe)
}
