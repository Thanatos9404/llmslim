"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Command, Menu, X } from "lucide-react";
import { AnimatedButton, CommandPalette } from "@/components/design-system";
import { GithubIcon } from "@/components/icons/GithubIcon";

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navLinks = [
    { name: "Home", href: "/" },
    { name: "Docs", href: "/docs" },
    { name: "Playground", href: "/playground" },
    { name: "Articles", href: "/articles" },
    { name: "Benchmarks", href: "/benchmarks" },
    { name: "Integrations", href: "/integrations" },
  ];

  return (
    <>
      {/* Raycast Command Palette Modal */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />

      <motion.header
        role="banner"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
          scrolled
            ? "bg-[#030508]/85 backdrop-blur-xl border-b border-white/10 py-3 shadow-[0_10px_30px_rgba(0,0,0,0.8)]"
            : "bg-transparent py-4 sm:py-5"
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-8 flex items-center justify-between">
          {/* Official LLMSlim Brand Logo */}
          <Link
            href="/"
            aria-label="LLMSlim Homepage"
            title="LLMSlim — Semantic Prompt & Context Compression Engine"
            className="flex items-center gap-3 group focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 rounded-xl"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-400 via-cyan-400 to-emerald-500 p-[1px] shadow-[0_0_15px_rgba(0,245,155,0.35)] group-hover:shadow-[0_0_25px_rgba(0,245,155,0.6)] transition-all overflow-hidden flex items-center justify-center bg-[#070A0F]">
              <Image
                src="/llmslim_logo.png"
                alt="LLMSlim Logomark"
                width={32}
                height={32}
                priority
                className="w-full h-full object-cover group-hover:scale-105 transition-transform"
              />
            </div>
            <span className="font-sans font-bold text-base sm:text-lg text-white tracking-tight flex items-center gap-1.5">
              LLMSlim
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono badge-scientific">
                v0.2.0
              </span>
            </span>
          </Link>

          {/* Center Desktop Navigation Pages */}
          <nav aria-label="Main Navigation" className="hidden lg:flex items-center gap-7 text-xs font-mono">
            {navLinks.map((link) => {
              const isActive = pathname === link.href || (link.href !== "/" && pathname?.startsWith(link.href));
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  prefetch={true}
                  title={`${link.name} Page`}
                  className={`transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 px-1 py-0.5 rounded ${
                    isActive
                      ? "text-emerald-400 font-bold"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {link.name}
                </Link>
              );
            })}
          </nav>

          {/* Right Action Controls */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setCommandPaletteOpen(true)}
              aria-label="Open Command Search Overlay"
              title="Open Command Palette (⌘K)"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-mono text-slate-300 transition-colors cursor-pointer min-h-[36px] focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              <Command className="w-3.5 h-3.5 text-emerald-400" />
              <span className="hidden sm:inline">⌘K</span>
            </button>

            <a
              href="https://github.com/Thanatos9404/llmslim"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub Repository for LLMSlim"
              title="View LLMSlim Source Code on GitHub"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-mono text-slate-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              <GithubIcon className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>

            <AnimatedButton
              variant="quantum"
              size="sm"
              aria-label="Install LLMSlim via PyPI"
              onClick={() => window.open("https://pypi.org/project/llmslim/", "_blank", "noopener,noreferrer")}
            >
              pip install
            </AnimatedButton>

            {/* Mobile Hamburger Toggle */}
            <button
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              aria-label={mobileMenuOpen ? "Close Navigation Menu" : "Open Navigation Menu"}
              title="Toggle Menu"
              className="lg:hidden p-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:text-white min-h-[36px] min-w-[36px] flex items-center justify-center cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
            >
              {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Drawer Navigation */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="lg:hidden bg-[#070A0F] border-b border-white/10 px-6 py-4 space-y-3 font-mono text-xs text-slate-300"
            >
              {navLinks.map((link) => {
                const isActive = pathname === link.href || (link.href !== "/" && pathname?.startsWith(link.href));
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`block py-2 border-b border-white/5 ${
                      isActive ? "text-emerald-400 font-bold" : "hover:text-emerald-400"
                    }`}
                  >
                    {link.name}
                  </Link>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.header>
    </>
  );
}
