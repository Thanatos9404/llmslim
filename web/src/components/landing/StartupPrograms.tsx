import Image from "next/image"
import Link from "next/link"

const programs = [
  { id: "sarvam", name: "Sarvam Startup Program", href: "/integrations/sarvam" },
  { id: "zoho", name: "Zoho for Startups", href: "https://www.zoho.com/startups/" },
  { id: "mongodb", name: "MongoDB for Startups", href: "https://www.mongodb.com/startups" },
  { id: "claude", name: "Claude for Startups" },
  { id: "openai", name: "OpenAI for Startups" },
] as const

function ProgramLogo({ id }: { id: string }) {
  if (id === "sarvam") return <span className="sarvam-brand"><span className="sarvam-symbol" /><span className="sarvam-wordmark" /></span>
  if (id === "zoho") return <span className="zoho-brand"><Image src="/zoho-logo-light.png" alt="" width={860} height={409} sizes="160px" className="art-light" /><Image src="/zoho-logo-dark.png" alt="" width={860} height={378} sizes="160px" className="art-dark" /></span>
  if (id === "mongodb") return <span className="mongodb-brand"><Image src="/mongodb-logo.png" alt="" width={600} height={600} sizes="160px" /></span>
  return <span className={`startup-ai-brand ${id}-brand`}><span className={`startup-ai-symbol ${id}-symbol`} />{id === "claude" ? "Claude" : "OpenAI"}</span>
}

function Program({ id, name }: { id: string; name: string }) {
  return <><span className="startup-logo" aria-hidden="true"><ProgramLogo id={id} /></span><span className="startup-program-name">{name}</span></>
}

export function StartupBrands() {
  return <div className="startup-program-brands">{programs.map(program => <div className="startup-program-brand" key={program.id}><Program {...program} /></div>)}</div>
}

export function StartupMarquee() {
  return <div className="startup-marquee" aria-label="LLMSlim startup programs">
    <div className="startup-marquee-heading"><span>Growing with</span><label className="startup-motion-control"><input type="checkbox" aria-label="Pause startup logo animation" /><span>Pause motion</span></label></div>
    <div className="startup-marquee-window"><div className="startup-marquee-track">
      <div className="startup-marquee-group">{programs.map(program => "href" in program
        ? <Link className="startup-marquee-item" href={program.href} key={program.id} {...(program.href.startsWith("https:") ? { target: "_blank", rel: "noreferrer" } : {})}><Program {...program} /></Link>
        : <span className="startup-marquee-item" key={program.id}><Program {...program} /></span>)}</div>
      <div className="startup-marquee-group startup-marquee-copy" aria-hidden="true" inert>{programs.map(program => <span className="startup-marquee-item" key={program.id}><Program {...program} /></span>)}</div>
    </div></div>
  </div>
}
