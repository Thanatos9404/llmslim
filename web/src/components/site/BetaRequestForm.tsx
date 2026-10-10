"use client"

import { useState, type FormEvent } from "react"
import { ArrowRight } from "lucide-react"
import { track } from "@/lib/analytics"
import { siteConfig } from "@/config/site"

const AGENT_TYPES = ["Support agent", "Internal knowledge agent", "Research agent", "Sales / CRM agent", "Workflow / automation agent", "Agentic RAG", "Other"] as const

/**
 * Platform beta request. Nothing is stored or sent by this site: submitting opens the visitor's
 * own email client with a message to the founder, so the request and any reply stay in email.
 * Analytics records only that a request was started, never the fields.
 */
export function BetaRequestForm() {
  const [opened, setOpened] = useState(false)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const field = (name: string) => String(data.get(name) ?? "").trim()
    const company = field("company")
    const body = [
      `Name: ${field("name")}`,
      `Work email: ${field("email")}`,
      `Company / project: ${company}`,
      `Agent type: ${field("agent")}`,
      `Link: ${field("link") || "-"}`,
      `Interested in a technical pilot: ${data.get("pilot") ? "Yes" : "Not yet"}`,
      "",
      "Where context goes wrong today:",
      field("problem"),
      "",
      "I agree to be contacted about the LLMSlim Platform beta.",
    ].join("\n")
    const subject = `Platform beta request: ${company}`
    track("beta_request_submitted", { location: "platform_beta" })
    window.location.href = `mailto:${siteConfig.founderEmail}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    setOpened(true)
  }

  return <form className="beta-form" onSubmit={submit}>
    <div className="beta-form-grid">
      <label>Name<input name="name" required autoComplete="name" maxLength={120} /></label>
      <label>Work email<input name="email" type="email" required autoComplete="email" maxLength={200} /></label>
      <label>Company or project<input name="company" required autoComplete="organization" maxLength={160} /></label>
      <label>What kind of agent are you building?<select name="agent" required defaultValue=""><option value="" disabled>Choose one</option>{AGENT_TYPES.map(type => <option key={type}>{type}</option>)}</select></label>
    </div>
    <label>Which context problem are you facing?<textarea name="problem" required rows={4} maxLength={2000} placeholder="Stale facts in long sessions, token overhead, hard-to-debug context decisions…" /></label>
    <label>Project or repository link <span>(optional)</span><input name="link" type="url" maxLength={300} placeholder="https://" /></label>
    <label className="beta-check"><input name="pilot" type="checkbox" /> I am interested in a scoped technical pilot on a real workload.</label>
    <label className="beta-check"><input name="consent" type="checkbox" required /> I agree to be contacted about the LLMSlim Platform beta.</label>
    <p className="beta-privacy">Submitting opens your email app with a message to {siteConfig.founderEmail}. This site does not store what you type. We use your details only to reply about the beta. No credit card or company registration needed.</p>
    <div className="beta-actions">
      <button className="button" type="submit">Send beta request <ArrowRight size={16} /></button>
      <span>or email <a className="text-link" href={`mailto:${siteConfig.founderEmail}?subject=${encodeURIComponent("LLMSlim Platform beta")}`}>{siteConfig.founderEmail}</a></span>
    </div>
    {opened && <p className="beta-status" role="status">Your email app should now be open with the request filled in. If it did not open, email {siteConfig.founderEmail} directly.</p>}
  </form>
}
