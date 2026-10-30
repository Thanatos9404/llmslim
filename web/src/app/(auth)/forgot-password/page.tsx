import { connection } from "next/server"
import { AuthCard, UnavailableNotice } from "@/components/auth/AuthCard"
import { getAuthConfig, publicFeatures } from "@/lib/auth/config"
import { constructMetadata } from "@/lib/seo"
import { ForgotPasswordForm } from "./ForgotPasswordForm"

export const metadata = constructMetadata({ title: "Reset your password", description: "Get a link to reset your LLMSlim password.", path: "/forgot-password", noIndex: true })

export default async function ForgotPasswordPage() {
  await connection()
  const features = publicFeatures(getAuthConfig())
  return (
    <AuthCard title="Reset your" accent="password." description="Enter the email you use for LLMSlim and we will send you a link to choose a new password.">
      {!features.available ? (
        <UnavailableNotice />
      ) : features.passwordReset ? (
        <ForgotPasswordForm />
      ) : (
        <div className="auth-status auth-status-info" role="status" data-testid="reset-disabled">
          <p>Password reset by email is not available right now. Sign in with a passkey, Google or GitHub if you have set one up.</p>
        </div>
      )}
    </AuthCard>
  )
}
