import React from "react";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { DocSidebar, type DocNavGroup } from "@/components/docs/DocSidebar";
import { DocsMobileBar } from "@/components/docs/DocsVersionSwitch";
import { DOC_CATEGORIES, docsInOrder, isNewIn } from "@/data/docs";
import { DOCS_VERSIONS, type DocsVersion } from "@/data/docs-versions";
import "./docs.css";

// Only titles and filter text reach the browser; the guides themselves stay on the server.
const NAV = Object.fromEntries(DOCS_VERSIONS.map(({ id }): [DocsVersion, DocNavGroup[]] => {
  const pages = docsInOrder(id);
  return [id, DOC_CATEGORIES.map((category) => ({
    category,
    items: pages.filter((doc) => doc.category === category).map((doc) => ({
      slug: doc.slug,
      title: doc.navTitle ?? doc.title,
      filter: `${doc.title} ${doc.description} ${doc.searchIntent}`.toLowerCase(),
      ...(doc.experimental ? { badge: "Experimental" as const } : isNewIn(id, doc.slug) ? { badge: "New" as const } : {}),
    })),
  })).filter((group) => group.items.length > 0)];
})) as Record<DocsVersion, DocNavGroup[]>;

const SLUGS = Object.fromEntries(Object.entries(NAV).map(([version, groups]) => [version, groups.flatMap((group) => group.items.map((item) => item.slug))])) as Record<DocsVersion, string[]>;

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="docs-shell flex min-h-screen flex-col">
      <SiteHeader />
      <div className="docs-frame">
        <DocSidebar className="docs-side" nav={NAV} />
        <main id="main-content" className="docs-main">
          <DocsMobileBar slugs={SLUGS} />
          {children}
        </main>
      </div>
      <SiteFooter />
    </div>
  );
}
