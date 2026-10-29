import type { NextConfig } from "next";
import bundleAnalyzer from "@next/bundle-analyzer";
import { securityHeaders, TOKEN_PAGES, tokenPageHeaders } from "./security-headers";

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
  async rewrites() {
    // Markdown twins for agents: "/index.md", "/docs.md", "/docs/<slug>.md", "/compare/<slug>.md" and so on (src/app/md).
    // afterFiles rewrites run before dynamic routes, so "/docs/<slug>.md" never reaches docs/[slug].
    const markdown = [
      { source: "/:page(index|changelog|docs|articles|integrations|benchmarks)\\.md", destination: "/md/:page" },
      { source: "/:section(docs|articles|integrations|benchmarks|compare)/:slug([a-z0-9-]+)\\.md", destination: "/md/:section/:slug" },
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
