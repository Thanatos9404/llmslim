"use client"
import { useEffect, useRef, useState } from "react"
import { Check, Copy, Terminal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"

export function DocCodeBlock({ language = "bash", filename, code }: { language?: string; filename?: string; code: string }) {
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState("")
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true); setCopyError("")
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), 2000)
    } catch { setCopied(false); setCopyError("Select the code and copy it manually.") }
  }
  return <Card className="my-6"><CardHeader className="flex flex-row items-center justify-between"><span className="flex items-center gap-2 text-xs text-muted-foreground"><Terminal className="size-4" />{filename || language}</span><Button variant="ghost" size="icon-sm" onClick={handleCopy} aria-label="Copy code block">{copied ? <Check /> : <Copy />}</Button></CardHeader><CardContent>{copyError && <p role="status" className="mb-2 text-sm text-muted-foreground">{copyError}</p>}<ScrollArea className="max-h-96 rounded-md border bg-muted/50"><pre className="p-4 text-sm"><code>{code}</code></pre></ScrollArea></CardContent></Card>
}
