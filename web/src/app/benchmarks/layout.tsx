import React from "react";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export default function BenchmarksLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="site-shell">
      <Navbar />
      <main id="main-content" className="pt-16 sm:pt-20 pb-20 max-w-7xl mx-auto px-4 sm:px-8">
          {children}
      </main>
      <Footer />
    </div>
  );
}
