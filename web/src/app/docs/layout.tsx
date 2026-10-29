import React from "react";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { DocSidebar, type DocNavGroup } from "@/components/docs/DocSidebar";
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs";
import "./docs.css";

// Only titles and filter text reach the browser; the guides themselves stay on the server.
const NAV: DocNavGroup[] = DOC_CATEGORIES.map((category) => ({
  category,
  items: Object.values(DOCS_REGISTRY)
    .filter((doc) => doc.category === category)
    .map((doc) => ({ slug: doc.slug, title: doc.title, filter: `${doc.title} ${doc.description} ${doc.searchIntent}`.toLowerCase() })),
}));

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="docs-shell flex min-h-screen flex-col">
      <SiteHeader />
      <div className="docs-frame">
        <DocSidebar className="docs-side" groups={NAV} />
        <main id="main-content" className="docs-main">{children}</main>
      </div>
      <SiteFooter />
    </div>
  );
}
