"use client"

import Link from "next/link"
import type { AnchorHTMLAttributes, ReactNode } from "react"
import { track, type AnalyticsEvent, type AnalyticsProperties } from "@/lib/analytics"

type TrackedLinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  href: string
  event: AnalyticsEvent
  properties?: AnalyticsProperties
  prefetch?: boolean
  children: ReactNode
}

/** A link that records one allow-listed click event. Navigation never waits for analytics. */
export function TrackedLink({ href, event, properties, prefetch, onClick, children, ...rest }: TrackedLinkProps) {
  const handle: TrackedLinkProps["onClick"] = clicked => { track(event, properties); onClick?.(clicked) }
  if (/^https?:/.test(href)) return <a href={href} onClick={handle} {...rest}>{children}</a>
  return <Link href={href} prefetch={prefetch} onClick={handle} {...rest}>{children}</Link>
}
