/**
 * Coarse, opt-in product analytics.
 *
 * Mixpanel receives only the events and properties allow-listed below. Nothing is sent unless
 * NEXT_PUBLIC_MIXPANEL_TOKEN is set. There is no SDK, no autocapture, no cookie or stored
 * identifier (the id lives for one page load) and no IP-based geolocation (`ip=0`). Do Not Track
 * and Global Privacy Control are honoured. Property values are short fixed slugs, booleans or
 * whole-number counts. Studio input, model output, URLs with query strings, names and emails are
 * never sent. Failures are swallowed: analytics can never break the page.
 */

const EVENTS = {
  homepage_view: [],
  platform_page_view: [],
  results_page_view: [],
  core_docs_clicked: ["location"],
  studio_clicked: ["location"],
  platform_beta_clicked: ["location"],
  beta_request_submitted: ["location"],
  startup_program_clicked: ["program"],
  // The Studio's "Answer with Sarvam" step: whether it answered, and token counts. No text.
  studio_sarvam_answer: ["ok", "context_tokens", "original_tokens"],
} as const satisfies Record<string, readonly string[]>

export type AnalyticsEvent = keyof typeof EVENTS
export type AnalyticsValue = string | number | boolean
export type AnalyticsProperties = Partial<Record<(typeof EVENTS)[AnalyticsEvent][number], AnalyticsValue>>

const TOKEN = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN
// Regional ingestion (for example https://api-eu.mixpanel.com); only Mixpanel hosts are accepted.
const HOST = process.env.NEXT_PUBLIC_MIXPANEL_API_HOST || "https://api-js.mixpanel.com"
const SAFE_VALUE = /^[a-z0-9_-]{1,40}$/
const MAX_COUNT = 10_000_000

let pageId: string | undefined

function allowed(): boolean {
  if (!TOKEN || typeof window === "undefined" || !/^https:\/\/api(-[a-z]+)?(-js)?\.mixpanel\.com$/.test(HOST)) return false
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean }
  return nav.doNotTrack !== "1" && nav.globalPrivacyControl !== true
}

/** A short slug, a boolean, or a whole-number count; anything else could carry content. */
function safe(value: unknown): value is AnalyticsValue {
  if (typeof value === "string") return SAFE_VALUE.test(value)
  if (typeof value === "boolean") return true
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= MAX_COUNT
}

/** Allow-listed properties with safe values only; everything else is dropped. */
export function sanitize(event: AnalyticsEvent, properties: Record<string, unknown> = {}): Record<string, AnalyticsValue> {
  const keys: readonly string[] = EVENTS[event]
  return Object.fromEntries(Object.entries(properties).filter(([key, value]) => keys.includes(key) && safe(value))) as Record<string, AnalyticsValue>
}

export function track(event: AnalyticsEvent, properties?: AnalyticsProperties): void {
  try {
    if (!(event in EVENTS) || !allowed()) return
    pageId ??= crypto.randomUUID()
    const payload = [{
      event,
      properties: { ...sanitize(event, properties), token: TOKEN, distinct_id: pageId, $insert_id: crypto.randomUUID(), time: Date.now(), path: window.location.pathname },
    }]
    const body = new URLSearchParams({ data: JSON.stringify(payload) })
    const url = `${HOST}/track?ip=0`
    if (!navigator.sendBeacon?.(url, body)) void fetch(url, { method: "POST", body, keepalive: true, credentials: "omit" }).catch(() => undefined)
  } catch {
    // Analytics is best-effort by design.
  }
}
