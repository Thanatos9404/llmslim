import Link from "next/link";
import { ArrowUpRight, PlugZap } from "lucide-react";
import { constructMetadata } from "@/lib/seo";
import { INTEGRATIONS_REGISTRY, INTEGRATION_CATEGORIES } from "@/data/integrations";
import { IntegrationIcon } from "@/components/integrations/IntegrationIcon";

export const metadata = constructMetadata({ title: "Python Integrations | LLMSlim", description: "Use LLMSlim output with documented Python model-client examples." });

export default function IntegrationsIndexPage() {
  const integrations = Object.values(INTEGRATIONS_REGISTRY);
  return <div className="hub-page integration-page"><header className="hub-header"><span className="hub-eyebrow"><PlugZap size={14} /> Python client examples</span><h1>Output that fits <span>your existing stack.</span></h1><p>These are integration patterns for passing LLMSlim output into model clients. They are not provider-specific adapters, and provider calls remain your application’s responsibility.</p></header><div className="integration-catalog">{INTEGRATION_CATEGORIES.map((category) => { const entries = integrations.filter((item) => item.category === category); if (!entries.length) return null; return <section key={category}><div className="integration-catalog__head"><span>{category}</span><small>{entries.length} examples</small></div><div className="integration-catalog__grid">{entries.map((item) => <Link href={`/integrations/${item.slug}`} className="integration-card" key={item.slug}><div><span className="integration-card__icon"><IntegrationIcon iconKey={item.iconKey} className="w-6 h-6" /></span><i>{item.badgeText}</i></div><h2>{item.name}</h2><p>{item.tagline}</p><span className="integration-card__link">Read guide <ArrowUpRight size={15} /></span></Link>)}</div></section>; })}</div></div>;
}
