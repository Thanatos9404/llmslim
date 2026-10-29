"use client"

import { useId, useState, type ComponentProps } from "react"
import { passwordStrength, PASSWORD_MAX, PASSWORD_MIN } from "@/lib/auth/validation"
import { EyeIcon, EyeOffIcon } from "./icons"
import { Field } from "./primitives"

/** The show/hide button inside a password input. Its name stays "Show password" or "Hide password". */
function RevealButton({ visible, onToggle }: { visible: boolean; onToggle: () => void }) {
  return (
    <button type="button" className="auth-reveal" onClick={onToggle} aria-pressed={visible} aria-label={visible ? "Hide password" : "Show password"} title={visible ? "Hide password" : "Show password"}>
      {visible ? <EyeOffIcon /> : <EyeIcon />}
    </button>
  )
}

/** Any password input (current, confirm), with a show/hide button. */
export function SecretField(props: Omit<ComponentProps<typeof Field>, "type" | "trailing">) {
  const [visible, setVisible] = useState(false)
  return <Field {...props} type={visible ? "text" : "password"} trailing={<RevealButton visible={visible} onToggle={() => setVisible((shown) => !shown)} />} />
}

/** A new-password field with a show/hide button and live strength feedback, using the server's own rules. */
export function NewPasswordField({ label = "Password", value, onChange, onBlur, error, context = [], showStrength = true, name = "password" }: { label?: string; value: string; onChange: (value: string) => void; onBlur?: () => void; error?: string | null; context?: string[]; showStrength?: boolean; name?: string }) {
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
      onBlur={onBlur}
      error={error}
      required
      minLength={PASSWORD_MIN}
      maxLength={PASSWORD_MAX}
      hint={`At least ${PASSWORD_MIN} characters. Passwords found in known data breaches are rejected.`}
      trailing={<RevealButton visible={visible} onToggle={() => setVisible((shown) => !shown)} />}
      after={
        showStrength && value ? (
          <div className="auth-strength" data-score={strength.score} id={meterId}>
            <div className="auth-strength-bar" aria-hidden="true">
              {[1, 2, 3, 4].map((step) => <span key={step} data-on={strength.score >= step ? "" : undefined} />)}
            </div>
            <p className="auth-strength-text" aria-live="polite" data-testid="password-strength">
              Strength: {strength.label}
              {strength.hint ? `. ${strength.hint}` : ""}
            </p>
          </div>
        ) : null
      }
    />
  )
}
