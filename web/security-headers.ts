/**
 * Security headers for every page, applied from next.config.ts.
 *
 * The Content Security Policy allows only what the site and the accounts pages use: our own origin,
 * Vercel Analytics and Speed Insights (same origin in production, va.vercel-scripts.com in
 * development), optional Mixpanel and Sentry ingestion, and Google and GitHub avatar images.
 * OAuth sign-in is a top-level navigation and WebAuthn is a browser API, so neither needs an entry.
 *
 * Scripts and styles keep 'unsafe-inline': the pages are statically rendered, so per-request nonces
 * are not possible without making the whole site dynamic, and Next.js and framer-motion emit inline
 * scripts and styles. Everything else is locked to an allow-list, and framing is forbidden.
 */

export type HeaderEnv = Readonly<Record<string, string | undefined>>

type Header = { key: string; value: string }

function sentryOrigin(dsn: string | undefined): string | null {
  if (!dsn) return null
  try {
    const url = new URL(dsn)
    return url.protocol === "https:" ? url.origin : null
  } catch {
    return null
  }
}

export function contentSecurityPolicy(env: HeaderEnv): string {
  const development = env.NODE_ENV === "development"
  const preview = env.VERCEL_ENV === "preview"
  const deployed = Boolean(env.VERCEL)
  // The Vercel Toolbar is injected on preview deployments only.
  const toolbar = preview ? ["https://vercel.live"] : []
  const sentry = sentryOrigin(env.NEXT_PUBLIC_SENTRY_DSN)
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", ...(development ? ["'unsafe-eval'"] : []), "https://va.vercel-scripts.com", ...toolbar],
    "style-src": ["'self'", "'unsafe-inline'", ...toolbar],
    "img-src": ["'self'", "data:", "blob:", "https://lh3.googleusercontent.com", "https://avatars.githubusercontent.com", ...toolbar, ...(preview ? ["https://vercel.com"] : [])],
    "font-src": ["'self'", "data:", ...(preview ? ["https://vercel.live", "https://assets.vercel.com"] : [])],
    "media-src": ["'self'", "blob:"],
    "connect-src": ["'self'", "https://*.mixpanel.com", "https://va.vercel-scripts.com", ...(sentry ? [sentry] : []), ...toolbar, ...(preview ? ["wss://ws-us3.pusher.com"] : []), ...(development ? ["ws:", "wss:"] : [])],
    "worker-src": ["'self'", "blob:"],
    "frame-src": preview ? toolbar : ["'none'"],
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
    "manifest-src": ["'self'"],
  }
  const policy = Object.entries(directives).map(([name, sources]) => `${name} ${sources.join(" ")}`)
  // Only over HTTPS deployments: on http://localhost it would break every request.
  if (deployed) policy.push("upgrade-insecure-requests")
  return policy.join("; ")
}

export function securityHeaders(env: HeaderEnv): Header[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(env) },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  ]
}

/** Pages whose URL can carry a one-time token: no Referer at all, and never cached. */
export const TOKEN_PAGES = ["/verify-email", "/reset-password"] as const

export function tokenPageHeaders(): Header[] {
  return [
    { key: "Referrer-Policy", value: "no-referrer" },
    { key: "Cache-Control", value: "no-store, max-age=0" },
  ]
}
