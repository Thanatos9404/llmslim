import { API_REFERENCE_DOCS } from "./api-reference";
import { API_REFERENCE_DOCS_0_12 } from "./api-reference-0.12";
import { CORE_DOCS } from "./docs-core";
import { siteConfig } from "@/config/site";
import { DEFAULT_DOCS_VERSION, DOCS_VERSIONS, versionStatus, type DocsVersion } from "./docs-versions";

/**
 * Text in a section, list item, table cell, callout or answer may hold `code` and [links](href). A link to another
 * guide is written [title](doc:slug) (or doc:slug#anchor) and resolves within the version being read;
 * [title](doc@1.0:slug) names the version.
 */
export interface DocCallout { type: "note" | "tip" | "warning" | "important"; title?: string; content: string; }
export interface DocFaq { question: string; answer: string; versions?: readonly DocsVersion[]; }
export interface DocSnippet { language: string; filename?: string; code: string; wrap?: boolean; }
export interface DocTable { headers: string[]; rows: string[][]; }
export interface DocSection {
  id: string; title: string; content: string;
  /** A list after the paragraph. */
  items?: string[];
  table?: DocTable;
  codeSnippet?: DocSnippet;
  /** More code blocks, after codeSnippet (a command and its output, say). */
  snippets?: DocSnippet[];
  /** A paragraph after the code. */
  after?: string;
  callout?: DocCallout;
  /** The versions this section is shown in; all when unset. */
  versions?: readonly DocsVersion[];
}
export type DocCategory = (typeof DOC_CATEGORIES)[number];
export interface DocPage {
  slug: string; title: string; subtitle: string; description: string; category: DocCategory; searchIntent: string; lastUpdated: string; readingTime: string;
  sections: DocSection[]; faqs: DocFaq[]; relatedPages: { title: string; slug: string }[];
  /** A shorter title for the sidebar, when the page's own would wrap. */
  navTitle?: string;
  /** The versions this page exists in; all when unset. */
  versions?: readonly DocsVersion[];
  /** Experimental API: a minor release may change it (docs/API_STABILITY.md). */
  experimental?: boolean;
}
export const DOC_CATEGORIES = ["Getting Started", "Guides & Strategies", "Core Concepts", "Migration", "API Reference", "Resources"] as const;
const updated = "September 2026";

/** The guides written for the site before 1.0; they hold for 0.12 and 1.0 alike. */
const COMPRESSION_DOCS: DocPage[] = [
  {
    slug: "getting-started", title: "Compression quickstart", subtitle: "Install, compress, and focus the context on the question your agent is answering.", description: "Install LLMSlim and compress long prompts with the Python API.", category: "Getting Started", searchIntent: "Install and use LLMSlim Python prompt compression.", lastUpdated: "November 2026", readingTime: "5 min read", relatedPages: [{ title: "Provenance and ContextRole", slug: "context-role" }, { title: "Pipelines", slug: "pipelines" }],
    faqs: [{ question: "Does LLMSlim require an LLM provider?", answer: "No. Extractive compression runs locally. Rewrite and hybrid strategies require a caller-supplied provider." }],
    sections: [{ id: "install", title: "Install", content: "Install the Python package with pip. Optional extras enable exact token counts.", codeSnippet: { language: "bash", filename: "terminal", code: "pip install llmslim\n# Optional exact token counter\npip install 'llmslim[fast-tokens]'" } }, { id: "compress", title: "Compress text", content: "The GENERAL role preserves the legacy compress(text) behavior.", codeSnippet: { language: "python", filename: "example.py", code: "from llmslim import compress\n\nresult = compress(long_context, target_ratio=0.5)\nprint(result.compressed_text)\nprint(result.token_counter_used)" } }, { id: "question", title: "Compress around a question", content: "Pass the question your agent is answering and LLMSlim 0.8 ranks chat rounds, documents, paragraphs or log lines against it, keeps the best ones whole and in their original order, and fits them into the budget. Logs, tracebacks and code keep their line structure.", codeSnippet: { language: "python", filename: "focus.py", code: "from llmslim import compress\n\nresult = compress(chat_history, target_ratio=0.25, query=\"Where should the replacement card be shipped?\")\nprint(result.selection)  # \"focus\", or \"lines\" for logs and other line-structured text\nprint(result.compressed_text)" } }, { id: "reranker", title: "Sharper retrieval with the reranker", content: "Relevance is lexical by default: no model, deterministic, tens of milliseconds on a 3k-token context. For retrieval and long chat memory, where the answer often shares few words with the question, add the optional 22M-parameter reranker. It also accepts any callable scorer(query, texts), such as a hosted reranking API.", codeSnippet: { language: "python", filename: "rag.py", code: "# pip install \"llmslim[semantic]\"\nfrom llmslim import compress_documents\n\nresults = compress_documents(documents, query=question, target_ratio=0.25, relevance=\"semantic\")\ncontext = \"\\n\\n\".join(r.compressed_text for r in results)" }, callout: { type: "tip", title: "Measured on public benchmarks", content: "With the reranker, LLMSlim kept long-chat accuracy within noise of the whole history at 1/62 of the cost at Haiku 5.5 list prices. See the results page for every benchmark." } }],
  },
  {
    slug: "adaptive-context-planner", title: "Adaptive Context Planner", subtitle: "Fit heterogeneous context into a real model budget without weakening hard constraints.", description: "Build deterministic, explainable context plans across instructions, chat, retrieval, memory, and tool contracts.", category: "Core Concepts", searchIntent: "LLMSlim adaptive context planner API and policies.", lastUpdated: "November 2026", readingTime: "6 min read", relatedPages: [{ title: "Provenance and ContextRole", slug: "context-role" }, { title: "MCP catalogs", slug: "mcp-catalogs" }],
    faqs: [{ question: "Can the planner drop trusted instructions?", answer: "No. Required trusted items are hard constraints. If they cannot fit, the plan is explicitly infeasible." }, { question: "Does planning call an LLM or execute tools?", answer: "No. Offline planning is local and deterministic. The separate hosted Sarvam mode calls a model only after server-side quota and spend checks; tool execution remains the host's responsibility." }, { question: "Is the hosted Sarvam key sent to the browser?", answer: "No. The key is read only by the server function and is never included in client configuration, responses, telemetry, or browser storage." }],
    sections: [
      { id: "plan", title: "Create a plan", content: "Choose a model profile, policy, and output-token reserve. The planner generates safe representation candidates, allocates them deterministically, validates the result, and explains every decision. An infeasible plan says why in plan.warnings; pass raise_on_infeasible=True to get a ContextPlanningError instead.", codeSnippet: { language: "python", filename: "planner.py", code: "from llmslim import plan_context\n\nplan = plan_context(\n    messages=[\n        {\"role\": \"system\", \"content\": \"Answer only from supplied evidence.\"},\n        *messages,\n    ],\n    documents=documents,\n    tools=tools,\n    model=\"sarvam-105b\",\n    policy=\"balanced\",\n    reserve_output_tokens=1024,\n)\n\nif not plan.feasible:\n    raise RuntimeError(\"; \".join(plan.warnings))\nprint(plan.final_context)" } },
      { id: "policies", title: "Policies and validation", content: "Balanced, quality-first, cost-first, and latency-first policies change the utility tradeoff, not the trust boundary. Post-plan validation can conservatively fall back to safer candidates.", callout: { type: "important", title: "Planning is not authorization", content: "Tool schema selection never grants permission to call a tool. Preserve authorization, argument validation, and execution in the host." } },
    ],
  },
  {
    slug: "context-role", title: "Provenance and ContextRole", subtitle: "Assign the trust semantics of the content you are compressing.", description: "Keep untrusted retrieval, tool, and assistant content out of the protected priority tier.", category: "Core Concepts", searchIntent: "LLMSlim ContextRole provenance security model.", lastUpdated: updated, readingTime: "5 min read", relatedPages: [{ title: "Pipelines", slug: "pipelines" }, { title: "Compression quickstart", slug: "getting-started" }],
    faqs: [{ question: "Does ContextRole prevent prompt injection?", answer: "No. It mitigates compression-induced instruction elevation. Applications still need defense in depth." }, { question: "Can LLMSlim authenticate a role label?", answer: "No. The caller is responsible for accurate provenance." }],
    sections: [{ id: "roles", title: "Roles", content: "SYSTEM and DEVELOPER are trusted. USER is semi-trusted. ASSISTANT, TOOL, and RAG are untrusted: wording and preservation-pattern matches cannot move them above Tier 2 or make them must_keep. GENERAL is the legacy default.", codeSnippet: { language: "python", filename: "roles.py", code: "from llmslim import ContextRole, compress\n\nresult = compress(retrieved_text, context_role=ContextRole.RAG)" }, callout: { type: "important", title: "Trust boundary", content: "LLMSlim trusts caller-provided role labels and cannot authenticate provenance." } }],
  },
  {
    slug: "mcp-catalogs", title: "MCP catalogs and agent hosts", subtitle: "Read complete tool contracts while keeping execution in your host.", description: "Use LLMSlim's MCP catalog sources, context plans, scoped caching, and the optional OpenAI Agents SDK bridge.", category: "Guides & Strategies", searchIntent: "LLMSlim MCP catalog and OpenAI Agents SDK integration.", lastUpdated: "November 2026", readingTime: "4 min read", relatedPages: [{ title: "Adaptive Context Planner", slug: "adaptive-context-planner" }, { title: "MCP quickstart", slug: "quickstart-mcp" }],
    faqs: [{ question: "Does this execute MCP tools?", answer: "Catalog sources only list tools. The optional Agents bridge requires your async invocation callback; your host remains responsible for authorization, argument validation, and execution." }, { question: "Does the default save schema tokens?", answer: "No. Full and measure-only plans retain every authoritative schema. Selective exposure is an explicit research-only experiment." }],
    sections: [
      { id: "install", title: "Install an optional integration", content: "MCP and Agents extras require Python 3.10 or newer. Base planning and text compression remain available without these SDKs. This page is about reading other MCP servers' tool catalogs; to give an MCP client memory, see the [MCP quickstart](doc:quickstart-mcp).", codeSnippet: { language: "bash", filename: "terminal", code: "pip install 'llmslim[mcp]'\n# For the optional Agents SDK bridge:\npip install 'llmslim[agents]'" } },
      { id: "catalog", title: "List, plan, and hydrate", content: "Configure a trusted endpoint explicitly. HTTP is allowed only for localhost development; remote endpoints require HTTPS. Stdio sources accept an executable and literal argument list. Plans default to the full catalog.", codeSnippet: { language: "python", filename: "catalog.py", code: "import asyncio\nfrom llmslim.mcp import MCPToolCatalogSource, plan_catalog_context, hydrate_plan\n\nasync def main():\n    source = MCPToolCatalogSource.from_streamable_http(\n        'http://127.0.0.1:8000/mcp', source_id='local-tools'\n    )\n    snapshot = await source.list_tools()\n    plan = plan_catalog_context(snapshot)\n    schemas = hydrate_plan(snapshot, plan)\n    print(len(schemas), plan.metrics.catalog_tokens)\n\nasyncio.run(main())" } },
      { id: "cache", title: "Freshness and host ownership", content: "The shortest page TTL governs the full snapshot. Private entries are isolated by the caller's cache principal; only explicitly public responses may be shared. Use source.refresh() or source.invalidate() when your host learns a catalog changed. Hydration rejects a plan from a different catalog fingerprint.", callout: { type: "important", title: "Selection is not permission", content: "Never use rankings or fingerprints as authorization. Keep provider credentials and execution policy in the host. Live-model task success is not established by the offline integration benchmark." } },
    ],
  },
  {
    slug: "pipelines", title: "Document and chat pipelines", subtitle: "Use explicit provenance for retrieval and conversational context.", description: "Compress retrieved documents and chat messages with role-aware defaults.", category: "API Reference", searchIntent: "LLMSlim pipeline API.", lastUpdated: updated, readingTime: "4 min read", relatedPages: [{ title: "Provenance and ContextRole", slug: "context-role" }], faqs: [{ question: "Are system messages compressed by default?", answer: "No. The default chat pipeline leaves system messages unchanged." }],
    sections: [{ id: "documents", title: "Retrieved documents", content: "compress_documents() defaults to ContextRole.RAG. This is an intentional v0.3.1 behavior change.", codeSnippet: { language: "python", filename: "rag.py", code: "from llmslim import compress_documents\nresults = compress_documents(documents, query=user_query, target_ratio=0.4)" } }, { id: "chat", title: "Chat messages", content: "compress_chat_messages() propagates system, developer, user, assistant, and tool roles. Unknown roles map to GENERAL.", codeSnippet: { language: "python", filename: "chat.py", code: "from llmslim import compress_chat_messages\ncompressed = compress_chat_messages(messages, target_ratio=0.5)" } }],
  },
  {
    slug: "telemetry", title: "Token counter telemetry", subtitle: "Understand token-count precision in each result.", description: "Read token_counter_used and handle the heuristic fallback appropriately.", category: "API Reference", searchIntent: "LLMSlim token_counter_used heuristic.", lastUpdated: updated, readingTime: "2 min read", relatedPages: [{ title: "Compression quickstart", slug: "getting-started" }], faqs: [{ question: "When is the heuristic used?", answer: "When the process cannot load the tiktoken encoder. LLMSlim emits one warning per process." }],
    sections: [{ id: "counter", title: "Inspect the counter", content: "token_counter_used reports the process-level active counter: tiktoken or heuristic.", codeSnippet: { language: "python", filename: "tokens.py", code: "from llmslim import compress\nresult = compress(long_text)\nprint(result.token_counter_used)" } }],
  },
];

/** Every page of every version. A slug may appear once per version: a page that changes between versions has two entries. */
export const ALL_DOCS: DocPage[] = [
  ...CORE_DOCS,
  ...COMPRESSION_DOCS,
  // Generated from the Python source by scripts/api_reference.py: main for 1.0, the v0.12.0 tag for 0.12.
  ...API_REFERENCE_DOCS.map((doc): DocPage => ({ ...doc, versions: ["1.0"] })),
  ...API_REFERENCE_DOCS_0_12.map((doc): DocPage => ({ ...doc, versions: ["0.12"] })),
];

const shownIn = (version: DocsVersion) => (item: { versions?: readonly DocsVersion[] }) => !item.versions || item.versions.includes(version);

/** The pages of one version, by slug, with the sections, answers and related pages that belong to it. */
export function docsFor(version: DocsVersion): Record<string, DocPage> {
  const pages = ALL_DOCS.filter(shownIn(version))
  const titles = new Map(pages.map((page) => [page.slug, page.title]))
  if (titles.size !== pages.length) throw new Error(`docs ${version}: a slug is used twice`)
  return Object.fromEntries(pages.map((page) => [page.slug, {
    ...page,
    sections: page.sections.filter(shownIn(version)),
    faqs: page.faqs.filter(shownIn(version)),
    // Related pages this version has, under their own titles.
    relatedPages: page.relatedPages.flatMap((related) => (titles.has(related.slug) ? [{ slug: related.slug, title: titles.get(related.slug)! }] : [])),
  }]))
}

export const DOCS_BY_VERSION = Object.fromEntries(DOCS_VERSIONS.map((version) => [version.id, docsFor(version.id)])) as Record<DocsVersion, Record<string, DocPage>>;

/** The pages /docs shows: the default version's (src/data/docs-versions.ts). */
export const DOCS_REGISTRY: Record<string, DocPage> = DOCS_BY_VERSION[DEFAULT_DOCS_VERSION];

/** A version's pages in reading order: by category, then as listed. */
export function docsInOrder(version: DocsVersion): DocPage[] {
  const pages = Object.values(DOCS_BY_VERSION[version])
  return DOC_CATEGORIES.flatMap((category) => pages.filter((page) => page.category === category))
}

/** Whether a page is new in this version: it exists here and in no older version. */
export function isNewIn(version: DocsVersion, slug: string): boolean {
  const index = DOCS_VERSIONS.findIndex((item) => item.id === version)
  const older = DOCS_VERSIONS.slice(index + 1)
  return older.length > 0 && older.every((item) => !DOCS_BY_VERSION[item.id][slug])
}

/** How a version reaches PyPI ("the 0.13 release candidate and then 1.0"). */
export const shipsAs = (version: DocsVersion): string => DOCS_VERSIONS.find((item) => item.id === version)?.ships ?? version

/** The plain-text notice the docs show above a page of a version other than the default (also used in Markdown). */
export function versionNoticeText(version: DocsVersion): string | null {
  const status = versionStatus(version)
  if (status === "preview") return `Upcoming in ${version} (preview). These pages describe the main branch of LLMSlim Core, which becomes ${shipsAs(version)}. \`pip install llmslim\` installs ${siteConfig.coreVersion} today, which doesn't have everything described here.`
  if (status === "previous") return `These are the docs for LLMSlim Core ${version}. The current version is ${DEFAULT_DOCS_VERSION}.`
  return null
}
