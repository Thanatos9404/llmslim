import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { getAuthConfig, publicFeatures } from "@/lib/auth/config"
import { constructMetadata } from "@/lib/seo"
import { VerifyEmail } from "./VerifyEmail"

export const metadata = constructMetadata({ title: "Confirm your email", description: "Confirm the email address for your LLMSlim account.", path: "/verify-email", noIndex: true })

type SearchParams = Promise<Record<string, string | string[] | undefined>>

export default async function VerifyEmailPage({ searchParams }: { searchParams: SearchParams }) {
  await connection()
  const params = await searchParams
  const raw = Array.isArray(params.token) ? params.token[0] : params.token
  // A JWT: three base64url parts. Anything else is not worth sending to the server.
  const token = raw && raw.length <= 2048 && /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(raw) ? raw : null
  const features = publicFeatures(getAuthConfig())
  return (
    <AuthCard title="Confirm your" accent="email.">
      {features.available ? <VerifyEmail token={token} malformed={Boolean(raw && !token)} canResend={features.emailSignUp} /> : <UnavailableNotice />}
    </AuthCard>
  )
}
