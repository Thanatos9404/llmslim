import type { Metadata } from "next";
import { siteConfig } from "@/config/site";

export function constructMetadata({
  title = siteConfig.title,
  description = siteConfig.description,
  image = siteConfig.ogImage,
  icons = [
    { url: "/llmslim_logo.png", type: "image/png" },
    { url: "/favicon.png", type: "image/png" },
  ],
  noIndex = false,
  canonicalUrl,
}: {
  title?: string;
  description?: string;
  image?: string;
  icons?: Array<{ url: string; type?: string }>;
  noIndex?: boolean;
  canonicalUrl?: string;
} = {}): Metadata {
  return {
    metadataBase: new URL(siteConfig.url),
    title: {
      default: title,
      template: `%s | ${siteConfig.name}`,
    },
    description,
    keywords: siteConfig.keywords,
    authors: [{ name: siteConfig.author, url: siteConfig.github }],
    creator: siteConfig.creator,
    publisher: siteConfig.publisher,
    category: siteConfig.category,
    applicationName: siteConfig.name,
    alternates: {
      canonical: canonicalUrl || siteConfig.url,
    },
    verification: {
      google: siteConfig.googleSiteVerification,
    },
    icons: {
      icon: icons,
      shortcut: "/llmslim_logo.png",
      apple: "/llmslim_logo.png",
    },
    openGraph: {
      title,
      description,
      url: canonicalUrl || siteConfig.url,
      siteName: siteConfig.name,
      images: [
        {
          url: image,
          width: 1200,
          height: 630,
          alt: `${siteConfig.name} Enterprise Prompt Compression Architecture`,
        },
      ],
      locale: "en_US",
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
      creator: "@Thanatos9404",
      site: "@Thanatos9404",
    },
    robots: {
      index: !noIndex,
      follow: !noIndex,
      googleBot: {
        index: !noIndex,
        follow: !noIndex,
        "max-video-preview": -1,
        "max-image-preview": "large",
        "max-snippet": -1,
      },
    },
  };
}

/**
 * Generates comprehensive Schema.org JSON-LD graph objects
 * for Google AI Overviews, Perplexity, ChatGPT, and Rich Snippets.
 */
export function getStructuredDataGraph() {
  const softwareApplication = {
    "@type": "SoftwareApplication",
    "@id": `${siteConfig.url}/#software`,
    name: siteConfig.name,
    operatingSystem: "Platform Independent",
    applicationCategory: "DeveloperApplication",
    softwareVersion: siteConfig.version,
    description: siteConfig.description,
    url: siteConfig.url,
    downloadUrl: siteConfig.pypi,
    programmingLanguage: "Python",
    license: siteConfig.license,
    author: {
      "@type": "Person",
      name: siteConfig.author,
      url: siteConfig.github,
    },
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      availability: "https://schema.org/InStock",
    },
    featureList: [
      "100.0% Instruction Fidelity Retention Shield",
      "Sub-50ms Offline LexRank TF-IDF Sentence Scoring",
      "Multi-turn Chat Message Context Compression",
      "Semantic RAG Vector Document Chunk Re-ranking",
      "Model Agnostic (OpenAI, Claude, Gemini, DeepSeek)",
    ],
  };

  const organization = {
    "@type": "Organization",
    "@id": `${siteConfig.url}/#organization`,
    name: siteConfig.name,
    url: siteConfig.url,
    logo: {
      "@type": "ImageObject",
      url: siteConfig.logo,
      width: 512,
      height: 512,
    },
    sameAs: [siteConfig.github, siteConfig.pypi],
  };

  const webSite = {
    "@type": "WebSite",
    "@id": `${siteConfig.url}/#website`,
    url: siteConfig.url,
    name: siteConfig.name,
    description: siteConfig.description,
    publisher: {
      "@id": `${siteConfig.url}/#organization`,
    },
  };

  const breadcrumbs = {
    "@type": "BreadcrumbList",
    "@id": `${siteConfig.url}/#breadcrumb`,
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: siteConfig.url,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Playground",
        item: `${siteConfig.url}/playground`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: "Benchmarks",
        item: `${siteConfig.url}/benchmarks`,
      },
    ],
  };

  const faqPage = {
    "@type": "FAQPage",
    "@id": `${siteConfig.url}/#faq`,
    mainEntity: [
      {
        "@type": "Question",
        name: "How does LLMSlim guarantee zero instruction loss in prompt compression?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "LLMSlim uses an explicit Priority Tier engine heuristic. Sentence boundaries containing imperative directives ('must', 'never', 'ensure', system prompt role markers, numbered lists, and code blocks) are tagged as Priority 4 Critical, guaranteeing 100.0% retention across all compression ratios.",
        },
      },
      {
        "@type": "Question",
        name: "Will compressing my RAG documents reduce LLM answer quality?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Empirical benchmarks demonstrate 95%+ entity retention and meaning preservation. By eliminating redundant boilerplate text and unfocused prose, models focus more directly on key facts, often improving task performance while cutting costs by 40-70%.",
        },
      },
      {
        "@type": "Question",
        name: "Does LLMSlim require heavy model downloads or internet access?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "No. Core LLMSlim works 100% offline out-of-the-box using lightweight TF-IDF centrality ranking with zero external model dependencies. For deep transformer semantic similarity, you can optionally install 'llmslim[semantic]'.",
        },
      },
      {
        "@type": "Question",
        name: "What processing latency overhead does LLMSlim add to API requests?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "The standard Python CPU execution latency is ~28ms for standard system prompts and <120ms for 5,000-token RAG contexts. Upcoming v0.3 releases introduce ONNX runtime acceleration and sub-5ms Rust C-extensions.",
        },
      },
      {
        "@type": "Question",
        name: "Is LLMSlim tied to any specific LLM provider?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "LLMSlim is completely model-agnostic. It compresses raw text before it ever leaves your server, making it 100% compatible with OpenAI GPT-5/GPT-4o, Anthropic Claude, Google Gemini, DeepSeek, Llama, and local vLLM instances.",
        },
      },
    ],
  };

  return {
    "@context": "https://schema.org",
    "@graph": [softwareApplication, organization, webSite, breadcrumbs, faqPage],
  };
}
