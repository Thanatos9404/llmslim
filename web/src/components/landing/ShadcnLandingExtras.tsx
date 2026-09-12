"use client"

import Link from "next/link"
import { useState } from "react"
import {
  ArrowRight,
  Check,
  Copy,
  Database,
  Fingerprint,
  GitBranch,
  Languages,
  ShieldAlert,
  ShieldCheck,
  Terminal,
} from "lucide-react"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { siteConfig } from "@/config/site"

const code = {
  extractive: `from llmslim import compress

result = compress(raw_prompt, target_ratio=0.5)
print(result.compressed_text)
print(result.detailed_summary())`,
  chat: `from llmslim import compress_chat_messages

compressed = compress_chat_messages(
    conversation,
    target_ratio=0.5,
)`,
  documents: `from llmslim import compress_documents

results = compress_documents(
    retrieved_chunks,
    query=user_query,
    target_ratio=0.4,
)`,
}

const strategies = [
  ["Extractive", "segment → rank → select", "Local sentence selection. Deterministic, inspectable, and available without a provider."],
  ["Semantic", "embed → score → select", "Use when an embedding setup is available and relevance—not merely a shorter string—is the goal."],
  ["Rewrite", "brief → provider → validate", "Bring a caller-supplied provider when concise reformulation is worth the explicit trust boundary."],
  ["Hybrid", "select → rewrite → review", "Select useful evidence first, then send only reduced material to a caller-supplied provider."],
] as const

const roles = ["System", "Developer", "User", "Assistant", "Tool", "RAG"] as const

const faq = [
  ["Does LLMSlim require an LLM provider?", "No. Its released default is offline extractive compression. Rewrite and hybrid are opt-in workflows requiring a provider you supply."],
  ["Does it solve prompt injection?", "No. It mitigates compression-induced priority elevation by preserving role provenance; it cannot authenticate caller-provided roles or eliminate injection risk."],
  ["What should I measure?", "Use your own workload to evaluate quality, cost, latency, and prompt behavior. The shipped corpus is a transparent regression set, not population proof."],
] as const

export function ShadcnLandingExtras() {
  const [model, setModel] = useState("2")
  const [requests, setRequests] = useState(50000)
  const [tokens, setTokens] = useState(1500)
  const [retention, setRetention] = useState(50)
  const [role, setRole] = useState<(typeof roles)[number]>("RAG")
  const [copied, setCopied] = useState(false)
  const prices: Record<string, number> = { "2": 2, "1.25": 1.25, "0.5": 0.5, "0.2": 0.2 }
  const saved = Math.round(tokens * (1 - retention / 100))
  const annual = (saved * requests * 365 / 1_000_000) * prices[model]
  const untrusted = role === "RAG" || role === "Tool" || role === "Assistant"
  const setSlider = (setter: (value: number) => void) => (value: number | readonly number[]) => setter(Array.isArray(value) ? value[0] : value)
  const copyInstall = async () => {
    await navigator.clipboard.writeText("pip install llmslim")
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="mt-20 space-y-20">
      <section id="features" className="grid scroll-mt-28 gap-4 md:grid-cols-3">
        <Card className="interactive-card md:col-span-3">
          <CardHeader>
            <Badge variant="outline" className="w-fit">Product surface</Badge>
            <CardTitle className="mt-3 font-serif text-3xl">Make every token explain itself.</CardTitle>
            <CardDescription>Role, strategy, and trust boundary stay visible instead of hiding behind a black-box claim.</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="Extractive">
              <TabsList className="h-auto w-full flex-wrap justify-start">{strategies.map(([name]) => <TabsTrigger key={name} value={name}>{name}</TabsTrigger>)}</TabsList>
              {strategies.map(([name, flow, description]) => (
                <TabsContent key={name} value={name} className="pt-5">
                  <div className="flex flex-col gap-4 rounded-xl border bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <p className="max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>
                    <Badge variant="secondary" className="w-fit font-mono">{flow}</Badge>
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>

        <Card className="interactive-card"><CardHeader><ShieldCheck className="size-5" /><CardTitle className="mt-3">Provenance-aware</CardTitle><CardDescription>System and developer context remain distinct from RAG, tool, and assistant text.</CardDescription></CardHeader></Card>
        <Card className="interactive-card"><CardHeader><Languages className="size-5" /><CardTitle className="mt-3">Four evaluated languages</CardTitle><CardDescription>English, Hindi, Chinese, and Japanese are disclosed as a small evaluation slice.</CardDescription></CardHeader></Card>
        <Card className="interactive-card"><CardHeader><GitBranch className="size-5" /><CardTitle className="mt-3">Transparent pipeline</CardTitle><CardDescription>Segment, score, prioritize, allocate budget, and reassemble.</CardDescription></CardHeader></Card>
      </section>

      <section id="pipeline" className="scroll-mt-28">
        <div className="mb-6 text-center">
          <Badge variant="outline">Trust boundary explorer</Badge>
          <h2 className="mt-4 font-serif text-4xl tracking-tight sm:text-5xl">Words do not grant authority.</h2>
          <p className="mx-auto mt-3 max-w-2xl text-muted-foreground">Select a context role to see how LLMSlim keeps caller-declared provenance visible.</p>
        </div>
        <Card className="overflow-hidden">
          <CardContent className="grid gap-6 p-5 lg:grid-cols-[1fr_1.15fr] lg:p-7">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" role="group" aria-label="Context role selector">
              {roles.map((item) => (
                <Button key={item} variant={role === item ? "default" : "outline"} className="h-auto min-h-20 flex-col items-start gap-1 px-4" onClick={() => setRole(item)} aria-pressed={role === item}>
                  <span>{item}</span>
                  <small className="font-normal opacity-70">{item === "System" || item === "Developer" ? "protected" : item === "User" ? "caller context" : "untrusted"}</small>
                </Button>
              ))}
            </div>
            <Alert className={untrusted ? "border-amber-500/30 bg-amber-500/5" : "border-violet-500/30 bg-violet-500/5"}>
              {untrusted ? <ShieldAlert /> : <Fingerprint />}
              <AlertTitle>{role} context · {untrusted ? "untrusted role" : "caller-declared role"}</AlertTitle>
              <AlertDescription>{untrusted ? `${role} text cannot gain protected priority merely by sounding imperative.` : `${role} remains prioritized, but LLMSlim cannot authenticate whether the caller assigned that provenance correctly.`}</AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      </section>

      <section id="benchmarks" className="scroll-mt-28">
        <Card className="overflow-hidden">
          <CardContent className="grid gap-8 p-6 lg:grid-cols-2 lg:p-9">
            <div>
              <Badge variant="outline">Schema tax · research track</Badge>
              <h2 className="mt-4 font-serif text-4xl tracking-tight">Tool definitions consume context too.</h2>
              <p className="mt-4 leading-7 text-muted-foreground">Phase 2 measured 18 synthetic tool catalogs across simple, medium, and complex schema classes. This is research—not a claim that schema optimization currently ships.</p>
              <Button className="mt-6" variant="outline" render={<Link href="/benchmarks" />}>Open the interactive explorer <ArrowRight /></Button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Metric label="1 simple tool" value="62 tokens" />
              <Metric label="64 complex tools" value="12,739 tokens" />
              <Metric label="Measured catalogs" value="18" />
              <Metric label="Generated schemas" value="375" />
              <p className="text-xs leading-5 text-muted-foreground sm:col-span-2">Derived 32-turn totals are labelled separately from directly measured values.</p>
            </div>
          </CardContent>
        </Card>
      </section>

      <section>
        <div className="mb-5"><Badge variant="outline">Developer experience</Badge><h2 className="mt-3 font-serif text-4xl tracking-tight">Basic compression in one call.</h2></div>
        <Card><CardContent><Tabs defaultValue="extractive"><TabsList className="h-auto flex-wrap"><TabsTrigger value="extractive">Extractive</TabsTrigger><TabsTrigger value="chat">Chat</TabsTrigger><TabsTrigger value="documents">RAG documents</TabsTrigger></TabsList>{Object.entries(code).map(([name, snippet]) => <TabsContent key={name} value={name} className="mt-4"><pre className="overflow-x-auto rounded-md border bg-muted/50 p-4 text-sm"><code>{snippet}</code></pre></TabsContent>)}</Tabs></CardContent></Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><Badge variant="outline" className="w-fit">Savings calculator</Badge><CardTitle className="mt-3">Estimate context spend.</CardTitle><CardDescription>Projection only—confirm model pricing and workload behavior independently.</CardDescription></CardHeader><CardContent className="space-y-5"><div className="space-y-2"><Label>Model input price / 1M tokens</Label><Select value={model} onValueChange={(value) => { if (value) setModel(value) }}><SelectTrigger className="w-full"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="2">$2.00 / 1M tokens</SelectItem><SelectItem value="1.25">$1.25 / 1M tokens</SelectItem><SelectItem value="0.5">$0.50 / 1M tokens</SelectItem><SelectItem value="0.2">$0.20 / 1M tokens</SelectItem></SelectContent></Select></div><SliderControl label="Requests / day" value={requests} min={1000} max={200000} step={1000} onChange={setSlider(setRequests)} /><SliderControl label="Average prompt tokens" value={tokens} min={300} max={8000} step={100} onChange={setSlider(setTokens)} /><SliderControl label="Target retention" value={retention} min={20} max={80} step={5} suffix="%" onChange={setSlider(setRetention)} /></CardContent></Card>
        <Card><CardHeader><CardTitle>Projected annual savings</CardTitle><CardDescription>Based on {saved.toLocaleString("en-US")} tokens saved per request.</CardDescription></CardHeader><CardContent className="space-y-5"><p className="font-serif text-5xl tracking-tight">${annual.toLocaleString("en-US", { maximumFractionDigits: 0 })}</p><div className="grid grid-cols-2 gap-3"><Metric label="Daily tokens saved" value={(saved * requests).toLocaleString("en-US")} /><Metric label="Retention target" value={`${retention}%`} /><Metric label="Requests / day" value={requests.toLocaleString("en-US")} /><Metric label="Prompt length" value={`${tokens.toLocaleString("en-US")} tokens`} /></div></CardContent><CardFooter><Button variant="outline" render={<Link href="/benchmarks" />}>Read methodology</Button></CardFooter></Card>
      </section>

      <section>
        <div className="mb-5"><Badge variant="outline">Compatibility</Badge><h2 className="mt-3 font-serif text-4xl tracking-tight">Works with your existing stack.</h2></div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{["OpenAI", "Anthropic", "Gemini", "Any Python client"].map((name) => <Card className="interactive-card" key={name}><CardHeader><Database className="size-5" /><CardTitle className="mt-3">{name}</CardTitle><CardDescription>Pass compressed text to your model client.</CardDescription></CardHeader><CardFooter><Button variant="ghost" size="sm" render={<Link href="/integrations" />}>View guide</Button></CardFooter></Card>)}</div>
      </section>

      <section id="faq" className="grid scroll-mt-28 gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Release roadmap</CardTitle><CardDescription>v0.4.0 is a Python release. Future milestones are exploratory.</CardDescription></CardHeader><CardContent className="space-y-3">{[["Released", "v0.4.0 · Contract-safe tool context"], ["Research", "Schema minification and selective loading"], ["Not promised", "No npm, Rust, ONNX, or WASM runtime"]].map(([label, text]) => <div key={label} className="flex gap-3"><Badge variant="outline">{label}</Badge><span className="text-sm text-muted-foreground">{text}</span></div>)}</CardContent></Card>
        <Card><CardHeader><CardTitle>Frequently asked questions</CardTitle></CardHeader><CardContent><Accordion>{faq.map(([question, answer]) => <AccordionItem key={question} value={question}><AccordionTrigger>{question}</AccordionTrigger><AccordionContent>{answer}</AccordionContent></AccordionItem>)}</Accordion></CardContent></Card>
      </section>

      <Alert className="border-amber-500/30 bg-amber-500/5"><ShieldAlert /><AlertTitle>Security boundary</AlertTitle><AlertDescription>LLMSlim mitigates compression-induced instruction elevation. It does not claim to solve prompt injection completely or authenticate caller-provided roles.</AlertDescription></Alert>

      <Card className="overflow-hidden bg-gradient-to-br from-violet-500/10 via-card to-blue-500/10">
        <CardHeader><Badge className="w-fit">Start saving tokens</Badge><CardTitle className="mt-3 font-serif text-3xl">Install LLMSlim in one command.</CardTitle><CardDescription>Try the live Studio, inspect the source, or install the released Python package.</CardDescription></CardHeader>
        <CardFooter className="flex flex-wrap gap-3"><Button variant="outline" onClick={copyInstall}><Terminal /> pip install llmslim {copied ? <Check className="text-primary" /> : <Copy />}</Button><Button render={<Link href="/playground" />}>Open Studio</Button><Button variant="ghost" render={<a href={siteConfig.pypi} target="_blank" rel="noreferrer" />}>View on PyPI</Button><Button variant="ghost" render={<a href={siteConfig.github} target="_blank" rel="noreferrer" />}>GitHub</Button></CardFooter>
      </Card>
    </div>
  )
}

function SliderControl({ label, value, suffix = "", onChange, min, max, step }: { label: string; value: number; suffix?: string; onChange: (value: number | readonly number[]) => void; min: number; max: number; step: number }) {
  return <div className="space-y-2"><div className="flex items-center justify-between"><Label>{label}</Label><Badge variant="outline">{value.toLocaleString("en-US")}{suffix}</Badge></div><Slider value={[value]} min={min} max={max} step={step} onValueChange={onChange} /></div>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border bg-background/50 p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-base font-medium">{value}</p></div>
}
