import { redirect } from "next/navigation"
import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { getAuthConfig, publicFeatures } from "@/lib/auth/config"
import { messageForCode, GENERIC_ERROR } from "@/lib/auth/messages"
import { sanitizeNext } from "@/lib/auth/next-path"
import { getCurrentSession } from "@/lib/auth/session"
import { constructMetadata } from "@/lib/seo"
import { SignUpForm } from "./SignUpForm"

export const metadata = constructMetadata({ title: "Create an account", description: "Create your LLMSlim account.", path: "/sign-up", noIndex: true })

type SearchParams = Promise<Record<string, string | string[] | undefined>>

export default async function SignUpPage({ searchParams }: { searchParams: SearchParams }) {
  await connection()
  const params = await searchParams
  const rawNext = Array.isArray(params.next) ? params.next[0] : params.next
  const next = sanitizeNext(rawNext)
  const features = publicFeatures(getAuthConfig())
  if (features.available && (await getCurrentSession())) redirect(next)
  const rawError = Array.isArray(params.error) ? params.error[0] : params.error
  const error = rawError ? (messageForCode(rawError) ?? GENERIC_ERROR) : null

  return (
    <AuthCard title="Create your" accent="account." description="Sign up with Google, GitHub or your email address. You can add a passkey afterwards.">
      {error ? (
        <div className="auth-status auth-status-error" role="alert">
          <p>{error}</p>
        </div>
      ) : null}
      {features.available ? <SignUpForm features={features} next={next} /> : <UnavailableNotice />}
    </AuthCard>
  )
}
