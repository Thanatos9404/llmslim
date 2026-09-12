import React from "react";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { DocSidebar } from "@/components/docs/DocSidebar";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader />
      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-8 px-4 py-10 sm:px-6 lg:px-8">
          {/* Left Navigation Sidebar */}
          <div className="hidden lg:block">
            <DocSidebar className="sticky top-28" />
          </div>

          {/* Main Content Workspace */}
          <main id="main-content" className="page-shell min-w-0 max-w-4xl flex-1">
            {children}
          </main>
      </div>
      <SiteFooter />
    </div>
  );
}
