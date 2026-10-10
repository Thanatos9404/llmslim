import type { Metadata } from "next";
import { siteConfig } from "@/config/site";

const TEMPLATE = "%s | " + siteConfig.name;

/** Absolute URL for a site path ("/" or "/docs/getting-started"). */
export function absoluteUrl(path = "/"): string {
  return path === "/" ? siteConfig.url : siteConfig.url + path;
}

export function constructMetadata({
  title = siteConfig.title,
  description = siteConfig.description,
  image = siteConfig.ogImage,
  icons = [{ url: "/llmslim_logo.png", type: "image/png" }, { url: "/favicon.png", type: "image/png" }],
  noIndex = false,
  path,
  canonicalUrl,
  markdownPath,
  type = "website",
}: {
  title?: string; description?: string; image?: string; icons?: Array<{ url: string; type?: string }>; noIndex?: boolean;
  /** Site path of this page. Sets the canonical URL and og:url; without it a page would claim to be the homepage. */
  path?: string;
  /** Full canonical URL; prefer `path`. */
  canonicalUrl?: string;
  /** Path of the page's Markdown version for agents, advertised as rel="alternate" type="text/markdown". */
  markdownPath?: string;
  type?: "website" | "article";
} = {}): Metadata {
  const url = canonicalUrl || absoluteUrl(path);
  // Titles that already name the brand are used as-is; the rest get the " | LLMSlim" suffix once.
  const pageTitle = title.includes(siteConfig.name) ? { absolute: title, template: TEMPLATE } : { default: title, template: TEMPLATE };
  return {
    metadataBase: new URL(siteConfig.url),
    title: pageTitle,
    description, keywords: siteConfig.keywords,
    authors: [{ name: siteConfig.author, url: siteConfig.github }],
    creator: siteConfig.creator, publisher: siteConfig.publisher, category: siteConfig.category, applicationName: siteConfig.name,
    alternates: { canonical: url, ...(markdownPath ? { types: { "text/markdown": absoluteUrl(markdownPath) } } : {}) },
    verification: { google: siteConfig.googleSiteVerification },
    icons: { icon: icons, shortcut: "/llmslim_logo.png", apple: "/llmslim_logo.png" },
    openGraph: { title, description, url, siteName: siteConfig.name, images: [{ url: image, width: 1200, height: 630, alt: "LLMSlim, the context layer for production AI agents" }], locale: "en_US", type },
    twitter: { card: "summary_large_image", title, description, images: [image], creator: "@Thanatos9404", site: "@Thanatos9404" },
    robots: { index: !noIndex, follow: !noIndex, googleBot: { index: !noIndex, follow: !noIndex, "max-video-preview": -1, "max-image-preview": "large", "max-snippet": -1 } },
  };
}

const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

/**
 * Parse a content date ("July 15, 2026", "30 Sep 2026", "September 2026") as a UTC date, or undefined.
 * A month without a day means the first of that month. Unrecognized text never becomes a guessed date.
 */
export function contentDate(text: string | undefined): Date | undefined {
  const match = text?.trim().match(/^(?:(\d{1,2}) )?([A-Za-z]+)(?: (\d{1,2}),)? (\d{4})$/);
  if (!match) return undefined;
  const month = MONTHS.indexOf(match[2].slice(0, 3).toLowerCase());
  const day = Number(match[1] ?? match[3] ?? 1);
  if (month < 0 || day < 1 || day > 31) return undefined;
  return new Date(Date.UTC(Number(match[4]), month, day));
}

/** ISO calendar date (YYYY-MM-DD) for structured data, or undefined. */
export function isoDate(text: string | undefined): string | undefined {
  return contentDate(text)?.toISOString().slice(0, 10);
}

/** Serialize JSON-LD for an inline <script>; "<" is escaped so content can never close the tag. */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

/** FAQPage structured data. Use only on a page that shows these questions and answers. */
export function faqJsonLd(faqs: ReadonlyArray<readonly [string, string]>, path = "/") {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "@id": absoluteUrl(path) + "#faq",
    mainEntity: faqs.map(([question, answer]) => ({ "@type": "Question", name: question, acceptedAnswer: { "@type": "Answer", text: answer } })),
  };
}

export function breadcrumbJsonLd(items: ReadonlyArray<readonly [name: string, path: string]>) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map(([name, path], index) => ({ "@type": "ListItem", position: index + 1, name, item: absoluteUrl(path) })),
  };
}

/** TechArticle for documentation, guides and engineering notes, linked to the site's organization. */
export function techArticleJsonLd({ path, headline, description, section, dateModified, datePublished, author }: {
  path: string; headline: string; description: string; section?: string; dateModified?: string; datePublished?: string; author?: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "TechArticle",
    "@id": absoluteUrl(path) + "#article",
    headline, description, url: absoluteUrl(path), mainEntityOfPage: absoluteUrl(path), inLanguage: "en",
    ...(section ? { articleSection: section } : {}),
    ...(datePublished ? { datePublished } : {}),
    ...(dateModified ? { dateModified } : {}),
    author: { "@type": "Person", name: author || siteConfig.author, url: siteConfig.github },
    publisher: { "@id": siteConfig.url + "/#organization" },
    about: { "@id": siteConfig.url + "/#software" },
  };
}

export function getStructuredDataGraph() {
  const softwareApplication = {
    "@type": "SoftwareApplication", "@id": siteConfig.url + "/#software", name: siteConfig.name,
    operatingSystem: "Platform Independent", applicationCategory: "DeveloperApplication", applicationSubCategory: "AI context engineering library",
    softwareVersion: siteConfig.coreVersion, softwareRequirements: "Python",
    description: siteConfig.description, url: siteConfig.url, downloadUrl: siteConfig.pypi, installUrl: siteConfig.pypi, license: siteConfig.license,
    sameAs: [siteConfig.github, siteConfig.pypi],
    author: { "@type": "Person", name: siteConfig.author, url: siteConfig.github },
    publisher: { "@id": siteConfig.url + "/#organization" },
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD", availability: "https://schema.org/InStock" },
    featureList: ["Local extractive, rewrite, and hybrid context compression", "Provenance-aware ContextRole handling", "Adaptive token-budget context planning", "Role-aware chat and RAG pipeline helpers"],
  };
  const sourceCode = {
    "@type": "SoftwareSourceCode", "@id": siteConfig.url + "/#source", name: "LLMSlim Core", codeRepository: siteConfig.github,
    programmingLanguage: "Python", license: siteConfig.license, version: siteConfig.coreVersion, targetProduct: { "@id": siteConfig.url + "/#software" },
  };
  const organization = { "@type": "Organization", "@id": siteConfig.url + "/#organization", name: siteConfig.name, url: siteConfig.url, logo: { "@type": "ImageObject", url: siteConfig.logo, width: 512, height: 512 }, founder: { "@type": "Person", name: siteConfig.author, url: siteConfig.linkedin }, sameAs: [siteConfig.github, siteConfig.linkedin, siteConfig.pypi, siteConfig.productHunt] };
  const webSite = { "@type": "WebSite", "@id": siteConfig.url + "/#website", url: siteConfig.url, name: siteConfig.name, description: siteConfig.description, inLanguage: "en", publisher: { "@id": siteConfig.url + "/#organization" } };
  return { "@context": "https://schema.org", "@graph": [softwareApplication, sourceCode, organization, webSite] };
}
