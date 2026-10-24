# Examples

Run each from the repository root. The examples under "Memory and context" run offline with no API key (fake or
test models stand in for the LLM), and CI runs them: `tests/test_examples.py`, and `npm test` for the TypeScript
one. Each of their folders has a README with its real output.

## Memory and context, start here

| Example | What it shows | Needs |
| :--- | :--- | :--- |
| [claude-code-memory](claude-code-memory/) | Claude Code setup, and a plain MCP client that calls `remember` and `recall` on `llmslim mcp` across two sessions | `llmslim[mcp]`, Python 3.10+ |
| [langchain-agent-memory](langchain-agent-memory/) | A LangChain 1.x agent with memory tools and `LLMSlimToolOutputMiddleware` | `llmslim[langchain-agents]`, Python 3.10+ |
| [pydantic-ai-memory](pydantic-ai-memory/) | A Pydantic AI agent with memory tools and `llmslim_history_processor` | `llmslim[pydantic-ai]`, Python 3.10+ |
| [fit-context-big-logs](fit-context-big-logs/) | A long build log fitted into a token budget, keeping the failure | base install |
| [typescript-client](typescript-client/) | The `llmslim` npm client storing, recalling and fitting text through `llmslim serve` | Node 18+, `llmslim[server]` |
| [memory_quickstart.py](memory_quickstart.py) | `llmslim.memory` on a month of chat in SQLite | base install |

## Compression and planning

| Example | What it shows |
| :--- | :--- |
| [chat_prompt_example.py](chat_prompt_example.py) | Compressing chat histories before sending them to a model |
| [long_document_example.py](long_document_example.py) | Compressing long documents |
| [rag_pipeline_example.py](rag_pipeline_example.py) | Query-aware compression for RAG |
| [adaptive_context_planner.py](adaptive_context_planner.py) | The Adaptive Context Planner, offline |
| [mixed_agent_context.py](mixed_agent_context.py) | One plan for chat, RAG, memory and tool schemas, offline |
| [agent_context_runtime.py](agent_context_runtime.py) | `ContextRuntime` on every model-context path of a custom agent |
| [openai_agents_context_runtime.py](openai_agents_context_runtime.py) | The OpenAI Agents SDK model-input hook |
| [rewrite_example.py](rewrite_example.py), [custom_provider_example.py](custom_provider_example.py) | Rewrite and hybrid strategies with your own provider |

## Integrations that need a service or an API key

| Example | What it shows |
| :--- | :--- |
| [gemini_context_example.py](gemini_context_example.py), [gemini_context_eval](gemini_context_eval/) | Gemini with LLMSlim's context runtime |
| [sarvam_chat_planning.py](sarvam_chat_planning.py), [sarvam_voice_agent.py](sarvam_voice_agent.py) | Sarvam chat and voice (`llmslim[sarvam]`) |
| [web_search_context.py](web_search_context.py) | Exa web search results as context (`llmslim[exa]`) |
| [zoho_crm_context.py](zoho_crm_context.py), [zoho_workdrive_context.py](zoho_workdrive_context.py) | Zoho CRM and WorkDrive (`llmslim[zoho]`) |
| [mongodb_memory.py](mongodb_memory.py), [neo4j_memory.py](neo4j_memory.py) | Memory on MongoDB and Neo4j |
