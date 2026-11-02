import { handleFoundingList } from "@/lib/founding-list/server"

export const runtime = "nodejs"

/** Confirms a place on the founding list from the emailed link's token. */
export function POST(request: Request): Promise<Response> {
  return handleFoundingList(request, (handlers) => handlers.confirm)
}
