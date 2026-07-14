"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Command, Terminal, Menu, X } from "lucide-react";
import { AnimatedButton } from "@/components/design-system";
import { GithubIcon } from "@/components/icons/GithubIcon";

export function Navbar({ onOpenCommandPalette }: { onOpenCommandPalette: () => void }) {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <motion.header
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
        {/* Brand Logomark */}
        <a href="#" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-400 via-cyan-400 to-violet-500 p-[1px] shadow-[0_0_15px_rgba(0,245,155,0.3)] group-hover:shadow-[0_0_25px_rgba(0,245,155,0.5)] transition-all">
            <div className="w-full h-full bg-[#070A0F] rounded-[11px] flex items-center justify-center font-mono font-bold text-xs text-white">
              S
            </div>
          </div>
          <span className="font-sans font-bold text-base sm:text-lg text-white tracking-tight flex items-center gap-1.5">
            LLMSlim
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono">
              v0.2.0
            </span>
          </span>
        </a>

        {/* Center Desktop Navigation */}
        <nav className="hidden lg:flex items-center gap-7 text-xs font-mono text-slate-400">
          <a href="#features" className="hover:text-white transition-colors">
            Features
          </a>
          <a href="#pipeline" className="hover:text-white transition-colors">
            Pipeline
          </a>
          <a href="#benchmarks" className="hover:text-white transition-colors">
            Benchmarks
          </a>
          <a href="#calculator" className="hover:text-white transition-colors">
            Savings ROI
          </a>
          <a href="#code" className="hover:text-white transition-colors">
            API Docs
          </a>
          <a href="#faq" className="hover:text-white transition-colors">
            FAQ
          </a>
        </nav>

        {/* Right Action Controls */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={onOpenCommandPalette}
            aria-label="Open Command Palette"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-mono text-slate-300 transition-colors cursor-pointer min-h-[36px]"
          >
            <Command className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden sm:inline">⌘K</span>
          </button>

          <a
            href="https://github.com/Thanatos9404/llmslim"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub Repository"
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-mono text-slate-300 transition-colors"
          >
            <GithubIcon className="w-3.5 h-3.5" />
            <span>GitHub</span>
          </a>

          <AnimatedButton
            variant="quantum"
            size="sm"
            onClick={() => window.open("https://pypi.org/project/llmslim/", "_blank")}
          >
            pip install
          </AnimatedButton>

          {/* Mobile Hamburger Toggle */}
          <button
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label="Toggle Navigation Menu"
            className="lg:hidden p-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:text-white min-h-[36px] min-w-[36px] flex items-center justify-center cursor-pointer"
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
            <a
              href="#features"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 border-b border-white/5 hover:text-emerald-400"
            >
              Features
            </a>
            <a
              href="#pipeline"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 border-b border-white/5 hover:text-emerald-400"
            >
              Pipeline Architecture
            </a>
            <a
              href="#benchmarks"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 border-b border-white/5 hover:text-emerald-400"
            >
              Empirical Benchmarks
            </a>
            <a
              href="#calculator"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 border-b border-white/5 hover:text-emerald-400"
            >
              Enterprise ROI Calculator
            </a>
            <a
              href="#code"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 border-b border-white/5 hover:text-emerald-400"
            >
              Python API References
            </a>
            <a
              href="#faq"
              onClick={() => setMobileMenuOpen(false)}
              className="block py-2 hover:text-emerald-400"
            >
              FAQ
            </a>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
