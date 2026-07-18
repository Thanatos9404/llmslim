"use client";

import React from "react";
import { CodeWindow } from "@/components/design-system";

export function CodeExamplesSection() {
  const tabs = [
    {
      id: "hybrid-strategy",
      title: "hybrid_compression.py",
      code: `from llmslim import compress, CallableProvider

# 1. Extractive Compression (Default: 100% Offline, Sub-5ms)
slim_ext = compress(raw_prompt, target_ratio=0.5, strategy="extractive")

# 2. Hybrid Strategy (v0.3.0: Extractive -> LLM Rewrite -> Validation)
def my_llm_rewrite(request):
    return client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "user", "content": request.user_prompt}]
    ).choices[0].message.content

provider = CallableProvider(my_llm_rewrite, name="openai_gpt5")

slim_hyb = compress(
    raw_prompt,
    target_ratio=0.5,
    strategy="hybrid",
    provider=provider,
)

print(slim_hyb.compressed_text)
print(slim_hyb.detailed_summary())`,
    },
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
  ];

  return (
    <section id="studio-playground" className="py-20 px-4 sm:px-8 max-w-7xl mx-auto space-y-12">
      <div className="text-center space-y-4 max-w-3xl mx-auto">
        <span className="text-xs font-mono uppercase tracking-widest text-cyan-400">
          Developer Experience
        </span>
        <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
          Drop-in Integration in <span className="text-gradient-cyan">1 Line of Code</span>
        </h2>
        <p className="text-slate-400 text-base leading-relaxed">
          Zero friction API surface supporting Extractive, Generative Rewrite, and Hybrid strategies across Python and TypeScript.
        </p>
      </div>

      <CodeWindow tabs={tabs} className="max-w-4xl mx-auto" />
    </section>
  );
}
