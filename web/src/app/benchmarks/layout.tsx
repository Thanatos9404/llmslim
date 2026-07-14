import React from "react";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { NoiseOverlay, AuroraBackground } from "@/components/design-system";

export default function BenchmarksLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen bg-[#030508] text-slate-100 selection:bg-emerald-500/30 selection:text-emerald-200">
      <NoiseOverlay opacity={0.03} />
      <Navbar />

      <AuroraBackground showRadialGradient={false}>
        <div className="pt-28 sm:pt-36 pb-20 max-w-7xl mx-auto px-4 sm:px-8">
          {children}
        </div>
        <Footer />
      </AuroraBackground>
    </div>
  );
}
