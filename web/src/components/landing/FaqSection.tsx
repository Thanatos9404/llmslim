"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, HelpCircle } from "lucide-react";
export interface FaqItem { question: string; answer: string; }
export function FaqSection() {
  const faqs: FaqItem[] = [
    { question: "Does LLMSlim prevent prompt injection?", answer: "No. v0.4.0 mitigates compression-induced instruction elevation by preventing untrusted RAG, tool, and assistant content from gaining protected priority through imperative or safety-critical wording. Applications still need defense in depth." },
    { question: "What does ContextRole do?", answer: "It carries caller-supplied provenance. System and developer are trusted; user is semi-trusted; assistant, tool, and RAG are untrusted and cannot become Tier 4 or must_keep through wording." },
    { question: "Does LLMSlim require internet access?", answer: "The default extractive strategy runs locally. Rewrite and hybrid strategies require a caller-supplied provider." },
    { question: "What performance should I expect?", answer: "Measure your workload. Compression ratio and latency depend on input, hardware, tokenizer availability, and strategy; v0.4.0 does not promise a universal latency target." },
    { question: "Are npm, Rust, or WASM runtimes available?", answer: "No. v0.4.0 is a Python release; those runtimes are not published product capabilities." },
  ];
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  return <section id="faq" aria-label="Frequently Asked Questions Section" className="py-20 px-4 sm:px-8 max-w-4xl mx-auto space-y-12"><div className="text-center space-y-4"><span className="badge-scientific text-cyan-400 text-xs">Frequently asked questions</span><h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">Product facts, plainly stated</h2></div><div className="space-y-4">{faqs.map((faq, idx) => { const open = openIndex === idx; return <div key={faq.question} className="rounded-xl bg-[#0D121C] border border-white/10 overflow-hidden"><button aria-expanded={open} onClick={() => setOpenIndex(open ? null : idx)} className="w-full px-6 py-4 flex items-center justify-between text-left"><span className="text-base font-bold text-white flex items-center gap-3"><HelpCircle className="w-4 h-4 text-emerald-400" />{faq.question}</span><ChevronDown className={"w-4 h-4 text-slate-400 " + (open ? "rotate-180" : "")} /></button><AnimatePresence initial={false}>{open && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}><div className="px-6 pb-5 pt-1 text-sm text-slate-400 leading-relaxed border-t border-white/5">{faq.answer}</div></motion.div>}</AnimatePresence></div>; })}</div></section>;
}
