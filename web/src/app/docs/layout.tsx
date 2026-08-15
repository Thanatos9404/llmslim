import React from "react";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { DocSidebar } from "@/components/docs/DocSidebar";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="site-shell">
      <Navbar />
      <div className="pt-16 sm:pt-20 pb-20 max-w-7xl mx-auto px-4 sm:px-8 flex gap-8">
          {/* Left Navigation Sidebar */}
          <div className="hidden lg:block">
            <DocSidebar className="sticky top-28" />
          </div>

          {/* Main Content Workspace */}
          <main id="main-content" className="flex-1 min-w-0 max-w-4xl">
            {children}
          </main>
      </div>
      <Footer />
    </div>
  );
}
