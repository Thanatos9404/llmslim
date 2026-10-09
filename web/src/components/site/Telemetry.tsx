"use client"

import { useEffect } from "react"
import { track, type AnalyticsEvent } from "@/lib/analytics"

/** Records one allow-listed page-view event after hydration. Renders nothing. */
export function PageView({ event }: { event: AnalyticsEvent }) {
  useEffect(() => { track(event) }, [event])
  return null
}

const QUOTED = /(["'`])(?:(?!\1).){1,400}\1/g

/** Keeps the error type and stack; drops quoted fragments that could echo user input. */
export function scrubMessage(value: string | undefined): string | undefined {
  return value?.replace(QUOTED, "$1[redacted]$1").replace(/https?:\/\/\S+/g, "[url]").slice(0, 200)
}

/**
 * Optional client error reporting. The Sentry SDK is fetched only when NEXT_PUBLIC_SENTRY_DSN is
 * set, so the default bundle carries none of it. Errors only: no tracing, no session replay, no
 * breadcrumbs (they can hold Studio text), no PII, no request data, no query strings.
 */
export function ErrorReporting() {
  useEffect(() => {
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN
    if (!dsn) return
    import("@sentry/browser").then(Sentry => {
      if (Sentry.isInitialized()) return
      Sentry.init({
        dsn,
        environment: process.env.NEXT_PUBLIC_VERCEL_ENV || "development",
        release: process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA,
        sendDefaultPii: false,
        defaultIntegrations: false,
        integrations: [Sentry.globalHandlersIntegration(), Sentry.linkedErrorsIntegration(), Sentry.dedupeIntegration()],
        maxBreadcrumbs: 0,
        tracesSampleRate: 0,
        beforeBreadcrumb: () => null,
        beforeSend(event) {
          delete event.user
          delete event.extra
          delete event.breadcrumbs
          if (event.request) event.request = { url: event.request.url?.split(/[?#]/)[0] }
          event.message = scrubMessage(event.message)
          for (const exception of event.exception?.values ?? []) exception.value = scrubMessage(exception.value)
          return event
        },
      })
    }).catch(() => undefined)
  }, [])
  return null
}
