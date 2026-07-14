import React from "react";
import Link from "next/link";
import { constructMetadata } from "@/lib/seo";
import { INTEGRATIONS_REGISTRY, INTEGRATION_CATEGORIES } from "@/data/integrations";
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon";
import { ArrowRight, Layers, Cpu, Code, ShieldCheck, Sparkles } from "lucide-react";
import { Card } from "@/components/design-system";

export const metadata = constructMetadata({
  title: "Framework & Model Integrations — LLMSlim",
  description: "Production integration guides for OpenAI, Anthropic, Gemini, Groq, Mistral, Ollama, LangChain, LlamaIndex, CrewAI, Vercel AI SDK, Mastra, and FastAPI.",
});

export default function IntegrationsIndexPage() {
  const integrationList = Object.values(INTEGRATIONS_REGISTRY);

  return (
    <div className="space-y-12">
      {/* Integrations Directory Header Banner */}
      <div className="space-y-4 max-w-4xl">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono">
          <Layers className="w-3.5 h-3.5" />
          <span>Production Ecosystem Integration Directory</span>
        </div>
        <h1 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
          LLMSlim <span className="text-gradient-emerald">Integrations</span>
        </h1>
        <p className="text-slate-400 text-base leading-relaxed font-sans">
          Production setup guides, architecture blueprints, installation snippets, and benchmarks for your favorite LLM provider, framework, or backend service.
        </p>
      </div>

      {/* Categorized Integrations Grid */}
      <div className="space-y-12 pt-4">
        {INTEGRATION_CATEGORIES.map((category) => {
          const categoryItems = integrationList.filter((item) => item.category === category);
          if (categoryItems.length === 0) return null;

          return (
            <div key={category} className="space-y-6 border-t border-white/10 pt-8">
              <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-400 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                {category} Ecosystem ({categoryItems.length} Platforms)
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {categoryItems.map((item) => (
                  <Link key={item.slug} href={`/integrations/${item.slug}`} className="group flex">
                    <Card glowColor="emerald" className="p-6 h-full flex flex-col justify-between space-y-5 hover:border-emerald-500/50 transition-all w-full">
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="w-12 h-12 rounded-2xl bg-[#070A0F] border border-white/10 p-2 flex items-center justify-center shadow-lg group-hover:scale-105 transition-transform">
                            <IntegrationIcon iconKey={item.iconKey} className="w-7 h-7" />
                          </div>
                          <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-mono font-bold">
                            {item.badgeText}
                          </span>
                        </div>

                        <div className="space-y-1.5">
                          <h3 className="text-xl font-bold text-white group-hover:text-emerald-400 transition-colors font-sans">
                            {item.name}
                          </h3>
                          <p className="text-slate-400 text-xs line-clamp-2 leading-relaxed font-sans">
                            {item.tagline}
                          </p>
                        </div>
                      </div>

                      <div className="pt-2 text-xs font-mono text-emerald-400 flex items-center gap-1 group-hover:translate-x-1.5 transition-transform font-bold">
                        Integration Guide <ArrowRight className="w-3.5 h-3.5" />
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
