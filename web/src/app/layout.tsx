import type { Viewport } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import { constructMetadata, getStructuredDataGraph } from "@/lib/seo";

const themeController = `(() => {
  const key = "llmslim-theme";
  const syncButtons = () => {
    const theme = document.documentElement.dataset.theme || "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
      button.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
    });
  };
  const apply = (theme) => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.documentElement.classList.toggle("theme-light", theme === "light");
    syncButtons();
  };
  try { apply(localStorage.getItem(key) === "light" ? "light" : "dark"); } catch { apply("dark"); }
  new MutationObserver(syncButtons).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    try { localStorage.setItem(key, next); } catch {}
    apply(next);
  });
})();`;

export const viewport: Viewport = {
  themeColor: "#030508",
  colorScheme: "light dark",
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
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">
        {/* Schema.org Complete JSON-LD Graph for Google AI Overviews, Perplexity & Rich Snippets */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdGraph) }}
        />
        <script dangerouslySetInnerHTML={{ __html: themeController }} />

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
