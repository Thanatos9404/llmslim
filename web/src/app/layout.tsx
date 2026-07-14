import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const viewport: Viewport = {
  themeColor: "#030508",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL("https://llmslim.vercel.app"),
  title: {
    default: "LLMSlim — Semantic Prompt & Context Compression Engine for LLM Infrastructure",
    template: "%s | LLMSlim",
  },
  description:
    "Open-source Python package cutting LLM token costs by 40-70% in 1 line of code. Guaranteed 100% instruction fidelity, entity preservation, and sub-50ms offline execution.",
  keywords: [
    "LLM prompt compression",
    "Context compressor",
    "LLMSlim",
    "RAG context optimization",
    "Token reduction",
    "OpenAI prompt optimizer",
    "Claude context compression",
    "Python AI infrastructure",
  ],
  authors: [{ name: "Yashvardhan Thanvi", url: "https://github.com/Thanatos9404" }],
  creator: "Yashvardhan Thanvi",
  verification: {
    google: "google372537cef67c55b3",
  },
  icons: {
    icon: [
      { url: "/llmslim_logo.png", type: "image/png" },
      { url: "/favicon.png", type: "image/png" },
    ],
    shortcut: "/llmslim_logo.png",
    apple: "/llmslim_logo.png",
  },
  openGraph: {
    title: "LLMSlim — Cut LLM Token Costs by 50% in 1 Line of Code",
    description:
      "Surgically compresses LLM prompts, RAG document contexts, and multi-turn chat histories while preserving guaranteed 100% instruction fidelity.",
    url: "https://llmslim.vercel.app",
    siteName: "LLMSlim",
    images: [
      {
        url: "/llmslim_brand_id.png",
        width: 1200,
        height: 630,
        alt: "LLMSlim Brand Identity",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "LLMSlim — Cut LLM Token Costs by 50% in 1 Line of Code",
    description:
      "Semantic prompt compression built for enterprise LLM pipelines. Works offline out-of-the-box.",
    images: ["/llmslim_brand_id.png"],
    creator: "@Thanatos9404",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "LLMSlim",
  operatingSystem: "Platform Independent",
  applicationCategory: "DeveloperApplication",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
  },
  description:
    "Open-source Python package for semantic prompt compression, context optimization, and token reduction in LLM pipelines.",
  url: "https://github.com/Thanatos9404/llmslim",
  logo: "https://llmslim.vercel.app/llmslim_logo.png",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col bg-[#030508] text-slate-100 font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
        {/* JSON-LD Structured Data Schema */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />

        {/* Accessibility Skip Link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-emerald-400 focus:text-[#030508] focus:font-bold focus:rounded-xl focus:shadow-2xl"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
