# API stability

From 1.0.0, LLMSlim follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for the public API on this
page. Until then, 0.x minor releases may still make breaking changes, and the CHANGELOG lists each one. The surface
below is the one 1.0 will freeze.

- **What is public:** the modules listed below, and in each one only the names in its `__all__`.
- **The record:** [`tests/fixtures/public_api.json`](../tests/fixtures/public_api.json) holds every public name with
  its signature, plus the command line, the `llmslim serve` routes, the `llmslim mcp` tools, the entry points and the
  environment variables. A test fails when any of them changes (see [Changing the API](#changing-the-api)).

## What a version number promises

From 1.0.0:

| Release | May contain |
|---|---|
| **Major** (2.0.0) | Removals and incompatible changes to the stable API. Each one was deprecated first. |
| **Minor** (1.1.0) | New features and additive changes. New deprecations. Changes to experimental API. |
| **Patch** (1.0.1) | Bug fixes only. No API changes and no new deprecations. |

**A breaking change** is anything that can stop correct code from working:
- removing or renaming a public module, name, method, attribute, parameter, command, flag, route, MCP tool or
  environment variable;
- adding a required parameter, or making an optional one required;
- moving a positional parameter, or narrowing what a parameter accepts;
- changing a return type or a response field incompatibly;
- changing what a flag or an option means.

**These are not breaking changes:**
- adding a module, a name, a keyword parameter with a default, a dataclass field with a default, a command, a flag,
  a route, an MCP tool, or an optional MCP tool input;
- adding fields to a JSON response or a result object;
- **output content:** which sentences, turns or documents are kept, scores, token counts, the text `recall`
  returns, and the wording of messages, help text and MCP tool descriptions. A minor release may change output
  content to improve results. A patch release changes it only to fix a bug. Within one release, the same input and
  options give the same output;
- raising the minimum version of a dependency or of an optional framework (see [Integrations](#integrations));
- dropping a Python version that has reached its end of life, in a minor release that the CHANGELOG announces.

## Deprecation policy

1. **Deprecate in a minor release.** The old name keeps working and raises a `DeprecationWarning` that names its
   replacement and the release that removes it, for example: `llmslim.squeeze is deprecated since llmslim 1.2 and
   will be removed in 2.0; use llmslim.fit instead.`
2. **Keep it for at least two minor releases and at least 90 days**, whichever is longer.
3. **Remove it only in a major release.**
4. **Announce each step** under `Deprecated` and then `Removed` in the CHANGELOG.

Python shows `DeprecationWarning` by default only in `__main__` and in test runners. To see them elsewhere, run with
`python -W default::DeprecationWarning` or set `PYTHONWARNINGS=default::DeprecationWarning`.

The same policy covers command-line flags, HTTP routes and fields, MCP tools and their inputs, and environment
variables. A deprecated flag or variable still works and prints a warning to stderr. A deprecated HTTP route or field
still answers, and the change is listed in the CHANGELOG and [SERVER.md](SERVER.md). A deprecated MCP tool or input
is still accepted.

Contributors deprecate with `llmslim._deprecation`, which checks that the removal is in a later major release:

```python
from llmslim._deprecation import Alias, deprecated, deprecated_attributes, renamed_parameter

@deprecated(since="1.2", removed_in="2.0", replacement="llmslim.fit")
def squeeze(text: str) -> str: ...

@renamed_parameter("ratio", "target_ratio", since="1.2", removed_in="2.0")
def compress(text: str, target_ratio: float = 0.5) -> CompressionResult: ...

# A moved or renamed module attribute:
__getattr__ = deprecated_attributes(
    __name__, {"OldName": Alias(NewName, since="1.2", removed_in="2.0", replacement="NewName")}
)
```

## Stable

These modules are public. In each one, the names in `__all__` are stable, except those listed under
[Experimental](#experimental). For a class, the promise covers its constructor, its public methods and properties,
and the attributes declared on the class (such as dataclass fields).

| Module | What it holds |
|---|---|
| `llmslim` | Compression, context planning, the agent context runtime, cache planning, token counting and the rewrite engine |
| `llmslim.memory` | `Memory`, its stores and result types |
| `llmslim.memory.compat` | `Mem0Memory`, the Mem0-compatible facade |
| `llmslim.planning` | The adaptive context planner and its data model |
| `llmslim.context` | Context sources and stores |
| `llmslim.tokens` | Token counting |
| `llmslim.tools` | Tool-schema contracts: canonical JSON, fingerprints, provider adapters, inspection |
| `llmslim.mcp` | MCP catalog ingestion and contract-safe catalog planning |
| `llmslim.mcp_server` | `build_server`, `fit_text` and the `llmslim mcp` entry point |
| `llmslim.server` | `create_app` and the `llmslim serve` entry point (`ChatUpstream` and the `chat` argument of `create_app` are [experimental](#experimental)) |

`llmslim` also exports three helpers for integrators that build their own context or caching on top of the planner:
`render_context_item` renders an item in its provenance boundary exactly as the planner does, `rendered_token_count`
counts the tokens of that rendering, and `compile_cache_plan` builds the cache plan for a prepared request.

### Integrations

| Module | Integration |
|---|---|
| `llmslim.integrations.langchain` | LangChain document compressor |
| `llmslim.integrations.langchain_agents` | LangChain 1.x agent middleware |
| `llmslim.integrations.llama_index` | LlamaIndex node postprocessor |
| `llmslim.integrations.haystack` | Haystack component |
| `llmslim.integrations.openai_agents` | OpenAI Agents SDK tool bridge |
| `llmslim.integrations.pydantic_ai` | Pydantic AI history processor |
| `llmslim.integrations.gptme` | gptme context provider |
| `llmslim.integrations.hermes` | Hermes Agent context engine |
| `llmslim.integrations.mongodb` | MongoDB context source and store |
| `llmslim.integrations.neo4j` | Neo4j temporal memory store |
| `llmslim.integrations.sarvam` | Sarvam chat, language tools and documents (also `llmslim.integrations.sarvam_text` and `llmslim.integrations.sarvam_documents`) |
| `llmslim.integrations.zoho` | Zoho CRM and WorkDrive context sources |
| `llmslim.integrations.exa` | Exa web search context source |
| `llmslim.integrations.web_search` | `WebSearchSource`, `WebSearchResult` and their errors, for web-search sources |

Each integration module exports its documented classes and functions, the types they return and the errors they
raise. Its constants, default limits and helper functions are internal, even when they are importable.

The API of each integration module is stable. The framework versions it supports follow the framework: when a
framework or vendor SDK changes incompatibly, a minor release may raise the minimum version in the extra, or cap it
until LLMSlim supports the new one. The CHANGELOG says so.

The entry points that gptme and Hermes Agent discover (`gptme.context_providers`, `gptme.plugins` and
`hermes_agent.plugins`, each named `llmslim`) and their configuration keys are stable too.

## Experimental

Experimental API is importable and documented, but a minor release may change or remove it. The CHANGELOG says so
each time, and a deprecation period is given when it is practical.

| What | Why it is experimental |
|---|---|
| `llmslim.proxy`, and the `llmslim proxy` and `llmslim wrap` commands | They sit on the Anthropic Messages wire format and on Claude Code's traffic, which change without notice, and they are new in 0.11. |
| The chat endpoint of `llmslim serve`: `POST /v1/chat/completions` and `GET /v1/models`, their `X-LLMSlim-*` request and response headers, the `--upstream-url`, `--memory-budget`, `--store-only` and `--upstream-timeout` flags, `llmslim.server.ChatUpstream` and the `chat` argument of `create_app` | It is new, it sits on the OpenAI chat-completions format and on how voice platforms call a custom LLM, and where recalled memory goes in a request may change once it is measured in real use. |
| `llmslim.tool_retrieval` and `llmslim.semantic_retrieval` | Research-only tool retrieval, documented as such since 0.4. |
| In `llmslim.tools`: `rank_tools`, `select_tools`, `plan_tool_context`, `RankedTool`, `ToolSelection`, `ToolContextPlan` and `LazyToolRegistry` | Ranking and showing a model fewer tools is research-only. The contract utilities in the same module are stable. |
| `PlanMode.SELECTIVE`, in `llmslim.mcp` and through `plan_mcp_context` | Research-only; it already needs `experimental=True`. The other modes are stable. |
| `llmslim.TransformersKVSession` | It works with Transformers' internal KV cache classes, which change between Transformers releases. |

Making experimental API stable is a CHANGELOG entry in a minor release.

## Internal

Everything else is internal and may change in any release:
- every module or name whose path has a part starting with `_`, such as `llmslim._deprecation` or
  `llmslim.memory._core`;
- names a public module doesn't list in `__all__`, even without an underscore;
- **implementation modules**, whose public names are re-exported by a module above: `llmslim.adapters`,
  `llmslim.analysis`, `llmslim.cache`, `llmslim.cache_adapters`, `llmslim.chunking`, `llmslim.context_graph`,
  `llmslim.context_policy`, `llmslim.core`, `llmslim.cost`, `llmslim.embeddings`, `llmslim.envelope`,
  `llmslim.focus`, `llmslim.modes`, `llmslim.optimizers`, `llmslim.pipelines`, `llmslim.quality`, `llmslim.ranking`,
  `llmslim.rerank`, `llmslim.rewrite`, `llmslim.runtime`, `llmslim.self_hosted`, `llmslim.tokenization`, the
  modules inside `llmslim.planning`, `llmslim.memory.stores` and `llmslim.memory.postgres`. Import their names from
  `llmslim`, `llmslim.planning` or `llmslim.memory`. A name may move between implementation modules in a minor
  release;
- `llmslim.cli` as a Python module (the command line itself is covered below, including `python -m llmslim.cli`);
- `llmslim.hosted`, the controls of the hosted Sarvam demo;
- `llmslim.integrations.gptme_plugin`, which gptme loads through its entry point;
- the modules inside `llmslim.proxy`.

## Command line, HTTP, MCP and environment

**Command line.** The commands `llmslim` (compress), `llmslim context`, `llmslim plan`, `llmslim tools`,
`llmslim mcp` and `llmslim serve`, and their flags and arguments, are stable. `--json` output may gain fields but
keeps the ones it has. Human-readable output may change. `llmslim proxy` and `llmslim wrap` are experimental, and
so are the chat endpoint's flags of `llmslim serve` (`--upstream-url`, `--memory-budget`, `--store-only`,
`--upstream-timeout`).

**HTTP (`llmslim serve`).** The routes and methods (`/healthz` and everything under `/v1` except the experimental
chat endpoint, `/v1/chat/completions` and `/v1/models`), the request fields, the
response fields and the error `code` values in [SERVER.md](SERVER.md) are stable. A minor release may add routes,
optional request fields and response fields. An incompatible change would come under `/v2`, with `/v1` kept until
the next major release.

**MCP (`llmslim mcp`).** The tool names (`remember`, `recall`, `list_memories`, `forget`, `fit_context`), their input
and output schemas (names, types and which inputs are required) and their read-only, destructive and idempotent hints
are stable. A minor release may add tools and optional inputs. Tool descriptions and the server instructions are
prompts for models: they may change in any minor release to make models use the tools better.

**Stored memory.** A SQLite file or Postgres table written by a 1.x release opens in every later 1.x release. If a
release changes the schema, it upgrades the store when it opens it, and the CHANGELOG says so. An older release
refuses a store with a newer schema rather than misreading it.

**Environment variables.**

| Variable | Read by | Status |
|---|---|---|
| `LLMSLIM_HOST`, `LLMSLIM_PORT`, `LLMSLIM_API_KEYS`, `LLMSLIM_ALLOWED_HOSTS` | `llmslim serve` | Stable |
| `LLMSLIM_MEMORY_DB` | `llmslim serve`, `llmslim mcp` | Stable |
| `LLMSLIM_USER_ID`, `LLMSLIM_AGENT_ID` | `llmslim mcp` | Stable |
| `LLMSLIM_RERANK_MODEL` | the cross-encoder reranker | Stable |
| `LLMSLIM_PROXY_DB`, `LLMSLIM_PROXY_UPSTREAM` | `llmslim proxy`, `llmslim wrap` | Experimental |
| `LLMSLIM_UPSTREAM_URL`, `LLMSLIM_UPSTREAM_API_KEY` | the chat endpoint of `llmslim serve` | Experimental |
| `LLMSLIM_<PREFIX>_REQUESTS_PER_MINUTE`, `_MAX_REQUESTS`, `_MAX_UNITS` | usage guards of the vendor integrations, with `<PREFIX>` one of `SARVAM_CHAT`, `SARVAM_TEXT`, `SARVAM_DOCUMENT`, `EXA` and `NEO4J` | Stable |

Each integration's `from_env()` reads one credential variable, named by its `env_var` parameter (for example
`SARVAM_API_KEY`, `EXA_API_KEY`, `MONGODB_URI`); those defaults are stable as part of the signatures. The
`LLMSLIM_HOSTED_SARVAM_*` and `LLMSLIM_SARVAM_*` variables configure the hosted demo and are internal.

## Changing the API

`tests/test_public_api.py` compares the live API with the snapshot and fails on any difference, naming what was
added, removed or changed. When the change is intended:

1. run `python scripts/public_api.py --write` in an environment with `pip install -e ".[all,dev]"`, and commit
   `tests/fixtures/public_api.json`;
2. add a CHANGELOG entry under `[Unreleased]`;
3. if a stable name is removed or changed incompatibly, deprecate it instead (above). After 1.0, removals wait for a
   major release.

A new module must be listed as public or internal in `scripts/public_api.py` and on this page. gptme and Hermes Agent
can't be installed with the `all` extra, so their entries are updated from an environment that has them:
`python scripts/public_api.py --write --module llmslim.integrations.gptme`.
