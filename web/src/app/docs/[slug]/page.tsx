import React from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { constructMetadata } from "@/lib/seo";
import { DOCS_REGISTRY } from "@/data/docs";
import { DocCallout } from "@/components/docs/DocCallout";
import { DocCodeBlock } from "@/components/docs/DocCodeBlock";
import { ArrowLeft, ArrowRight, BookOpen, Clock, HelpCircle } from "lucide-react";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = DOCS_REGISTRY[slug];

  if (!doc) {
    return constructMetadata({
      title: "Page Not Found | LLMSlim Docs",
      description: "Requested documentation guide not found.",
    });
  }

  return constructMetadata({
    title: `${doc.title} — LLMSlim Documentation`,
    description: doc.description,
  });
}

export async function generateStaticParams() {
  return Object.keys(DOCS_REGISTRY).map((slug) => ({ slug }));
}

export default async function DocSlugPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = DOCS_REGISTRY[slug];

  if (!doc) {
    notFound();
  }

  // Build JSON-LD TechArticle & FAQPage Schema Graph for Google Search & AI Engines
  const techArticleJsonLd = {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    headline: doc.title,
    description: doc.description,
    url: `https://llmslim.app/docs/${doc.slug}`,
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
    doc.faqs.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: doc.faqs.map((faq) => ({
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
    <article className="space-y-10">
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

      {/* Header Info */}
      <div className="space-y-4 border-b border-white/10 pb-8">
        <div className="flex items-center gap-3 font-mono text-xs text-slate-400">
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold">
            {doc.category}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {doc.readingTime}
          </span>
          <span>•</span>
          <span>Updated {doc.lastUpdated}</span>
        </div>

        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          {doc.title}
        </h1>

        <p className="text-base sm:text-lg text-slate-300 font-sans leading-relaxed">
          {doc.subtitle}
        </p>
      </div>

      {/* Sections Flow */}
      <div className="space-y-10">
        {doc.sections.map((section) => (
          <section key={section.id} id={section.id} className="space-y-4 scroll-mt-32">
            <h2 className="text-2xl font-bold text-white tracking-tight border-b border-white/5 pb-2 font-sans">
              {section.title}
            </h2>

            <div className="text-slate-300 text-sm leading-relaxed whitespace-pre-line font-sans">
              {section.content}
            </div>

            {section.callout && <DocCallout callout={section.callout} />}

            {section.codeSnippet && (
              <DocCodeBlock
                language={section.codeSnippet.language}
                filename={section.codeSnippet.filename}
                code={section.codeSnippet.code}
              />
            )}
          </section>
        ))}
      </div>

      {/* Per-Page FAQs for AI Search & Google Indexing */}
      {doc.faqs.length > 0 && (
        <section id="faqs" className="space-y-6 pt-8 border-t border-white/10">
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 font-sans">
            <HelpCircle className="w-5 h-5 text-emerald-400" />
            Frequently Asked Questions
          </h2>

          <div className="space-y-4">
            {doc.faqs.map((faq, idx) => (
              <div key={idx} className="p-5 rounded-2xl bg-[#0D121C] border border-white/10 space-y-2">
                <h3 className="text-base font-bold text-white font-sans">
                  {faq.question}
                </h3>
                <p className="text-slate-400 text-xs leading-relaxed font-sans">
                  {faq.answer}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Footer Related Guides Navigation */}
      {doc.relatedPages.length > 0 && (
        <div className="pt-10 border-t border-white/10 space-y-4">
          <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">
            Next Recommended Guides
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {doc.relatedPages.map((rel) => (
              <Link key={rel.slug} href={`/docs/${rel.slug}`} className="group">
                <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 hover:border-emerald-500/40 transition-colors flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-200 group-hover:text-emerald-400 font-bold transition-colors">
                    {rel.title}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-emerald-400 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}
