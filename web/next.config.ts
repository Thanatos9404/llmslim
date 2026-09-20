import type { NextConfig } from "next";
import bundleAnalyzer from "@next/bundle-analyzer";

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const localStudioApiOrigin = process.env.LLMSLIM_STUDIO_LOCAL_API_ORIGIN;
const localSarvamApiOrigin = process.env.LLMSLIM_STUDIO_LOCAL_SARVAM_API_ORIGIN ?? localStudioApiOrigin;
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
    optimizePackageImports: ["lucide-react", "framer-motion", "@radix-ui/react-dialog"],
  },
  async rewrites() {
    if (!localStudioApiOrigin) return [];
    return [
      { source: "/api/compress", destination: `${localStudioApiOrigin}/api/compress` },
      { source: "/api/plan", destination: `${localStudioApiOrigin}/api/plan` },
      { source: "/api/sarvam", destination: `${localSarvamApiOrigin}/api/sarvam` },
    ];
  },
};

export default withBundleAnalyzer(nextConfig);
