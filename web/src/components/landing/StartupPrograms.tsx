import Image from "next/image"
import type { CSSProperties } from "react"

/**
 * Verified startup programs. One list drives the program wall and every count.
 *
 * Logos are the companies' official artwork, unmodified. `logoDark` is the vendor's own variant
 * for dark backgrounds; MongoDB's is its reverse logo (white wordmark, green leaf), cut from the
 * official artwork. Two treatments predate this list: "mask" tints a supplied single-colour
 * mark to the text colour, and "symbol" pairs an official symbol with the product name.
 */
export type StartupProgram = {
  id: string
  name: string
  href: string
  logo: string
  logoDark?: string
  alt: string
  /** Intrinsic artwork size, used for the aspect ratio. */
  width: number
  height: number
  /** Rendered artwork height in the showcase, in pixels. */
  display?: number
  treatment?: "image" | "mask" | "symbol"
  /** Symbol treatment: an official wordmark asset or the product name set in type. */
  wordmark?: string
  label?: string
}

export const startupPrograms: readonly StartupProgram[] = [
  { id: "sarvam", name: "Sarvam Startup Program", href: "https://www.sarvam.ai/startup-program", logo: "/sarvam-symbol.svg", wordmark: "/sarvam-wordmark.svg", alt: "Sarvam logo", width: 1, height: 1, treatment: "symbol" },
  { id: "zoho", name: "Zoho for Startups", href: "https://www.zoho.com/startups/", logo: "/zoho-logo-light.png", logoDark: "/zoho-logo-dark.png", alt: "Zoho logo", width: 860, height: 409 },
  { id: "mongodb", name: "MongoDB for Startups", href: "https://www.mongodb.com/startups", logo: "/mongodb-logo.png", logoDark: "/mongodb-logo-dark.png", alt: "MongoDB logo", width: 600, height: 600 },
  { id: "claude", name: "Claude for Startups", href: "https://claude.com/programs/startups", logo: "/claude-symbol.svg", label: "Claude", alt: "Claude logo", width: 1, height: 1, treatment: "symbol" },
  { id: "openai", name: "OpenAI for Startups", href: "https://openai.com/startups/", logo: "/openai-symbol.svg", label: "OpenAI", alt: "OpenAI logo", width: 1, height: 1, treatment: "symbol" },
  { id: "auth0", name: "Auth0 for Startups", href: "https://auth0.com/startups", logo: "/auth0-logo.webp", alt: "Auth0 logo", width: 1, height: 1, treatment: "mask" },
  { id: "zendesk", name: "Zendesk for Startups", href: "https://www.zendesk.com/startups/", logo: "/zendesk-logo.webp", alt: "Zendesk logo", width: 1, height: 1, treatment: "mask" },
  { id: "mixpanel", name: "Mixpanel for Startups", href: "https://mixpanel.com/startups/", logo: "/startups/mixpanel-black.svg", logoDark: "/startups/mixpanel-white.svg", alt: "Mixpanel logo", width: 798, height: 189, display: 26 },
  { id: "sentry", name: "Sentry for Startups", href: "https://sentry.io/for/startups/", logo: "/startups/sentry-dark-text.svg", logoDark: "/startups/sentry-white-text.svg", alt: "Sentry logo", width: 222, height: 66, display: 44 },
  { id: "descope", name: "Descope Hello World Startup Program", href: "https://www.descope.com/for-startups", logo: "/startups/descope-dark-text.svg", logoDark: "/startups/descope-white-text.svg", alt: "Descope logo", width: 281, height: 64, display: 30 },
  { id: "pulumi", name: "Pulumi for Startups", href: "https://www.pulumi.com/pulumi-for-startups/", logo: "/startups/pulumi-light.svg", logoDark: "/startups/pulumi-dark.svg", alt: "Pulumi logo", width: 425, height: 106, display: 32 },
  // Programs join this list only once acceptance is confirmed. Nebius AI Builder
  // (/startups/nebius.svg) is applied for and pending.
]

export const startupProgramCount = startupPrograms.length

/** "A, B, and C" for prose that names every program. */
export const startupProgramNames = new Intl.ListFormat("en", { style: "long", type: "conjunction" }).format(startupPrograms.map(program => program.name))

type Mark = CSSProperties & { "--startup-mark"?: string }

export function ProgramLogo({ program }: { program: StartupProgram }) {
  const { id, logo, logoDark, alt, width, height, display, treatment = "image" } = program
  if (treatment === "mask") return <span className={`startup-supplied-logo ${id}-brand`} style={{ "--startup-mark": `url('${logo}')` } as Mark} />
  if (treatment === "symbol") return <span className={`startup-ai-brand ${id}-brand`}>
    <span className={`startup-ai-symbol ${id}-symbol`} style={{ "--startup-mark": `url('${logo}')` } as Mark} />
    {program.wordmark ? <span className="startup-wordmark" style={{ "--startup-mark": `url('${program.wordmark}')` } as Mark} /> : program.label}
  </span>
  const style = display ? { height: display, width: "auto" } : undefined
  return <span className={`startup-artwork ${id}-brand`}>
    <Image src={logo} alt={alt} width={width} height={height} sizes="160px" style={style} className={logoDark ? "art-light" : undefined} />
    {logoDark && <Image src={logoDark} alt={alt} width={width} height={height} sizes="160px" style={style} className="art-dark" />}
  </span>
}
