import { redirect } from "next/navigation"
import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { getAuthConfig, publicFeatures } from "@/lib/auth/config"
import { messageForCode, GENERIC_ERROR } from "@/lib/auth/messages"
import { getCurrentSession } from "@/lib/auth/session"
import { FRESH_SESSION_AGE, getAuthInstance } from "@/lib/auth/server"
import { constructMetadata } from "@/lib/seo"
import { AccountClient } from "./AccountClient"
import { isFresh, loadAccountView, type AccountView } from "./data"

export const metadata = constructMetadata({ title: "Your account", description: "Manage your LLMSlim account.", path: "/account", noIndex: true })

type SearchParams = Promise<Record<string, string | string[] | undefined>>

export default async function AccountPage({ searchParams }: { searchParams: SearchParams }) {
  await connection()
  const instance = getAuthInstance()
  if (!instance) {
    return (
      <AuthCard title="Your" accent="account.">
        <UnavailableNotice />
      </AuthCard>
    )
  }
  // The server decides: no session, no account page.
  const current = await getCurrentSession()
  if (!current) redirect("/sign-in?next=/account")

  const params = await searchParams
  const rawError = Array.isArray(params.error) ? params.error[0] : params.error
  const notice = rawError ? (messageForCode(rawError) ?? GENERIC_ERROR) : null
  const features = publicFeatures(getAuthConfig())
  const data = await loadAccountView(instance.db, current.user.id, current.session.id)
  const view: AccountView = {
    ...data,
    user: { name: current.user.name, email: current.user.email, emailVerified: current.user.emailVerified, image: current.user.image ?? null },
    available: { google: features.google, github: features.github, passkey: features.passkey },
    fresh: isFresh(current.session.createdAt, FRESH_SESSION_AGE),
  }

  return (
    <AuthCard title="Your" accent="account." description="Manage how you sign in, your passkeys and your active sessions." wide>
      <AccountClient view={view} notice={notice} />
    </AuthCard>
  )
}
