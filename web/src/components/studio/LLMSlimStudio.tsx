"use client"
import { useEffect, useRef, useState } from "react"
import { Check, Copy, LoaderCircle, RefreshCw, ShieldAlert, Sparkles } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

type ContextRole = "general" | "system" | "developer" | "user" | "assistant" | "tool" | "rag"
type Result = { output: string; original_tokens: number; compressed_tokens: number; tokens_saved: number; reduction_percent: number; target_ratio: number; actual_ratio: number; strategy: string; context_role: ContextRole; token_counter_used: string; elapsed_ms: number; backend: string; max_chunk_tokens: number | null }
const sample = "Retrieved source: Enterprise plans include 50 seats. Overage charges are calculated from active seats at the end of each billing cycle. Administrators view active seats in Workspace > Members. Support tickets can contain old plan names; verify them against the policy.\n\nQuestion: How are overages calculated, and where can an administrator view active seats?"
const roles: ContextRole[] = ["general", "system", "developer", "user", "assistant", "tool", "rag"]

export function LLMSlimStudio() {
  const [text, setText] = useState(sample); const [role, setRole] = useState<ContextRole>("rag"); const [retention, setRetention] = useState(50); const [budget, setBudget] = useState("500"); const [result, setResult] = useState<Result | null>(null); const [error, setError] = useState(""); const [running, setRunning] = useState(false); const [copied, setCopied] = useState(false)
  const activeRequest = useRef<AbortController | null>(null)
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const invalidate = () => {
    activeRequest.current?.abort()
    activeRequest.current = null
    setRunning(false)
    setResult(null)
    setError("")
    setCopied(false)
  }
  useEffect(() => () => { activeRequest.current?.abort() }, [])
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current) }, [])
  const run = async () => {
    const max = Number(budget)
    if (!text.trim()) return setError("Paste context before running compression.")
    if (!Number.isInteger(max) || max < 32 || max > 4000) return setError("Maximum chunk size must be a whole number from 32 to 4000.")
    activeRequest.current?.abort()
    const controller = new AbortController()
    activeRequest.current = controller
    const timeout = setTimeout(() => controller.abort(), 8000)
    setRunning(true); setError(""); setResult(null); setCopied(false)
    try {
      const response = await fetch("/api/compress", { method: "POST", signal: controller.signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, strategy: "extractive", target_ratio: retention / 100, context_role: role, max_chunk_tokens: max }) })
      const payload = await response.json()
      if (!response.ok || typeof payload?.data?.output !== "string") throw new Error(payload?.error?.message || "Live compression could not be completed.")
      if (activeRequest.current === controller) setResult(payload.data)
    } catch (cause) {
      if (activeRequest.current === controller) setError(controller.signal.aborted ? "The request timed out. Please try again." : cause instanceof Error ? cause.message : "Live compression could not be completed.")
    } finally {
      clearTimeout(timeout)
      if (activeRequest.current === controller) { activeRequest.current = null; setRunning(false) }
    }
  }
  const copy = async () => {
    if (!result) return
    try {
      await navigator.clipboard.writeText(result.output)
      setCopied(true)
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 1500)
    } catch { setError("Clipboard access is unavailable. Select and copy the output manually.") }
  }
  return <section aria-label="LLMSlim Studio live playground" className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"><Card className="lg:row-span-2"><CardHeader><Badge variant="secondary" className="w-fit">Configure</Badge><CardTitle className="mt-3">Context editor</CardTitle><CardDescription>Live extractive compression with caller-declared context provenance.</CardDescription></CardHeader><CardContent className="space-y-5"><div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label>Context role</Label><Select value={role} onValueChange={(value) => { setRole(value as ContextRole); invalidate() }}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent>{roles.map((item) => <SelectItem key={item} value={item}>{item}</SelectItem>)}</SelectContent></Select></div><div className="space-y-2"><Label htmlFor="studio-budget">Maximum chunk size</Label><Input id="studio-budget" type="number" min="32" max="4000" value={budget} onChange={(event) => { setBudget(event.target.value); invalidate() }} /></div></div><div className="space-y-3"><div className="flex items-center justify-between"><Label>Target retention</Label><Badge variant="outline">{retention}%</Badge></div><Slider value={[retention]} min={10} max={90} step={1} onValueChange={(value) => { setRetention(Array.isArray(value) ? value[0] : value); invalidate() }} aria-label="Target retention" /></div><div className="space-y-2"><div className="flex items-center justify-between"><Label htmlFor="studio-context">Context</Label><Button variant="ghost" size="sm" onClick={() => { setText(sample); setRole("rag"); invalidate() }}><RefreshCw /> Reset sample</Button></div><Textarea id="studio-context" value={text} onChange={(event) => { setText(event.target.value); invalidate() }} className="min-h-96 resize-y font-mono text-sm" /></div>{error && <Alert variant="destructive"><ShieldAlert /><AlertTitle>Live run unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}</CardContent><CardFooter><Button onClick={run} disabled={running} className="w-full">{running ? <LoaderCircle className="animate-spin" /> : <Sparkles />} {running ? "Running live compression" : "Run live compression"}</Button></CardFooter></Card><Card><CardHeader><div className="flex items-start justify-between gap-4"><div><Badge variant="outline">Live output</Badge><CardTitle className="mt-3">Compression result</CardTitle></div>{result && <Button variant="outline" size="sm" onClick={copy}>{copied ? <Check /> : <Copy />}{copied ? "Copied" : "Copy"}</Button>}</div></CardHeader><CardContent>{running ? <div className="flex min-h-64 items-center justify-center text-muted-foreground"><LoaderCircle className="mr-2 animate-spin" /> Running the LLMSlim Python engineÃ¢â‚¬Â¦</div> : !result ? <div className="flex min-h-64 items-center justify-center text-center text-sm text-muted-foreground">Run compression to view the exact output and returned token metrics.</div> : <Tabs defaultValue="output"><TabsList><TabsTrigger value="output">Output</TabsTrigger><TabsTrigger value="metrics">Metrics</TabsTrigger><TabsTrigger value="inspect">Inspect</TabsTrigger></TabsList><TabsContent value="output" className="mt-4"><ScrollArea className="h-64 rounded-md border bg-muted/50"><pre className="p-4 text-sm whitespace-pre-wrap">{result.output}</pre></ScrollArea></TabsContent><TabsContent value="metrics" className="mt-4"><MetricGrid result={result} /></TabsContent><TabsContent value="inspect" className="mt-4"><MetricGrid result={result} inspect /></TabsContent></Tabs>}</CardContent></Card><Alert className="lg:col-start-2"><ShieldAlert /><AlertTitle>Provider paths stay protected</AlertTitle><AlertDescription>Rewrite and hybrid require a caller-supplied provider and are not exposed by the public Studio.</AlertDescription></Alert></section>
}

function MetricGrid({ result, inspect = false }: { result: Result; inspect?: boolean }) { const values = inspect ? [["Strategy", result.strategy], ["Context role", result.context_role], ["Tokenizer", result.token_counter_used], ["Backend", result.backend || "default"], ["Elapsed", `${Math.round(result.elapsed_ms)} ms`], ["Chunk size", result.max_chunk_tokens ? `${result.max_chunk_tokens} tokens` : "default"]] : [["Original", `${result.original_tokens} tokens`], ["Compressed", `${result.compressed_tokens} tokens`], ["Tokens saved", `${result.tokens_saved} tokens`], ["Reduction", `${result.reduction_percent}%`], ["Requested", `${Math.round(result.target_ratio * 100)}%`], ["Actual", `${Math.round(result.actual_ratio * 100)}%`]]; return <div className="grid gap-3 sm:grid-cols-2">{values.map(([label, value]) => <Card key={label} size="sm"><CardHeader><CardDescription>{label}</CardDescription><CardTitle>{value}</CardTitle></CardHeader></Card>)}</div> }
