"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DOCS_REGISTRY, DOC_CATEGORIES } from "@/data/docs";
import { cn } from "@/lib/utils";
import { BookOpen, Sparkles } from "lucide-react";

export function DocSidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const currentSlug = pathname?.split("/").pop() || "getting-started";

  const docList = Object.values(DOCS_REGISTRY);

  return (
    <aside aria-label="Documentation Navigation" className={cn("w-64 shrink-0 font-sans text-xs space-y-7 pr-4 select-none", className)}>
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono font-bold">
        <Sparkles className="w-3.5 h-3.5" />
        <span>LLMSlim Documentation Hub</span>
      </div>

      {DOC_CATEGORIES.map((category) => {
        const items = docList.filter((doc) => doc.category === category);
        if (items.length === 0) return null;

        return (
          <div key={category} className="space-y-2">
            <h3 className="px-2 font-mono text-[11px] font-bold uppercase tracking-wider text-slate-400">
              {category}
            </h3>
            <ul className="space-y-0.5 border-l border-white/10 pl-2 ml-2">
              {items.map((item) => {
                const isActive = currentSlug === item.slug;

                return (
                  <li key={item.slug}>
                    <Link
                      href={`/docs/${item.slug}`}
                      className={cn(
                        "block px-3 py-1.5 rounded-lg transition-all font-medium text-xs border border-transparent",
                        isActive
                          ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 font-bold shadow-[0_0_15px_rgba(0,245,155,0.15)]"
                          : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                      )}
                    >
                      {item.title}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </aside>
  );
}
