export interface IntegrationFaq { question: string; answer: string; }
export interface IntegrationTroubleshooting { issue: string; solution: string; }
export interface IntegrationBenchmark { metric: string; uncompressed: string; compressed: string; impact: string; }
export interface IntegrationData {
  slug: string; name: string; category: "LLM Provider" | "Framework" | "Local & Edge" | "Backend Services"; badgeText: string; tagline: string; description: string;
  installation: { packageManager: string; command: string }; architectureFlow: string[];
  codeExample: { language: string; filename: string; code: string }; deploymentGuide: string; optimizationTips: string[]; benchmarks: IntegrationBenchmark[]; faqs: IntegrationFaq[]; troubleshooting: IntegrationTroubleshooting[]; iconKey: string;
}
export const INTEGRATION_CATEGORIES = ["LLM Provider", "Framework", "Local & Edge", "Backend Services"] as const;
const common = {
  category: "LLM Provider" as const, badgeText: "Python integration", installation: { packageManager: "pip", command: "pip install llmslim" },
  architectureFlow: ["1. Retrieve or construct application context.", "2. Label provenance accurately and compress with LLMSlim.", "3. Send the resulting text to the provider SDK.", "4. Apply application-level policy and output validation."],
  deploymentGuide: "Use LLMSlim in your Python application before constructing the provider request. Measure target workloads before choosing a compression ratio.",
  optimizationTips: ["Use compress_documents() for retrieved documents; it defaults to RAG provenance.", "Leave system messages unchanged by default in compress_chat_messages().", "Do not treat compression as a complete prompt-injection defense."],
  benchmarks: [{ metric: "v0.3.1 release gate", uncompressed: "N/A", compressed: "432 tests passed", impact: "92.57% branch coverage; benchmark reliability 100/100" }],
  troubleshooting: [{ issue: "Unexpected compression result", solution: "Check target_ratio, role labels, and whether the input is long enough to benefit from compression." }],
};
export const INTEGRATIONS_REGISTRY: Record<string, IntegrationData> = {
  openai: {
    ...common, slug: "openai", name: "OpenAI", iconKey: "openai", tagline: "Compress Python application context before an OpenAI SDK request.", description: "LLMSlim is provider-agnostic Python preprocessing. Use RAG provenance for retrieved content.", codeExample: { language: "python", filename: "openai_app.py", code: "from llmslim import compress_documents\n\nresults = compress_documents(retrieved_docs, query=user_question, target_ratio=0.4)\ncontext = '\\n\\n'.join(item.compressed_text for item in results)\n# Pass context to your OpenAI SDK request." },
    faqs: [{ question: "Does LLMSlim guarantee provider output correctness?", answer: "No. It reduces context according to its scoring and provenance rules; validate outputs in your application." }],
  },
  anthropic: {
    ...common, slug: "anthropic", name: "Anthropic", iconKey: "anthropic", tagline: "Prepare long Python-managed context before an Anthropic SDK request.", description: "Use the same Python LLMSlim API with your Anthropic client.", codeExample: { language: "python", filename: "anthropic_app.py", code: "from llmslim import compress\n\nresult = compress(long_context, target_ratio=0.5)\n# Pass result.compressed_text to your Anthropic SDK request." },
    faqs: [{ question: "Is an Anthropic-specific LLMSlim package required?", answer: "No. LLMSlim is provider-agnostic and does not bundle provider SDKs." }],
  },
  gemini: {
    ...common, slug: "gemini", name: "Google Gemini", iconKey: "gemini", tagline: "Compress retrieved Python context before a Gemini SDK request.", description: "Use compress_documents() for retrieved text and preserve accurate provenance.", codeExample: { language: "python", filename: "gemini_app.py", code: "from llmslim import compress_documents\n\ncompressed = compress_documents(documents, query=query, target_ratio=0.4)" },
    faqs: [{ question: "Does LLMSlim process multimodal inputs?", answer: "No. The released engine processes text." }],
  },
};
