import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { constructMetadata } from "@/lib/seo";
import { INTEGRATIONS_REGISTRY } from "@/data/integrations";
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon";
import { DocCodeBlock } from "@/components/docs/DocCodeBlock";
import { ArrowLeft, CheckCircle2, Cpu, HelpCircle, AlertTriangle, Layers, Zap, ShieldCheck } from "lucide-react";
import { Card } from "@/components/design-system";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const item = INTEGRATIONS_REGISTRY[slug];

  if (!item) {
    return constructMetadata({
      title: "Integration Not Found | LLMSlim",
      description: "Requested platform integration not found.",
    });
  }

  return constructMetadata({
    title: `LLMSlim + ${item.name} Integration Guide — Prompt & Context Compression`,
    description: item.description,
  });
}

export async function generateStaticParams() {
  return Object.keys(INTEGRATIONS_REGISTRY).map((slug) => ({ slug }));
}

export default async function IntegrationSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const item = INTEGRATIONS_REGISTRY[slug];

  if (!item) {
    notFound();
  }

  // Build JSON-LD TechArticle & SoftwareApplication Schema Graph
  const techArticleJsonLd = {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    headline: `LLMSlim + ${item.name} Production Integration Guide`,
    description: item.description,
    url: `https://llmslim.app/integrations/${item.slug}`,
    datePublished: "2026-07-15",
    dateModified: "2026-07-15",
    author: {
      "@type": "Person",
      name: "Yashvardhan Thanvi",
      url: "https://github.com/Thanatos9404",
    },
    publisher: {
      "@type": "Organization",
      name: "LLMSlim",
      logo: {
        "@type": "ImageObject",
        url: "https://llmslim.app/llmslim_logo.png",
      },
    },
  };

  const faqJsonLd =
    item.faqs.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: item.faqs.map((faq) => ({
            "@type": "Question",
            name: faq.question,
            acceptedAnswer: {
              "@type": "Answer",
              text: faq.answer,
            },
          })),
        }
      : null;

  return (
    <div className="max-w-4xl mx-auto space-y-12 font-sans">
      {/* JSON-LD Structured Data Schema Insertion */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(techArticleJsonLd) }}
      />
      {faqJsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
        />
      )}

      {/* Top Back Link */}
      <Link href="/integrations" className="inline-flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-emerald-400 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Integrations Directory
      </Link>

      {/* Header Banner */}
      <div className="space-y-6 border-b border-white/10 pb-8">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-[#070A0F] border border-white/15 p-3 flex items-center justify-center shadow-xl">
            <IntegrationIcon iconKey={item.iconKey} className="w-10 h-10" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono font-bold">
                {item.category}
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-mono font-bold">
                {item.badgeText}
              </span>
            </div>
            <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
              LLMSlim + {item.name}
            </h1>
          </div>
        </div>

        <p className="text-base sm:text-xl text-slate-300 font-normal leading-relaxed">
          {item.tagline}
        </p>

        <p className="text-sm text-slate-400 leading-relaxed">
          {item.description}
        </p>
      </div>

      {/* Step 1: Installation */}
      <section id="installation" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <Zap className="w-5 h-5 text-emerald-400" /> 1. Package Installation
        </h2>
        <p className="text-xs font-mono text-slate-400">
          Install LLMSlim and the official {item.name} SDK using your package manager:
        </p>
        <DocCodeBlock
          language="bash"
          filename="terminal"
          code={item.installation.command}
        />
      </section>

      {/* Step 2: Architecture Workflow */}
      <section id="architecture" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <Layers className="w-5 h-5 text-emerald-400" /> 2. Architecture & Execution Flow
        </h2>
        <div className="p-6 rounded-2xl bg-[#0D121C] border border-white/10 space-y-3 font-mono text-xs text-slate-300">
          {item.architectureFlow.map((step, idx) => (
            <div key={idx} className="flex items-start gap-3">
              <span className="text-emerald-400 font-bold shrink-0">STEP 0{idx + 1}</span>
              <p className="leading-relaxed">{step}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Step 3: Production Runnable Code */}
      <section id="code-example" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <Cpu className="w-5 h-5 text-emerald-400" /> 3. Production Code Pattern
        </h2>
        <p className="text-xs font-mono text-slate-400">
          Complete, runnable implementation wrapper for {item.name}:
        </p>
        <DocCodeBlock
          language={item.codeExample.language}
          filename={item.codeExample.filename}
          code={item.codeExample.code}
        />
      </section>

      {/* Step 4: Production Deployment */}
      <section id="deployment" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <ShieldCheck className="w-5 h-5 text-emerald-400" /> 4. Production Deployment Best Practices
        </h2>
        <div className="p-5 rounded-2xl bg-white/[0.03] border border-white/10 text-slate-300 text-sm leading-relaxed font-sans">
          {item.deploymentGuide}
        </div>
      </section>

      {/* Step 5: Optimization Tips */}
      <section id="optimization-tips" className="space-y-4 scroll-mt-32">
        <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" /> 5. Key Optimization Tips
        </h2>
        <Card glowColor="emerald" className="p-6">
          <ul className="space-y-2.5 font-sans text-xs text-slate-300">
            {item.optimizationTips.map((tip, idx) => (
              <li key={idx} className="flex items-start gap-2.5">
                <span className="text-emerald-400 font-mono font-bold">0{idx + 1}.</span>
                <span>{tip}</span>
              </li>
            ))}
          </ul>
        </Card>
      </section>

      {/* Step 6: Benchmarks */}
      {item.benchmarks.length > 0 && (
        <section id="benchmarks" className="space-y-4 scroll-mt-32">
          <h2 className="text-2xl font-bold text-white tracking-tight font-sans">
            6. Performance Metrics & Benchmark Matrix
          </h2>
          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#0D121C] font-mono text-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/10 bg-[#070A0F] text-emerald-400">
                  <th className="px-4 py-3 font-bold uppercase tracking-wider">Metric Dimension</th>
                  <th className="px-4 py-3 font-bold uppercase tracking-wider">Uncompressed Payload</th>
                  <th className="px-4 py-3 font-bold uppercase tracking-wider">LLMSlim Compressed</th>
                  <th className="px-4 py-3 font-bold uppercase tracking-wider">Recorded Impact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-slate-200">
                {item.benchmarks.map((row, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition-colors font-tabular">
                    <td className="px-4 py-3 font-bold text-slate-100">{row.metric}</td>
                    <td className="px-4 py-3 text-slate-400">{row.uncompressed}</td>
                    <td className="px-4 py-3 text-emerald-400 font-bold">{row.compressed}</td>
                    <td className="px-4 py-3 text-cyan-400 font-bold">{row.impact}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Step 7: Platform FAQs */}
      {item.faqs.length > 0 && (
        <section id="faqs" className="space-y-4 scroll-mt-32">
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
            <HelpCircle className="w-5 h-5 text-emerald-400" /> 7. Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {item.faqs.map((faq, idx) => (
              <div key={idx} className="p-5 rounded-2xl bg-[#0D121C] border border-white/10 space-y-2">
                <h3 className="text-base font-bold text-white font-sans">{faq.question}</h3>
                <p className="text-slate-400 text-xs leading-relaxed font-sans">{faq.answer}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Step 8: Troubleshooting Guide */}
      {item.troubleshooting.length > 0 && (
        <section id="troubleshooting" className="space-y-4 scroll-mt-32">
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
            <AlertTriangle className="w-5 h-5 text-amber-400" /> 8. Troubleshooting & Diagnostics
          </h2>
          <div className="space-y-4">
            {item.troubleshooting.map((item, idx) => (
              <div key={idx} className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/20 space-y-2 text-xs font-sans">
                <div className="font-mono font-bold text-amber-300 uppercase tracking-wider">
                  Issue: {item.issue}
                </div>
                <div className="text-amber-200/90 leading-relaxed pl-4 border-l border-amber-500/30">
                  Solution: {item.solution}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
