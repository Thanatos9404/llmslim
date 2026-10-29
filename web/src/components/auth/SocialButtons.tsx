"use client"

import { useState } from "react"
import { authClient, takeRetryAfter } from "@/lib/auth/client"
import { describeError, OFFLINE_ERROR } from "@/lib/auth/messages"
import { GitHubMark, GoogleMark } from "./icons"
import type { Status } from "./primitives"

export type Provider = "google" | "github"

const LABELS: Record<Provider, string> = { google: "Continue with Google", github: "Continue with GitHub" }

/**
 * Google and GitHub buttons. A provider without its environment variables is never rendered (the
 * server decides). The server returns the provider's authorization URL and the browser goes there.
 */
export function SocialButtons({ google, github, callbackURL, errorCallbackURL, onStatus, disabled, beforeStart, labels }: { google: boolean; github: boolean; callbackURL: string; errorCallbackURL: string; onStatus: (status: Status) => void; disabled?: boolean; beforeStart?: () => boolean; labels?: Partial<Record<Provider, string>> }) {
  const [pending, setPending] = useState<Provider | null>(null)
  const providers = ([google ? "google" : null, github ? "github" : null] as const).filter((provider): provider is Provider => provider !== null)
  if (providers.length === 0) return null

  async function start(provider: Provider) {
    if (beforeStart && !beforeStart()) return
    if (!navigator.onLine) return onStatus({ kind: "error", text: OFFLINE_ERROR })
    setPending(provider)
    onStatus(null)
    const { data, error } = await authClient.signIn.social({ provider, callbackURL, errorCallbackURL, disableRedirect: true })
    if (error || !data?.url) {
      setPending(null)
      return onStatus({ kind: "error", text: describeError(error, takeRetryAfter()) })
    }
    window.location.assign(data.url)
  }

  return (
    <div className={`auth-social${providers.length === 1 ? " is-single" : ""}`} data-testid="social-buttons">
      {providers.map((provider) => {
        const label = labels?.[provider] ?? LABELS[provider]
        // Equal-weight buttons show the provider's name; the rest of the label stays for screen readers.
        const lead = label.endsWith(BRANDS[provider]) ? label.slice(0, -BRANDS[provider].length) : null
        return (
          <button key={provider} type="button" className={`auth-button auth-button-social auth-button-${provider}`} onClick={() => start(provider)} disabled={disabled || pending !== null} aria-busy={pending === provider || undefined} data-provider={provider}>
            {pending === provider ? <span className="auth-spinner" aria-hidden="true" /> : <ProviderMark provider={provider} />}
            {lead === null ? label : <span><span className="lp-sr">{lead}</span>{BRANDS[provider]}</span>}
          </button>
        )
      })}
    </div>
  )
}

const BRANDS: Record<Provider, string> = { google: "Google", github: "GitHub" }

/** The providers' own marks (sources in icons.tsx): Google in colour, GitHub in the text colour. */
export function ProviderMark({ provider, size = 18 }: { provider: Provider; size?: number }) {
  return provider === "github" ? <GitHubMark size={size} className="auth-provider-mark" /> : <GoogleMark size={size} className="auth-provider-mark" />
}
