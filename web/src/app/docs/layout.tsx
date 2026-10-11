import React from "react";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { DocSidebar } from "@/components/docs/DocSidebar";
import "./docs.css";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="docs-shell flex min-h-screen flex-col">
      <SiteHeader />
      <div className="docs-frame">
        <DocSidebar className="docs-side" />
        <main id="main-content" className="docs-main">{children}</main>
      </div>
      <SiteFooter />
    </div>
  );
}
