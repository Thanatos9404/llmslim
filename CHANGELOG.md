# Changelog

All notable changes to `llmslim` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Breaking
- **Python 3.10 or newer is required.** Python 3.9 is no longer supported: it reached end of life in October 2025,
  and the MCP server and most framework extras already needed 3.10. `requires-python` is `>=3.10`, CI no longer runs
  on 3.9, and Ruff and mypy check against 3.10. On Python 3.9, pip keeps installing 0.12.0. No public API changes.
  - The extras lose their `python_version >= '3.10'` markers, and `mongodb` drops a dead pin for Python 3.8.

### Added
- **`llmslim mcp --transport http` shares one memory across machines.** The MCP server also speaks MCP's Streamable
  HTTP transport, so the clients on a laptop, a desktop and a CI runner can use one memory. It follows
  `llmslim serve`:
  - every request needs `Authorization: Bearer <key>` (`--api-key`, `LLMSLIM_MCP_API_KEYS`), compared in constant
    time against every key. `llmslim serve`'s `LLMSLIM_API_KEYS` reach every user, so they are not read, and a key
    in both gets a warning. A missing or wrong key is a 401 with `WWW-Authenticate: Bearer`, and the key is never
    logged or echoed. Without a key, the server refuses any interface but loopback;
  - without a key, it answers only requests addressed to this machine by name that no other web page sent, so DNS
    rebinding and cross-site requests get a 403. `--allowed-host` and `LLMSLIM_ALLOWED_HOSTS` add names, or pin them
    on a server with keys;
  - one server holds one scope, the `--user-id` and `--agent-id` it was started with, and every key reaches that
    scope and nothing else. No tool takes a user or agent id, as over stdio. For several people, run one server
    each; they can share a database;
  - it is stateless and answers in JSON, so it runs behind any reverse proxy or load balancer, and a restart doesn't
    break connected clients. Bodies are capped at 1 MB (413), malformed JSON-RPC is a 400, `GET /healthz` answers
    without a key, and requests still running at shutdown get 10 seconds to finish;
  - `--host` (`LLMSLIM_MCP_HOST`, default 127.0.0.1), `--port` (`LLMSLIM_MCP_PORT`, default 8000) and `--path`
    (default `/mcp`). The startup line prints the URL and the scope, never a key.

  stdio stays the default and is unchanged; the HTTP options are refused with it. `docs/MCP.md` shows the setup
  behind TLS, the client configuration for Claude Code, VS Code and Cursor, and who can read whose memory. The HTTP
  transport is experimental in its first release (`docs/API_STABILITY.md`).
- **An OpenAI-compatible chat endpoint in `llmslim serve` that adds memory to any client (experimental).** Start the
  server with `--upstream-url` (an OpenAI-compatible base URL) and the upstream's key in `LLMSLIM_UPSTREAM_API_KEY`,
  and `POST /v1/chat/completions` works with any client that takes an OpenAI base URL: the OpenAI SDKs, and voice
  platforms with a custom LLM setting. `docs/SERVER.md` has curl, SDK and voice-platform examples.
  - **Scope** comes from `X-LLMSlim-User-Id` (or the request's `user` field), `X-LLMSlim-Agent-Id` and
    `X-LLMSlim-Session-Id`. Without a user or agent id, memory is not touched and the request passes through.
  - **Recall:** the latest user message searches the user's memory within `--memory-budget` tokens (default 1000),
    and what it finds goes in one user message just before that message, framed as data in an untrusted
    `<llmslim_context>` block. Turns the request already carries are left out. Nothing the client sent is edited or
    reordered, but the recalled message isn't in the history the client re-sends, so each request misses the prompt
    cache on its last turn. `--store-only` (or `X-LLMSlim-Memory: store-only`) keeps every request byte-identical.
  - **Storage:** after a successful answer, the new user turn and the reply's text are stored word for word, once.
    Nothing is stored when the upstream fails or a stream breaks off. When the client goes away mid-stream (a voice
    caller talking over the reply), the user turn is stored without the reply, and a retry of that request within 10
    minutes doesn't store it again.
  - **Streams** pass through chunk by chunk. The upstream connection is closed however a stream ends.
  - **Security:** the upstream is fixed by the server, so no request field or header can redirect it, and redirects
    are not followed. The client's key is never forwarded, and the upstream's key never reaches answers, errors or
    logs. Memory failures never fail the call.
  - `GET /v1/models` lists the upstream's models. The `server` extra now installs httpx.
- **`Memory.search(..., explain=True)` says why each turn was kept, cut or left out.** The context carries an
  `explanation` (`SearchExplanation`), built from what the search decided:
  - for every stored turn of the scope, those outside the time window included: its pool, `status` (`kept`,
    `clipped` or `dropped`) and `reason`, the tokens its block takes in the text and its share of the budget;
  - for every candidate a turn had (a user turn, a reply's windows, a summary's opening): its rank and score in its
    pool, its size and what became of it;
  - for each section (standing requests, preferences, conflicts): whether it is shown and why not, its cap, and
    every statement it weighed, best first;
  - the reasons are concrete: over the budget, over its pool's share, a duplicate, outside the time window, dropped
    at the exact count, cut by the last resort, and so on. `docs/MEMORY.md` lists them all.

  Each block is counted on the returned text, so with tiktoken the turns' and sections' tokens add up to the
  context's count exactly; any remainder (with the 4-characters-per-token estimate) is `unattributed_tokens`. The
  explanation names turns by id and never repeats their text. `to_dict()` gives JSON and `from_dict()` reads it back.
  With `explain` off, the default, the output is byte-for-byte what it was and no extra work is done:
  `tests/fixtures/memory_search_golden.json` pins 30 searches recorded before the change. `ExplainedTurn`,
  `ExplainedCandidate` and `ExplainedSection` are exported from `llmslim.memory` with `SearchExplanation`.
  - `llmslim serve` takes `"explain": true` on `POST /v1/memories/search` and adds `explanation` to the response.
    The `recall` tool of `llmslim mcp` and `Mem0Memory` are unchanged.
- **`llmslim import`: bring your chat history into memory in one command** (`llmslim.memory.import_history` in
  Python). It reads Claude Code transcripts (`~/.claude/projects`, the default), ChatGPT and Claude.ai data exports
  (the zip as downloaded, its folder or `conversations.json`), a Mem0 export (`get_all` output or a list of
  memories) and generic JSONL, or tells them apart with `auto`. Each message is stored verbatim under its original
  time, one session per transcript or conversation, with no model call. See `docs/IMPORT.md`.
  - **Only what was said.** User and assistant text by default. Thinking is never imported, tool calls and results
    only with `--include-tool-output`. ChatGPT conversations follow `current_node`, the thread you saw last, not the
    branches you left. Mem0 memories keep their own `user_id`, `agent_id` and `run_id`, so `Mem0Memory` filters find
    them.
  - **Idempotent.** Turn ids come from the source's message ids (or, without them, a content hash per session), so
    importing again stores only what is new. `--dry-run`, `--since`/`--until`, `--limit`, `--strict`, `--json`.
  - **Untrusted input.** JSONL is streamed line by line and `conversations.json` one conversation at a time. Files,
    records, nesting depth and turns are capped (`ImportLimits`), zip archives are read in place with zip-bomb and
    path-traversal checks, and malformed records are skipped and counted.
  - **Credentials redacted first** (best-effort): API keys, AWS keys, private key blocks, bearer tokens, passwords
    in URLs and key-like `api_key = ...` values become `[REDACTED:<kind>]` before anything is stored.
  - New in `llmslim.memory`: `import_history`, `ImportReport`, `ImportedSession`, `ImportLimits` and
    `HistoryImportError`.
- **`MongoStore` keeps memory in MongoDB** (`pip install "llmslim[mongodb]"`, PyMongo).
  - `Memory("mongodb://...")` and `mongodb+srv://` URLs (Atlas) use it, and so do `llmslim serve --db`,
    `llmslim mcp --db` and `llmslim import --db`. Several processes or machines can share one memory on MongoDB 6.0+,
    standalone or as a replica set.
  - It takes a URL (it opens and closes its own client), a `MongoClient` or a `Database`. The database is
    `database=...`, else the URL's, else `llmslim`; `admin`, `local` and `config` are refused. One collection holds the turns
    (`llmslim_memory`, or `collection=...`).
  - It creates an index per scope field and a unique index on the order number when it opens, and creating them
    again changes nothing, so several processes can start at once. A collection written by a newer llmslim is
    refused.
  - Turns come back in the same order as in every other store, ties included: each batch takes its order numbers
    in one atomic update. On a replica set or sharded cluster each batch is one transaction, so it is stored whole
    or not at all, even if the connection drops partway. On a standalone server, which has no transactions, a batch
    with a duplicate id is undone and leaves nothing behind.
  - Times are stored as UTC dates and also in microseconds, so they come back exactly, although a BSON date keeps
    only milliseconds.
  - Caller values are data, never operators: ids and scope values must be strings and are matched with `$eq`, and
    metadata whose keys MongoDB would read as operators or paths (`$where`, `a.b`) is stored as JSON text and comes
    back as given. Lone surrogates are refused before anything is stored, as in `SQLiteStore`, and so is a turn over
    16 MB.
  - Errors raised while opening the store have the URL's password and secret options removed, and `repr` shows
    only the database and collection.
  - `mongodb+srv://` needs nothing beyond the extra: PyMongo requires dnspython, which resolves it. Tests answer the
    SRV and TXT lookups locally, with no network, and connect through them to the test server.
  - CI runs the whole memory suite against MongoDB 6.0, 7.0 and 8.2, standalone with authentication and as a
    one-node replica set, and once more with exactly PyMongo 4.13.0, the extra's floor. A separate job builds the
    wheel, installs it with `[mongodb,server,mcp]` in a clean environment, and runs the real commands against
    MongoDB 6.0 and 8.2, standalone with authentication and as a replica set: `llmslim serve` (add, search,
    `explain`, list, update, delete, two servers on one memory), `llmslim mcp --transport http` with an MCP client,
    `llmslim import` of every format (MongoDB stores what SQLite stores), the chat endpoint against a stand-in
    upstream, a 20,000-turn import into the replica set, and a restart and a stop of MongoDB under running servers.
    No output, answer or error shows the URL's password. Guide: `docs/MEMORY.md`.
- **A generated API reference on the site.** `scripts/api_reference.py` reads the signatures, type annotations and
  docstrings of `llmslim` and `llmslim.memory` with griffe and writes them as two documentation pages
  (`/docs/api-llmslim` and `/docs/api-llmslim-memory`). Each public name gets a summary and a typed stub with its
  docstring. `tests/test_api_reference.py` fails when the pages are out of date with the source, when a public name
  has no docstring, or when a public function or method has an unannotated parameter or return type.
- CI checks that the wheel ships `py.typed`.
- **A public API contract for 1.0** in `docs/API_STABILITY.md`:
  - what is stable, experimental and internal, and the semantic-versioning promise from 1.0.0;
  - the deprecation policy: a `DeprecationWarning` that names the replacement and the removal release, at least two
    minor releases and 90 days, and removal only in a major release;
  - the same rules for the command line, the `llmslim serve` routes, the `llmslim mcp` tools, stored memory and
    environment variables.
  - **Experimental:** `llmslim.proxy` with `llmslim proxy` and `llmslim wrap`, `llmslim.tool_retrieval`,
    `llmslim.semantic_retrieval`, tool ranking and selection in `llmslim.tools`, `PlanMode.SELECTIVE` and
    `TransformersKVSession`.
  - **Internal:** implementation modules such as `llmslim.core` and `llmslim.runtime`. Import their names from
    `llmslim`.
- **A snapshot of the public API.** `tests/fixtures/public_api.json` records every public name and signature, the
  command-line flags, the `llmslim serve` routes, the `llmslim mcp` tools and schemas, the entry points and the
  `LLMSLIM_*` variables. `tests/test_public_api.py` fails on any difference. `python scripts/public_api.py --write`
  regenerates it.
- `llmslim._deprecation`, a helper that deprecates functions, classes, keyword arguments and module attributes.
- **Rendering and cache-plan helpers for integrators**, now exported from `llmslim` with docstrings and full type
  annotations: `render_context_item` (an item in its provenance boundary, as the planner renders it),
  `rendered_token_count` (the tokens of that rendering) and `compile_cache_plan` (the cache plan of a prepared
  request).
- **Signed releases with an SBOM.** For each release, the release workflow now:
  - attests every wheel and sdist with SLSA build provenance and an SBOM attestation (GitHub artifact attestations,
    signed through Sigstore);
  - writes `llmslim-<version>.cdx.json`, a CycloneDX SBOM of the runtime dependencies, and attaches it to the GitHub
    release;
  - asks for PyPI attestations explicitly. Trusted publishing already uploaded them by default.

  `SECURITY.md` shows how to verify each one with `gh attestation verify` and `pypi-attestations`.
- The build and SBOM steps also run on pull requests that touch packaging, without attesting or publishing.
- **Mastra memory in the TypeScript client** (`llmslim/mastra`, on npm as `llmslim` 0.2.0). With `@mastra/core`
  1.29.1 or newer (earlier releases sometimes pass an output processor the reply twice, so it would be saved twice):
  - `memoryTools()` gives an agent the same `recall_memory` and `remember` tools as `llmslim/ai-sdk`;
  - `memoryProcessor()` is an output processor that saves the latest user message and the reply, word for word, once
    per `generate()` or `stream()`. It saves nothing when a guardrail's tripwire stopped the run, when the run was
    aborted or failed, or while it waits for a tool approval, and a failed save never fails the response.
  - The scope is fixed ids or a function of Mastra's request context, so one agent serves many users. It never comes
    from the model, and a request without a user reads and saves nothing.
  - Neither changes the prompt, so prompt caches and Claude's preserved thinking stay valid. There is no input
    processor that injects memory.
  - CI runs the tests against a real `llmslim serve` and against the oldest supported `@mastra/core` (1.29.1), with a
    test that saves the same reply 50 times, and imports the packed package without its optional peers.

### Changed
- **`Memory.search` shows a session's date once: `date_format` now defaults to `None`.** When a long history is
  selected from, the first kept turn of a session shows its full stamp, and so does a later turn whose time differs
  from the one shown last in its session. Any other kept turn used to repeat the date, `[2026-10-17] assistant: ...`.
  It now shows `assistant: ...` alone, under the stamp above it. Pass `date_format="%Y-%m-%d"` to get the old labels
  back; the output is then byte for byte what 0.12 and the previous main returned. A history that fits the budget
  whole still shows the full stamp on every turn.
  - **Why:** the repeated date was most of each kept turn's label. Labels took 21-22% of a LoCoMo context and 11-15%
    of a LongMemEval one; without the repeated date they take 9-11% and 6-9%, so more turns fit.
  - **Measured on development data** (no model; share of questions whose labelled evidence is all in the context, at
    2,500 and 10,000 tokens): LoCoMo goes from 78.7% to 80.0% and from 92.2% to 93.5% (+1.3 points at both, 95%
    interval 0.0 to +3.0; 3 questions up, none down). LongMemEval does not change: 89.9% and 95.1%, and the short
    answer is present as often. This is not a claimed recall improvement: the LoCoMo interval touches zero, so it
    misses the pass rule set before measuring. It ships for the label cost.
  - **Stored text still can't pass for a label.** Where a label can be the role alone, a line in a code block or
    table that starts at the beginning of the line with `user:`, `assistant:`, `system:` or `tool:` is indented by
    two spaces, as a line that looks like a dated label already was. A line that already starts with whitespace is
    left as it is. With a `date_format` string, only dated lookalikes are indented, as before.
  - `tests/fixtures/memory_search_golden.json` is recorded again with the new default.
    `tests/fixtures/memory_search_golden_date_0_12.json` pins the output with `date_format="%Y-%m-%d"`: it equals the
    previous recording.
- Docstrings for the public names that had none: `PolicyPreset`, `EdgeType`, `ContextEdge`, `ContextPolicy`,
  `QualityReport`, `RuntimeSession`, `PreparedContext`, `CacheStatus`, `CacheCapabilities`, `CachePolicy`,
  `CacheSegment`, `CachePlan`, `CacheTelemetry`, `MODEL_PRICING` and `PROVIDER_CAPABILITIES`.
- **Site:** the docs sidebar gets its list of guides from the server instead of importing every guide into the
  browser.
- `llmslim.tokens`, `llmslim.mcp` and `llmslim.integrations.openai_agents` declare `__all__`. Nothing is renamed or
  removed.
- **Smaller public lists before 1.0 freezes them.** The names below leave `__all__`, so they become internal. They stay
  importable from the modules that define them.
  - `llmslim.integrations.web_search` exports `WebSearchSource`, `WebSearchResult` and their errors. Its 20 helper
    functions and limits are internal.
  - `llmslim.integrations.sarvam` keeps its documented classes and functions, the result types they return and their
    errors: 35 names, down from 42. Its guard prefixes, default limits and `sarvam_chat_cost_inr` are internal, and it
    no longer re-exports the text and document default limits and guard prefixes.
  - `llmslim.integrations.sarvam_text` and `llmslim.integrations.sarvam_documents` keep their documented names and
    result types.
  - `llmslim.server` exports `create_app` and `main`. `api_keys_from` and `is_loopback` are internal.
- `llmslim.proxy.cli` builds the `llmslim proxy stats` and `llmslim wrap` parsers in `build_stats_parser` and
  `build_wrap_parser`. The commands are unchanged.
- **A database that is down is a clean, retryable error.** When Postgres or MongoDB can't be reached (restarting, a
  network cut), `llmslim serve` answers a 503 with `"type": "store_unavailable"` and `Retry-After: 5`, and logs one
  line with the error's type; it used to answer a plain-text 500 and log a traceback. The `llmslim mcp` tools fail
  with "the memory store can't be reached right now; try again shortly". Neither shows a host, URL or driver message,
  and both work again when the database is back, without a restart. Any other failure in a `serve` route is a JSON
  500 (`"type": "server_error"`), with the traceback in the log only.
- `llmslim serve` and `llmslim mcp` exit at start with one line (`could not open the memory store: <error>`) when
  the store can't be opened, such as an unreachable database, a wrong password or a missing extra, instead of a
  traceback. The URL's password is never shown.
- **`llmslim import` writes at most 500 turns or about 4 MB at a time.** Each write is one transaction on a MongoDB
  replica set or Atlas, which MongoDB aborts after 60 seconds by default, and 500 turns of up to 100,000 characters
  each could make one 200 MB transaction. On MongoDB it also checks which turns are already stored a thousand ids
  per query instead of one query per turn, so importing again over a slow link to Atlas no longer takes a round trip
  per turn.

### Security
From a security review of 1.0's HTTP server, MCP server, proxy and the website's functions.
- **Web pages can no longer use a keyless `llmslim serve` or the proxy.** A server on 127.0.0.1 is reachable from
  any page the user opens: a cross-site "simple" POST could store a memory (a planted instruction that later reached
  the user's prompts) or start an expensive `fit`, and DNS rebinding let a page read and delete every memory,
  including the `default` user that `llmslim mcp` keeps in the same `~/.llmslim/memory.db`. A keyless `serve` and the
  proxy now answer only requests whose `Host` names this machine (`localhost`, a `*.localhost` name, 127.0.0.0/8,
  `[::1]`) and refuse with a 403 any request whose `Origin` is another site. Clients that send no `Origin` (curl, SDKs,
  agents) are not affected.
  - **Behaviour change:** a keyless server reached by another name now answers 403. Add the name with
    `--allowed-host` (repeatable; `*` for any), `LLMSLIM_ALLOWED_HOSTS` or `create_app(..., allowed_hosts=[...])`.
    Servers with API keys accept any `Host` as before, unless you pin names the same way. The proxy takes
    `--allowed-host` and `create_proxy_app(..., allowed_hosts=[...])`; with `--allow-remote` on another interface it
    accepts any name unless you set one.
- **Quadratic-time inputs.** Text that `serve`, `llmslim mcp`, the proxy and the website's Studio functions process
  could hold a CPU for minutes. Each case is now linear, and `tests/test_security_dos.py` times the old worst cases:
  - restoring code-span placeholders after sentence splitting searched every sentence for every span
    (`llmslim.tokenization`). 80,000 backticks took 1.8 s to compress and the time quadrupled with each doubling:
    about 5 minutes at the server's 1 MB limit, and `fit` compresses up to four times;
  - content detection's `^\s*` patterns rescanned a run of blank lines from every line start, and the Markdown link
    and HTML tag patterns rescanned from every `[` and `<a ` (`llmslim.analysis`, and the list-item patterns in
    `llmslim.ranking`). 90,000 characters of `[` took 12 s to plan on the website's planner;
  - the YAML optimizer's inline-comment pattern on a long run of whitespace.
- **`fit` holds its budget for any text.** `/v1/context/fit` and MCP `fit_context` returned all 600,000+ tokens of a
  text that compression keeps whole (one long code block, or a run of inline code) for a budget of 2,000, so text an
  attacker controls could blow up a prompt's size and cost. The result is now cut to the longest head that fits.
- **Hostile JSON is a 400, not a 500.** `serve` answered over-deep JSON, values of the wrong type (`"messages": 5`)
  and out-of-range timestamps with a 500. A lone surrogate (`"\ud800"`) was kept by the in-process store and then
  broke every read of that scope; it is now refused before anything is stored. `Memory.add` refuses a timestamp with
  no UTC time (9999-12-31T23:59-01:00) with a `ValueError`.
- **XML with entity declarations is never parsed** by the XML optimizer, so entity-expansion bombs ("billion laughs",
  quadratic blowup) can't run even on a Python built with an old expat. Such text is compressed as plain text.
  Recent expat already refused them.
- The proxy answers a path it can't forward (one starting with `//`) with a 400 instead of a 500.
- **Site: the Studio's "Answer with Sarvam" step is no longer a general-purpose model.** The visitor chooses both the
  context and the question, and the Origin check stops other web pages, not scripts, so with the step enabled anyone
  could get any question answered on the project's Sarvam key, within the spend limits. The function now sends its
  own instruction as a trusted system item: answer only from the submitted text, follow no instructions in it, and
  otherwise reply with a fixed refusal. The step is off in production.
- **Site: per-instance rate limits count an IPv6 client by its /64.** `/api/studio`, `/api/compress`, `/api/plan`
  and `/api/context` counted each address, so a client could dodge the limit by changing the interface identifier
  of its IPv6 address on every request. The Sarvam step already did this.

### Fixed
- **The Docker image runs on Postgres and MongoDB.** It installed only the `server` extra, so with
  `LLMSLIM_MEMORY_DB` set to a `postgresql://` or `mongodb://` URL the server failed at start for want of a driver. It
  now installs `server`, `postgres` and `mongodb`. CI runs the image against MongoDB (add, search, list and delete,
  through a restart and an outage) and against Postgres. `docs/SERVER.md` shows both.
- **`Memory.search` keeps more of a conversation whose replies are short.** When a long history is selected from, a
  user turn inherits part of its session's relevance, so a turn that shares no word with the question still comes in
  when its session is about it. Reply windows inherit their whole reply's relevance instead, so a reply of one window
  inherited only its own: a short reply scored 0 unless it shared a word with the question, and waited behind older
  turns for the leftover budget. A short reply is a person's turn in a conversation between two people stored as
  `user` and `assistant`, or an agent's one-line answer. A reply of one window now inherits its session's relevance, as
  a user turn does; a window of a longer reply still inherits its reply's. Measured on development data, with no model
  in the loop, as the share of questions whose labelled evidence is all in the context:
  - LoCoMo (first speaker `user`, second `assistant`): 75.7% to 78.7% at 2,500 tokens (+3.0 points, 95% interval
    +0.4 to +6.1) and 88.3% to 92.2% at 10,000 (+3.9, +1.3 to +7.0);
  - LongMemEval: no loss, 89.6% to 89.9% and 94.8% to 95.1%.

  This changes output content only; the API is unchanged.
- **Sarvam documents work with `sarvamai` 0.1.40.** That release renamed `doc_ai.digitise`, the call that creates and
  starts a document job, to `doc_ai.parse`, with the same arguments. `SarvamDocumentSource` and
  `AsyncSarvamDocumentSource` failed with `Sarvam request failed (AttributeError)` before sending anything; they now
  call `parse` when the SDK has it and `digitise` otherwise, so the whole supported range (0.1.34 up to 0.2) works.
  The job is still created once, with the SDK's retries off.

## [0.12.0] - 2026-10-27

### Merged from 0.11.2
- **The 0.11.2 fixes hold on the turn-level read path.** `Memory.search` ranks stored turns itself (below), so it
  does not use 0.11.2's `memory/_selection.py`, which is left out; the guarantees are kept as follows:
  - **Each turn shows its own time.** When the whole history fits, every turn carries its own stamp. When it is
    selected from, the first kept turn of a session shows its full stamp, and a later one shows its own full stamp
    when its time differs from the one shown last in its session, else the date alone.
  - **Never over the budget.** A context is at most `budget` tokens (it was allowed 2% over): the fit drops the
    weakest pieces until the whole fits, and anything still over is cut to the longest prefix of whole words, as in
    0.11.2. `history_tokens` counts the history as one text, blank lines between sessions included.
  - **The turns of a day are ranked by relevance**, as every turn already is; a one-speaker or one-session history
    goes through the same selection.
  - **A section's best line may take at most a quarter of the room** (was half), so at budgets of about a hundred
    tokens a request or preference no longer crowds out the turns that answer the question.

### Changed
- **Memory: a long history is read turn by turn.** When the history does not fit the budget, `Memory.search` now
  ranks the stored turns themselves instead of rendered session text. When the whole history fits, the output is
  unchanged.
  - **User turns are their own pool**, ranked by the same relevance as the rest (lexical, then the reranker over the
    160 strongest candidates when one is set), with 55% of the budget reserved for them. A user turn is kept whole
    when it fits its cap (a tenth of the budget, between 120 and 400 tokens); a longer one keeps its most relevant
    sentences and is marked `partial`.
  - **Replies are cut into windows** of a few sentences (about a thirty-second of the budget, 60 to 200 tokens; code
    blocks and tables stay whole), ranked in a second pool, and fill the rest of the budget.
  - **Near-duplicates are left out:** a candidate whose word 5-grams are mostly in the text already kept is skipped.
  - **One labelled, dated block per turn:** `[date] role: text`. Prose stays on the label's line; code blocks and
    tables follow it, fenced. Markdown headings are folded into the sentence they head, so no heading stands alone,
    and a label never starts in the middle of a line. A stored line that looks like a turn label is indented, so
    stored text can't pass for another turn. Kept turns are in date order, with a blank line between sessions.
  - **Dates:** the first kept turn of each session shows the full stamp (`stamp_format`); a later one shows its own
    full stamp when its time differs from the one shown last in its session, else the date (`date_format`, new,
    default `%Y-%m-%d`).
  - **Cuts:** when a budget is too small for any whole turn, the best one is cut to fit, at a space when it has
    one. A turn with no space where a whole word fits (Chinese or Japanese prose, a long URL or token) is cut between
    two characters instead, never splitting what shows as one character (a letter and its accents, an emoji with its
    modifiers, a flag). 0.11.2 returned such a turn's label with no text.
- **Memory: questions with no Latin-script word are matched on their letters.** A question written in Chinese,
  Japanese, Russian or another script, or made only of common words ("What is it?"), has nothing for the lexical
  ranking to match; it used to get no ranking at all (even with a reranker), so the earliest turns filled the budget.
  Such a question is now matched on pairs of adjacent letters, with the same BM25; when no turn shares any, the most
  recent turns come first; and a reranker or custom scorer reads the strongest of these candidates. A history check
  with nothing to match gets no conflicts section. Questions with a Latin-script word or a number are ranked exactly
  as before.
  - A standing request's words are not added to such a question: they would switch the letter matching off.
  - When a user turn shares letters with the question but no reply does, the replies wait for that turn instead of
    filling the budget by recency (without a reranker).
- **MCP:** the `recall` tool's description says the stored messages come back under their dates and whole where they
  fit (the most relevant parts of longer ones), as the turn-level read path returns them.
- **Memory: the kind of question decides the sections** (fixed English patterns, no model; see
  `llmslim/memory/_routing.py`):
  - a plain lookup of a past fact or a history check ("What is my salary?", "When did I say ...?", "Have I ever
    ...?") gets no requests or preferences section, so the budget goes to the turns that answer it (a history check
    can get the section of statements that may conflict, below);
  - a request for help, advice or a plan gets the standing requests and the stated preferences that best match it;
  - other questions get the standing requests that best match them;
  - a summary, recap, ordering or "how did it develop" question is answered from the digest.

### Added
- **Memory: standing requests.** When a history does not fit, `Memory.search` puts the user's explicit standing
  requests that best match the question (at most three) in their own section at the top ("Requests the user made
  earlier:"), within 15% of the budget.
  - **What counts:** a request opens with its directive ("Always ...", "From now on ..."), asks the assistant
    directly ("I'd like you to never ..."), or says when it applies ("... when I ask about X"). It is kept even when
    it shares no word with the question.
  - **What does not:** a pattern word in passing ("I want to make sure my site is fast"), and assistant turns.
  - **Shape:** each request is cut to about 100 tokens, around its directive. The matching turns are returned in
    `MemoryContext.requests`.
  - **What it asks for is fetched too:** when the best-matching request says what an answer should include ("Always
    include the number of writers when I ask about my team"), those words are added to the retrieval query. Words
    that only describe a format ("step-by-step", "a table") are not.
  - **Controls:** `Memory(standing_requests=...)` and `search(standing_requests=...)`.
- **Memory: preferences.** For a request for advice, a recommendation or help, `Memory.search` shows the user's
  earlier statements of preference ("I prefer ...", "I'd rather ...", "I usually ...", "I don't like ...") that best
  match it, in their own section after the requests ("Preferences the user stated earlier:"), at most 8 within 10% of
  the budget. A long sentence is shown around the words that state the preference. The matching turns are returned
  in `MemoryContext.preferences`.
  - **What does not:** a preference word that is only asked about ("should I prioritize ...?", "how can I
    prioritize ...?").
  - **Controls:** `Memory(preferences=...)` and `search(preferences=...)`.
- **Memory: statements that may conflict.** For a question about whether something happened ("Have I ever ...?",
  "Did I ... before?", "Have I completed any ...?"), `Memory.search` reads the user's statements that bear on it most
  (prose only: no code, no questions on their own, no standing requests). When some of them deny it ("I have never
  ...", "I haven't ...", "not yet") and some do not, both kinds are shown together in date order in their own
  section at the top ("Statements the user made on this that may conflict (in date order):"), at most two of each,
  within 8% of the budget (the first pair may take up to a quarter of a small budget). The matching turns are
  returned in `MemoryContext.conflicts`.
  - **Controls:** `Memory(conflicts=...)` and `search(conflicts=...)`.
- **Memory: a statement is shown once per section**, even when the user said it in several turns.
- **Memory: overview questions.** A summary, recap or ordering question ("summarize what we discussed", "in what
  order did I ...", "how did my plan develop?") is answered from a digest: the opening of each user turn and each
  reply, without code and without the reply's opening pleasantry ("Great question!"), plus the reply's outline (its
  headings and bold list leads). Many more exchanges fit in the budget than as whole turns.
  - User openings get half of the digest (30% in a summary under 5,000 tokens, which keeps no reply passage
    whole, so the replies' openings and outlines get more of the room), or 80% for a question about the order of
    what the user brought up.
  - With a budget of 5,000 tokens or more, a summary also keeps the most relevant reply passages whole, in 30% of
    the budget.
  - **Controls:** `Memory(coverage="auto" | "always" | "never")` and `search(coverage=...)`.
- `llmslim.focus.rank` takes an optional `candidates`: how many of the strongest lexical candidates the reranker
  reads.
- `MemoryContext.requests`, `preferences` and `conflicts`, and the same three lists in `MemoryContext.to_dict()`, so
  in `llmslim serve`'s `POST /v1/memories/search` response (each turn with its id, role, content, timestamps,
  `score` and `partial`). Empty when the section is not shown.
- `Memory.search` logs one line per search at DEBUG level on the `llmslim.memory` logger: the kind of question, token
  counts, turns and sessions kept, the size of each section and the time taken. It never logs the query or any
  stored text.

## [0.11.2] - 2026-10-24

### Fixed
- **`Memory.search` ranks the turns of a session by relevance when the session does not fit the budget.** Turns
  without a `run_id` are grouped by calendar day, so a day of `remember` calls to the `llmslim mcp` server is one
  session. When that session did not fit, `recall` kept the newest turns of the day and dropped the ones that answered
  the question: ten notes from one morning, asked "How do I run the tests, and where can I deploy from?", came back
  as the last four notes at a 150-token budget. The same notes spread over ten days were recalled correctly.
  - The turns of a one-speaker session are now ranked one by one, as the turns of a two-speaker session already were.
    The kept turns stay in their order, under the session's date.
  - A history of one session (one day, or one `run_id`) goes through the same selection as a history of many. It was
    compressed as one text, whose `[date] role: content` lines read as a log, so its newest lines won.
  - In both cases each kept turn is counted with the line break and `...` line it can add.
  - A history of several sessions with two speakers each selects exactly as before.
- **`... [N lines omitted]` counts every line of a collapsed run.** When a run of near-identical lines was omitted
  from its first line on, the marker counted only that run's first and last lines: a 250-line run of passing tests
  showed as `... [2 lines omitted]`. It now counts all 250. Only the number changes; which lines are kept does not.
- **`Memory.search` shows each turn's own time.** It stamped every turn of a session with the session's first turn's
  time, so turns added hours apart on the same day (the normal case for the `llmslim mcp` memory server, which groups
  turns without a `run_id` by calendar day) all showed the first one's time. A session whose turns share one
  timestamp renders byte for byte as before, with the stamp shown once as its header, so LongMemEval and BEAM style
  contexts do not change.
- **`Memory.search` (and the MCP `recall` tool) no longer return more tokens than the budget.** A pass of the
  selection was accepted up to 2% over, and selection does not charge the `...` it puts between kept turns or, for
  very small budgets, the session's date header. Five notes searched with `budget=120` came back at 121 tokens.
  - A pass is now accepted only within the budget. When the last pass is still over, the context is cut to the
    longest prefix of whole words that fits, which can be empty for a budget smaller than a date header.
  - `history_tokens` counts the history as one text, with the blank lines between sessions, so a history that fits
    is returned whole only when it fits as joined.
  - `recall` says when no stored message fits the budget, instead of "No stored memories yet."
- **A memory session with one speaker keeps one turn per line.** Notes stored with the MCP `remember` tool are all
  `user` turns, and selection read a block as a transcript only with two speakers. Such a session was flattened into
  one paragraph: its date was repeated on every turn and kept turns were joined with spaces. A block with one speaker
  now reads as a transcript when every turn is stamped, so the date is shown once and each turn stays on its line.
  Text with two speakers is selected as before.

### Added
- **A Hermes Agent plugin for the Hermes plugin catalog, in `plugins/hermes`.** It installs the existing
  `LLMSlimContextEngine` with `hermes plugins install`, pins `llmslim==0.11.1` as its one Python dependency, and
  declares the engine's settings so the Hermes desktop app shows them as a form. It is not part of the PyPI package.
- **A VS Code extension, LLMSlim Memory, in `plugins/vscode`**, for the VS Code Marketplace and Open VSX. It adds the
  pinned MCP server (`uvx --from "llmslim[mcp]==0.11.1" llmslim mcp`) to VS Code's MCP support through
  `vscode.lm.registerMcpServerDefinitionProvider`, with settings for an installed `llmslim` command and the memory
  file. It is not published yet and is not part of the PyPI package.

### Packaging
- **The Claude Code plugin pins its MCP server to an exact version** (`llmslim[mcp]==0.11.1`, was `>=0.11.0`). The
  Claude plugin directory blocks a version range as an unpinned uvx launcher.
- **The plugin has a README** (`plugins/llmslim/README.md`): what it runs, what it stores and what reaches the
  network. The directory requires one.
- **A Gemini CLI extension manifest** (`gemini-extension.json` at the repo root) runs the same pinned server, so
  `gemini extensions install https://github.com/Thanatos9404/llmslim` works and the extensions gallery can index the
  repo.
- **One-click install links** in the README for VS Code, Cursor, LM Studio, Goose and Kiro.
- **A Codex plugin manifest** (`plugins/llmslim/.codex-plugin/plugin.json`) starts the same pinned server from the
  plugin's `.mcp.json`, for Codex and the awesome-codex-plugins list.
- **The plugin folder has its own LICENSE and SECURITY.md**, its two skills declare a `name`, and the marketplace
  declares `"strict": true`. The HOL plugin scanner that the awesome-ai-plugins and awesome-codex-plugins lists run
  checks for all of these.
- **The Codex plugin has an icon** (`plugins/llmslim/assets/icon.png`), which the awesome-codex-plugins list requires.
- **Agent Plugins manifests for Copilot CLI** (`plugins/llmslim/plugin.json` and `mcp.json`, schema 1.0.0) start the
  same pinned server. Copilot CLI already read the Claude layout; the awesome-copilot list checks only these files.
- **Security and conduct reports go to support@llmslim.app.** `SECURITY.md` and `CODE_OF_CONDUCT.md` gave a GitHub
  noreply address, which receives no mail.

### Documentation
- **Corrected figures from the 0.11.1 notes**, found by checking every published claim against the raw runs:
  - the lint task has 240 warnings, not 260;
  - the JSON task's command returned 74 open issues (the fixture holds 90);
  - the replay of real sessions priced Claude Opus 5.5 cache reads at 0.1x input; Opus 5.5 reads at 0.05x. At the
    right rates cache reads are 60.9% of that bill, not 75.6%, and the compression ceiling is 13.4%, not 13.8%;
  - "444 real sessions" is 32 sessions plus the 412 subagent runs they started;
  - pooled and test-run results now lead with the primary (default permission mode) measurement instead of a range
    across two modes;
  - interactive sessions through the proxy were not tested for their permission mode.
- **A shorter first screen in the README**: what LLMSlim does in one line, setup commands for Claude Code, Codex,
  Copilot CLI, Gemini CLI, Hermes Agent, Python and TypeScript, and a recorded session with llmslim 0.11.1 from PyPI
  (`docs/assets/llmslim-memory-demo.svg`). Every earlier section is still there, below it.
- **Runnable examples with tests** in `examples/`: Claude Code memory over MCP, LangChain and Pydantic AI agents with
  memory, fitting a long log into a budget, and the TypeScript client against `llmslim serve`. They run offline with
  fake or test models; `tests/test_examples.py` and the TypeScript client CI job run them.

## [0.11.1] - 2026-10-17

We measured what `llmslim wrap claude` does to a real Claude Code bill: billed dollars, with cache reads and writes
priced separately, over 572 published runs (`benchmarks/claude_code_cost/`). The benchmark found three problems in
0.11.0, fixed here.

### Fixed
- **`llmslim wrap claude` no longer makes every request about 7,100 tokens longer.** Claude Code turns tool search off
  when `ANTHROPIC_BASE_URL` points anywhere but Anthropic, and then sends every tool definition on every request.
  - `wrap` now sets `ENABLE_TOOL_SEARCH=true` unless you set it yourself. The proxy forwards tool search blocks
    unchanged.
  - Measured on Claude Code 2.1.296 with Claude Haiku 5.5, with the same prompt:
    - the first request was 26,885 tokens through the 0.11.0 proxy;
    - it is 19,716 with this fix, against 19,712 without the proxy;
    - a tool search through the proxy loaded WebFetch from its `tool_reference` block.
- **Print-mode runs keep the default permission mode.** Through a proxy, Claude Code can't fetch its feature flags,
  and `claude -p` then starts in auto mode, where commands outside `--allowedTools` go to a classifier instead of
  being refused.
  - `wrap` now starts print-mode runs with `--permission-mode default`, unless you pass a mode or set
    `permissions.defaultMode` in your settings.
  - Interactive sessions get no added flag. We measured the switch to auto mode only in print mode, so pass
    `--permission-mode` yourself if an interactive session must stay in default mode.

### Changed
- **JSON tool output is left as it is by default**, in `llmslim proxy` and `LLMSlimToolOutputMiddleware`. In the
  benchmark (default permission mode), an agent given a shortened JSON list of 74 open issues went back for the issue
  text that was cut and took a median of 12 turns instead of 4, and the run cost about twice as much. This applies when
  the whole output is one JSON document; JSON Lines or JSON mixed with other text is still shortened as text. `--json` (proxy) or `compress_json=True` (middleware) turns it
  back on.

### Added
- **`benchmarks/claude_code_cost/`:** the billed-cost benchmark, with its protocols written before each run and every
  run's result.
  - Long CI and lint logs cost 17-32% less.
  - Test runs cost about 4% less in default permission mode (within noise) and 2-15% less in auto mode: agents
    already trim them with `tail`.
  - Pooled over 8 tasks: +5.3% in default mode (the primary result, mostly from the JSON task) and -5.1% in auto
    mode.
  - Replaying the maintainer's transcripts (32 sessions and 412 subagent runs) shows tool output is a small part of a
    Claude Code bill: with the same turns, all shell, search and web output costing nothing would have cut it by
    13.4%.
- **A Claude Code plugin marketplace in this repo.** `/plugin marketplace add Thanatos9404/llmslim`, then
  `/plugin install llmslim@llmslim`.
  - The plugin starts LLMSlim's memory server with `uvx`.
  - `/llmslim:wrap-claude` walks through starting Claude Code through the proxy.
  - `/llmslim:savings` runs `llmslim proxy stats`.
  - Both commands run only when you type them.
- `glama.json`, so the maintainer can claim the Glama listing.

### Known limitation
- With a custom `ANTHROPIC_BASE_URL`, Claude Code skips the server-managed settings of a Team or Enterprise
  organization (documented by Claude Code). Don't use the proxy where those settings must apply.

## [0.11.0] - 2026-10-17

### Added
- **The TypeScript client is on npm:** `npm install llmslim` (0.1.0). It includes the `llmslim/ai-sdk` tools and
  middleware for the Vercel AI SDK.
- **JSON tool results keep every item.** When `llmslim proxy` or `LLMSlimToolOutputMiddleware` shortens a JSON
  result with a list, it keeps every item, one compact line each, instead of a window of lines.
  - Each item shows its short identifying fields: ids, names, titles, states and dates.
  - Items related to the call stay whole.
  - Long text is cut, and nesting is summarized as `[n items]`.
  - Envelopes such as `{"total_count": ..., "items": [...]}` keep their other fields.
  - Items are dropped only if even identity fields don't fit. They come from the middle, never related ones, and a
    line names them.
  - An 80-issue GitHub list went from 12,247 to 3,108 tokens with every issue listed and the related one whole.
- **`LLMSlimToolOutputMiddleware` for LangChain 1.x agents** (`pip install "llmslim[langchain-agents]"`).
  - It shortens a long tool result the first time the model is about to see it, and writes it back into the agent's
    state under the same id. Later calls send the same bytes, so prompt caches and Claude's thinking stay valid.
  - Unlike `ContextEditingMiddleware`'s `[cleared]`, it keeps errors and the lines related to the call.
  - Options: `only` and `never` tool filters. Each shortened message records its token counts in
    `response_metadata["llmslim"]`.
  - Measured with Claude Haiku 5.5 and adaptive thinking: a 7,545-token log reached the model as 160 tokens, and a
    second turn with thinking in the history answered correctly.
  - The shortening itself moved to `llmslim._tool_output`, shared with `llmslim proxy`.
- **`llmslim wrap claude` and `llmslim proxy`: lean context for coding agents** (`pip install "llmslim[proxy]"`).
  - A local proxy for the Anthropic Messages API. It compresses long tool output (shell, search and web tools; MCP
    tools opt-in) the first time the model is about to see it.
  - It stores each decision under the tool call id and the text, and replays the same bytes on every later request.
    So the prompt cache keeps hitting and Claude's thinking blocks stay valid.
  - `Read`, `Edit`, `Write` and unknown tools are never touched, nor is output seen before the proxy started.
  - Headers, `cache_control` and streamed responses pass through. A failed rewrite forwards the original request.
  - The proxy listens on loopback only. Credentials are forwarded and never stored.
  - **Measured on Claude Haiku 5.5 with adaptive thinking:**
    - a 10,545-token pytest log went out as 156 tokens;
    - cache reads grew every turn;
    - 62,334 input tokens were not sent across seven requests;
    - the same request without the replay was rejected with HTTP 400.
  - Real Claude Code 2.1.296 through `llmslim wrap claude` sent a 6,045-token log as 156 tokens and answered
    correctly.
  - `llmslim proxy stats` reports tokens not sent. Guide: `docs/PROXY.md`.
- **`PostgresStore` for `llmslim.memory`** (`pip install "llmslim[postgres]"`, psycopg 3).
  - `Memory("postgresql://...")`, `llmslim serve --db postgresql://...` and `llmslim mcp --db postgresql://...` use
    it. Several processes or machines can share one memory on Postgres 12+: self-hosted, Supabase, Neon or RDS.
  - It creates its table and a version table under an advisory lock, so several processes can start at once. A table
    written by a newer llmslim is refused.
  - It takes a URL (it opens its own pool), a `psycopg_pool.ConnectionPool` or an autocommit connection.
  - Times are `TIMESTAMPTZ` and come back in UTC. Concurrent writers keep every turn and one order.
  - CI runs the whole memory suite against a Postgres 17 service.

## [0.10.1] - 2026-10-17

### Fixed
- **The MCP Registry name now matches the GitHub account's casing.** It is `io.github.Thanatos9404/llmslim` in
  `server.json` and in the README's `mcp-name` marker. The registry grants namespaces with the exact GitHub login and
  checks the marker on PyPI, so 0.10.0's lowercase name could not be published. No code changes.

## [0.10.0] - 2026-10-17

### Added
- **`llmslim.memory`: agent memory with no LLM in the loop.**
  - `Memory.add` stores turns verbatim. There is no extraction model, so writes cost nothing and a turn can never
    become a wrong "fact".
  - `Memory.search(query, user_id=..., budget=...)` selects the turns that answer the question at read time, within a
    token budget.
  - Each session (a `run_id`, or a calendar day) is shown under one date stamp.
  - Scopes follow Mem0 (`user_id`, `agent_id`, `run_id`), and at least one is required.
  - Stores: `InMemoryStore` and `SQLiteStore` (Python's built-in `sqlite3`, no extra dependency).
  - `llmslim.memory.compat.Mem0Memory` has Mem0 2.x's methods and return shapes, so switching is one import.
  - With the round-3 benchmark's date format, `Memory.search` reproduced the benchmark builder's contexts byte for
    byte on 120 of 120 LongMemEval-S development contexts. Its measured results therefore apply to it.
  - Guide: `docs/MEMORY.md`. Example: `examples/memory_quickstart.py`. Roadmap: `docs/roadmap/1.0.md`.
- **`llmslim mcp`: memory and context tools for any MCP client** (`pip install "llmslim[mcp]"`, Python 3.10+).
  - Tools:
    - `remember` stores a message word for word;
    - `recall` returns the stored messages that answer a question within a token budget, labelled as data;
    - `list_memories` and `forget` show and delete stored messages;
    - `fit_context` shrinks a long text to a budget around a question.
  - The user and agent scope is fixed by the server (`--user-id`, `--agent-id`), never chosen by the model. `forget`
    refuses ids outside it.
  - Storage is a local SQLite file. The server uses stdio, makes no model or network calls, and gives tool hints
    (read-only, destructive).
  - `llmslim.mcp_server.build_server(memory, user_id=...)` builds the same server from Python.
  - Guide: `docs/MCP.md`. `server.json` is ready for the MCP Registry once a release includes the server.
- **`llmslim serve`: memory and context over HTTP** (`pip install "llmslim[server]"`, Python 3.9+).
  - A JSON API over `llmslim.memory`:
    - add, list, get, update and delete messages;
    - delete a scope;
    - search within a token budget;
    - `POST /v1/context/fit` for long text.
  - Bearer API keys (`--api-key` or `LLMSLIM_API_KEYS`) are compared in constant time and must be at least 16
    characters. Without a key, the server refuses any interface other than loopback.
  - Bodies are capped at 1 MB, budgets at 100,000 tokens and list pages at 1,000 items. Errors come back as JSON.
  - A `Dockerfile` runs it as a non-root user with the SQLite file on a `/data` volume and a health check. CI builds
    the image and checks that it refuses to start without a key and answers with one.
  - `llmslim.server.create_app(memory, api_keys=...)` returns the ASGI app.
  - Guide: `docs/SERVER.md`.
- The `mcp` and `server` extras now install `tiktoken`, so token budgets are exact.
- **TypeScript client** (`clients/typescript`, npm package `llmslim`, not published yet).
  - `LLMSlim` wraps every `llmslim serve` route. It has no dependencies and runs on Node 18+, Bun, Deno and edge
    runtimes.
  - `llmslim/ai-sdk` adds the Vercel AI SDK `memoryTools()` (`recall_memory`, `remember`) and a `memoryMiddleware()`
    that saves turns.
    - Neither changes the prompt, so prompt caches and Claude's preserved thinking stay valid.
    - The scope comes from your code, never from the model.
  - CI runs its tests against a real `llmslim serve`.

### Fixed
- **The agent-history adapters broke Claude's preserved thinking.**
  - **The bug:**
    - On Claude models with preserved thinking (Haiku 5.5, Sonnet 5.5, Opus
      5.5 and Fable 5.1), each thinking block's signature is bound to
      everything sent before it.
    - The Pydantic AI history processor, the Hermes Agent context engine, the
      gptme context provider and `compress_chat_messages` compressed or dropped
      earlier turns, but sent later assistant turns back with their thinking
      unchanged.
    - Anthropic then rejected the request with HTTP 400 ("The block is bound to
      a different conversation"), the default for accounts created on or after
      2026-08-31. Older accounts silently lost the reasoning.
    - Reproduced on Claude Haiku 5.5.
  - **The fix:**
    - Once an adapter changes or removes a message, it removes the signed
      thinking from that message and every later assistant message, and keeps
      the thinking before it. Anthropic allows removing blocks from the end,
      never from the middle.
    - The result is a pure function of the history, so later requests send the
      same bytes again.
    - A history that fits is passed through unchanged.
  - **Unfinished tool rounds:** while a tool round is unfinished and its
    assistant turns have thinking, the adapters first try to fit by shortening
    only the tool output after the round's last thinking, and compact the
    earlier history at the next user message. Only when that can't fit does the
    round lose its thinking too. The limit is `max_tokens` for Pydantic AI, the
    limit for gptme, and the context window for Hermes.
  - **`compress_chat_messages`** keeps an unfinished tool round's thinking and
    otherwise follows the same rule. Call it on the full history with the same
    options on every request.
  - **Logging:** every removal is logged and counted:
    `HistoryFit.thinking_stripped` (Pydantic AI's `fit_messages`, Hermes's
    `last_fit`), or a line in gptme's `limitations`.
  - **Request settings** such as `anthropic-beta` and `thinking.block_binding`
    are never touched.
- gptme: an assistant message with Claude thinking (gptme's inline `<think>`
  block and its `think-sig` signature) could be compressed as text, cutting
  the thinking or its signature. Only its visible text is compressed now.
- Pydantic AI: only Claude thinking (a signed `ThinkingPart` from Anthropic or
  Bedrock) is removed. OpenAI's encrypted reasoning and Gemini's thought
  signatures have no such binding and are left as they are. The OpenAI Agents
  SDK input filter already refuses `reasoning` items, so it never changes the
  history in front of them; that is now documented and tested.
- **Query matching across word forms.** Lexical selection stems the question
  and the context so that different forms of a word match. Some common forms
  did not:
  - Four-letter words ending in "e" kept the "e", while their other forms lost
    it: "move" did not match "moved", nor "time" "times", nor "live" "living".
    A question like "Where did I move to?" could miss the turn "I moved to
    Pune".
  - A doubled consonant stayed after "-ing" and "-ed", so "shopping" did not
    match "shop", nor "planned" "plan".
  - Words ending in "ss" or "us" lost their final "s" as if plural, so "class"
    did not match "classes", nor "status" "statuses".

  All of these now share one stem. On the round-3 development splits, measured
  offline with no model calls, the share of answer-bearing text kept changed by:
  - LoCoMo: +0.9 points at 1,000 tokens and +1.1 points at 2,500;
  - LongMemEval-S: -0.3 points at 2,500 tokens and 0.0 at 10,000;
  - NQ: -0.5 points;
  - HotpotQA: +0.3 points.

  None of these changes is statistically significant. The held-out test
  splits were not run. Other derived forms such as "allergy" and "allergic"
  still don't match; `relevance="semantic"` covers them.

## [0.9.0] - 2026-10-15

### Added
- **Usage guard for paid integrations** (`llmslim.integrations._guard`).
  `UsageGuard` admits or refuses each call before it leaves the process. It
  enforces a sliding per-minute rate, a lifetime request cap and an optional
  unit cap (INR, USD, credits or queries). Callers reserve before the call,
  then settle with the vendor-reported amount, or release when nothing was
  billed. Limits come from `LLMSLIM_<PREFIX>_REQUESTS_PER_MINUTE`, `_MAX_REQUESTS`
  and `_MAX_UNITS`; `none` disables one limit.
- **Sarvam, beyond chat** (`llmslim[sarvam]`):
  - `AsyncSarvamProvider`.
  - `SarvamLanguageTools` and `AsyncSarvamLanguageTools`: language
    identification, transliteration and translation, chunked to Sarvam's
    per-request limits without splitting graphemes.
  - Opt-in `annotate_languages()` and `normalize_scripts()` context helpers.
  - `SarvamDocumentSource`: a PDF or image becomes one RAG item per page, with
    file type, size and 10-page checks, a poll timeout and partial-job handling.
  - Typed, sanitized errors for 402, other 4xx, 5xx, failed jobs and timeouts.
  - Every call is guarded with dated INR prices.
  - `examples/sarvam_voice_agent.py` now runs Saaras speech-to-text → plan →
    `sarvam-105b` → Bulbul text-to-speech end to end.
- **Exa web search** (`llmslim[exa]`): `ExaSearchSource` returns untrusted RAG
  context items. Each item carries its URL, published date, rank and a recency
  score, and is capped in USD and settled with Exa's reported cost. Requests are
  never retried automatically and never follow redirects. The vendor-neutral
  `llmslim.integrations.web_search` module has `WebSearchSource`,
  `WebSearchResult`, validation and sanitization helpers, and typed errors.
- **Neo4j temporal agent memory** (`llmslim[neo4j]`): `Neo4jContextStore` keeps
  tenant-scoped facts with validity intervals.
  - `supersede()` closes a fact and links `(new)-[:SUPERSEDES]->(old)` in one
    transaction. It refuses cycles and cross-tenant IDs.
  - `recall(as_of=...)`, `history()` and `conflicts()` make stale and
    conflicting memory auditable.
- **Secondary-reader benchmarks.** `benchmarks/live_secondary_reader.py` runs
  the frozen v0.6 suite with Sarvam as reader, in three arms: full, LLMSlim, and
  truncated to the same budget. It reports paired bootstrap CIs and a weak-spots
  section, labels the run as secondary to the Claude Haiku 5.5 headline, and
  caps spend in INR. Nebius is off unless `LLMSLIM_NEBIUS_ALLOW_LIVE=1`, with a
  US$0.10 cap and a required verified price. LangSmith tracing of public
  datasets only is available in `benchmarks/_tracing.py`.
- **Studio "Answer with Sarvam" step** (`web/api/sarvam_answer.py`): sends the
  compressed context and question to `sarvam-105b` through `llmslim.hosted`,
  with its spend ledger, HMAC identity, exact-origin check and kill switch.
  Off unless configured.
- **Server-side Sentry for the Studio functions**: errors only. Bodies,
  cookies, query strings, headers and secret-looking values are scrubbed.
- `.env.example` lists every variable by name.
- **Agent-history adapters** for gptme, Hermes Agent and Pydantic AI. Each fits
  an agent's message history into a token budget locally, with no model call:
  the system prompt, tool calls and the latest turns stay as they are, older
  tool output and turns are compressed first (tool output keeps its failures,
  tracebacks and line structure), and older material is dropped only when
  compression is not enough. Tool calls always stay paired with their results.
  Guides with runnable examples are in `docs/integrations/`.
  - `llmslim.integrations.gptme.LLMSlimContextProvider`, a gptme
    `ContextProvider`, registered through the `gptme.context_providers` entry
    point as `llmslim`. A `gptme.plugins` entry point makes it the provider
    gptme's automatic compaction and `/compact trim` use when the gptme config
    has `[plugin.llmslim] compaction = true`; without that, gptme is
    unchanged. Install `llmslim[gptme]` (gptme 0.34 or newer, Python 3.10+).
    Tested with gptme 0.34.0.
  - `llmslim.integrations.hermes.LLMSlimContextEngine`, a Hermes Agent
    `ContextEngine`, loaded through the `hermes_agent.plugins` entry point or a
    two-file directory plugin and selected with `context.engine: llmslim`. It
    returns the system prompt and protected head as the same objects and, on
    later compactions, leaves the previously compacted prefix byte-identical
    when compressing the newer turns is enough, so prompt caches keep hitting.
    `/compress <topic>` focuses compression on the topic. No extra: install
    llmslim into Hermes's environment. Tested with Hermes Agent 0.19.0 (PyPI)
    and v0.21.7 (GitHub).
  - `llmslim.integrations.pydantic_ai.llmslim_history_processor(max_tokens)`,
    a Pydantic AI history processor for `ProcessHistory(...)` or
    `history_processors=[...]`. It removes older tool exchanges and turns only
    as whole units that share no tool call id with the rest of the history, so
    calls and returns stay paired and requests and responses still alternate.
    Install `llmslim[pydantic-ai]` (Python 3.10+). Tested with
    pydantic-ai-slim 1.0.0, 1.107.7 and 2.55.0.
- `llmslim[all]` includes `pydantic-ai-slim`. gptme is not in `all`: it pins
  `mcp<2`, which conflicts with the `mcp` extra.

### Changed
- **Transcripts keep more of the evidence a question needs.** Two dev-only
  changes to query-focused selection:
  - A reply that asks a question back keeps its own reply too ("How long have
    you been into art?" stays with "Seven years now"), up to three turns.
  - In "how long / how many / how much ..." questions the word after "how"
    names the kind of answer, not a topic, so it no longer matches text such as
    "long time no see". The answer-type bonus still favours units with numbers
    and dates.
  On the round-3 dev splits (no API calls), labelled evidence kept by the
  default lexical mode: LoCoMo 74.3% → 75.6% at 1,000 tokens, 82.7% → 83.4% at
  2,500 and 96.1% → 97.1% at 10,000; LongMemEval-S 75.4% → 77.3% at 2,500 and
  91.8% → 93.2% at 10,000; with the reranker, LoCoMo 84.4% → 86.6% at 2,500.
  NQ, HotpotQA and LongBench dev checks are unchanged or slightly up. With
  Claude Haiku 5.5 reading LoCoMo dev: 92.7 → 92.7 at 1,000 tokens, 95.7 → 97.4
  at 2,500.
- **Plain-text transcripts are selected turn by turn.** A block of
  speaker-prefixed lines (`Caroline: ...`, `user: ...`, optionally after a
  stamp such as `[8 May 2023]`) is no longer joined into one paragraph and cut
  into sentence windows that straddle turns. Instead:
  - each turn is its own unit, so turns are never split or merged;
  - a turn that asks a question is kept together with the reply that follows;
  - a stamp shared by every line of the block is shown once, as its header.
  JSON chat messages were already handled this way; nothing else changes
  (identical output on the NQ, HotpotQA, LongBench and LongMemEval-JSON dev
  checks). On the round-3 dev splits, with Claude Haiku 5.5 reading:
  - LoCoMo (2 dev conversations, 233 questions): 90.1 → 92.7 at 1,000 tokens.
    Labelled evidence turns kept: 60% → 74% at 1,000 tokens, 77% → 83% at
    2,500 and 93% → 96% at 10,000.
  - LongMemEval-S in the same line format (120 dev questions, official judge):
    77.5 → 78.3 at 2,500 tokens and 76.7 → 80.0 at 10,000.
- **Round-3 test results for the two transcript changes above**, read once
  with Claude Haiku 5.5 (`benchmarks/live/round3/RESULTS.md`). On 1,307 LoCoMo
  test questions the default lexical mode goes from 84.4% to 87.5% at 1,000
  tokens, 90.9% to 91.7% at 2,500 and 94.0% to 94.3% at 10,000 (Mem0's judge).
  On 180 LongMemEval-S test questions the reply-chaining and quantity-word
  change adds 1.7 points at both budgets (70.6% at 2,500 tokens, 77.8% at
  10,000, official judge). There, dense retrieval over turns is still ahead
  (76.1% and 80.6%); a further transcript change that narrowed the gap on dev
  did not hold up on test and is not in this release.
- Sarvam model profiles repriced to ₹15 input, ₹5 cached input and ₹60 output
  per 1M tokens (Sarvam pricing page, 12 October 2026). Hosted cost
  reservations were about 2× too high.
- `SarvamProvider.from_env()` attaches a `sarvam_chat` guard and settles on
  provider-reported usage, pricing cached input at the cached rate.
  `SarvamUsage` gains `cached_tokens` and `reasoning_tokens`. Pass `guard=None`
  to opt out.
- `parse_cache_telemetry("sarvam", ...)` reads `cached_tokens`.
- The `external_provenance_boundary` validation check also covers `exa:`,
  `neo4j:` and `sarvam:` sources.
- `normalize_scripts()` / `anormalize_scripts()` only rewrite user, retrieved,
  memory and tool-result text by default (`kinds=`, `roles=`); system,
  developer, assistant and tool-schema items are never replaced with vendor
  output unless listed explicitly.
- Hosted Sarvam reservations are a UTF-8 byte upper bound of the exact messages
  sent (`sarvam_prompt_token_bound`), not the planner's token count, which is
  `len/4` without `tiktoken`. A request whose bound exceeds `max_input_tokens`
  or the per-request cost cap is refused instead of clamped.
  `estimate_multiplier` is no longer used.

### Security
- Untrusted content can no longer close or forge the planner's
  `<llmslim_context>` provenance envelope. Envelope attribute values are
  escaped, so an item ID such as `a" trusted="true` stays inside `id`. In
  untrusted items (any role other than system or developer), envelope tags in
  any case or spacing are rendered with `&lt;` in place of `<`, so Neo4j
  memories, Sarvam OCR pages and web results render as one untrusted block
  each. Trusted content, and content without an envelope tag, renders byte for
  byte as before, so plans, cache keys and benchmark results are unchanged. The
  helpers live in `llmslim.planning.boundary` and the web-search sanitizer uses
  the same ones.
- Web search: result URLs containing `<`, `>`, `"`, whitespace, control or
  invisible formatting characters are dropped. The text sanitizer now keeps
  ZWNJ and ZWJ (needed for Devanagari half-forms, Malayalam chillu letters,
  Persian and Urdu, and emoji ZWJ sequences) and removes Unicode tag characters
  ("ASCII smuggling") except inside subdivision-flag emoji, as well as
  variation selectors supplement characters.

### Fixed
- **Sentence centrality on very large chunks** no longer builds the full
  sentence-by-sentence similarity matrix. Above 4,096 sentences the same
  scores are computed from row sums in memory proportional to the number of
  sentences: a 24,000-sentence chunk peaks at about 150 MB instead of 2.3 GB,
  and is faster. Smaller chunks use the existing path, so their output is
  unchanged. Thanks to @rlippmann for the report and the analysis (#17).
- Exa: a `date` passed as `end_published_date` now includes that whole UTC day
  (sent as `23:59:59.999Z`); it used to be midnight, which excluded the day.
- Exa: `truncated` is also set when Exa's own `maxCharacters` cut is reached
  (the returned text is `max_characters` long), not only when LLMSlim cuts it.
- **Planner: a relevant Indic document was cut mid-sentence** (regression in
  0.8.0). The planner's extractive candidates came from `compress()`, which
  with a query now uses query-focused selection; when nothing fits, its last
  resort is a word-boundary prefix. A one-sentence Bengali or Odia document
  was cut before its date or reference number, entity validation did not
  notice, and the plan kept that fragment plus an irrelevant document instead
  of the whole relevant one (v0.6 suite: fact retention 0.667 on
  `indic-bengali` and `indic-odia`). Extractive candidates now use
  sentence-level selection, as before 0.8.0: whole sentences only, and a
  single sentence is kept raw or dropped. The adaptive planner's results are
  again identical to 0.6.0 on the 28-case v0.6 suite and to 0.7.x on the
  112-case v0.7 suite. `compress()` itself is unchanged.
- Planner relevance is script-aware: Indic words keep their vowel signs and
  viramas (Python's `\w` dropped them, so an Odia or Telugu query had no terms
  and every document scored 0.5), words are NFC-normalised without zero-width
  joiners, and digits of every script compare as ASCII (`২০২৬` matches
  `2026`). New helper: `llmslim.tokenization.words()`. The agent context
  runtime now fits `indic-telugu` and `indic-odia` of the v0.7 suite within
  their budgets.
- Sarvam calls that can be billed (chat, language tools, document-job creation,
  the benchmark reader and the voice example) are sent once:
  `request_options={"max_retries": 0}` on every call, also with injected
  clients. `sarvamai` otherwise retried 408/409/429/5xx up to twice.
- Sarvam SDK clients built by LLMSlim never follow redirects. `httpx` strips
  only `Authorization` on a cross-origin redirect, so the
  `api-subscription-key` header and the body could reach another host.
- `llmslim.hosted` builds its provider with `guard=None` again, so
  `LLMSLIM_SARVAM_CHAT_*` cannot break or refuse hosted requests; a refusal
  before the network, or an error Sarvam returns unbilled (401/403, 402, 4xx
  validation, 429), releases the hosted reservation instead of keeping it. The
  per-request provider's HTTP pool is closed after each request.
- A multi-request Sarvam operation that needs more requests than the
  per-minute rate allows raises `UsageCapExceeded`, not a `RateLimitExceeded`
  that waiting could never fix.
- `last_usage` uses one module-level `ContextVar` instead of one per provider,
  which pinned a variable per provider ever used (hosted makes one per request).
- Sarvam document pages without a `page_number` keep their text, numbered by
  position and marked `page_number_inferred`, instead of failing a billed job.
- Sarvam providers, language tools and document sources have `close()` /
  `aclose()` and `with` / `async with` support for clients they built.
- Secondary-reader benchmark: the Nebius limits may only be lowered by
  `LLMSLIM_NEBIUS_BENCH_*` (a higher value or `none` is refused), and a
  persistent per-day ledger (`benchmarks/results/.nebius-spend.json`) caps all
  Nebius runs on a machine at US$0.10 per UTC day. A case stopped mid-way (guard
  refusal, rate-limit stop, Ctrl-C) keeps its billed arms in the results and
  totals.

## [0.8.1] - 2026-10-12

### Added
- **Framework adapters** that run `compress_documents` inside LangChain,
  LlamaIndex and Haystack, with the same shared budget when there is a query.
  Kept documents keep their order, id, score and metadata; documents that
  compress to nothing are dropped; the original and kept token counts are
  recorded in the metadata (`record_token_counts=False` turns this off).
  - `llmslim.integrations.langchain.LLMSlimCompressor`, a
    `BaseDocumentCompressor` for `ContextualCompressionRetriever`, where you'd
    use `LLMLinguaCompressor`. Install `llmslim[langchain]`.
  - `llmslim.integrations.llama_index.LLMSlimPostprocessor`, a
    `BaseNodePostprocessor`, where you'd use `LongLLMLinguaPostprocessor`. The
    token counts are kept out of the LLM and embedding text. Install
    `llmslim[llamaindex]` (Python 3.10+).
  - `llmslim.integrations.haystack.LLMSlimDocumentCompressor`, a Haystack
    component with `run(documents, query)`. Install `llmslim[haystack]`.
  - Options: `target_ratio` (default 0.25), `relevance`, `selection`,
    `context_role` and `additional_compress_kwargs`. Tested with
    langchain-core 0.3.0 and 1.6.9, llama-index-core 0.12.0 and 0.14.25, and
    haystack-ai 2.0.0, 2.21.0 and 3.3.0. Guides with runnable examples are in
    `docs/integrations/`.

### Changed
- PyPI metadata: the summary now says what LLMSlim does (context compression
  and planning for RAG and agents), with keywords for prompt and context
  compression and the supported frameworks, and the Python 3.13,
  `Python :: 3 :: Only` and `Typing :: Typed` classifiers.
- `llmslim[all]` includes the three framework extras.

## [0.8.0] - 2026-10-12

### Changed
- **Query-focused selection.** With a `query`, `compress()` no longer gives
  every chunk a proportional share of the budget. It ranks the context's
  structural units (documents, chat rounds with their session headers,
  paragraphs, or sentence windows of long paragraphs) against the query with
  BM25, light stemming, one round of pseudo-relevance feedback and a
  document-level prior, keeps the best units whole in their original order,
  and fills what is left with the best sentences of the next unit. Headers
  such as `Document [3](Title: ...)` or `Session Date: ...` are shown once
  above any kept unit. Everything stays local and deterministic.
- `compress_documents()` with a query shares one budget (`target_ratio` of the
  combined tokens) across documents by relevance: the most relevant documents
  stay whole and irrelevant ones come back empty. Without a query it still
  compresses each document on its own.
- **Line-structured text** (code, logs, test output, diffs, listings) keeps its
  line breaks: failures, tracebacks and their neighbourhood are kept first,
  runs of near-identical lines collapse into one line and a count, a
  contiguous tail is kept (most of the budget without a query), code keeps its
  skeleton (imports and every signature) plus the full bodies of the
  definitions most relevant to the query, and omitted spans are marked
  `... [N lines omitted]`.
- `ContextCompressor(selection=...)`: `"auto"` (default) as above,
  `"focus"` to always use query-focused selection, `"proportional"` for the
  0.7 behaviour. `CompressionResult.selection` records the path used.
- Compound words match in either direction ("superbowl" finds "Super Bowl",
  "gall bladder" finds "gallbladder").
- Units are about 1/32 of the budget (between 40 and 220 tokens), so a
  multi-passage context keeps more distinct passages.

### Added
- `relevance="semantic"` (on `compress()`, `compress_documents()` and
  `ContextCompressor`): an optional cross-encoder reranker,
  `cross-encoder/ms-marco-MiniLM-L-6-v2` (22M parameters, trained on MS MARCO
  only), rescoring the 80 strongest lexical candidates. It finds answers that
  share few words with the question. It runs on CPU, or on a GPU when one is
  available; install with `pip install "llmslim[semantic]"`. Any callable
  `scorer(query, texts) -> scores` can be passed instead, for example a hosted
  reranking API. The default stays `"lexical"`: no model, no download.

### Performance
- Sentence splitting looked for NLTK's punkt data on disk on every call. It
  now looks once per process: query-focused compression of a 2.9k-token,
  20-document context went from 213 ms to 24 ms, and of a 115k-token chat
  history from 2.4 s to 0.8 s.
- Guardrail detection skips text that cannot contain a protected sentence and
  no longer computes entity scores it does not need. The result is unchanged
  (checked on 109,424 sentence, role and floor combinations).

### Fixed
- Compression never returns empty text for non-empty input: if no whole unit
  fits, the best sentences or, at worst, a word-boundary prefix are kept.
- Trusted guardrails and developer `preserve_patterns` survive selection even
  inside units too large to keep whole (only the protected sentences are
  kept). Untrusted RAG, tool and assistant text still cannot earn this tier.
- A `ContextRole` enum passed as `context_role` is recognised as system or
  developer for guardrail protection (its `str()` form was compared before).

### Measured (Claude Haiku 5.5, `effort: low`; 0.7.2 → 0.8.0 lexical → 0.8.0 + reranker)
- LongMemEval-S, 90 questions, 8,000-token budget: 25.6% → 68.9% → 76.7%
  (full 114k-token history: 82.2%; on 90 fresh questions 76.7% against 72.2%).
- NaturalQuestions, 20 documents, 25% budget: 62.3 → 65.7 → 75.0 (full: 86.3).
- HotpotQA distractor, 200 questions: F1 61.7 → 67.5 → 69.4 (full: 74.9).
- LongBench v1 macro at 3,000 tokens: 52.4 → 54.9 → 54.2 (full: 54.9).
- LongBench v2, 180 questions: 51.1 → 53.9 → 55.6 (full: 60.0).
- Compressing a 1.3k-token Python file: about 3.5 s → 7 ms.
- Head to head on NaturalQuestions, 300 cases (100 questions × 3 answer positions)
  at the same budget: 78.7 with the reranker, against 78.0 for LongLLMLingua (a 7B
  model) and 69.0 for LLMLingua-2.
- Full tables, fresh-sample reruns and head-to-head runs of LLMLingua-2 and
  LongLLMLingua: `benchmarks/live/README.md`.

## [0.7.2] - 2026-10-11

### Fixed
- On Python 3.9, creating a `RuntimeSession` outside a running event loop no
  longer raises "There is no current event loop". The session lock is now
  created lazily inside the running loop and recreated when the loop changes.
  Behaviour on Python 3.10+ is unchanged.
- `plan_context()` no longer drops the most relevant optional document in
  favour of strictly lower-relevance documents that merely cost fewer tokens.
  After the value-maximizing knapsack, a deterministic relevance guard
  re-solves the allocation so the single most relevant, non-superseded
  evidence item is kept whenever it fits by dropping or compressing
  lower-relevance evidence. The decision reason records when the guard applied.
- Documents, memories and tool results whose caller metadata marks them
  superseded (`superseded` truthy, `superseded_by` set, or `valid_until` in the
  past) now have their planning value scaled by 0.05, so they are dropped
  before current evidence; the plan warns for each one. The v0.7 progressive
  planner may drop such non-required items regardless of lexical relevance,
  and `ContextRuntime` keeps these three metadata keys on external source items.
- Imperative wording in untrusted RAG, tool or assistant content no longer
  raises its planning value through instruction density. Such content remains
  rendered with `trusted="false"`.

## [0.7.1] - 2026-09-30

### Added
- Added opt-in cache planning with provenance-aware segmentation, provider-
  visible prefix fingerprints, append-only reuse estimates, generations,
  invalidation reasons, tenant-scoped metadata, and separate provider usage.
- Added execution-free request builders for OpenAI Responses, Anthropic
  Messages, Gemini CachedContent, and vLLM, plus strict in-process
  Transformers KV continuation checks. Sarvam prompt caching remains
  unverified and disabled.
- Added optional OpenAI provider-stateful continuation with guarded
  `previous_response_id`, Studio cache diagnostics, and a multi-turn offline
  benchmark. Existing runtime, planner, and compression calls remain valid.

### Verification
- The offline benchmark measures structural reuse opportunities and serialized
  request bytes; it does not claim provider hits, latency, or billed savings.
  See the release engineering report for test and deployment gates.

## [0.7.0] - 2026-09-26

### Added
- Added `ContextEnvelope`, a deterministic `ContextGraph`, progressive
  quality-gated planning, local `ContextPolicy`, `ContextRuntime`, bounded
  in-memory sessions, and prompt-free local `ContextTrace`.
- Added execution-free generic, Sarvam, OpenAI-compatible, and text-only
  OpenAI Agents SDK input adapters. The existing APIs and planner remain
  available unchanged.
- Added a Studio Context Inspector, offline context CLI, a frozen 112-case
  five-baseline benchmark, and opt-in live Sarvam/OpenAI evaluation harness.
- Tagged and hash-pinned the 0.7.0 wheel for Studio server functions so they
  install the matching runtime without depending on a previous package release.

### Verification
- Local release candidate: 623 tests passed, three optional MCP skips,
  90.20% branch coverage, Ruff passed, a scoped MyPy check passed, and
  wheel/sdist built. Hosted deployment and live-provider evaluation remain
  release gates.

## [0.6.0] - 2026-09-20

### Added
- Added deterministic multiple-choice context allocation across trusted
  instructions, chat, RAG, memory, tool results, and authoritative tool
  schemas, with explainable decisions and explicit infeasibility.
- Added balanced, quality-first, cost-first, and latency-first policies,
  conservative post-plan validation, local metrics, estimated cost telemetry,
  and stable `plan_context()` / `AdaptiveContextPlanner` APIs.
- Added `llmslim plan`, unified `ContextSource` / `ContextStore` boundaries,
  runnable examples, migration guidance, and dedicated planning documentation.

### Changed
- Retained the existing `compress()` family while positioning compression as
  one representation mechanism inside complete-context planning.
- Raised the declared minimum Python version from 3.8 to 3.9 so packaging
  metadata matches the tested CI matrix and source/tooling baseline.

### Security
- Added a disabled-by-default hosted Sarvam control plane with HMAC-pseudonymous
  network/session identities, distributed sliding rate windows, repeated
  high-cost request detection, atomic token and spend reservations, expiring
  concurrency slots, strict payload ceilings, safe errors, aggregate-only
  telemetry, and an environment kill switch.
- Preserved provenance hard constraints, authoritative tool schemas, no tool
  execution, no automatic persistence, and no browser/provider key exposure.

### Integrations
- Added optional official-SDK Sarvam rewrite/chat support and dated INR model
  profiles for `sarvam-105b` and `sarvam-105b-conversations`.
- Added bounded read-only Zoho CRM/WorkDrive sources and explicit PyMongo async
  memory/Atlas retrieval. External content remains untrusted by default.
- Added a separate MongoDB operational ledger for hosted rate, token, spend,
  concurrency, and aggregate telemetry records; local LLMSlim needs no database.
- Added a data-only MCP bridge. FULL and MEASURE_ONLY remain stable;
  SELECTIVE remains explicit and experimental and never executes tools.

### Benchmarks
- Added a 28-case frozen multilingual offline planner benchmark across chat,
  RAG, tools, mixed context, mocked external sources, and 12 languages.
- Added a separately gated live Sarvam harness; normal tests never spend credits
  and no live result is claimed without a sanitized measured artifact.

### Web/Studio
- Added Offline Planner and quota-limited Hosted Sarvam modes, planner decision
  traces, final answers, and clearly separated `ESTIMATED` versus
  `PROVIDER_REPORTED` usage/cost telemetry.
- Added same-origin Vercel and Catalyst server routes. Hosted mode remains off
  until the key, durable quota store, HMAC secret, and budgets are configured.

### Packaging
- Added optional `sarvam`, `zoho`, and `mongodb` extras while preserving
  `semantic`, `mcp`, and `agents`; the combined `all` extra includes each.
- Kept MCP Streamable HTTP on the official MCP 2.x `httpx2` transport and
  declared that directly imported client in the MCP/Agents extras.

### Known limitations
- MCP SELECTIVE remains experimental and opt-in.
- Offline benchmark checks are task-grounded but are not a universal model
  quality claim. Live Sarvam metrics are absent unless the paid harness runs.
- Hosted inference depends on operator-configured MongoDB, provider/platform
  alerts, production secrets, and explicit activation; it is not unlimited.

## [0.5.0] - 2026-09-13

### MCP catalog integration
- Added optional `llmslim[mcp]` support for official-SDK Streamable HTTP and
  argv-only stdio catalog sources, bounded `tools/list` pagination, monotonic
  cache hints, immutable snapshots, and stale-plan-safe hydration.
- Added stable full-catalog and measure-only plans. Selective exposure remains
  explicit, opt-in, and **RESEARCH_ONLY**.
- Added a framework-neutral host bridge and an optional OpenAI Agents SDK
  bridge. Both preserve host authorization and execution ownership.

### Packaging and security
- Kept MCP and Agents SDK dependencies out of the base install; the extras
  require Python 3.10+.
- Rejected credential-bearing endpoint URLs and non-localhost HTTP; stdio
  sources take an executable plus literal argv and never invoke a shell.

---

### Fixed
- Refreshed catalogs revoke stale cache entries, and returned snapshots cannot mutate cached authority.
- Agents bridges reject mismatched plans and hydrate authoritative schemas before exposing tools.

### Website
- Redesigned responsive landing page, dark/light themes, restrained parallax, and a Sarvam integration section.
- LLMSlim is accepted into the Sarvam Startup Program; existing indexing routes are preserved.

## [0.4.0] - 2026-08-20

### Tool contract infrastructure
- Added provider-aware `ToolSchema` representations and adapters for supported
  MCP, OpenAI function, Anthropic, and generic tool shapes.
- Added deterministic canonical JSON serialization, complete-contract SHA-256
  fingerprints, conservative exact-equivalence verification, schema
  inspection, and safe catalog optimization.
- Preserved authoritative raw schemas: stable infrastructure operates on copied
  representations and does not authorize, execute, or rewrite a contract.

### Experimental tool-context retrieval
- Added deterministic TF-IDF and BM25 retrievers, catalog-fingerprint caches,
  and conservative full-catalog fail-open behavior.
- Added optional local-only multilingual dense retrieval and BM25+dense RRF
  using `intfloat/multilingual-e5-small` at pinned revision
  `0e60b8d9d2166d80387f86e3b48ec9ced55f4d15`.
- Retrieval, selective exposure, context planning, and lazy hydration remain
  **RESEARCH_ONLY**; they are never enabled automatically.

### Benchmarks
- Added Phase 4 measurements for 375 schemas across 18 catalogs. Lossless
  serialization saved 0 tokens because the baseline was already compact
  canonical JSON.
- Added frozen-corpus Phase 4.5/4.6 retrieval evaluation. Dynamic retrieval
  retains high all-required recall by failing open often and has zero median
  tokens avoided, so it is not a production optimization claim.
- External ToolRet validation was attempted but not completed within the
  declared CPU/resource budget; no external metric is claimed.

### Security
- Retrieval representations exclude tool annotations and `_meta` where
  applicable; remote references are not fetched automatically.
- Ranking is not authorization and does not execute tools. Caller/provider
  provenance remains unauthenticated by LLMSlim.

### Packaging
- Added `jsonschema` for stable schema inspection and retained semantic
  dependencies behind the optional `llmslim[semantic]` extra.

## [0.3.1] - 2026-08-13

> Verified release: 432 tests passed, 0 failed; 92.57% branch coverage;
> Ruff passed; `benchmark.py` reported 432 passed / 0 failed.

### Security
- **Provenance-aware priority locking (P0-1, prompt-injection hardening;
  internally found, no CVE or advisory).** Added a
  `ContextRole` trust boundary (`system`/`developer`/`user`/`assistant`/`tool`/
  `rag`/`general`). Untrusted content (`rag`/`tool`/`assistant`) can no longer
  reach the hard-locked Priority Tier 4 or become `must_keep` from imperative
  wording, safety patterns, **or** `preserve_patterns`, closing the indirect
  prompt-injection amplification path. Trusted `system`/`developer` content
  retains full protection. This *mitigates compression-induced instruction
  elevation*; it is **not** complete prompt-injection prevention (defense in
  depth still required).
- **Rewrite template fence-breakout protection (P1-1).** A literal
  `---END TEXT---` (etc.) inside user text can no longer terminate the template's
  content region. Uses a content-preserving nonce fence: user text is passed
  **byte-for-byte unchanged**; only the template's own delimiters are hardened.

### Added
- `ContextRole` enum (exported from `llmslim`) and a `context_role` parameter on
  `compress()` / `ContextCompressor` (string or enum accepted).
- `CompressionResult.token_counter_used` (`"tiktoken"` | `"heuristic"`) and
  `tokens.get_active_token_counter_name()` (P1-4).
- Inline backtick code-span protection in sentence splitting (P0-2).
- CJK ideographic sentence boundaries `。` / `！` / `？` (P1-2).

### Changed (intentional behavioural changes, NOT 100% backward compatible)
- **`compress_documents()` now defaults to `context_role=ContextRole.RAG`.**
  Imperative sentences in retrieved documents are no longer force-kept.
- **`compress_chat_messages()` now propagates each message's role** as
  provenance (`system`→SYSTEM, `developer`→DEVELOPER, `user`→USER,
  `assistant`→ASSISTANT, `tool`→TOOL; unknown→GENERAL). No silent collapse.
- `count_tokens()` emits a one-time `logging.warning` when falling back to the
  character heuristic (P1-4).

### Fixed
- **Benchmark runner (P0-3).** `benchmarks/benchmark.py` now reports the real
  pytest pass/fail counts via a result-collector plugin instead of hardcoded
  `(159, 0)` / `(154, 5)` tuples, eliminating the false 5-failure result.

### Removed
- Dead code (P1-3): unused `_select_for_chunk()`, `_knapsack_select()`, and
  `_greedy_select()` static methods in `core.py`.

### Backward compatibility
- The default `compress(text, ...)` call (role `GENERAL`) is byte-for-byte
  identical to v0.3.0.

---

## [0.3.0] - 2026-07-18


### Added
- **Hybrid Prompt Compression & Semantic Optimization**: Extended `compress()` with `strategy` parameter supporting `"extractive"` (default), `"rewrite"`, and `"hybrid"` strategies.
- **Provider Abstraction Layer**: Zero-dependency `BaseRewriteProvider` ABC and `CallableProvider` wrapping custom functions or LLM APIs without hardcoding external dependencies.
- **Future-Proof `RewriteRequest`**: Clean request object interface passing text, target ratio, content type hints, prompt constraints, and metadata to providers.
- **Multi-Stage Semantic Validation Pipeline**: 4 independent validators (`StructuralValidator`, `InstructionValidator`, `EntityValidator`, `BaseSimilarityValidator`) ensuring rewrites never compromise prompt fidelity.
- **Pluggable Similarity Validation**: `BaseSimilarityValidator` interface with default offline `TfidfSimilarityValidator` (replaceable by embedding models or custom metrics).
- **Versioned Prompt Templates**: Builder functions (`build_general_template`, `build_rag_template`, `build_chat_template`, `build_system_prompt_template`, `build_documentation_template`, `build_code_template`) and `TemplateResolver` for domain-specific prompt generation.
- **Grouped `RewriteMetadata`**: Clean telemetry grouping inside `CompressionResult` for strategy outcomes, validation scores, latency, and failure reasons.
- **Strategy Benchmarking**: Benchmark framework extension in `benchmarks/benchmark_rewrite.py` measuring token reduction, latency, instruction/entity retention, and Validation Failure Rate.
- **CLI Strategy Parameter**: CLI `-s` / `--strategy` flag supporting `extractive`, `rewrite`, and `hybrid` modes.

### Changed
- Refactored rewrite functionality into isolated `llmslim.rewrite` sub-package (`base`, `engine`, `templates`, `validation`).
- Top-level `__init__.py` clean exports for `BaseRewriteProvider`, `CallableProvider`, `RewriteRequest`, `RewriteEngine`, `RewriteMetadata`, `RewriteValidator`, and `ValidationResult`.

### Improved
- Single-responsibility architecture separating prompt construction (`TemplateResolver`), execution (`RewriteEngine`), and validation (`RewriteValidator`).
- Improved error handling in `RewriteEngine` to automatically catch provider exceptions and fall back to extractive compression.

### Performance
- Extractive mode performance remains untouched (< 5ms CPU overhead for standard prompts).
- Hybrid mode executes fast extractive pre-compression to reduce tokens before optional LLM provider invocation.

### Testing
- Comprehensive test suite expansion with 130+ new test assertions across `test_providers.py`, `test_templates.py`, `test_validation.py`, `test_rewrite.py`, and `test_v03_regression.py`.
- Maintained > 90% code coverage (92.42% measured across 22 source modules).

### Documentation
- Created `examples/rewrite_example.py` demonstrating extractive, rewrite, and hybrid strategy workflows.
- Created `examples/custom_provider_example.py` showing custom `BaseRewriteProvider` subclassing.
- Updated `README.md` quickstart, CLI options, and feature tables.

### Backward Compatibility
- 100% backward compatible with v0.2.0. Default `strategy="extractive"` remains offline, deterministic, and byte-identical. Existing code calling `compress(text, target_ratio=0.5)` continues working without changes.

### Migration
- No code changes required for upgrading from v0.2.0 to v0.3.0 when using default extractive compression.
- To enable semantic rewriting, pass `strategy="rewrite"` (or `"hybrid"`) and supply a `provider=` parameter (e.g. `CallableProvider(my_llm_func)`).

### Known Limitations
- Semantic rewrite strategy requires user-supplied `provider=` parameter since core `llmslim` carries zero external LLM SDK dependencies.
- Lexical TF-IDF similarity validator may require a custom `BaseSimilarityValidator` implementation when validating heavily paraphrased text.

---

## [0.2.0] - 2026-07-13

### Added
- **Instruction Retention Engine**: Automatically extracts and prioritizes explicit user instructions, System Prompts, Markdown headers, code block delimiters, and task constraints.
- **Named Entity Preservation**: Integrated regex and heuristic entity recognition for proper names, dates, financial metrics, technical identifiers, and URLs.
- **Semantic & Hybrid Chunking**: Sliding-window semantic boundary splitting with dynamic fallback to paragraph/sentence boundaries.
- **Multi-Model Embeddings Support**: Optional integration with `sentence-transformers` alongside TF-IDF / N-gram fallback ranking.
- **Model Cost Estimation**: `cost.py` utility for calculating token savings and USD cost reduction across OpenAI (GPT-4o, O1), Anthropic (Claude 3.5 Sonnet), and Google (Gemini 1.5 Pro) models.
- **CLI Interface**: Interactive and file-based CLI tool (`llmslim input.txt -o compressed.txt --ratio 0.5`).
- **Comprehensive Benchmarks**: Benchmark regression suite, quality evaluation on multi-domain prompt datasets, and memory profile tooling.

### Improved
- Extractive sentence ranking using TF-IDF + PageRank sentence centrality.
- Token calculation accuracy using fallback word-token estimation and optional `tiktoken` exact token counting.
- Speed performance: Reduced compression overhead to < 5ms for 4k-token prompts.

### Changed
- Standardized `CompressionResult` output dataclass with detailed telemetry (original tokens, compressed tokens, compression ratio, preserved instructions count, entity count, processing time).

### Breaking Changes
- None. Fully backward compatible with `v0.1.0`.

### Known Limitations
- High-ratio compression (> 80%) on technical code snippets may drop syntactically dependent variable declarations if instructions are not explicitly flagged.

---

## [0.1.0] - 2026-06-16

### Added
- Initial public release of `llmslim`.
- Basic prompt compression engine with static ratio parameters.
- Basic TF-IDF sentence scoring and thresholding.
- Python 3.8+ package structure.
