import React from "react";
import {
  AuroraBackground,
  NoiseOverlay,
} from "@/components/design-system";

import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { MarqueeSection } from "@/components/landing/MarqueeSection";
import { CalculatorSection } from "@/components/landing/CalculatorSection";
import { FeatureGridSection } from "@/components/landing/FeatureGridSection";
import { PipelineSection } from "@/components/landing/PipelineSection";
import { CodeExamplesSection } from "@/components/landing/CodeExamplesSection";
import { ArchitectureSection } from "@/components/landing/ArchitectureSection";
import { BenchmarksSection } from "@/components/landing/BenchmarksSection";
import { IntegrationsSection } from "@/components/landing/IntegrationsSection";
import { RoadmapSection } from "@/components/landing/RoadmapSection";
import { TestimonialsSection } from "@/components/landing/TestimonialsSection";
import { FaqSection } from "@/components/landing/FaqSection";
import { CtaSection } from "@/components/landing/CtaSection";
import { Footer } from "@/components/landing/Footer";

export default function Home() {
  return (
    <div className="relative min-h-screen bg-[#030508] text-slate-100 selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* Global Background Systems */}
      <NoiseOverlay opacity={0.03} />

      {/* Sticky Header Nav */}
      <Navbar />

      {/* Main Flow Canvas */}
      <AuroraBackground showRadialGradient={true}>
        <main id="main-content" className="relative z-10 space-y-4">
          <HeroSection />
          <MarqueeSection />
          <CalculatorSection />
          <FeatureGridSection />
          <PipelineSection />
          <CodeExamplesSection />
          <ArchitectureSection />
          <BenchmarksSection />
          <IntegrationsSection />
          <RoadmapSection />
          <TestimonialsSection />
          <FaqSection />
          <CtaSection />
        </main>
        <Footer />
      </AuroraBackground>
    </div>
  );
}
