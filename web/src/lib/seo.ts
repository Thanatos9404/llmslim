import type { Metadata } from "next";
import { siteConfig } from "@/config/site";

export function constructMetadata({
  title = siteConfig.title,
  description = siteConfig.description,
  image = siteConfig.ogImage,
  icons = [{ url: "/llmslim_logo.png", type: "image/png" }, { url: "/favicon.png", type: "image/png" }],
  noIndex = false,
  canonicalUrl,
}: {
  title?: string; description?: string; image?: string; icons?: Array<{ url: string; type?: string }>; noIndex?: boolean; canonicalUrl?: string;
} = {}): Metadata {
  return {
    metadataBase: new URL(siteConfig.url),
    title: { default: title, template: "%s | " + siteConfig.name },
    description, keywords: siteConfig.keywords,
    authors: [{ name: siteConfig.author, url: siteConfig.github }],
    creator: siteConfig.creator, publisher: siteConfig.publisher, category: siteConfig.category, applicationName: siteConfig.name,
    alternates: { canonical: canonicalUrl || siteConfig.url },
    verification: { google: siteConfig.googleSiteVerification },
    icons: { icon: icons, shortcut: "/llmslim_logo.png", apple: "/llmslim_logo.png" },
    openGraph: { title, description, url: canonicalUrl || siteConfig.url, siteName: siteConfig.name, images: [{ url: image, width: 1200, height: 630, alt: "LLMSlim Python context compression" }], locale: "en_US", type: "website" },
    twitter: { card: "summary_large_image", title, description, images: [image], creator: "@Thanatos9404", site: "@Thanatos9404" },
    robots: { index: !noIndex, follow: !noIndex, googleBot: { index: !noIndex, follow: !noIndex, "max-video-preview": -1, "max-image-preview": "large", "max-snippet": -1 } },
  };
}
export function getStructuredDataGraph() {
  const softwareApplication = {
    "@type": "SoftwareApplication", "@id": siteConfig.url + "/#software", name: siteConfig.name,
    operatingSystem: "Platform Independent", applicationCategory: "DeveloperApplication", softwareVersion: siteConfig.version,
    description: siteConfig.description, url: siteConfig.url, downloadUrl: siteConfig.pypi, programmingLanguage: "Python", license: siteConfig.license,
    author: { "@type": "Person", name: siteConfig.author, url: siteConfig.github },
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD", availability: "https://schema.org/InStock" },
    featureList: ["Extractive, rewrite, and hybrid Python compression", "Provenance-aware ContextRole handling", "Role-aware chat and RAG pipeline helpers", "Token-counter telemetry"],
  };
  const organization = { "@type": "Organization", "@id": siteConfig.url + "/#organization", name: siteConfig.name, url: siteConfig.url, logo: { "@type": "ImageObject", url: siteConfig.logo, width: 512, height: 512 }, sameAs: [siteConfig.github, siteConfig.pypi] };
  const webSite = { "@type": "WebSite", "@id": siteConfig.url + "/#website", url: siteConfig.url, name: siteConfig.name, description: siteConfig.description, publisher: { "@id": siteConfig.url + "/#organization" } };
  const faqPage = { "@type": "FAQPage", "@id": siteConfig.url + "/#faq", mainEntity: [
    { "@type": "Question", name: "What does provenance-aware priority handling do?", acceptedAnswer: { "@type": "Answer", text: "It prevents untrusted RAG, tool, and assistant content from gaining protected priority solely through imperative or safety-critical wording." } },
    { "@type": "Question", name: "Does LLMSlim prevent prompt injection?", acceptedAnswer: { "@type": "Answer", text: "No. It mitigates compression-induced instruction elevation and applications still need defense in depth." } },
    { "@type": "Question", name: "Does LLMSlim require remote calls?", acceptedAnswer: { "@type": "Answer", text: "The default extractive strategy runs locally. Rewrite and hybrid strategies use a caller-supplied provider." } },
  ] };
  return { "@context": "https://schema.org", "@graph": [softwareApplication, organization, webSite, faqPage] };
}
