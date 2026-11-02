import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { getAuthConfig } from "@/lib/auth/config"
import { isConfirmToken } from "@/lib/founding-list/tokens"
import { constructMetadata } from "@/lib/seo"
import { ConfirmFoundingList } from "./ConfirmFoundingList"

export const metadata = constructMetadata({ title: "Confirm your place", description: "Confirm your place on the LLMSlim Orbit founding list.", path: "/founding-list/confirm", noIndex: true })

type SearchParams = Promise<Record<string, string | string[] | undefined>>

export default async function ConfirmFoundingListPage({ searchParams }: { searchParams: SearchParams }) {
  await connection()
  const params = await searchParams
  const raw = Array.isArray(params.token) ? params.token[0] : params.token
  const token = isConfirmToken(raw) ? raw : null
  const available = getAuthConfig().unavailable === null
  return (
    <AuthCard kicker="Founding list" title="Confirm your" accent="place.">
      {available ? <ConfirmFoundingList token={token} /> : <UnavailableNotice what="The founding list is" />}
    </AuthCard>
  )
}
