"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, HelpCircle } from "lucide-react";

export interface FaqItem {
  question: string;
  answer: string;
}

export function FaqSection() {
  const faqs: FaqItem[] = [
    {
      question: "How does LLMSlim guarantee zero instruction loss?",
      answer:
        "LLMSlim uses an explicit Priority Tier engine heuristic. Sentence boundaries containing imperative directives ('must', 'never', 'ensure', system prompt role markers, numbered lists, and code blocks) are tagged as Priority 4 Critical, guaranteeing 100.0% retention across all compression ratios.",
    },
    {
      question: "Will compressing my RAG documents reduce LLM answer quality?",
      answer:
        "Empirical benchmarks demonstrate 95%+ entity retention and meaning preservation. By eliminating redundant boilerplate text and unfocused prose, models focus more directly on key facts, often improving task performance while cutting costs by 40-70%.",
    },
    {
      question: "Does LLMSlim require heavy model downloads or internet access?",
      answer:
        "No. Core LLMSlim works 100% offline out-of-the-box using lightweight TF-IDF centrality ranking with zero external model dependencies. For deep transformer semantic similarity, you can optionally install 'llmslim[semantic]'.",
    },
    {
      question: "What processing latency overhead does LLMSlim add?",
      answer:
        "The standard Python CPU execution latency is ~28ms for standard system prompts and <120ms for 5,000-token RAG contexts. Upcoming v0.3 releases introduce ONNX runtime acceleration and sub-5ms Rust C-extensions.",
    },
    {
      question: "Is LLMSlim tied to any specific LLM provider?",
      answer:
        "LLMSlim is completely model-agnostic. It compresses raw text before it ever leaves your server, making it 100% compatible with OpenAI GPT-5/GPT-4o, Anthropic Claude, Google Gemini, DeepSeek, Llama, and local vLLM instances.",
    },
  ];

  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" aria-label="Frequently Asked Questions Section" className="py-20 px-4 sm:px-8 max-w-4xl mx-auto space-y-12">
      <div className="text-center space-y-4">
        <span className="badge-scientific text-cyan-400 text-xs">
          Frequently Answered Telemetry
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Everything You Need to Know
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          Clear answers regarding instruction fidelity, offline support, and latency.
        </p>
      </div>

      <div className="space-y-4">
        {faqs.map((faq, idx) => {
          const isOpen = openIndex === idx;
          return (
            <div
              key={idx}
              className="rounded-xl bg-[#0D121C] border border-white/10 overflow-hidden transition-all duration-300 hover:border-emerald-500/30"
            >
              <button
                id={`faq-button-${idx}`}
                aria-expanded={isOpen}
                aria-controls={`faq-answer-${idx}`}
                onClick={() => setOpenIndex(isOpen ? null : idx)}
                className="w-full px-6 py-4.5 flex items-center justify-between text-left cursor-pointer hover:bg-white/[0.03] transition-colors min-h-[52px] focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              >
                <span className="text-base font-bold text-white font-sans flex items-center gap-3">
                  <HelpCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                  {faq.question}
                </span>
                <ChevronDown
                  className={`w-4 h-4 text-slate-400 transition-transform duration-300 ${
                    isOpen ? "rotate-180 text-emerald-400" : ""
                  }`}
                />
              </button>

              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    id={`faq-answer-${idx}`}
                    role="region"
                    aria-labelledby={`faq-button-${idx}`}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ type: "spring", damping: 25, stiffness: 300 }}
                  >
                    <div className="px-6 pb-5 pt-1 text-sm text-slate-400 leading-relaxed border-t border-white/5 font-sans">
                      {faq.answer}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </section>
  );
}
