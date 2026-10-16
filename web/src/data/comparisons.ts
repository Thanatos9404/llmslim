/**
 * Comparison pages (/compare/<slug>). The page and its Markdown twin (/compare/<slug>.md, llms-full.txt) both
 * render from this data.
 *
 * Every benchmark number comes from round 3 in the public repository (benchmarks/live/round3: RESULTS.md,
 * README.md, results/*.jsonl.gz; LLMSlim Core 0.9.0) and matches /benchmarks. Wording: "level with" whenever the
 * 95% interval includes zero, never "beats"; "faster per question", never "less compute"; costs are per 1,000
 * questions end to end, as in METHOD_NOTES. Competitor APIs in the migration snippets were checked against their
 * source on GitHub.
 */
import { siteConfig } from "@/config/site"
import { ROUND3_REPORT } from "@/data/live-benchmarks"

export type GlanceRow = {
  aspect: string
  llmslim: string
  /** LLMLingua-2. When `longLingua` is absent, this cell spans both LLMLingua columns. */
  lingua2: string
  longLingua?: string
}

/** A paired difference on the same questions: first system minus second, with its 95% interval. */
export type PairedDiff = { comparison: string; benchmark: string; difference: string; reading: "Level" | "Ahead" }

/** Scores on every test question of each benchmark: one row per system, one cell per column. */
export type ResultTable = { columns: string[]; rows: { system: string; cells: string[] }[]; note: string }

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
  /** Introduces the head-to-head table (HEAD_TO_HEAD in live-benchmarks, shared with /benchmarks). */
  headToHeadIntro: string
  pairedDiffs: PairedDiff[]
  pairedNote: string
  testSets: ResultTable
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
  description: "LLMSlim vs LLMLingua-2 and LongLLMLingua: how each compresses, same-budget results on NaturalQuestions, HotpotQA and LoCoMo with cost and confidence intervals, and migration code.",
  kicker: "Comparison · LLMLingua alternative",
  heading: ["LLMSlim vs LLMLingua.", "An honest comparison."],
  lede: "LLMLingua-2 and LongLLMLingua are prompt compressors from Microsoft Research that prune tokens with a language model. LLMSlim is an MIT-licensed Python library that selects whole passages and sentences around the question, with no model by default. Here is how they differ, what three public benchmarks show, and when LLMLingua is the better choice.",
  lastUpdated: "October 15, 2026",
  disclosure: "We build LLMSlim. We are not affiliated with Microsoft or the LLMLingua authors. We ran both LLMLingua methods ourselves from their public code, in public Kaggle notebooks that anyone can rerun.",
  shortAnswer: [
    "We ran LLMLingua-2 and LongLLMLingua with their published settings on NaturalQuestions, HotpotQA and LoCoMo, at the same token budget as LLMSlim Core 0.9. Claude Haiku 5.5 read every context with the same answer prompt.",
    "Level with LongLLMLingua on retrieval. On its 1,000-question NaturalQuestions sample, LLMSlim with its optional 22M-parameter reranker scored 72.7% to LongLLMLingua's 70.5% (+2.2 points, 95% CI −0.8 to +5.3). On HotpotQA the default LLMSlim scored 53.3% to 50.4% (+2.9, 95% CI −0.1 to +5.7). Neither gap is significant.",
    "Ahead of LongLLMLingua on long conversations: on LoCoMo at about 2,500 tokens, 93.3% against 73.3% on its 300-question sample (+20.0 points, 95% CI +15.0 to +25.0).",
    "With its reranker, ahead of LLMLingua-2 on every benchmark we ran both on: +20.7 points on NaturalQuestions (95% CI +17.2 to +24.2), +3.9 on HotpotQA (+0.8 to +7.0) and +60.3 on LoCoMo (+54.7 to +66.0). On LongMemEval's chat histories of about 111k tokens, LLMLingua-2 answered 7.2% at 2,500 tokens, against 74.4% for LLMSlim with its reranker.",
    "A quarter of LongLLMLingua's cost, and faster per question without a GPU: $0.33 per 1,000 NaturalQuestions questions end to end, against $1.32 for LongLLMLingua and $0.86 for LLMLingua-2, and a median of 1.3 s per question on a CPU, against 6.9 s for LongLLMLingua on a T4 GPU.",
    "Where LLMSlim is behind: without the reranker it runs no model and scores 59.6% on NaturalQuestions, 10.9 points below LongLLMLingua, because paraphrased questions need semantic matching. A plain reranker is level with LLMSlim and its reranker there (73.6%), and full context still scores higher on NaturalQuestions and HotpotQA (77.2% and 58.5%).",
  ],
  glance: [
    { aspect: "How it compresses", llmslim: "Ranks documents, paragraphs and sentences against the query; keeps the best whole and in their original order", lingua2: "Classifies every token as keep or drop", longLingua: "Scores each document by the question's perplexity given it with a small language model, reorders them, then drops tokens with a ratio per document" },
    { aspect: "Model it runs", llmslim: "None by default (BM25). Optional 22.7M-parameter cross-encoder", lingua2: "XLM-RoBERTa-large, about 560M parameters", longLingua: "A causal language model: LLaMA-2-7B in its paper's NaturalQuestions setup and by default in the LangChain and LlamaIndex classes" },
    { aspect: "Reads the question", llmslim: "Yes, when you pass one. Without one, each text is compressed on its own", lingua2: "No: task-agnostic", longLingua: "Yes: question-aware" },
    { aspect: "What the reader gets", llmslim: "Whole sentences copied from the input, in their original order", lingua2: "The input with tokens removed inside sentences", longLingua: "Documents reordered by relevance, with tokens removed" },
    { aspect: "Budget", llmslim: "target_ratio, a fraction of tokens (cl100k_base)", lingua2: "rate, or target_token in tokens" },
    { aspect: "Install", llmslim: "pip install llmslim: numpy, scikit-learn and jsonschema; no PyTorch", lingua2: "pip install llmlingua: PyTorch, transformers, accelerate, nltk, tiktoken" },
    { aspect: "Framework classes", llmslim: "LangChain, LlamaIndex and Haystack adapters in the llmslim package", lingua2: "LangChain LLMLinguaCompressor (langchain-community); LlamaIndex LongLLMLinguaPostprocessor" },
    { aspect: "Median time to compress one NaturalQuestions question in our run", llmslim: "18 ms on a CPU without a model; 1.3 s on a CPU with the reranker", lingua2: "3.5 s on a T4 GPU", longLingua: "6.9 s on a T4 GPU (LLaMA-2-7B-chat in float16)" },
    { aspect: "Cost per 1,000 NaturalQuestions questions in our run, end to end", llmslim: "$0.30 without a model; $0.33 with the reranker", lingua2: "$0.86", longLingua: "$1.32" },
    { aspect: "Peer-reviewed paper", llmslim: "None. Evidence is public benchmark runs: Kaggle build notebooks and per-question results", lingua2: "Pan et al., Findings of ACL 2024", longLingua: "Jiang et al., ACL 2024" },
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
  baselinesNote: "Both are open source in microsoft/LLMLingua under the MIT license. We ran their public code ourselves (llmlingua 0.2.2); Microsoft and the papers' authors did not run, review or endorse this comparison.",
  differences: [
    { title: "Selection, not token pruning", body: "LLMSlim ranks the context's units (documents, chat rounds, paragraphs) against the query, keeps the best ones whole and in their original order, and fills the rest of the budget sentence by sentence. It never deletes words inside a sentence, so the model reads text from your documents, unchanged." },
    { title: "No 7B model", body: "Relevance is lexical by default: BM25 with light stemming and one round of pseudo-relevance feedback. No model, no download and deterministic output, at a median of 18 ms per question on a CPU in our NaturalQuestions run." },
    { title: "An optional 22M reranker", body: "pip install \"llmslim[semantic]\" and relevance=\"semantic\" add cross-encoder/ms-marco-MiniLM-L-6-v2 (22.7M parameters, trained on MS MARCO web search). It rescores the 80 strongest lexical candidates, so it works on top of BM25, and it runs on a CPU. Any callable scorer(query, texts) works too." },
    { title: "One budget across documents", body: "With a query, retrieved documents share one budget: the relevant ones stay whole and the rest are dropped, instead of every document losing the same share. Retrieved text keeps untrusted RAG provenance, so imperative wording inside it is never force-kept." },
  ],
  headToHeadIntro: "Each compressor ran with its published settings and the same token budget: 25% of 20 retrieved passages on NaturalQuestions, 40% of 10 Wikipedia paragraphs on HotpotQA, and about 2,500 tokens of a long conversation on LoCoMo. Claude Haiku 5.5 read every context with the same answer prompt, so only the context changes.",
  pairedDiffs: [
    { comparison: "LLMSlim + reranker vs LongLLMLingua", benchmark: "NaturalQuestions (1,000)", difference: "+2.2 (−0.8, +5.3)", reading: "Level" },
    { comparison: "LLMSlim + reranker vs LLMLingua-2", benchmark: "NaturalQuestions (1,000)", difference: "+20.7 (+17.2, +24.2)", reading: "Ahead" },
    { comparison: "LLMSlim + reranker vs a plain reranker", benchmark: "NaturalQuestions (1,000)", difference: "−0.9 (−3.5, +1.5)", reading: "Level" },
    { comparison: "LLMSlim, no model, vs LongLLMLingua", benchmark: "HotpotQA (1,000)", difference: "+2.9 (−0.1, +5.7)", reading: "Level" },
    { comparison: "LLMSlim + reranker vs LongLLMLingua", benchmark: "HotpotQA (1,000)", difference: "+2.4 (−0.4, +5.3)", reading: "Level" },
    { comparison: "LLMSlim + reranker vs LLMLingua-2", benchmark: "HotpotQA (1,000)", difference: "+3.9 (+0.8, +7.0)", reading: "Ahead" },
    { comparison: "LLMSlim + reranker vs LongLLMLingua", benchmark: "LoCoMo (300)", difference: "+20.0 (+15.0, +25.0)", reading: "Ahead" },
    { comparison: "LLMSlim + reranker vs LLMLingua-2", benchmark: "LoCoMo (300)", difference: "+60.3 (+54.7, +66.0)", reading: "Ahead" },
  ],
  pairedNote: "Paired differences in points, first system minus second, on the same questions (LongLLMLingua's pre-registered samples), with the paired bootstrap 95% interval in brackets. Level means the interval includes zero, so the gap may be noise. LLMSlim is Core 0.9.0.",
  testSets: {
    columns: ["NaturalQuestions (2,255)", "HotpotQA (2,000)", "LoCoMo (1,307)", "LongMemEval-S (180)"],
    rows: [
      { system: "LLMSlim 0.9 + reranker", cells: ["73.5", "52.2", "93.0", "74.4 / 74.4"] },
      { system: "LLMSlim 0.9", cells: ["60.6", "52.4", "91.7", "70.6 / 77.8"] },
      { system: "LLMLingua-2", cells: ["52.5", "46.7", "34.1", "7.2 / 15.6"] },
      { system: "Plain reranker", cells: ["73.9", "50.5", "not run", "not run"] },
      { system: "Full context", cells: ["78.4", "58.0", "95.1", "77.8"] },
    ],
    note: "Every test question of each benchmark, at the budgets above. LongMemEval-S is at about 2,500 / 10,000 tokens of histories averaging 111k tokens, scored by its official judge; full context there sends the whole history. LongLLMLingua is not in this table: it ran only on its samples, and not on LongMemEval. At 10,000 tokens on LoCoMo, LLMLingua-2 scores 77.9% and LLMSlim 94.3%.",
  },
  caveats: [
    { title: "One reader", body: "Every number uses Claude Haiku 5.5 at effort low. Another reader may rank these systems differently. The papers' own NaturalQuestions numbers use GPT-3.5-Turbo, so raw scores are not comparable across the two." },
    { title: "Samples for LongLLMLingua", body: "LongLLMLingua takes about 7 s a question on a T4 GPU, so it ran on pre-registered samples: 1,000 NaturalQuestions, 1,000 HotpotQA and 300 LoCoMo questions. The paired 95% intervals are about ±3 points on 1,000 questions and ±5 to ±6 on 300. It was not run on LongMemEval, whose 180 histories of about 115k tokens would need roughly 13 hours, more than a Kaggle session allows." },
    { title: "Baselines we ran ourselves", body: "We used published settings: LongLLMLingua's NaturalQuestions settings from its paper, with NousResearch/Llama-2-7b-chat-hf in float16, the precision its weights are published in; LLMLingua-2's MeetingBank checkpoint. We also build one of the systems compared. Other settings may score differently. The builds ran in public Kaggle notebooks pinned to a commit, whose manifests hash every output." },
    { title: "Same budget, not always the same use", body: "Every compressor was held to the same token budget. On NaturalQuestions all used close to it: a mean of 668 tokens for LLMSlim with the reranker, 636 for LongLLMLingua and 683 for LLMLingua-2. On HotpotQA LongLLMLingua used fewer (449 against 523 for LLMSlim), and on LoCoMo both LLMLingua methods came in about 20% under 2,500 tokens (a mean of about 2,000, against about 2,500 for LLMSlim). A smaller context may cost them some points; at 10,000 tokens LLMLingua-2 scores 77.9% on LoCoMo, still below LLMSlim at 2,500 (91.7%)." },
    { title: "Timings and costs on different machines", body: "Times are medians to compress one NaturalQuestions question, excluding the reader call: LLMSlim on a CPU, the LLMLingua methods on a T4 GPU, all on Kaggle. Costs add that machine time at cloud prices (a T4 at $0.526 an hour, 2 vCPUs at $0.0892) to the reader's answer call at list prices; judge calls are not counted for anyone. Other hardware will give other times." },
    { title: "Where LLMSlim is behind", body: "Without its reranker LLMSlim scores 59.6% on NaturalQuestions, against 70.5% for LongLLMLingua: open-domain questions are often worded differently from the passage that answers them, and lexical matching misses them. A plain reranker is level with LLMSlim and its reranker there, and full context still leads on NaturalQuestions and HotpotQA." },
  ],
  chooseThem: [
    { title: "You compress one long prompt with no question", body: "LLMSlim's selection is designed around a query, and it keeps or drops whole sentences. If you compress instructions, few-shot examples or a transcript with nothing to rank against, and want every sentence shortened rather than some sentences dropped, task-agnostic token-level compression such as LLMLingua-2 is built for that." },
    { title: "Open-domain retrieval without LLMSlim's reranker", body: "If you will run LLMSlim only in its default, no-model mode, LongLLMLingua is the more accurate of the two on open-domain questions: 70.5% against 59.6% on NaturalQuestions. With its 22M reranker, LLMSlim is level with LongLLMLingua there (72.7%)." },
    { title: "You want a method with peer-reviewed papers", body: "LLMLingua-2 and LongLLMLingua are described and evaluated in peer-reviewed papers at ACL venues. LLMSlim has no paper: its evidence is public benchmark runs, with Kaggle build notebooks, per-question results and spend ledgers." },
    { title: "LongLLMLingua already works for you on retrieval", body: "On NaturalQuestions and HotpotQA the two were level (+2.2 points on NaturalQuestions, 95% CI −0.8 to +5.3). If you already run a GPU for the 7B model and it meets your latency budget, switching buys a lower cost and faster compression per question, not a measured accuracy gain. On long conversations LLMSlim was 20 points ahead." },
    { title: "Your text is mostly not in English", body: "LLMSlim's default lexical scoring uses English stemming and stopwords, and we have no published results on other languages. Evaluate both on your own data before choosing." },
  ],
  chooseUs: [
    "Retrieval with a question, where you want the reader to see verbatim passages that match it, inside one shared budget.",
    "Chat memory and long conversations: on LoCoMo at about 2,500 tokens, LLMSlim with its reranker answered 93.3% to LongLLMLingua's 73.3% and LLMLingua-2's 33.0%.",
    "No GPU, or a tight latency or cost budget: the default needs no model, and the reranker is 22M parameters rather than 7B and runs on a CPU. $0.33 per 1,000 NaturalQuestions questions end to end, against $1.32 for LongLLMLingua.",
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
    "Re-run your own evaluation after switching. Our results cover three English benchmarks and one reader.",
  ],
  faqs: [
    ["Is LLMSlim better than LLMLingua?", "Not across the board. Read by Claude Haiku 5.5 at the same token budget, LLMSlim Core 0.9 with its 22M reranker was level with LongLLMLingua on retrieval: 72.7% against 70.5% on NaturalQuestions (+2.2 points, 95% CI −0.8 to +5.3) and 52.8% against 50.4% on HotpotQA (+2.4, −0.4 to +5.3). It was ahead on long conversations: 93.3% against 73.3% on LoCoMo (+20.0, +15.0 to +25.0). It was ahead of LLMLingua-2 on all three. Without the reranker LLMSlim scored 59.6% on NaturalQuestions, well behind LongLLMLingua, and full context still scores higher on NaturalQuestions and HotpotQA."],
    ["Can LLMSlim replace LLMLingua in LangChain or LlamaIndex?", "It goes in the same slots. LLMSlimCompressor is a LangChain BaseDocumentCompressor, like LLMLinguaCompressor, and LLMSlimPostprocessor is a LlamaIndex BaseNodePostprocessor, like LongLLMLinguaPostprocessor. The budget is a fraction (target_ratio) instead of a token count, and the output keeps whole sentences instead of pruned tokens."],
    ["Does LLMSlim need a GPU?", "No. The default lexical mode runs no model: a median of 18 ms per NaturalQuestions question on a CPU. The optional 22M-parameter reranker also runs on a CPU, and our published timing for it is on one: a median of 1.3 s per question, against 6.9 s for LongLLMLingua and 3.5 s for LLMLingua-2 on a T4 GPU."],
    ["Is LLMSlim affiliated with Microsoft or LLMLingua?", "No. LLMSlim is an independent MIT-licensed project from AMEYOR. We ran LLMLingua-2 and LongLLMLingua from Microsoft's public code; Microsoft and the papers' authors did not run, review or endorse the comparison."],
    ["How did you run LongLLMLingua?", "With its paper's NaturalQuestions settings and NousResearch/Llama-2-7b-chat-hf in float16, the precision its weights are published in, from llmlingua 0.2.2 on Kaggle's T4 GPUs, held to the same token budget as every other system. It takes about 7 s a question there, so it ran on pre-registered samples: 1,000 NaturalQuestions, 1,000 HotpotQA and 300 LoCoMo questions. It was not run on LongMemEval, whose 180 histories of about 115k tokens would need roughly 13 hours, more than a Kaggle session allows."],
    ["Can I reproduce the numbers?", "Yes. Every compressor's context was built in public Kaggle notebooks pinned to a commit, whose manifests hash every input and output, so anyone can rerun them and compare byte for byte. The splits, reader scripts and every answer and judgement are in benchmarks/live/round3 in the public repository. All of round 3, every system and benchmark, cost $107.10 in Claude API calls."],
  ],
  sources: [
    { label: "LLMLingua-2 paper (arXiv:2403.12968)", url: "https://arxiv.org/abs/2403.12968" },
    { label: "LongLLMLingua paper (arXiv:2310.06839)", url: "https://arxiv.org/abs/2310.06839" },
    { label: "microsoft/LLMLingua on GitHub", url: "https://github.com/microsoft/LLMLingua" },
    { label: "LLMLingua-2 checkpoint (Hugging Face)", url: "https://huggingface.co/microsoft/llmlingua-2-xlm-roberta-large-meetingbank" },
    { label: "LongLLMLingua's scorer, Llama-2-7b-chat-hf (Hugging Face)", url: "https://huggingface.co/NousResearch/Llama-2-7b-chat-hf" },
    { label: "LangChain LLMLinguaCompressor source", url: LANGCHAIN_SOURCE },
    { label: "LlamaIndex LongLLMLinguaPostprocessor source", url: LLAMAINDEX_SOURCE },
    { label: "LLMSlim reranker model card", url: "https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2" },
    { label: "Round 3 report and tables", url: ROUND3_REPORT },
    { label: "How round 3 was run, and what went wrong", url: `${siteConfig.github}/tree/main/benchmarks/live/round3` },
    { label: "Per-question results", url: `${siteConfig.github}/tree/main/benchmarks/live/round3/results` },
    { label: "LongLLMLingua build notebook (Kaggle)", url: `${siteConfig.github}/blob/main/benchmarks/live/round3/kaggle_round3_longlingua.ipynb` },
  ],
}

export const COMPARISONS: Record<string, Comparison> = { [LLMLINGUA_COMPARISON.slug]: LLMLINGUA_COMPARISON }
