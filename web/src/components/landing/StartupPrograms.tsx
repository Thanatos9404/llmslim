import Image from "next/image"
import type { CSSProperties } from "react"
import { TrackedLink } from "@/components/site/TrackedLink"

/**
 * Verified startup programs. One list drives the hero marquee, the showcase and every count.
 *
 * Logos are the companies' official artwork, unmodified. `logoDark` is the vendor's own variant
 * for dark backgrounds. Two treatments predate this list: "mask" tints a supplied single-colour
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
  { id: "mongodb", name: "MongoDB for Startups", href: "https://www.mongodb.com/startups", logo: "/mongodb-logo.png", alt: "MongoDB logo", width: 600, height: 600 },
  { id: "claude", name: "Claude for Startups", href: "https://claude.com/programs/startups", logo: "/claude-symbol.svg", label: "Claude", alt: "Claude logo", width: 1, height: 1, treatment: "symbol" },
  { id: "openai", name: "OpenAI for Startups", href: "https://openai.com/startups/", logo: "/openai-symbol.svg", label: "OpenAI", alt: "OpenAI logo", width: 1, height: 1, treatment: "symbol" },
  { id: "auth0", name: "Auth0 for Startups", href: "https://auth0.com/startups", logo: "/auth0-logo.png", alt: "Auth0 logo", width: 1, height: 1, treatment: "mask" },
  { id: "zendesk", name: "Zendesk for Startups", href: "https://www.zendesk.com/startups/", logo: "/zendesk-logo.png", alt: "Zendesk logo", width: 1, height: 1, treatment: "mask" },
  { id: "mixpanel", name: "Mixpanel for Startups", href: "https://mixpanel.com/startups/", logo: "/startups/mixpanel-black.svg", logoDark: "/startups/mixpanel-white.svg", alt: "Mixpanel logo", width: 798, height: 189, display: 26 },
  { id: "sentry", name: "Sentry for Startups", href: "https://sentry.io/for/startups/", logo: "/startups/sentry-dark-text.svg", logoDark: "/startups/sentry-white-text.svg", alt: "Sentry logo", width: 222, height: 66, display: 44 },
  { id: "descope", name: "Descope Hello World Startup Program", href: "https://www.descope.com/for-startups", logo: "/startups/descope-dark-text.svg", logoDark: "/startups/descope-white-text.svg", alt: "Descope logo", width: 281, height: 64, display: 30 },
  { id: "pulumi", name: "Pulumi for Startups", href: "https://www.pulumi.com/pulumi-for-startups/", logo: "/startups/pulumi-light.svg", logoDark: "/startups/pulumi-dark.svg", alt: "Pulumi logo", width: 425, height: 106, display: 32 },
]

export const startupProgramCount = startupPrograms.length

/** "A, B, and C" for prose that names every program. */
export const startupProgramNames = new Intl.ListFormat("en", { style: "long", type: "conjunction" }).format(startupPrograms.map(program => program.name))

type Mark = CSSProperties & { "--startup-mark"?: string }

function ProgramLogo({ program }: { program: StartupProgram }) {
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

/** The visible program name is the accessible name; the artwork beside it is decorative. */
function Program({ program }: { program: StartupProgram }) {
  return <><span className="startup-logo" aria-hidden="true"><ProgramLogo program={program} /></span><span className="startup-program-name">{program.name}</span></>
}

export function StartupBrands() {
  return <ul className="startup-program-brands" aria-label={`${startupProgramCount} startup programs`}>{startupPrograms.map(program => <li className="startup-program-brand" key={program.id}><Program program={program} /></li>)}</ul>
}

export function StartupMarquee() {
  const duration = { "--marquee-duration": `${startupProgramCount * 5.5}s` } as CSSProperties
  return <div className="startup-marquee" role="region" aria-label="LLMSlim startup programs">
    <div className="startup-marquee-heading"><span>Building with support from</span><label className="startup-motion-control"><input type="checkbox" aria-label="Pause startup logo animation" /><span>Pause motion</span></label></div>
    <div className="startup-marquee-window"><div className="startup-marquee-track" style={duration}>
      <div className="startup-marquee-group">{startupPrograms.map(program => <TrackedLink className="startup-marquee-item" href={program.href} key={program.id} event="startup_program_clicked" properties={{ program: program.id }} target="_blank" rel="noreferrer"><Program program={program} /></TrackedLink>)}</div>
      <div className="startup-marquee-group startup-marquee-copy" aria-hidden="true" inert>{startupPrograms.map(program => <span className="startup-marquee-item" key={program.id}><Program program={program} /></span>)}</div>
    </div></div>
  </div>
}
