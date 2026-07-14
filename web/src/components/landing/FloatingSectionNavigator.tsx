"use client";

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";

interface SectionItem {
  id: string;
  label: string;
}

const SECTIONS: SectionItem[] = [
  { id: "hero", label: "Overview" },
  { id: "calculator", label: "Calculator" },
  { id: "features", label: "Features" },
  { id: "pipeline", label: "Pipeline" },
  { id: "architecture", label: "Architecture" },
  { id: "benchmarks", label: "Benchmarks" },
  { id: "integrations", label: "Integrations" },
  { id: "roadmap", label: "Roadmap" },
  { id: "faq", label: "FAQ" },
];

export function FloatingSectionNavigator() {
  const [activeSection, setActiveSection] = useState<string>("hero");
  const [visible, setVisible] = useState<boolean>(false);

  useEffect(() => {
    // Show navigator only after scrolling past top 150px
    const handleScroll = () => {
      setVisible(window.scrollY > 150);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const observerCallback: IntersectionObserverCallback = (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActiveSection(entry.target.id);
        }
      });
    };

    const observerOptions: IntersectionObserverInit = {
      root: null,
      rootMargin: "-20% 0px -60% 0px",
      threshold: 0,
    };

    const observer = new IntersectionObserver(observerCallback, observerOptions);

    SECTIONS.forEach((section) => {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  if (!visible) return null;

  return (
    <nav
      aria-label="Floating Page Section Outline"
      className="fixed right-5 top-1/2 -translate-y-1/2 z-40 hidden xl:flex flex-col items-end gap-1.5 pointer-events-auto select-none"
    >
      <div className="p-2 rounded-2xl bg-[#030508]/85 backdrop-blur-xl border border-white/10 shadow-[0_10px_35px_rgba(0,0,0,0.8)] flex flex-col gap-1">
        {SECTIONS.map((sec) => {
          const isActive = activeSection === sec.id;
          return (
            <button
              key={sec.id}
              onClick={() => scrollToSection(sec.id)}
              aria-label={`Jump to ${sec.label} section`}
              title={sec.label}
              className="group relative flex items-center justify-end p-1.5 rounded-lg transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 cursor-pointer"
            >
              {/* Floating Tooltip Label on Hover */}
              <span className="absolute right-9 px-2 py-0.5 rounded bg-[#070A0F] border border-white/10 text-[11px] font-mono text-slate-200 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none shadow-lg">
                {sec.label}
              </span>

              {/* Active Indicator Bar / Dot */}
              <div className="relative w-4 h-4 flex items-center justify-center">
                {isActive && (
                  <motion.div
                    layoutId="activeFloatingDot"
                    className="absolute inset-0 rounded-full bg-emerald-500/20 border border-emerald-400"
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
                <div
                  className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                    isActive
                      ? "bg-emerald-400 scale-125 shadow-[0_0_8px_rgba(0,245,155,0.8)]"
                      : "bg-slate-600 group-hover:bg-slate-300"
                  }`}
                />
              </div>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
