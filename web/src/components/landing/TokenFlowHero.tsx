"use client"

import Link from "next/link"
import type { CSSProperties } from "react"
import { useMemo, useState } from "react"
import { ArrowRight, Check, Copy, LockKeyhole, Play, RotateCcw, Sparkles } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

const sourceTokens = [
  ["Please", true], ["carefully", false], ["review", true], ["all", false], ["of", false], ["the", false],
  ["retrieved", true], ["billing", true], ["context", false], ["and", false], ["make", false], ["sure", false],
  ["you", false], ["must", true], ["return", true], ["valid", true], ["JSON", true], ["with", false],
  ["sources", true], ["and", false], ["exact", true], ["seat", true], ["counts", true], ["only", false],
] as const

const outputByMode = {
  balanced: ["Review", "billing", "context", "Return", "valid", "JSON", "sources", "exact", "seat", "counts"],
  aggressive: ["Billing", "Return", "JSON", "sources", "seat", "counts"],
  protected: ["must", "return", "valid", "JSON", "sources", "exact", "seat", "counts"],
} as const

type FlowMode = keyof typeof outputByMode

export function TokenFlowHero() {
  const [mode, setMode] = useState<FlowMode>("balanced")
  const [retention, setRetention] = useState(50)
  const [playing, setPlaying] = useState(true)
  const [copied, setCopied] = useState(false)
  const output = outputByMode[mode]
  const saved = Math.max(18, Math.round(100 - retention))
  const flowKey = useMemo(() => `${mode}-${retention}-${playing}`, [mode, retention, playing])

  const copyInstall = async () => {
    await navigator.clipboard.writeText("pip install llmslim")
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <section className="flow-hero relative isolate overflow-hidden rounded-[2rem] border bg-card/70 px-5 py-10 shadow-2xl shadow-primary/5 backdrop-blur sm:px-10 sm:py-14 lg:px-14 lg:py-16">
      <div className="flow-hero__orb flow-hero__orb--one" aria-hidden="true" />
      <div className="flow-hero__orb flow-hero__orb--two" aria-hidden="true" />
      <div className="relative z-10 mx-auto flex max-w-4xl flex-col items-center text-center">
        <Badge variant="secondary" className="gap-2"><Sparkles className="size-3.5" /> Local-first context compression</Badge>
        <h1 className="mt-6 max-w-4xl font-serif text-5xl leading-[0.95] font-medium tracking-[-0.055em] text-balance sm:text-7xl lg:text-[6.5rem]">
          Less context, <em className="font-normal text-violet-500 dark:text-violet-300">more signal.</em>
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
          Watch verbose context flow through LLMSlim while instructions, entities, numbers, and provenance stay visible.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-3">
          <Button size="lg" render={<Link href="/playground" />}><Play /> Try live compression</Button>
          <Button size="lg" variant="outline" render={<Link href="/docs/getting-started" />}>Read the docs <ArrowRight /></Button>
        </div>
      </div>

      <Card className="flow-stage relative z-10 mx-auto mt-12 max-w-6xl overflow-visible bg-background/75 backdrop-blur-xl">
        <CardContent className="p-3 sm:p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Tabs value={mode} onValueChange={(value) => setMode(value as FlowMode)}>
              <TabsList>
                <TabsTrigger value="balanced">Balanced</TabsTrigger>
                <TabsTrigger value="aggressive">Aggressive</TabsTrigger>
                <TabsTrigger value="protected">Instruction lock</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{saved}% fewer tokens</Badge>
              <Button size="icon-sm" variant="ghost" onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause token flow" : "Play token flow"}>{playing ? <RotateCcw /> : <Play />}</Button>
            </div>
          </div>

          <div key={flowKey} className={`token-flow ${playing ? "is-playing" : "is-paused"}`}>
            <div className="token-flow__lane token-flow__lane--input">
              <span className="token-flow__label">Verbose context</span>
              <div className="token-cloud" aria-label="Input tokens">
                {sourceTokens.map(([token, protectedToken], index) => (
                  <span key={`${token}-${index}`} className={`token-chip ${protectedToken ? "token-chip--signal" : ""}`} style={{ "--token-index": index } as CSSProperties}>{token}</span>
                ))}
              </div>
            </div>

            <div className="compression-core" aria-label="LLMSlim compression field">
              <div className="compression-core__rings" aria-hidden="true"><i /><i /><i /></div>
              <div className="compression-core__body"><Sparkles className="size-5" /><strong>LLMSlim</strong><span>rank · protect · select</span></div>
              <div className="compression-core__lock"><LockKeyhole className="size-3.5" /> priority preserved</div>
            </div>

            <div className="token-flow__lane token-flow__lane--output">
              <span className="token-flow__label">Compressed context</span>
              <div className="output-stream" aria-label="Compressed output tokens">
                {output.map((token, index) => <span key={`${token}-${index}`} className="output-token" style={{ "--output-index": index } as CSSProperties}>{token}</span>)}
              </div>
              <div className="flow-result"><Check className="size-4" /><span>Constraints intact</span><b>{output.length} tokens</b></div>
            </div>
          </div>

          <div className="mt-5 grid gap-4 border-t pt-5 md:grid-cols-[1fr_auto] md:items-center">
            <div className="space-y-2"><div className="flex items-center justify-between text-sm"><span className="text-muted-foreground">Target retention</span><Badge variant="secondary">{retention}%</Badge></div><Slider value={[retention]} min={20} max={80} step={5} onValueChange={(value) => setRetention(Array.isArray(value) ? value[0] : value)} aria-label="Target token retention" /></div>
            <Button variant="outline" onClick={copyInstall}>{copied ? <Check /> : <Copy />} {copied ? "Copied" : "pip install llmslim"}</Button>
          </div>
        </CardContent>
      </Card>
    </section>
  )
}
