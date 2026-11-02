import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { getAuthConfig } from "@/lib/auth/config"
import { constructMetadata } from "@/lib/seo"
import { UnsubscribeFoundingList, type Outcome } from "./UnsubscribeFoundingList"

export const metadata = constructMetadata({ title: "Leave the founding list", description: "Leave the LLMSlim Orbit founding list.", path: "/founding-list/unsubscribe", noIndex: true })

type SearchParams = Promise<Record<string, string | string[] | undefined>>

// The row id and its HMAC (src/lib/founding-list/tokens.ts). The server checks the signature.
const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[A-Za-z0-9_-]{43}$/
const OUTCOMES: readonly Outcome[] = ["done", "invalid", "limited"]

export default async function UnsubscribeFoundingListPage({ searchParams }: { searchParams: SearchParams }) {
  await connection()
  const params = await searchParams
  const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value)
  const raw = first(params.token)
  const token = raw && TOKEN.test(raw) ? raw : null
  // Set by the API's redirect after the no-JavaScript form posts.
  const result = first(params.result)
  const outcome = OUTCOMES.find((value) => value === result) ?? null
  const available = getAuthConfig().unavailable === null
  return (
    <AuthCard kicker="Founding list" title="Leave the" accent="founding list.">
      {available ? <UnsubscribeFoundingList token={token} outcome={outcome ?? (token ? null : "invalid")} /> : <UnavailableNotice what="The founding list is" />}
    </AuthCard>
  )
}
