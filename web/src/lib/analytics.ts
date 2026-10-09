/**
 * Coarse, opt-in product analytics.
 *
 * Mixpanel receives only the events and properties allow-listed below. Nothing is sent unless
 * NEXT_PUBLIC_MIXPANEL_TOKEN is set. There is no SDK, no autocapture, no cookie or stored
 * identifier (the id lives for one page load) and no IP-based geolocation (`ip=0`). Do Not Track
 * and Global Privacy Control are honoured. Studio input, model output, URLs with query strings,
 * names and emails are never sent. Failures are swallowed: analytics can never break the page.
 */

const EVENTS = {
  homepage_view: [],
  platform_page_view: [],
  core_docs_clicked: ["location"],
  studio_clicked: ["location"],
  platform_beta_clicked: ["location"],
  startup_program_clicked: ["program"],
} as const satisfies Record<string, readonly string[]>

export type AnalyticsEvent = keyof typeof EVENTS
export type AnalyticsProperties = Partial<Record<(typeof EVENTS)[AnalyticsEvent][number], string>>

const TOKEN = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN
// Regional ingestion (for example https://api-eu.mixpanel.com); only Mixpanel hosts are accepted.
const HOST = process.env.NEXT_PUBLIC_MIXPANEL_API_HOST || "https://api-js.mixpanel.com"
const SAFE_VALUE = /^[a-z0-9_-]{1,40}$/

let pageId: string | undefined

function allowed(): boolean {
  if (!TOKEN || typeof window === "undefined" || !/^https:\/\/api(-[a-z]+)?(-js)?\.mixpanel\.com$/.test(HOST)) return false
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean }
  return nav.doNotTrack !== "1" && nav.globalPrivacyControl !== true
}

/** Allow-listed properties with short slug values only; everything else is dropped. */
export function sanitize(event: AnalyticsEvent, properties: Record<string, unknown> = {}): Record<string, string> {
  const keys: readonly string[] = EVENTS[event]
  return Object.fromEntries(Object.entries(properties).filter(([key, value]) => keys.includes(key) && typeof value === "string" && SAFE_VALUE.test(value))) as Record<string, string>
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
