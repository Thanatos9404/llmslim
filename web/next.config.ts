import type { NextConfig } from "next";
import bundleAnalyzer from "@next/bundle-analyzer";
import { securityHeaders, TOKEN_PAGES, tokenPageHeaders } from "./security-headers";
import { DEFAULT_DOCS_VERSION } from "./src/data/docs-versions";

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const localStudioApiOrigin = process.env.LLMSLIM_STUDIO_LOCAL_API_ORIGIN;
const localStudioE2E = process.env.LLMSLIM_STUDIO_E2E === "1";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  ...(localStudioE2E ? { distDir: ".next-studio-e2e" } : {}),
  compress: true,
  images: {
    formats: ["image/avif", "image/webp"],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },
  experimental: {
    cpus: 2,
    optimizePackageImports: ["lucide-react", "framer-motion", "@radix-ui/react-dialog"],
  },
  async redirects() {
    // LLMSlim Platform was renamed LLMSlim Vault on 29 October 2026; old links (including /platform#beta) keep working.
    // The default docs version is served at /docs, so its own prefix points there. Not permanent: when the default
    // changes (src/data/docs-versions.ts), /docs/<old default>/... serves that version's pages again.
    const docsDefault = `/docs/${DEFAULT_DOCS_VERSION.replace(".", "\\.")}`;
    return [
      { source: "/platform", destination: "/vault", permanent: true },
      { source: docsDefault, destination: "/docs", permanent: false },
      { source: `${docsDefault}/:slug([a-z0-9-]+)`, destination: "/docs/:slug", permanent: false },
      { source: `${docsDefault}/:slug([a-z0-9-]+)\\.md`, destination: "/docs/:slug.md", permanent: false },
    ];
  },
  async rewrites() {
    // Markdown twins for agents: "/index.md", "/docs.md", "/docs/<slug>.md", "/compare/<slug>.md" and so on (src/app/md).
    // afterFiles rewrites run before dynamic routes, so "/docs/<slug>.md" never reaches docs/[...path].
    const markdown = [
      { source: "/:page(index|changelog|pricing|docs|articles|integrations|benchmarks)\\.md", destination: "/md/:page" },
      { source: "/:section(docs|articles|integrations|benchmarks|compare)/:slug([a-z0-9-]+)\\.md", destination: "/md/:section/:slug" },
      // Docs of a version other than the default: "/docs/1.0.md" and "/docs/1.0/<slug>.md".
      { source: "/docs/:version(\\d+\\.\\d+)\\.md", destination: "/md/docs/:version" },
      { source: "/docs/:version(\\d+\\.\\d+)/:slug([a-z0-9-]+)\\.md", destination: "/md/docs/:version/:slug" },
    ];
    // Local development only: forward the Studio's Python functions to a local server.
    const studio = localStudioApiOrigin ? ["studio", "compress", "plan", "context", "sarvam_answer"].map((name) => ({ source: `/api/${name}`, destination: `${localStudioApiOrigin}/api/${name}` })) : [];
    return { beforeFiles: [], afterFiles: [...markdown, ...studio], fallback: [] };
  },
  async headers() {
    // Later entries win for the same key, so the token pages' stricter Referrer-Policy comes last.
    return [
      { source: "/:path*", headers: securityHeaders(process.env) },
      ...TOKEN_PAGES.map((page) => ({ source: page, headers: tokenPageHeaders() })),
    ];
  },
};

export default withBundleAnalyzer(nextConfig);
