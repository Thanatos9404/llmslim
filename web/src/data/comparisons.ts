/**
 * Comparison pages (/compare/<slug>). The page and its Markdown twin (/compare/<slug>.md, llms-full.txt) both
 * render from this data.
 *
 * Every benchmark number comes from benchmarks/live in the public repository (README, results/*.jsonl.gz) and
 * matches /benchmarks and the methodology article. Wording follows the launch fact sheet: "level with
 * LongLLMLingua", never "beats"; "faster per question", never "less compute"; "cases", never "questions" for
 * the 300. Competitor APIs in the migration snippets were checked against their source on GitHub.
 */
import { siteConfig } from "@/config/site"

export type GlanceRow = {
  aspect: string
  llmslim: string
  /** LLMLingua-2. When `longLingua` is absent, this cell spans both LLMLingua columns. */
  lingua2: string
  longLingua?: string
}

export type PairedDiff = { comparison: string; original: string; fresh: string; byCase: string; byQuestion: string }

export type Snippet = { filename: string; install: string; code: string }

export type Migration = {
  framework: string
  /** The LLMLingua class this replaces, or undefined when there is no LLMLingua counterpart. */
  before?: Snippet & { label: string }
  after: Snippet & { label: string }
  notes: string[]
  /** Site path of the integration page. */
  guide: string
}

export type Comparison = {
  slug: string
  /** Search title; it names the brand, so no suffix is added. */
  title: string
  description: string
  kicker: string
  heading: [string, string]
  lede: string
  lastUpdated: string
  disclosure: string
  shortAnswer: string[]
  glance: GlanceRow[]
  baselines: { name: string; citation: string; url: string; body: string }[]
  baselinesNote: string
  differences: { title: string; body: string }[]
  pairedDiffs: PairedDiff[]
  pairedNote: string
  caveats: { title: string; body: string }[]
  chooseThem: { title: string; body: string }[]
  chooseUs: string[]
  migrations: Migration[]
  migrationNotes: string[]
  faqs: ReadonlyArray<readonly [question: string, answer: string]>
  sources: { label: string; url: string }[]
}

const LANGCHAIN_SOURCE = "https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/document_compressors/llmlingua_filter.py"
const LLAMAINDEX_SOURCE = "https://github.com/run-llama/llama_index/blob/main/llama-index-integrations/postprocessor/llama-index-postprocessor-longllmlingua/llama_index/postprocessor/longllmlingua/base.py"

export const LLMLINGUA_COMPARISON: Comparison = {
  slug: "llmlingua",
  title: "LLMLingua Alternative: LLMSlim vs LLMLingua-2 and LongLLMLingua",
  description: "LLMSlim vs LLMLingua-2 and LongLLMLingua: sentence selection vs token pruning, a same-budget NaturalQuestions test with confidence intervals, when to pick LLMLingua, and migration code.",
  kicker: "Comparison · LLMLingua alternative",
  heading: ["LLMSlim vs LLMLingua.", "An honest comparison."],
  lede: "LLMLingua-2 and LongLLMLingua are prompt compressors from Microsoft Research that prune tokens with a language model. LLMSlim is an MIT-licensed Python library that selects whole passages and sentences around the question, with no model by default. Here is how they differ, what one public benchmark shows, and when LLMLingua is the better choice.",
  lastUpdated: "October 13, 2026",
  disclosure: "We build LLMSlim. We are not affiliated with Microsoft or the LLMLingua authors, and we ran both LLMLingua methods ourselves from their public code.",
  shortAnswer: [
    "On NaturalQuestions with 20 retrieved passages and a 25% token budget, read by Claude Haiku 5.5, LLMSlim Core 0.8 with its optional 22M-parameter reranker scored 78.7%. LongLLMLingua scored 78.0% and LLMLingua-2 69.0%. That is over 300 cases: 100 questions, each with the answer passage placed 1st, 10th and 20th.",
    "Level with LongLLMLingua: +0.7 points (95% CI −4.7 to +6.0). LongLLMLingua won the original sample by 6.0 and LLMSlim won the fresh sample by 7.3.",
    "9.7 points ahead of LLMLingua-2 at the same token budget (paired bootstrap 95% CI +3.7 to +15.7). The interval resamples the 300 cases; resampling by question widens it to about 0 to +19.",
    "Without the reranker, LLMSlim runs no model and is level with LLMLingua-2: 68.7% against 69.0%.",
    "About 100× faster than LongLLMLingua per question on the same 6 GB laptop GPU: a median of 0.09 s against 9.3 s. LongLLMLingua ran LLaMA-2-7B-chat in 4-bit to fit that GPU.",
    "Full context still scores higher: 89.0% on the same cases. The two LLMLingua methods were measured on this one dataset, with one reader.",
  ],
  glance: [
    { aspect: "How it compresses", llmslim: "Ranks documents, paragraphs and sentences against the query; keeps the best whole and in their original order", lingua2: "Classifies every token as keep or drop", longLingua: "Scores each document by the question's perplexity given it with a small language model, reorders them, then drops tokens with a ratio per document" },
    { aspect: "Model it runs", llmslim: "None by default (BM25). Optional 22.7M-parameter cross-encoder", lingua2: "XLM-RoBERTa-large, about 560M parameters", longLingua: "A causal language model: LLaMA-2-7B in its paper's NaturalQuestions setup and by default in the LangChain and LlamaIndex classes" },
    { aspect: "Reads the question", llmslim: "Yes, when you pass one. Without one, each text is compressed on its own", lingua2: "No: task-agnostic", longLingua: "Yes: question-aware" },
    { aspect: "What the reader gets", llmslim: "Whole sentences copied from the input, in their original order", lingua2: "The input with tokens removed inside sentences", longLingua: "Documents reordered by relevance, with tokens removed" },
    { aspect: "Budget", llmslim: "target_ratio, a fraction of tokens (cl100k_base)", lingua2: "rate, or target_token in tokens" },
    { aspect: "Install", llmslim: "pip install llmslim: numpy, scikit-learn and jsonschema; no PyTorch", lingua2: "pip install llmlingua: PyTorch, transformers, accelerate, nltk, tiktoken" },
    { aspect: "Framework classes", llmslim: "LangChain, LlamaIndex and Haystack adapters in the llmslim package", lingua2: "LangChain LLMLinguaCompressor (langchain-community); LlamaIndex LongLLMLinguaPostprocessor" },
    { aspect: "Median time per question in our run", llmslim: "25 ms on CPU without a model; 0.09 s on GPU with the reranker", lingua2: "2.3 s on GPU", longLingua: "9.3 s on GPU (4-bit)" },
    { aspect: "Peer-reviewed paper", llmslim: "None. Evidence is a public harness with per-case results", lingua2: "Pan et al., Findings of ACL 2024", longLingua: "Jiang et al., ACL 2024" },
    { aspect: "License", llmslim: "MIT", lingua2: "MIT (microsoft/LLMLingua)" },
  ],
  baselines: [
    {
      name: "LLMLingua-2",
      citation: "Pan et al., Findings of ACL 2024 (arXiv:2403.12968)",
      url: "https://arxiv.org/abs/2403.12968",
      body: "Treats compression as token classification. An encoder, XLM-RoBERTa-large fine-tuned on MeetingBank transcripts with keep-or-drop labels distilled from GPT-4, decides for each token whether to keep it. It is task-agnostic: it does not read the question. The public checkpoint has about 560M parameters according to its Hugging Face metadata.",
    },
    {
      name: "LongLLMLingua",
      citation: "Jiang et al., ACL 2024 (arXiv:2310.06839)",
      url: "https://arxiv.org/abs/2310.06839",
      body: "Targets long, question-specific contexts. A small causal language model scores how much each document and token matters given the question. Compression runs coarse to fine, documents are reordered by relevance, and each document gets its own compression ratio. Its NaturalQuestions experiments use LLaMA-2-7B-chat as that model.",
    },
  ],
  baselinesNote: "Both are open source in microsoft/LLMLingua under the MIT license. We ran their public code ourselves; Microsoft and the papers' authors did not run, review or endorse this comparison.",
  differences: [
    { title: "Selection, not token pruning", body: "LLMSlim ranks the context's units (documents, chat rounds, paragraphs) against the query, keeps the best ones whole and in their original order, and fills the rest of the budget sentence by sentence. It never deletes words inside a sentence, so the model reads text from your documents, unchanged." },
    { title: "No 7B model", body: "Relevance is lexical by default: BM25 with light stemming and one round of pseudo-relevance feedback. No model, no download and deterministic output, at a median of 25 ms per question on CPU in our NaturalQuestions run." },
    { title: "An optional 22M reranker", body: "pip install \"llmslim[semantic]\" and relevance=\"semantic\" add cross-encoder/ms-marco-MiniLM-L-6-v2 (22.7M parameters, trained on MS MARCO web search). It rescores the 80 strongest lexical candidates, so it works on top of BM25. Any callable scorer(query, texts) works too." },
    { title: "One budget across documents", body: "With a query, retrieved documents share one budget: the relevant ones stay whole and the rest are dropped, instead of every document losing the same share. Retrieved text keeps untrusted RAG provenance, so imperative wording inside it is never force-kept." },
  ],
  pairedDiffs: [
    { comparison: "LLMSlim + reranker vs LongLLMLingua", original: "−6.0 (−14.7, +2.0)", fresh: "+7.3 (+0.7, +14.7)", byCase: "+0.7 (−4.7, +6.0)", byQuestion: "+0.7 (−8.0, +9.3)" },
    { comparison: "LLMSlim + reranker vs LLMLingua-2", original: "+9.3 (+0.7, +18.0)", fresh: "+10.0 (+1.3, +19.3)", byCase: "+9.7 (+3.7, +15.7)", byQuestion: "+9.7 (+0.0, +19.3)" },
    { comparison: "LLMSlim, no model, vs LLMLingua-2", original: "−1.3 (−8.7, +6.0)", fresh: "+0.7 (−9.3, +10.7)", byCase: "−0.3 (−6.7, +6.0)", byQuestion: "−0.3 (−9.7, +9.3)" },
  ],
  pairedNote: "Paired differences in accuracy points, first system minus second, with the bootstrap 95% interval in brackets (4,000 resamples). Each question appears at three answer positions, so the three cases are correlated: resampling whole questions is the more conservative interval. Bounds move by a few tenths of a point with the random draws.",
  caveats: [
    { title: "One reader", body: "Every number uses Claude Haiku 5.5 at effort low. Another reader may rank these systems differently. The papers' own NaturalQuestions numbers use GPT-3.5-Turbo, so raw scores are not comparable across the two." },
    { title: "One dataset for the competitors", body: "LLMLingua-2 and LongLLMLingua were run on 20-document NaturalQuestions only: short factual answers, one gold passage. That says little about summarisation, multi-hop reasoning, code or chat memory, where they were not measured." },
    { title: "Baselines we ran ourselves", body: "We used published settings (LongLLMLingua's NaturalQuestions settings from its paper, LLMLingua-2's MeetingBank checkpoint), and we build one of the systems compared. Other settings may score differently. The configuration and scripts are public." },
    { title: "LongLLMLingua in 4-bit", body: "LLaMA-2-7B-chat ran in 4-bit NF4 to fit a 6 GB laptop GPU. The paper does not report quantization, and 4-bit can change the perplexity scores LongLLMLingua ranks with. We did not measure the effect, in either direction." },
    { title: "Small samples", body: "100 questions (50 per split), each at three answer positions. A 6 to 7 point swing between splits is within sampling noise, which is why both splits are reported and pooled." },
    { title: "Same budget, slightly different use", body: "Every arm had the same nominal budget, 25% of the context's cl100k tokens (about 722), and all came in under it: a mean of 668 tokens for LLMSlim with the reranker, 630 for LongLLMLingua and 680 for LLMLingua-2." },
    { title: "Cut-off responses", body: "14 LLMLingua-2 responses hit the 1,024-token output limit, against 5 for LLMSlim with the reranker and 1 for LongLLMLingua. A response cut off before it names the answer scores 0, so this may cost LLMLingua-2 a few points." },
    { title: "Timings from one machine", body: "Wall-clock medians per question, excluding the reader call. \"About 100× faster\" is wall-clock speed, not a count of operations; by parameters the reranker is about 300× smaller than LLaMA-2-7B. The reranker ran as two worker processes sharing the GPU, the baselines as one." },
  ],
  chooseThem: [
    { title: "You compress one long prompt with no question", body: "LLMSlim's selection is designed around a query, and it keeps or drops whole sentences. If you compress instructions, few-shot examples or a transcript with nothing to rank against, and want every sentence shortened rather than some sentences dropped, task-agnostic token-level compression such as LLMLingua-2 is built for that." },
    { title: "Your reader does better with reordered passages", body: "LongLLMLingua won our original sample by 6.0 points. The benchmark README's error analysis traces that gap to reading, not retention: the reader answered more reliably from LongLLMLingua's reordered, more complete passages. (Those retention figures need the prompts that were sent, which are not committed yet.) Ordering by relevance did not help LLMSlim on our development split (−2.7 points), so LLMSlim keeps the original order." },
    { title: "You want a method with peer-reviewed papers", body: "LLMLingua-2 and LongLLMLingua are described and evaluated in peer-reviewed papers at ACL venues. LLMSlim has no paper: its evidence is a public harness with per-case results and spend ledgers." },
    { title: "LongLLMLingua already works for you", body: "Over 300 cases the two were level (+0.7, 95% CI −4.7 to +6.0). If you already run a GPU for the 7B model and it meets your latency budget, switching buys speed and a smaller footprint, not a measured accuracy gain." },
    { title: "Your text is mostly not in English", body: "LLMSlim's default lexical scoring uses English stemming and stopwords, and we have no published results on other languages. Evaluate both on your own data before choosing." },
  ],
  chooseUs: [
    "Retrieval with a question, where you want the reader to see verbatim passages that match it, inside one shared budget.",
    "No GPU, or a tight latency budget: the default needs no model, and the reranker is 22M parameters rather than 7B.",
    "Deterministic output and a small install, with no PyTorch unless you add the reranker.",
    "LangChain, LlamaIndex or Haystack pipelines, with the same adapter options in each.",
    "Agents and RAG where retrieved or tool text must stay untrusted when it is compressed.",
  ],
  migrations: [
    {
      framework: "LangChain",
      before: {
        label: "LLMLinguaCompressor",
        filename: "before.py",
        install: "pip install langchain-community llmlingua",
        code: `from langchain_classic.retrievers.contextual_compression import (
    ContextualCompressionRetriever,
)
from langchain_community.document_compressors import LLMLinguaCompressor

compressor = LLMLinguaCompressor(
    model_name="NousResearch/Llama-2-7b-hf",  # the class defaults
    device_map="cuda",
    target_token=300,
)
retriever = ContextualCompressionRetriever(
    base_compressor=compressor, base_retriever=base_retriever
)`,
      },
      after: {
        label: "LLMSlimCompressor",
        filename: "after.py",
        install: "pip install \"llmslim[langchain]\" langchain-classic",
        code: `from langchain_classic.retrievers.contextual_compression import (
    ContextualCompressionRetriever,
)
from llmslim.integrations.langchain import LLMSlimCompressor

compressor = LLMSlimCompressor(
    target_ratio=0.25,       # a fraction of the retrieved tokens
    # relevance="semantic",  # optional 22M reranker: llmslim[semantic]
)
retriever = ContextualCompressionRetriever(
    base_compressor=compressor, base_retriever=base_retriever
)`,
      },
      notes: ["On LangChain 0.3, import ContextualCompressionRetriever from langchain.retrievers.contextual_compression."],
      guide: "/integrations/langchain",
    },
    {
      framework: "LlamaIndex",
      before: {
        label: "LongLLMLinguaPostprocessor",
        filename: "before.py",
        install: "pip install llama-index-postprocessor-longllmlingua",
        code: `from llama_index.postprocessor.longllmlingua import LongLLMLinguaPostprocessor

# Loads NousResearch/Llama-2-7b-hf on CUDA unless you pass model_name and device_map.
postprocessor = LongLLMLinguaPostprocessor(
    instruction_str="Given the context, please answer the final question",
    target_token=300,
    rank_method="longllmlingua",
)
query_engine = index.as_query_engine(
    similarity_top_k=10, node_postprocessors=[postprocessor]
)`,
      },
      after: {
        label: "LLMSlimPostprocessor",
        filename: "after.py",
        install: "pip install \"llmslim[llamaindex]\"   # Python 3.10+",
        code: `from llmslim.integrations.llama_index import LLMSlimPostprocessor

postprocessor = LLMSlimPostprocessor(
    target_ratio=0.25,       # a fraction of the retrieved tokens
    # relevance="semantic",  # optional 22M reranker: llmslim[semantic]
)
query_engine = index.as_query_engine(
    similarity_top_k=10, node_postprocessors=[postprocessor]
)`,
      },
      notes: ["The llamaindex extra needs Python 3.10 or newer."],
      guide: "/integrations/llamaindex",
    },
    {
      framework: "Plain Python",
      before: {
        label: "llmlingua.PromptCompressor",
        filename: "before.py",
        install: "pip install llmlingua",
        code: `from llmlingua import PromptCompressor

compressor = PromptCompressor(
    model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
    use_llmlingua2=True,
)
result = compressor.compress_prompt(docs, target_token=500)
context = result["compressed_prompt"]`,
      },
      after: {
        label: "llmslim.compress_documents",
        filename: "after.py",
        install: "pip install llmslim",
        code: `from llmslim import compress_documents

results = compress_documents(docs, query=question, target_ratio=0.25)
context = "\\n\\n".join(r.compressed_text for r in results)`,
      },
      notes: ["Pass the question as query so the documents share one budget; documents left out come back with empty compressed_text."],
      guide: "/docs/pipelines",
    },
    {
      framework: "Haystack",
      after: {
        label: "LLMSlimDocumentCompressor",
        filename: "pipeline.py",
        install: "pip install \"llmslim[haystack]\"",
        code: `from llmslim.integrations.haystack import LLMSlimDocumentCompressor

pipeline.add_component("compressor", LLMSlimDocumentCompressor(target_ratio=0.25))
pipeline.connect("retriever.documents", "compressor.documents")
pipeline.connect("compressor.documents", "prompt_builder.documents")
# Pass the query to the compressor too: {"compressor": {"query": query}}`,
      },
      notes: ["A Haystack 2.x component that also works with Haystack 3."],
      guide: "/integrations/haystack",
    },
  ],
  migrationNotes: [
    "target_ratio is a fraction of the input's tokens, not a token count: 0.25 keeps a quarter.",
    "Kept documents gain llmslim_original_tokens and llmslim_compressed_tokens in their metadata; record_token_counts=False turns this off.",
    "Re-run your own evaluation after switching. Our results cover one dataset and one reader.",
  ],
  faqs: [
    ["Is LLMSlim better than LLMLingua?", "Not across the board. On NaturalQuestions with 20 retrieved passages at a 25% token budget, read by Claude Haiku 5.5, LLMSlim with its 22M reranker was level with LongLLMLingua (78.7% against 78.0%; +0.7 points, 95% CI −4.7 to +6.0) and 9.7 points ahead of LLMLingua-2 (95% CI +3.7 to +15.7). Without the reranker it was level with LLMLingua-2 (68.7% against 69.0%). The LLMLingua methods were measured on that one dataset, with one reader."],
    ["Can LLMSlim replace LLMLingua in LangChain or LlamaIndex?", "It goes in the same slots. LLMSlimCompressor is a LangChain BaseDocumentCompressor, like LLMLinguaCompressor, and LLMSlimPostprocessor is a LlamaIndex BaseNodePostprocessor, like LongLLMLinguaPostprocessor. The budget is a fraction (target_ratio) instead of a token count, and the output keeps whole sentences instead of pruned tokens."],
    ["Does LLMSlim need a GPU?", "No. The default lexical mode runs no model; it took a median of 25 ms per question on CPU in the NaturalQuestions run. The optional 22M-parameter reranker also runs on CPU; our published timing for it, a median of 0.09 s, is on a 6 GB laptop GPU."],
    ["Is LLMSlim affiliated with Microsoft or LLMLingua?", "No. LLMSlim is an independent MIT-licensed project from AMEYOR. We ran LLMLingua-2 and LongLLMLingua from Microsoft's public code; Microsoft and the papers' authors did not run, review or endorse the comparison."],
    ["Why did you run LongLLMLingua in 4-bit?", "To fit LLaMA-2-7B-chat on the 6 GB laptop GPU that ran every arm. The paper does not report quantization, and llmlingua loads the model unquantized by default. 4-bit may change LongLLMLingua's scores in either direction; we did not measure by how much."],
    ["Can I reproduce the numbers?", "Yes. The splits, scripts, per-case results and spend ledgers are in benchmarks/live in the public repository, and the methodology article lists every setting. Total API spend for every suite together was about $30."],
  ],
  sources: [
    { label: "LLMLingua-2 paper (arXiv:2403.12968)", url: "https://arxiv.org/abs/2403.12968" },
    { label: "LongLLMLingua paper (arXiv:2310.06839)", url: "https://arxiv.org/abs/2310.06839" },
    { label: "microsoft/LLMLingua on GitHub", url: "https://github.com/microsoft/LLMLingua" },
    { label: "LLMLingua-2 checkpoint (Hugging Face)", url: "https://huggingface.co/microsoft/llmlingua-2-xlm-roberta-large-meetingbank" },
    { label: "LangChain LLMLinguaCompressor source", url: LANGCHAIN_SOURCE },
    { label: "LlamaIndex LongLLMLinguaPostprocessor source", url: LLAMAINDEX_SOURCE },
    { label: "LLMSlim reranker model card", url: "https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2" },
    { label: "Benchmark README and harness", url: `${siteConfig.github}/tree/main/benchmarks/live` },
    { label: "Per-case results", url: `${siteConfig.github}/tree/main/benchmarks/live/results` },
    { label: "Script that reruns the competitors", url: `${siteConfig.github}/blob/main/benchmarks/live/competitors.sh` },
  ],
}

export const COMPARISONS: Record<string, Comparison> = { [LLMLINGUA_COMPARISON.slug]: LLMLINGUA_COMPARISON }
