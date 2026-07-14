"use client";

import React from "react";
import { CodeWindow } from "@/components/design-system";

export function CodeExamplesSection() {
  const tabs = [
    {
      id: "drop-in",
      title: "openai_integration.py",
      code: `from llmslim import compress
from openai import OpenAI

client = OpenAI()

# Compress massive system prompt in 1 line — drop-in, zero friction
prompt = compress(massive_system_prompt, target_ratio=0.5)

response = client.chat.completions.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": str(prompt)},  # ← compressed!
        {"role": "user", "content": user_question},
    ],
)
# Same response accuracy. 50% lower API invoice cost.`,
    },
    {
      id: "chat-messages",
      title: "compress_chat.py",
      code: `from llmslim import compress_chat_messages

conversation = [
    {"role": "system", "content": "You are a helpful coding assistant..."},
    {"role": "user", "content": very_long_user_message},
    {"role": "assistant", "content": very_long_assistant_response},
    {"role": "user", "content": follow_up_question},
]

# Compress user & assistant conversation turns while preserving system prompt
compressed_messages = compress_chat_messages(conversation, target_ratio=0.5)

response = client.chat.completions.create(model="gpt-5", messages=compressed_messages)`,
    },
    {
      id: "rag-documents",
      title: "compress_rag.py",
      code: `from llmslim import compress_documents

# Chunks retrieved from vector DB
retrieved_chunks = [chunk1, chunk2, chunk3, chunk4]
user_query = "How do I handle authentication in FastAPI?"

# Query-aware relevance compression: retains sentences matching user question
results = compress_documents(
    retrieved_chunks,
    query=user_query,
    target_ratio=0.4,  # aggressive 60% token reduction
)

context = "\\n\\n".join(r.compressed_text for r in results)`,
    },
    {
      id: "advanced-config",
      title: "advanced_compressor.py",
      code: `from llmslim import ContextCompressor

compressor = ContextCompressor(
    max_chunk_tokens=300,          # token cap per topic chunk
    similarity_threshold=0.10,     # TF-IDF topic drift boundary
    
    weights={
        "centrality": 0.20,        # LexRank degree centrality
        "entity": 0.40,            # named entities, acronyms, URLs
        "instruction": 0.40,       # imperative directives & role markers
    },

    preserve_patterns=[
        r"API_KEY",                # custom regex pattern protection
        r"^(?:WARNING|CAUTION):",  # retain security warnings
    ],
)

result = compressor.compress(text, target_ratio=0.5)`,
    },
  ];

  return (
    <section id="code" className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-cyan-400">
          Developer Experience
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Drop-in Integration in <span className="text-gradient-cyan">1 Line of Python</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          Zero friction API surface designed to wrap any existing OpenAI, Anthropic, LangChain, or custom LLM client call.
        </p>
      </div>

      <CodeWindow tabs={tabs} className="max-w-4xl mx-auto" />
    </section>
  );
}
