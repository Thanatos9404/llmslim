"use client";

import { useMemo, useState, type ReactNode } from "react";
import { ArrowUpRight, Braces, Gauge, Layers3, ShieldCheck } from "lucide-react";
import type { SchemaComplexity, SchemaTaxCatalog } from "@/lib/phase2-data";

interface SchemaTaxExplorerProps {
  catalogs: SchemaTaxCatalog[];
  compact?: boolean;
}

const toolCounts = [1, 4, 8, 16, 32, 64];
const complexities: SchemaComplexity[] = ["SIMPLE", "MEDIUM", "COMPLEX"];

function formatTokens(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

export function SchemaTaxExplorer({ catalogs, compact = false }: SchemaTaxExplorerProps) {
  const [toolCount, setToolCount] = useState(64);
  const [complexity, setComplexity] = useState<SchemaComplexity>("COMPLEX");
  const catalog = useMemo(() => catalogs.find((item) => item.tool_count === toolCount && item.complexity === complexity) ?? catalogs[0], [catalogs, complexity, toolCount]);
  const sixteenTurns = catalog?.cumulative_schema_tokens["16"]?.tokens ?? 0;
  const thirtyTwoTurns = catalog?.cumulative_schema_tokens["32"]?.tokens ?? 0;

  if (!catalog) return null;

  return <section className={`schema-explorer ${compact ? "schema-explorer--compact" : ""}`} aria-labelledby="schema-explorer-title">
    <div className="schema-explorer__header">
      <div><span className="section-label">Research track · not shipped</span><h2 id="schema-explorer-title">The schema tax is visible.</h2><p>Measured synthetic tool contracts show the context cost of resending a whole catalog. This is measurement, not schema compression, selection, or lazy loading.</p></div>
      <div className="schema-explorer__legend"><span>Measured</span><span>Derived</span></div>
    </div>
    <div className="schema-explorer__body">
      <div className="schema-controls">
        <fieldset><legend>Catalog tools</legend><div className="segmented-control" aria-label="Tool count">{toolCounts.map((count) => <button type="button" aria-pressed={toolCount === count} onClick={() => setToolCount(count)} key={count}>{count}</button>)}</div></fieldset>
        <fieldset><legend>Schema complexity</legend><div className="segmented-control" aria-label="Schema complexity">{complexities.map((item) => <button type="button" aria-pressed={complexity === item} onClick={() => setComplexity(item)} key={item}>{item[0] + item.slice(1).toLowerCase()}</button>)}</div></fieldset>
        <p className="schema-controls__note"><ShieldCheck size={15} /> Contracts retain names, parameter types, required fields, enums, nested shape, constraints, and meaningful defaults in the research comparison.</p>
      </div>
      <div className="schema-result" aria-live="polite">
        <div className="schema-result__lead"><div className="schema-result__icon"><Braces size={20} /></div><div><span>Measured full catalog</span><strong>{formatTokens(catalog.total_schema_tokens)} tokens</strong><small>{catalog.token_counter_used} · {complexity.toLowerCase()} · {toolCount} tools</small></div></div>
        <div className="schema-result__meters"><Meter label="Tokens per tool" value={catalog.mean_tokens_per_tool} suffix="" icon={<Gauge size={15} />} /><Meter label="16 turns" value={sixteenTurns} suffix="tokens" derived /><Meter label="32 turns" value={thirtyTwoTurns} suffix="tokens" derived /></div>
        <p className="schema-result__question">Why send {toolCount} contracts when the model may need one?</p>
      </div>
    </div>
    {!compact && <div className="schema-explorer__foot"><Layers3 size={16} /><span>Future research: contract-safe minification, relevance evaluation, selective loading, and lazy schema hydration.</span><a href="#methodology">Read methodology <ArrowUpRight size={14} /></a></div>}
  </section>;
}

function Meter({ label, value, suffix, icon, derived = false }: { label: string; value: number; suffix: string; icon?: ReactNode; derived?: boolean }) {
  return <div className="schema-meter"><span>{icon}{label}{derived && <i>Derived</i>}</span><strong>{formatTokens(value)} {suffix}</strong></div>;
}
