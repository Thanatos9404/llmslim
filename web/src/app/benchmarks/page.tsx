import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowUpRight, BarChart3, CheckCircle2, FileText, ShieldCheck, Timer, TriangleAlert } from "lucide-react";
import { constructMetadata } from "@/lib/seo";
import { getPhase2Truth, phase2ReleaseGate } from "@/lib/phase2-data";
import { SchemaTaxExplorer } from "@/components/benchmarks/SchemaTaxExplorer";

export const metadata = constructMetadata({ title: "Benchmarks | LLMSlim", description: "Phase 2 evaluation: reproducible context-compression, security, structure, and schema-tax evidence.", canonicalUrl: "https://www.llmslim.app/benchmarks" });

function percent(value: number) { return `${(value * 100).toFixed(1)}%`; }

export default function BenchmarksPage() {
  const phase2 = getPhase2Truth();
  const micro = phase2.summary.micro;
  const structural = phase2.summary.structural_integrity;

  return <div className="benchmark-page">
    <header className="benchmark-hero"><div><span className="eyebrow">Phase 2 evaluation system</span><h1>Evidence that keeps its <span>limitations visible.</span></h1><p>LLMSlim’s offline, deterministic evaluation separates measured results from derived session totals and work that is not applicable to the released local engine.</p><div className="benchmark-hero__actions"><Link href="/docs/getting-started" className="button button--primary">Read the docs <ArrowUpRight size={15} /></Link><a href="https://github.com/Thanatos9404/llmslim" target="_blank" rel="noreferrer" className="button">Inspect source <ArrowUpRight size={15} /></a></div></div><div className="benchmark-hero__proof"><span>Release gate</span><strong>PASS</strong><p>Offline runner · canonical JSON · independent labels</p><div><i>Measured</i><i>Derived</i><i>Not applicable</i></div></div></header>

    <section className="phase-metric-grid" aria-label="Phase 2 evaluation metrics">
      <Metric value={`${phase2ReleaseGate.testsPassed}`} label="tests passing" detail={`${phase2ReleaseGate.testsFailed} failures`} />
      <Metric value={`${phase2ReleaseGate.branchCoverage}%`} label="branch coverage" detail={`${phase2ReleaseGate.coverageGate}% release gate`} />
      <Metric value={`${Object.keys(phase2.dataset.categories).length}`} label="evaluation categories" detail={`${phase2.dataset.sample_count} curated samples`} />
      <Metric value={`${Object.keys(phase2.dataset.languages).length}`} label="languages" detail="English · Hindi · Chinese · Japanese" />
      <Metric value={`${phase2.schema_tax.tool_schema_count}`} label="generated schemas" detail={`${phase2.schema_tax.catalog_count} measured catalogs`} />
      <Metric value="0" label="provenance violations" detail={`${phase2.security.toLowerCase()} security regression`} />
    </section>

    <section className="benchmark-band"><div className="benchmark-band__intro"><span className="section-label">Compression quality</span><h2>Small corpus. Explicitly scoped.</h2><p>The 24 synthetic, independently labelled samples are a transparent regression set—not population-level proof. The default suite exercises extractive compression; provider-dependent rewrite and hybrid results are not reported as local measurements.</p><Link href="/docs/getting-started">Start with the released Python API <ArrowUpRight size={14} /></Link></div><div className="retention-grid"><Retention icon={<ShieldCheck size={18} />} label="Instruction retention" value={percent(micro.instruction_retention.mean)} note={`${micro.instruction_retention.count} applicable labels · measured`} /><Retention icon={<CheckCircle2 size={18} />} label="Entity retention" value={percent(micro.entity_retention.mean)} note={`${micro.entity_retention.count} applicable labels · measured`} /><Retention icon={<BarChart3 size={18} />} label="Lexical Jaccard" value={percent(micro.semantic_similarity.mean)} note={`${micro.semantic_similarity.count} samples · proxy, not semantic equivalence`} /><Retention icon={<Timer size={18} />} label="Median latency" value={`${micro.latency_ms.median.toFixed(3)} ms`} note={`p95 ${micro.latency_ms.p95.toFixed(3)} ms · local wall-clock`} /></div></section>

    <SchemaTaxExplorer catalogs={phase2.schema_tax_details.catalogs} />

    <section className="benchmark-report-grid"><article><span className="section-label">Structural integrity</span><h2>{structural.valid_count} / {structural.applicable_count} checks passed.</h2><p>The Markdown structural sample is invalid after compression. It is retained as a visible limitation; JSON, XML, YAML, and code checks are not presented as a blanket preservation claim.</p><span className="benchmark-status benchmark-status--warning"><TriangleAlert size={15} /> Known limitation</span></article><article><span className="section-label">Security regression</span><h2>Priority cannot be earned by imperative text.</h2><p>RAG, tool, and assistant context cannot be elevated to protected priority solely by wording. This mitigates compression-induced instruction elevation; it does not claim complete prompt-injection prevention.</p><span className="benchmark-status"><ShieldCheck size={15} /> 0 observed boundary violations</span></article><article><span className="section-label">Reproducibility</span><h2>Results exist as checked-in artifacts.</h2><p>Dataset composition, mode, iteration metadata, classification, and environment details are emitted with the canonical output. Run the repository suite on your own hardware before making performance decisions.</p><a href="https://github.com/Thanatos9404/llmslim" target="_blank" rel="noreferrer" className="benchmark-link"><FileText size={15} /> Open the repository <ArrowUpRight size={14} /></a></article></section>

    <section className="benchmark-methodology" id="methodology"><div><span className="section-label">Methodology</span><h2>Claims carry their own class.</h2></div><div className="methodology-steps"><div><b>Measured</b><p>Observed from the deterministic suite: retention, ratios, structure, latency, schema catalog tokens, and security regressions.</p></div><div><b>Derived</b><p>Explicit arithmetic from measured catalog tokens, such as 16- and 32-turn totals assuming a full catalog is resent each turn.</p></div><div><b>Not applicable</b><p>Provider-dependent rewrite/hybrid outcomes, dollar savings, and tool-selection quality are not fabricated for the default local suite.</p></div></div></section>
  </div>;
}

function Metric({ value, label, detail }: { value: string; label: string; detail: string }) { return <div className="phase-metric"><strong>{value}</strong><span>{label}</span><small>{detail}</small></div>; }
function Retention({ icon, label, value, note }: { icon: ReactNode; label: string; value: string; note: string }) { return <div className="retention-card"><span>{icon}{label}</span><strong>{value}</strong><small>{note}</small></div>; }
