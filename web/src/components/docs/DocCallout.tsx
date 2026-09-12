import { AlertTriangle, Info, Lightbulb, ShieldAlert } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { DocCallout as DocCalloutType } from "@/data/docs"

const config = { note: [Info, "Note"], tip: [Lightbulb, "Tip"], warning: [AlertTriangle, "Warning"], important: [ShieldAlert, "Important requirement"] } as const

export function DocCallout({ callout }: { callout: DocCalloutType }) {
  const [Icon, title] = config[callout.type] ?? config.note
  return <Alert className="my-6"><Icon /><AlertTitle>{callout.title || title}</AlertTitle><AlertDescription>{callout.content}</AlertDescription></Alert>
}
