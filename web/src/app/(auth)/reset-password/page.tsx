import Link from "next/link"
import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { getAuthConfig, publicFeatures } from "@/lib/auth/config"
import { constructMetadata } from "@/lib/seo"
import { ResetPasswordForm } from "./ResetPasswordForm"

export const metadata = constructMetadata({ title: "Choose a new password", description: "Choose a new password for your LLMSlim account.", path: "/reset-password", noIndex: true })

type SearchParams = Promise<Record<string, string | string[] | undefined>>

export default async function ResetPasswordPage({ searchParams }: { searchParams: SearchParams }) {
  await connection()
  const params = await searchParams
  const raw = Array.isArray(params.token) ? params.token[0] : params.token
  // Better Auth reset tokens are 24 alphanumeric characters.
  const token = raw && /^[A-Za-z0-9]{16,64}$/.test(raw) ? raw : null
  const features = publicFeatures(getAuthConfig())
  return (
    <AuthCard title="Choose a new" accent="password.">
      {!features.available ? (
        <UnavailableNotice />
      ) : token ? (
        <ResetPasswordForm token={token} />
      ) : (
        <div className="auth-stack">
          <div className="auth-status auth-status-error" role="alert" data-testid="reset-invalid">
            <p>This reset link is invalid or has expired. Request a new one.</p>
          </div>
          <Link href="/forgot-password" className="auth-button auth-button-primary">
            Request a new link
          </Link>
        </div>
      )}
    </AuthCard>
  )
}
