"use client"

import { LazyMotion } from "framer-motion"
import type { ReactNode } from "react"

const loadFeatures = () => import("./motion-features").then((module) => module.default)

/** Pages render `m` components; their animation features arrive in a separate chunk right after the page loads. */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <LazyMotion features={loadFeatures}>{children}</LazyMotion>
}
