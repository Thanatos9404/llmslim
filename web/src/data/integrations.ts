export interface IntegrationFaq {
  question: string;
  answer: string;
}

export interface IntegrationTroubleshooting {
  issue: string;
  solution: string;
}

export interface IntegrationBenchmark {
  metric: string;
  uncompressed: string;
  compressed: string;
  impact: string;
}

export interface IntegrationData {
  slug: string;
  name: string;
  category: "LLM Provider" | "Framework" | "Local & Edge" | "Backend Services";
  badgeText: string;
  tagline: string;
  description: string;
  installation: {
    packageManager: string;
    command: string;
  };
  architectureFlow: string[];
  codeExample: {
    language: string;
    filename: string;
    code: string;
  };
  deploymentGuide: string;
  optimizationTips: string[];
  benchmarks: IntegrationBenchmark[];
  faqs: IntegrationFaq[];
  troubleshooting: IntegrationTroubleshooting[];
  iconKey: string;
}

export const INTEGRATION_CATEGORIES = [
  "LLM Provider",
  "Framework",
  "Local & Edge",
  "Backend Services",
] as const;

export const INTEGRATIONS_REGISTRY: Record<string, IntegrationData> = {
  openai: {
    slug: "openai",
    name: "OpenAI",
    category: "LLM Provider",
    badgeText: "GPT-4o & GPT-5 Ready",
    tagline: "Cut OpenAI API costs by 40-70% while preserving 100% instruction fidelity.",
    description: "Surgically compress input system prompts and RAG contexts before dispatching requests to OpenAI GPT-4o, GPT-4o-mini, and flagship models.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim openai",
    },
    architectureFlow: [
      "1. Application captures user input & RAG search context.",
      "2. LLMSlim executes local TF-IDF & Priority Tier compression (< 30ms).",
      "3. Token-dense compressed prompt payload dispatched to OpenAI Chat Completions API.",
      "4. GPT model processes prefill context with 50%+ lower input token billing.",
    ],
    codeExample: {
      language: "python",
      filename: "openai_llmslim.py",
      code: `from openai import OpenAI
from llmslim import compress

client = OpenAI()

def generate_answer(long_context: str, query: str) -> str:
    # Compress verbose RAG context to 40% target token count
    slim = compress(long_context, target_ratio=0.4, mode="auto")
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a senior enterprise analyst."},
            {"role": "user", "content": f"Context:\\n{slim.compressed_text}\\n\\nQuery: {query}"}
        ]
    )
    return response.choices[0].message.content`,
    },
    deploymentGuide: "Deploy LLMSlim pre-dispatch compression directly inside your API client handlers or custom SDK wrapper functions.",
    optimizationTips: [
      "Pre-compress static system directives once at application startup to eliminate repetitive system token billing.",
      "Use target_ratio=0.4 for large document contexts and target_ratio=0.6 for dense technical instructions.",
      "Enable preserve_code=True when system prompts contain JSON format schemas."
    ],
    benchmarks: [
      { metric: "Input Token Volume", uncompressed: "4,200 tokens", compressed: "1,680 tokens", impact: "60% Billed Token Reduction" },
      { metric: "Instruction Retention", uncompressed: "100.0%", compressed: "100.0%", impact: "Zero Rule Loss" },
    ],
    faqs: [
      {
        question: "Does LLMSlim work with OpenAI Structured Outputs (JSON Schema)?",
        answer: "Yes. Priority Tier 4 automatically locks JSON schema definition tags, guaranteeing structural syntax remains valid.",
      },
    ],
    troubleshooting: [
      {
        issue: "OpenAI API returns 400 validation error due to empty prompt.",
        solution: "Ensure target_ratio is set between 0.2 and 0.8. Check that input string is non-empty before calling compress().",
      },
    ],
    iconKey: "openai",
  },

  anthropic: {
    slug: "anthropic",
    name: "Anthropic Claude",
    category: "LLM Provider",
    badgeText: "Claude 3.5 Sonnet Ready",
    tagline: "Enhance Claude needle-in-a-haystack recall by pruning middle context fluff.",
    description: "Optimize context density for Claude 3.5 Sonnet, Claude Opus, and Haiku models using structural XML boundary locking.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim anthropic",
    },
    architectureFlow: [
      "1. Prepare system instructions wrapped in Claude XML tags (<instructions>).",
      "2. LLMSlim locks XML boundaries in Tier 4 and prunes repetitive narrative prose.",
      "3. Dispatch compressed prompt payload via Anthropic Messages API.",
    ],
    codeExample: {
      language: "python",
      filename: "claude_llmslim.py",
      code: `import anthropic
from llmslim import compress

client = anthropic.Anthropic()

raw_prompt = """
<instructions>
You MUST extract user entities strictly into <output> tags.
</instructions>
<context>
Verbose customer support transcript details and repetitive prose...
</context>
"""

slim_prompt = compress(raw_prompt, target_ratio=0.5, mode="xml").compressed_text

message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{"role": "user", "content": slim_prompt}]
)
print(message.content[0].text)`,
    },
    deploymentGuide: "Pass XML-structured context payloads through compress(mode='xml') before dispatching to client.messages.create().",
    optimizationTips: [
      "Wrap Claude system directives inside explicit XML tags to trigger Tier 4 hard locking.",
      "Combine compress_documents() with Claude 200k context windows for high-density document analysis."
    ],
    benchmarks: [
      { metric: "Context Token Payload", uncompressed: "8,500 tokens", compressed: "3,400 tokens", impact: "60% Payload Reduction" },
    ],
    faqs: [
      {
        question: "Does LLMSlim strip Claude XML tags?",
        answer: "No. The XML optimizer mode explicitly locks tags like <instructions>, <context>, and <examples>.",
      },
    ],
    troubleshooting: [
      {
        issue: "Malformed XML error from Anthropic SDK.",
        solution: "Set mode='xml' explicitly in compress() to enable tag structural awareness.",
      },
    ],
    iconKey: "anthropic",
  },

  gemini: {
    slug: "gemini",
    name: "Google Gemini",
    category: "LLM Provider",
    badgeText: "Gemini 2.5 Pro 1M+ Ready",
    tagline: "Control costs and prefill latency across 1M+ token Gemini context windows.",
    description: "High-density context engineering for Gemini 1.5 and 2.5 Pro prompts in Google Vertex AI and Gemini REST SDKs.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim google-genai",
    },
    architectureFlow: [
      "1. Ingest multi-megabyte document context for Gemini analysis.",
      "2. LLMSlim executes offline sentence centrality scoring to extract core informational nodes.",
      "3. Forward token-dense prompt to google.genai client.",
    ],
    codeExample: {
      language: "python",
      filename: "gemini_llmslim.py",
      code: `from google import genai
from llmslim import compress

client = genai.Client()

large_document = "... 50,000 tokens of unstructured enterprise report ..."
slim_doc = compress(large_document, target_ratio=0.35).compressed_text

response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents=f"Document:\\n{slim_doc}\\n\\nQuery: Summarize executive findings."
)
print(response.text)`,
    },
    deploymentGuide: "Use LLMSlim as a document pre-processor prior to dispatching large payloads to Google Generative AI bindings.",
    optimizationTips: [
      "Compress 100k+ token documents down to 35% density to drastically reduce prefill latency.",
      "Utilize preserve_entities=True when analyzing complex data sheets."
    ],
    benchmarks: [
      { metric: "Large Document Payload", uncompressed: "25,000 tokens", compressed: "8,750 tokens", impact: "65% Token Savings" },
    ],
    faqs: [
      {
        question: "Is LLMSlim compatible with Google Vertex AI Python SDK?",
        answer: "Yes. LLMSlim outputs standard Python strings compatible with all Vertex AI and Google GenAI client libraries.",
      },
    ],
    troubleshooting: [
      {
        issue: "Slow response time on massive prompts.",
        solution: "Apply LLMSlim locally prior to SDK invocation to accelerate initial prefill execution.",
      },
    ],
    iconKey: "gemini",
  },

  groq: {
    slug: "groq",
    name: "Groq",
    category: "LLM Provider",
    badgeText: "LPU Inference Acceleration",
    tagline: "Combine Groq ultra-fast LPU speed with 50% prompt token reduction.",
    description: "Accelerate processing throughput on Groq LPU hardware by reducing prompt context tokens prior to API dispatch.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim groq",
    },
    architectureFlow: [
      "1. Application formats system prompt and user query.",
      "2. LLMSlim compresses payload in < 30ms locally.",
      "3. Groq LPU processes token-dense payload at ultra-high tokens/sec.",
    ],
    codeExample: {
      language: "python",
      filename: "groq_llmslim.py",
      code: `from groq import Groq
from llmslim import compress

client = Groq()

verbose_prompt = "... verbose context payload ..."
slim_prompt = compress(verbose_prompt, target_ratio=0.5).compressed_text

completion = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": slim_prompt}]
)
print(completion.choices[0].message.content)`,
    },
    deploymentGuide: "Integrate LLMSlim into your Groq API client caller functions for lightning-fast inference pipelines.",
    optimizationTips: [
      "Pairing Groq LPU inference speed with LLMSlim input token compression yields ultra-low end-to-end response latency.",
    ],
    benchmarks: [
      { metric: "Input Token Budget", uncompressed: "3,000 tokens", compressed: "1,500 tokens", impact: "50% Token Reduction" },
    ],
    faqs: [
      {
        question: "Does Groq SDK require special prompt parameters?",
        answer: "No. Groq follows standard OpenAI chat completion signature specifications.",
      },
    ],
    troubleshooting: [
      {
        issue: "Groq rate limit errors (TPM limits).",
        solution: "Use LLMSlim to shrink input prompt size to stay safely under Tokens Per Minute (TPM) quota limits.",
      },
    ],
    iconKey: "groq",
  },

  mistral: {
    slug: "mistral",
    name: "Mistral AI",
    category: "LLM Provider",
    badgeText: "Mistral Large & Codestral Ready",
    tagline: "Optimize prompt payloads for Mistral Large, Pixtral, and Codestral models.",
    description: "Surgically compress prompt context while preserving code syntax and system rules for Mistral models.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim mistralai",
    },
    architectureFlow: [
      "1. Format prompt payload containing system rules and code.",
      "2. LLMSlim locks code syntax with Tier 4 rules and compresses prose.",
      "3. Dispatch to Mistral Client API.",
    ],
    codeExample: {
      language: "python",
      filename: "mistral_llmslim.py",
      code: `from mistralai import Mistral
from llmslim import compress

client = Mistral()

raw_code_prompt = """
Fix bugs in the following Python snippet:
\`\`\`python
def calculate(a, b):
    return a + b
\`\`\`
Additional explanatory context...
"""

slim = compress(raw_code_prompt, target_ratio=0.5, preserve_code=True).compressed_text

res = client.chat.complete(
    model="mistral-large-latest",
    messages=[{"role": "user", "content": slim}]
)
print(res.choices[0].message.content)`,
    },
    deploymentGuide: "Wrap code and prompt contexts in compress(preserve_code=True) before sending to Mistral API endpoints.",
    optimizationTips: [
      "Enable preserve_code=True when using Codestral for inline code generation tasks.",
    ],
    benchmarks: [
      { metric: "Code Context Tokens", uncompressed: "2,400 tokens", compressed: "1,200 tokens", impact: "50% Token Savings" },
    ],
    faqs: [
      {
        question: "Does LLMSlim support Codestral code prompts?",
        answer: "Yes. Priority Tier 4 explicitly protects fenced code blocks and function definitions.",
      },
    ],
    troubleshooting: [
      {
        issue: "Code syntax corrupted after compression.",
        solution: "Ensure preserve_code=True is set explicitly in the compress() call.",
      },
    ],
    iconKey: "mistral",
  },

  ollama: {
    slug: "ollama",
    name: "Ollama",
    category: "Local & Edge",
    badgeText: "Local & Offline LLM Runner",
    tagline: "Accelerate local model execution by reducing VRAM prefill workload.",
    description: "Compress input prompts for local models (Llama 3, DeepSeek-R1, Qwen 2.5) running on Ollama.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim ollama",
    },
    architectureFlow: [
      "1. User sends prompt to local backend application.",
      "2. LLMSlim executes 100% offline CPU compression (< 20ms).",
      "3. Forward compressed text to local Ollama daemon.",
    ],
    codeExample: {
      language: "python",
      filename: "ollama_llmslim.py",
      code: `import ollama
from llmslim import compress

prompt = "Long system instructions... " + "Context detail... " * 50

# Compress prompt locally without external API calls
slim_prompt = compress(prompt, target_ratio=0.4).compressed_text

response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": slim_prompt}]
)
print(response['message']['content'])`,
    },
    deploymentGuide: "Combine Ollama local offline inference with LLMSlim offline CPU compression for 100% air-gapped local setups.",
    optimizationTips: [
      "Pre-compress prompts before sending to local GPUs to significantly reduce initial model evaluation time.",
    ],
    benchmarks: [
      { metric: "Local Context Payload", uncompressed: "5,000 tokens", compressed: "2,000 tokens", impact: "60% VRAM Prefill Reduction" },
    ],
    faqs: [
      {
        question: "Does LLMSlim require internet access when used with Ollama?",
        answer: "No. Core LLMSlim runs entirely offline using local Python algorithms.",
      },
    ],
    troubleshooting: [
      {
        issue: "Ollama context window overflow error.",
        solution: "Use LLMSlim with target_ratio=0.3 to ensure prompts fit within local num_ctx parameter bounds.",
      },
    ],
    iconKey: "ollama",
  },

  langchain: {
    slug: "langchain",
    name: "LangChain",
    category: "Framework",
    badgeText: "Chain & Agent Integration",
    tagline: "Compress document retrievers and chain contexts automatically in LangChain.",
    description: "Integrate LLMSlim document compression transformers into LangChain pipelines and autonomous agents.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim langchain-core",
    },
    architectureFlow: [
      "1. LangChain VectorStoreRetriever fetches matching document chunks.",
      "2. LLMSlim DocumentTransformer prunes redundant prose across chunks.",
      "3. Formatted dense prompt passed into LCEL chain runnable.",
    ],
    codeExample: {
      language: "python",
      filename: "langchain_llmslim.py",
      code: `from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from llmslim import compress

def compress_input_runnable(input_dict: dict) -> dict:
    raw_context = input_dict["context"]
    slim = compress(raw_context, target_ratio=0.4).compressed_text
    return {"context": slim, "question": input_dict["question"]}

prompt = ChatPromptTemplate.from_template("Context:\\n{context}\\n\\nQuestion: {question}")
model = ChatOpenAI(model="gpt-4o")

# Chain with pre-dispatch prompt compression
chain = compress_input_runnable | prompt | model
res = chain.invoke({"context": "... long text ...", "question": "What is the key takeaway?"})
print(res.content)`,
    },
    deploymentGuide: "Use LLMSlim function wrappers as LCEL chain runnables or custom document post-processors.",
    optimizationTips: [
      "Place LLMSlim compression immediately after retriever steps in LCEL pipelines.",
    ],
    benchmarks: [
      { metric: "Retrieved Chain Context", uncompressed: "6,000 tokens", compressed: "2,400 tokens", impact: "60% Billed Token Reduction" },
    ],
    faqs: [
      {
        question: "Can I use LLMSlim in LCEL (LangChain Expression Language)?",
        answer: "Yes. You can pipe custom Python functions using RunnableLambda or standard composition.",
      },
    ],
    troubleshooting: [
      {
        issue: "TypeError when piping dictionary output in LCEL chain.",
        solution: "Ensure custom runnable returns a clean dictionary mapping expected prompt variables.",
      },
    ],
    iconKey: "langchain",
  },

  llamaindex: {
    slug: "llamaindex",
    name: "LlamaIndex",
    category: "Framework",
    badgeText: "RAG Pipeline Optimization",
    tagline: "Surgically prune retrieved node texts before feeding into LlamaIndex query engines.",
    description: "Integrate sentence-level prompt context reduction into LlamaIndex index retrievers and synthesized responses.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim llama-index-core",
    },
    architectureFlow: [
      "1. LlamaIndex Retriever queries vector store for top-K nodes.",
      "2. LLMSlim processes node text content with query-aware compression.",
      "3. Dense context passed to ResponseSynthesizer.",
    ],
    codeExample: {
      language: "python",
      filename: "llamaindex_llmslim.py",
      code: `from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llmslim import compress_documents

# Ingest documents and initialize index
documents = SimpleDirectoryReader("./data").load_data()
index = VectorStoreIndex.from_documents(documents)

# Custom retrieval wrapper with LLMSlim pruning
retriever = index.as_retriever(similarity_top_k=5)
nodes = retriever.retrieve("What is total operating expenditure?")

node_texts = [n.get_content() for n in nodes]
compressed_nodes = compress_documents(node_texts, query="operating expenditure", target_ratio=0.35)

print(f"Compressed {len(node_texts)} nodes to high-density context payload.")`,
    },
    deploymentGuide: "Wrap retriever node contents with compress_documents() prior to calling response synthesis engines.",
    optimizationTips: [
      "Use compress_documents(query=...) to rank sentences directly against the query string.",
    ],
    benchmarks: [
      { metric: "RAG Node Text Volume", uncompressed: "7,500 tokens", compressed: "2,625 tokens", impact: "65% Token Reduction" },
    ],
    faqs: [
      {
        question: "Does LLMSlim preserve LlamaIndex node metadata?",
        answer: "LLMSlim processes node string content while maintaining your underlying NodeWithScore objects.",
      },
    ],
    troubleshooting: [
      {
        issue: "Empty string returned from node text processing.",
        solution: "Verify node.get_content() returns valid string text prior to calling compression functions.",
      },
    ],
    iconKey: "llamaindex",
  },

  crewai: {
    slug: "crewai",
    name: "CrewAI",
    category: "Framework",
    badgeText: "Multi-Agent Swarm Efficiency",
    tagline: "Prevent multi-agent conversation history context blowup in CrewAI swarms.",
    description: "Compress agent-to-agent task outputs and state memory in CrewAI multi-agent workflows.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim crewai",
    },
    architectureFlow: [
      "1. Worker agent completes intermediate task and returns result.",
      "2. LLMSlim prunes verbose output before appending to shared Crew state.",
      "3. Manager agent receives token-dense task context.",
    ],
    codeExample: {
      language: "python",
      filename: "crewai_llmslim.py",
      code: `from crewai import Agent, Task, Crew
from llmslim import compress

def slim_task_output_callback(output):
    # Compress intermediate agent output before passing to downstream agents
    raw_text = str(output.raw)
    compressed_text = compress(raw_text, target_ratio=0.4).compressed_text
    print(f"[LLMSlim] Compressed task output by 60%")
    return compressed_text

researcher = Agent(
    role="Market Analyst",
    goal="Gather financial metrics",
    backstory="Senior enterprise analyst",
    verbose=True
)

task = Task(
    description="Analyze 2026 enterprise software market trends.",
    agent=researcher,
    callback=slim_task_output_callback
)`,
    },
    deploymentGuide: "Use LLMSlim inside CrewAI task callbacks to intercept and prune intermediate agent outputs.",
    optimizationTips: [
      "Compressing intermediate agent outputs prevents context accumulation across multi-step execution graphs.",
    ],
    benchmarks: [
      { metric: "Inter-Agent State Volume", uncompressed: "12,000 tokens", compressed: "4,800 tokens", impact: "60% Memory Reduction" },
    ],
    faqs: [
      {
        question: "Can I use LLMSlim with CrewAI task callbacks?",
        answer: "Yes. Task callbacks accept custom Python processing functions.",
      },
    ],
    troubleshooting: [
      {
        issue: "Crew execution stalls on callback return.",
        solution: "Ensure callback function returns a clean string object.",
      },
    ],
    iconKey: "crewai",
  },

  "vercel-ai-sdk": {
    slug: "vercel-ai-sdk",
    name: "Vercel AI SDK",
    category: "Framework",
    badgeText: "Next.js & Node.js Edge Ready",
    tagline: "Compress prompt payloads in Next.js Server Actions and Route Handlers.",
    description: "Integrate client/server-side prompt optimization into Next.js and Vercel AI SDK streams using @llmslim/core.",
    installation: {
      packageManager: "npm",
      command: "npm install @llmslim/core ai @ai-sdk/openai",
    },
    architectureFlow: [
      "1. User submits prompt payload to Next.js Route Handler.",
      "2. @llmslim/core compresses text on Vercel Serverless / Edge runtime.",
      "3. Pass compressed context into generateText() or streamText().",
    ],
    codeExample: {
      language: "typescript",
      filename: "app/api/chat/route.ts",
      code: `import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";
import { compress } from "@llmslim/core";

export async function POST(req: Request) {
  const { prompt } = await req.json();

  // Compress input prompt on Vercel Serverless / Edge execution environment
  const slim = compress(prompt, { targetRatio: 0.5 });

  const { text } = await generateText({
    model: openai("gpt-4o"),
    prompt: slim.compressedText,
  });

  return Response.json({ text, savings: slim.savingsPercent });
}`,
    },
    deploymentGuide: "Import @llmslim/core directly into Next.js App Router Route Handlers or Server Actions.",
    optimizationTips: [
      "Execute @llmslim/core synchronously inside Edge functions for sub-10ms prompt compression.",
    ],
    benchmarks: [
      { metric: "Next.js Route Payload", uncompressed: "3,500 tokens", compressed: "1,750 tokens", impact: "50% Token Reduction" },
    ],
    faqs: [
      {
        question: "Is @llmslim/core compatible with Next.js App Router and Edge Runtime?",
        answer: "Yes. @llmslim/core uses zero native C bindings and runs natively on Vercel Edge.",
      },
    ],
    troubleshooting: [
      {
        issue: "Module not found: @llmslim/core.",
        solution: "Run npm install @llmslim/core in your Next.js project directory.",
      },
    ],
    iconKey: "vercel",
  },

  mastra: {
    slug: "mastra",
    name: "Mastra",
    category: "Framework",
    badgeText: "TypeScript Agent Framework",
    tagline: "Optimize prompt contexts inside Mastra TypeScript workflow tools.",
    description: "Compress tool inputs, agent system instructions, and RAG contexts inside Mastra AI applications.",
    installation: {
      packageManager: "npm",
      command: "npm install @llmslim/core @mastra/core",
    },
    architectureFlow: [
      "1. Mastra workflow step fetches raw unstructured context.",
      "2. Execute @llmslim/core compress() inside step handler.",
      "3. Pass compressed string payload into Mastra Agent execution.",
    ],
    codeExample: {
      language: "typescript",
      filename: "mastra-workflow.ts",
      code: `import { Agent } from "@mastra/core";
import { compress } from "@llmslim/core";

const agent = new Agent({
  name: "ResearchAgent",
  instructions: "You extract enterprise data insights.",
  model: { provider: "OPEN_AI", name: "gpt-4o" },
});

export async function executeTask(rawContext: string, query: string) {
  // Compress input context before passing to Mastra Agent
  const slim = compress(rawContext, { targetRatio: 0.4 });
  
  const response = await agent.generate([
    { role: "user", content: \`Context:\\n\${slim.compressedText}\\n\\nQuery: \${query}\` }
  ]);
  
  return response.text;
}`,
    },
    deploymentGuide: "Import @llmslim/core in Mastra workflows, tools, and custom step execution functions.",
    optimizationTips: [
      "Pre-compress document contexts in workflow step handlers before agent generation steps.",
    ],
    benchmarks: [
      { metric: "Mastra Agent Payload", uncompressed: "4,000 tokens", compressed: "1,600 tokens", impact: "60% Billed Token Reduction" },
    ],
    faqs: [
      {
        question: "Can @llmslim/core be used inside Mastra tool definitions?",
        answer: "Yes. Simply invoke compress() inside your tool execute() block.",
      },
    ],
    troubleshooting: [
      {
        issue: "TypeScript build error on compress import.",
        solution: "Ensure tsconfig.json moduleResolution is set to 'bundler' or 'node16'.",
      },
    ],
    iconKey: "mastra",
  },

  fastapi: {
    slug: "fastapi",
    name: "FastAPI",
    category: "Backend Services",
    badgeText: "Python Microservice Gateway",
    tagline: "Deploy a high-throughput context compression reverse proxy gateway.",
    description: "Build an enterprise reverse proxy middleware using FastAPI and LLMSlim to intercept and compress API payloads at 100% reliability.",
    installation: {
      packageManager: "pip",
      command: "pip install llmslim fastapi uvicorn httpx",
    },
    architectureFlow: [
      "1. Client sends chat completion POST request to FastAPI gateway.",
      "2. Middleware inspects message tokens; applies LLMSlim if length > threshold.",
      "3. Gateway proxies token-dense payload to upstream OpenAI/Anthropic provider.",
    ],
    codeExample: {
      language: "python",
      filename: "gateway_server.py",
      code: `from fastapi import FastAPI, Request, Response
import httpx
from llmslim import compress

app = FastAPI()
client = httpx.AsyncClient()

@app.post("/v1/chat/completions")
async def proxy_chat(request: Request):
    payload = await request.json()
    
    # Intercept and compress prompt contents
    for msg in payload.get("messages", []):
        if len(msg.get("content", "")) > 500:
            msg["content"] = compress(msg["content"], target_ratio=0.5).compressed_text
            
    # Forward payload to upstream model provider
    res = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=dict(request.headers))
    return Response(content=res.content, status_code=res.status_code, headers=dict(res.headers))`,
    },
    deploymentGuide: "Run FastAPI with Uvicorn or Gunicorn inside Docker container clusters on Kubernetes / AWS ECS.",
    optimizationTips: [
      "Deploy with gunicorn -w 4 -k uvicorn.workers.UvicornWorker for high concurrent throughput.",
      "Set an explicit minimum token threshold before applying compression to skip short queries."
    ],
    benchmarks: [
      { metric: "Gateway Payload Throughput", uncompressed: "Uncompressed Payloads", compressed: "50% Token Reduced Payloads", impact: "Sub-30ms Proxy Overhead" },
    ],
    faqs: [
      {
        question: "Does LLMSlim introduce asynchronous blocking in FastAPI?",
        answer: "No. Core LLMSlim CPU compression finishes in under 30ms, running synchronously within route handlers.",
      },
    ],
    troubleshooting: [
      {
        issue: "Gateway timeout on high concurrency.",
        solution: "Increase Uvicorn worker count or deploy behind an NGINX / Envoy load balancer.",
      },
    ],
    iconKey: "fastapi",
  },
};
