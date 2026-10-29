import { redirect } from "next/navigation"
import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { RecallMoment } from "@/components/auth/AuthMoments"
import type { Status } from "@/components/auth/primitives"
import { getAuthConfig, publicFeatures } from "@/lib/auth/config"
import { messageForCode, GENERIC_ERROR } from "@/lib/auth/messages"
import { sanitizeNext } from "@/lib/auth/next-path"
import { getCurrentSession } from "@/lib/auth/session"
import { constructMetadata } from "@/lib/seo"
import { SignInForm } from "./SignInForm"

export const metadata = constructMetadata({ title: "Sign in", description: "Sign in to your LLMSlim account.", path: "/sign-in", noIndex: true })

type SearchParams = Promise<Record<string, string | string[] | undefined>>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default async function SignInPage({ searchParams }: { searchParams: SearchParams }) {
  await connection()
  const params = await searchParams
  const next = sanitizeNext(first(params.next))
  const reauth = first(params.reauth) === "1"
  const features = publicFeatures(getAuthConfig())

  if (features.available && !reauth) {
    const session = await getCurrentSession()
    if (session) redirect(next)
  }

  let initialStatus: Status = null
  const error = first(params.error)
  if (error) initialStatus = { kind: "error", text: messageForCode(error) ?? GENERIC_ERROR }
  else if (reauth) initialStatus = { kind: "info", text: "For your security, sign in again to continue." }
  else if (first(params.signedOut) === "1") initialStatus = { kind: "success", text: "You have signed out." }
  else if (first(params.deleted) === "1") initialStatus = { kind: "success", text: "Your account has been deleted." }
  else if (first(params.reset) === "1") initialStatus = { kind: "success", text: "Your password has been changed. Sign in with your new password." }

  return (
    <AuthCard title={reauth ? "Confirm it's you" : "Sign in"} description="Use a passkey, Google, GitHub or your email and password." aside={<RecallMoment />}>
      {features.available ? <SignInForm features={features} next={next} initialStatus={initialStatus} /> : <UnavailableNotice />}
    </AuthCard>
  )
}
