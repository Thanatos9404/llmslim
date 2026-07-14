"use client";

import React, { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Terminal, Zap, Shield, BookOpen, Calculator, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CommandItem {
  id: string;
  title: string;
  category: string;
  icon?: React.ReactNode;
  shortcut?: string;
  onSelect?: () => void;
}

export function CommandPalette({ isOpen: externalIsOpen, onClose }: { isOpen?: boolean; onClose?: () => void }) {
  const [internalOpen, setInternalOpen] = useState(false);
  const [query, setQuery] = useState("");

  const isOpen = externalIsOpen !== undefined ? externalIsOpen : internalOpen;

  const handleClose = () => {
    if (onClose) onClose();
    else setInternalOpen(false);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (externalIsOpen === undefined) setInternalOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [externalIsOpen]);

  const commandList: CommandItem[] = [
    {
      id: "quickstart",
      title: "pip install llmslim",
      category: "Quickstart",
      icon: <Terminal className="w-4 h-4 text-emerald-400" />,
      shortcut: "⌘C",
      onSelect: () => navigator.clipboard.writeText("pip install llmslim"),
    },
    {
      id: "pipeline",
      title: "View 6-Step Compression Engine Architecture",
      category: "Architecture",
      icon: <Zap className="w-4 h-4 text-cyan-400" />,
      shortcut: "⌘P",
    },
    {
      id: "calculator",
      title: "Calculate Enterprise Token Savings ROI",
      category: "Tools",
      icon: <Calculator className="w-4 h-4 text-violet-400" />,
      shortcut: "⌘S",
    },
    {
      id: "benchmarks",
      title: "Inspect Empirical Benchmark Data",
      category: "Metrics",
      icon: <Shield className="w-4 h-4 text-emerald-400" />,
      shortcut: "⌘B",
    },
    {
      id: "docs",
      title: "Read Python API Reference Documentation",
      category: "Resources",
      icon: <BookOpen className="w-4 h-4 text-pink-400" />,
      shortcut: "⌘D",
    },
  ];

  const filteredCommands = commandList.filter(
    (item) =>
      item.title.toLowerCase().includes(query.toLowerCase()) ||
      item.category.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <AnimatePresence>
        {isOpen && (
          <Dialog.Portal>
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-[#030508]/80 backdrop-blur-md"
              />
            </Dialog.Overlay>

            <Dialog.Content asChild>
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: -20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -20 }}
                transition={{ type: "spring", damping: 25, stiffness: 350 }}
                className="fixed top-[20%] left-1/2 -translate-x-1/2 z-50 w-[92vw] max-w-xl rounded-2xl bg-[#0D121C] border border-white/15 shadow-[0_25px_60px_rgba(0,0,0,0.9)] p-0 overflow-hidden font-sans"
              >
                {/* Search Bar Input */}
                <div className="flex items-center gap-3 px-4 py-3.5 border-b border-white/10 bg-[#070A0F]">
                  <Search className="w-5 h-5 text-slate-400 shrink-0" />
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search LLMSlim commands, benchmarks, docs... (Press Esc to close)"
                    className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-mono"
                    autoFocus
                  />
                  <button onClick={handleClose} className="p-1 rounded text-slate-400 hover:text-white cursor-pointer">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {/* Command Items List */}
                <div className="max-h-80 overflow-y-auto p-2 space-y-1">
                  {filteredCommands.length > 0 ? (
                    filteredCommands.map((cmd) => (
                      <button
                        key={cmd.id}
                        onClick={() => {
                          if (cmd.onSelect) cmd.onSelect();
                          handleClose();
                        }}
                        className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-left text-xs font-mono transition-all hover:bg-white/[0.08] hover:text-emerald-300 group cursor-pointer"
                      >
                        <div className="flex items-center gap-3">
                          <span className="p-1.5 rounded-lg bg-white/5 border border-white/10 group-hover:border-emerald-500/30">
                            {cmd.icon}
                          </span>
                          <div>
                            <div className="text-slate-200 group-hover:text-white font-medium">
                              {cmd.title}
                            </div>
                            <div className="text-[10px] text-slate-500">{cmd.category}</div>
                          </div>
                        </div>

                        {cmd.shortcut && (
                          <kbd className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[10px] text-slate-400">
                            {cmd.shortcut}
                          </kbd>
                        )}
                      </button>
                    ))
                  ) : (
                    <div className="p-8 text-center text-xs text-slate-500 font-mono">
                      No matching commands found.
                    </div>
                  )}
                </div>

                {/* Footer Bar */}
                <div className="px-4 py-2.5 bg-[#070A0F] border-t border-white/10 flex items-center justify-between text-[10px] font-mono text-slate-500">
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3 text-emerald-400" />
                    LLMSlim Command Palette v0.2.0
                  </span>
                  <span>Use ↑ ↓ to navigate • Esc to dismiss</span>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
