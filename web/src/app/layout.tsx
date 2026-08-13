import type { Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import { constructMetadata, getStructuredDataGraph } from "@/lib/seo";

export const viewport: Viewport = {
  themeColor: "#030508",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export const metadata = constructMetadata();

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLdGraph = getStructuredDataGraph();

  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      suppressHydrationWarning
      className="h-full antialiased dark"
    >
      <body className="min-h-full flex flex-col bg-[#030508] text-slate-100 font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
        {/* Schema.org Complete JSON-LD Graph for Google AI Overviews, Perplexity & Rich Snippets */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdGraph) }}
        />

        {/* Accessibility Skip Link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-emerald-400 focus:text-[#030508] focus:font-bold focus:rounded-xl focus:shadow-2xl"
        >
          Skip to main content
        </a>
        {children}

        {/* Vercel Web Analytics & Real User Speed Insights Tracking */}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
