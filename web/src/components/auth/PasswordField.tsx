"use client"

import { useId, useState } from "react"
import { Eye, EyeOff } from "lucide-react"
import { passwordStrength, PASSWORD_MAX, PASSWORD_MIN } from "@/lib/auth/validation"
import { Field } from "./primitives"

/** The eye button inside a password input that shows or hides what was typed. */
export function RevealToggle({ visible, onToggle }: { visible: boolean; onToggle: () => void }) {
  const label = visible ? "Hide password" : "Show password"
  return (
    <button type="button" className="auth-reveal" onClick={onToggle} aria-pressed={visible} aria-label={label} title={label}>
      {visible ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
    </button>
  )
}

/** A new-password field with a show/hide toggle and live strength feedback. */
export function NewPasswordField({ label = "Password", value, onChange, error, context = [], showStrength = true, name = "password" }: { label?: string; value: string; onChange: (value: string) => void; error?: string | null; context?: string[]; showStrength?: boolean; name?: string }) {
  const [visible, setVisible] = useState(false)
  const meterId = useId()
  const strength = passwordStrength(value, context)
  return (
    <Field
      label={label}
      name={name}
      type={visible ? "text" : "password"}
      autoComplete="new-password"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      error={error}
      required
      minLength={PASSWORD_MIN}
      maxLength={PASSWORD_MAX}
      hint={`At least ${PASSWORD_MIN} characters. Passwords found in known data breaches are rejected.`}
      trailing={<RevealToggle visible={visible} onToggle={() => setVisible((shown) => !shown)} />}
      after={
        showStrength && value ? (
          <div className="auth-password-tools">
            <div className="auth-strength" data-score={strength.score} id={meterId}>
              <div className="auth-strength-bar" aria-hidden="true">
                <span style={{ width: `${(strength.score / 4) * 100}%` }} />
              </div>
              <p className="auth-strength-text" aria-live="polite" data-testid="password-strength">
                Strength: {strength.label}
                {strength.hint ? `. ${strength.hint}` : ""}
              </p>
            </div>
          </div>
        ) : null
      }
    />
  )
}
