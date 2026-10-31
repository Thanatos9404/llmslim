# `llmslim serve`: memory and context over HTTP

`llmslim serve` puts [`llmslim.memory`](MEMORY.md) and context fitting behind a small JSON API, so apps written in any
language can use them:
- one process and one SQLite file;
- no model calls;
- nothing leaves your infrastructure.

```bash
pip install "llmslim[server]"
llmslim serve                      # http://127.0.0.1:8080, no key needed on loopback
```

It needs llmslim 0.10.0 or newer.

## Run it for other machines

With no API key, the server only binds to the loopback interface. To serve a network, set one or more keys. Clients
then send `Authorization: Bearer <key>` on every `/v1` request.

Without a key, the server also answers only requests addressed to this machine by name (`localhost`, `127.0.0.1`,
`[::1]` or a `*.localhost` name) that no other web page sent; other requests get a 403 (see [Security](#security)). If
your clients reach it by another name, such as `host.docker.internal` from a container, add it with `--allowed-host`.

```bash
export LLMSLIM_API_KEYS="$(llmslim serve --new-key)"
llmslim serve --host 0.0.0.0 --port 8080 --db /var/lib/llmslim/memory.db
```

Or with Docker, from a checkout of this repository:

```bash
docker build -t llmslim .
docker run -p 8080:8080 -e LLMSLIM_API_KEYS="<your key>" -v llmslim-data:/data llmslim
```

| Flag | Environment variable | Default |
|---|---|---|
| `--host` | `LLMSLIM_HOST` | `127.0.0.1` (`0.0.0.0` in the image) |
| `--port` | `LLMSLIM_PORT` | `8080` |
| `--db` (a SQLite path or a `postgresql://` URL) | `LLMSLIM_MEMORY_DB` | `~/.llmslim/memory.db` (`/data/memory.db` in the image) |
| `--api-key` (repeatable) | `LLMSLIM_API_KEYS` (comma-separated) | none |
| `--allowed-host` (repeatable; `*` for any) | `LLMSLIM_ALLOWED_HOSTS` (comma-separated) | none: loopback names only without a key, any name with keys |
| `--budget` | | `2000` tokens for search |
| `--upstream-url` ([chat endpoint](#chat-with-memory-an-openai-compatible-endpoint-experimental)) | `LLMSLIM_UPSTREAM_URL` | none: the chat endpoint is off |
| (no flag: the upstream's key never goes on a command line) | `LLMSLIM_UPSTREAM_API_KEY` | none |
| `--memory-budget` | | `1000` tokens of recalled memory per chat request |
| `--store-only` | | off: chat requests get recalled memory |
| `--upstream-timeout` | | `120` seconds for the upstream to start answering, and between streamed chunks |

To run several server processes or machines on one memory, point `--db` at Postgres. It needs `pip install "llmslim[server,postgres]"`:

```bash
LLMSLIM_MEMORY_DB="postgresql://llmslim:<password>@db.example.com:5432/llmslim" llmslim serve --host 0.0.0.0
```

## API

All bodies and responses are JSON. Errors look like `{"error": {"type": "invalid_request", "message": "..."}}`, with
status 400, 401, 403, 404, 413 or 501. A value of the wrong type or out of range, JSON nested past the parser's
limit, and text that isn't valid Unicode (a lone surrogate such as `"\ud800"`) are 400s.

| Method and path | Body or query | Returns |
|---|---|---|
| `POST /v1/memories` | `messages` (a string, a `{role, content}` object or a list of them), at least one of `user_id`, `agent_id`, `run_id`, optional `timestamp`, `metadata` | `201 {"items": [...]}`, the stored messages |
| `GET /v1/memories` | `?user_id=&agent_id=&run_id=&since=&until=&limit=100&offset=0` | `{"items", "total", "offset", "limit"}`, oldest first |
| `GET /v1/memories/{id}` | | one message |
| `PATCH /v1/memories/{id}` | `content` and/or `metadata` | the updated message |
| `DELETE /v1/memories/{id}` | | `{"deleted": 1}` |
| `DELETE /v1/memories` | `?user_id=` (or `agent_id`, `run_id`; one is required) | `{"deleted": n}` |
| `POST /v1/memories/search` | `query`, the scope, optional `budget`, `relevance` (`"lexical"` or `"semantic"`), `since`, `until`, `explain` (`true` or `false`) | `{"text", "tokens", "budget", "history_tokens", "sessions_total", "sessions_kept", "turns": [...]}`, and `"explanation"` with `explain` |
| `POST /v1/context/fit` | `text`, `budget` (default 2000), optional `query` | `{"text", "tokens", "original_tokens"}`, within the budget for any text |
| `GET /v1/info` | | name, version and budgets |
| `POST /v1/chat/completions` | an OpenAI chat-completions request | the upstream's answer, with memory (see [below](#chat-with-memory-an-openai-compatible-endpoint-experimental)); 404 unless started with an upstream |
| `GET /v1/models` | | the upstream's model list; 404 unless started with an upstream |
| `GET /healthz` | | `{"status": "ok"}`, without a key |

The fields mean what they mean in Python (see [MEMORY.md](MEMORY.md)):
- `since` and `until` are ISO 8601 times.
- Messages are stored word for word.
- `search` returns all of a scope's history when it fits the budget, and otherwise the turns that answer the query.
- `"explain": true` adds `explanation` to a search: why each stored turn and each section was kept, cut or left out, as `SearchExplanation.to_dict()` gives it (see [MEMORY.md](MEMORY.md#why-a-turn-was-kept-or-left-out)). The rest of the response is the same.

```bash
curl -s localhost:8080/v1/memories -H 'content-type: application/json' \
  -d '{"user_id": "asha", "messages": [{"role": "user", "content": "I moved to Pune last month."}]}'

curl -s localhost:8080/v1/memories/search -H 'content-type: application/json' \
  -d '{"user_id": "asha", "query": "Where did I move to?", "budget": 1500}'
```

Put `text` from a search into your prompt as **data, not instructions**. Add it to the new user turn rather than
rewriting earlier turns or a system prompt (see [MEMORY.md](MEMORY.md#where-to-put-the-context-never-re-render-earlier-turns)).

## Chat with memory: an OpenAI-compatible endpoint (experimental)

Start the server with an upstream, and `POST /v1/chat/completions` answers like the OpenAI API, with memory. Any
client that takes an OpenAI base URL gets memory without code: the OpenAI SDKs, and voice platforms with a "custom
LLM" setting.

```bash
export LLMSLIM_API_KEYS="$(llmslim serve --new-key)"   # what your clients send
export LLMSLIM_UPSTREAM_API_KEY="<the upstream's key>"  # read from the environment only, never from a flag
llmslim serve --host 0.0.0.0 --upstream-url https://api.openai.com/v1
```

Any OpenAI-compatible base URL works, such as a model provider's or a local vLLM or Ollama server
(`--upstream-url http://127.0.0.1:11434/v1`, no key needed). Without `--upstream-url` the endpoint is off and answers
404. It is experimental: it may change in a minor release (see [API_STABILITY.md](API_STABILITY.md#experimental)).

For each request, the server:
1. **Recalls.** It searches the scope's memory with the latest user message, within `--memory-budget` tokens (default
   1000), and adds what it finds as one new user message just before that message. Turns the request already carries
   are left out, so a conversation's own earlier turns don't come back twice. When nothing is found, nothing is added.
2. **Forwards** the request to the upstream with the upstream's key, and passes the answer back: JSON as it came, a
   stream chunk by chunk as it arrives.
3. **Stores** the new turns after a successful answer, word for word: the latest user message (when it is the last
   message, a new user turn) and the text of the reply. The history the client re-sends is never stored again.

### Which memory: the scope

| Request | Scope |
|---|---|
| `X-LLMSlim-User-Id` header, or else the request's `user` field | the user. The header wins when both are set. |
| `X-LLMSlim-Agent-Id` header | the agent, so each agent keeps its own memory of a user |
| `X-LLMSlim-Session-Id` header | one conversation or call: turns are stored under it, and recall searches all the user's sessions |

Without a user or agent id the server doesn't touch memory: the request goes to the upstream as it is and nothing is
stored (a session id alone is not a scope). Ids are 1 to 256 characters on one line; headers are ASCII. Anything
else is a 400.

Two more request headers:
- `X-LLMSlim-Memory`: `store-only` (store, don't recall), `recall-only` (recall, don't store) or `off` (neither).
- `X-LLMSlim-Memory-Budget`: the most tokens of recalled memory for this request, up to the server's limit.

Each answer says what recall did in `X-LLMSlim-Recall`: `injected` (with `X-LLMSlim-Recall-Tokens`), `none` (nothing
found), `off`, `no-scope` or `failed` (memory raised an error; the request went on without it).

### Examples

```bash
curl -s https://memory.example.com/v1/chat/completions \
  -H "Authorization: Bearer $LLMSLIM_KEY" -H 'content-type: application/json' \
  -H 'X-LLMSlim-User-Id: asha' -H 'X-LLMSlim-Session-Id: call-0193' \
  -d '{"model": "<model>", "messages": [{"role": "user", "content": "Book my usual slot for Tuesday."}]}'
```

With the OpenAI Python SDK, point `base_url` at the server and use an llmslim key as the API key:

```python
from openai import OpenAI

client = OpenAI(base_url="https://memory.example.com/v1", api_key="<an llmslim server key>")
reply = client.chat.completions.create(
    model="<model>",
    messages=[{"role": "user", "content": "Book my usual slot for Tuesday."}],
    user="asha",                                          # or extra_headers={"X-LLMSlim-User-Id": "asha"}
    extra_headers={"X-LLMSlim-Session-Id": "chat-42"},
    stream=True,
)
```

**Voice platforms.** Where a platform takes a custom LLM as an OpenAI-compatible URL (Vapi and ElevenLabs Agents
do, for example), set the URL to your server's `https://.../v1` and the API key to an llmslim server key. The server
must be reachable from the platform, so run it with keys and TLS, never keyless. Pass the caller's id as
`X-LLMSlim-User-Id` if the platform lets you set request headers, or in the request's `user` field, and a call id as
`X-LLMSlim-Session-Id`. Without a user id there is no memory.

### Cache safety, and its one-turn cost

The server never edits, removes or reorders anything the client sent. Everything before the latest user message goes
to the upstream byte for byte, including assistant messages with reasoning or thinking fields and their signatures.
The recalled message goes right before the latest user message, never between an assistant's tool call and its
result, and it is never put into the system prompt.

The client re-sends its own history each turn, and that history doesn't have the recalled message the server added
last turn. So turn N goes upstream as `[system, history, recalled N, user N]` and turn N+1 as
`[system, history, user N, reply N, recalled N+1, user N+1]`: two consecutive requests share their prefix only up to
just before user N. A provider's prompt cache misses on the last turn and its reply, once per request. Within a tool
loop (requests whose last message is a tool result), the recalled message stays the same as long as memory hasn't
changed, so the loop's prefix holds.

- **Voice agents:** the cost is usually small. Prompts are short, each turn is a sentence or two, and many voice
  prompts are below the length providers start caching at.
- **Coding agents and long agent loops**, where most of a bill is cache reads: use `--store-only` (or
  `X-LLMSlim-Memory: store-only`). Requests then reach the upstream exactly as the client sent them, turns are still
  stored, and the model can read memory through tools instead (`llmslim mcp`, or `memoryTools()` in the TypeScript
  client), which keep the whole prefix byte-identical.

### What is stored

- The latest user message when it is the last message, and the reply's text, word for word, under the scope (session
  included) with `metadata` `{"source": "chat"}`. Only text: images and audio in a list of content parts are skipped.
- Not stored: the history the client re-sends, system and developer messages, tool calls and tool results, reasoning,
  and with `n` above 1, every choice but the first.
- Nothing is stored when the upstream answers with an error, a stream breaks off or ends without saying it finished,
  or the client goes away before a stream ends. A request the client retries after a success is stored again.
- If memory fails (a locked database, say), the answer still goes out: without recalled memory, or unstored. The log
  says so, without what anyone said.

### Trust model

- **Recalled text is data.** It goes in a user message (never `system` or `developer`) that says it is data, not
  instructions, inside an `<llmslim_context ... trusted="false">` block. Envelope tags inside stored text are made
  inert, so a stored turn can't close the block or forge a trusted one. Text such as "ignore previous instructions"
  stays inside the block as data. This frames the text for the model; it is not a guarantee that a model won't follow
  it, so keep tools that act in the world behind your own checks.
- **The upstream is fixed by the server.** No body field (`model`, `base_url`, ...), header (`Host`,
  `X-Forwarded-*`, ...) or redirect changes where a request goes. Redirects are not followed.
- **Two keys, kept apart.** The client's `Authorization` is the llmslim server key; it is checked and never forwarded,
  and neither are the client's other headers. The upstream's key comes only from `LLMSLIM_UPSTREAM_API_KEY` (no flag,
  so it never shows in `ps`), and never appears in answers, errors or logs: an upstream 401 or 403 becomes a 502 with
  no detail, other upstream errors keep their `message`, `type`, `code` and `param` with the key redacted, and an
  answer that contains the key is cut off.
- **A server key spends the upstream key and reaches every scope**, because the client names the user. Give keys only
  to your backend or to a platform you trust with your model spend.
- **Without a key**, the endpoint follows the rest of the server: loopback only, `Host` names this machine, and no
  requests from other web pages.

### Limits

- Requests: the server's body cap (1 MB, so large base64 images may not fit), at most 1,000 messages, each with a
  string `role` and `content` that is a string, a list of content parts or null. Fields the server doesn't use go to
  the upstream untouched.
- The upstream: 10 seconds to connect, `--upstream-timeout` (default 120) to start answering and between streamed
  chunks, and 8 MB for an answer that isn't streamed.
- Errors: 502 when the upstream can't be reached, refuses the server's credentials, redirects or fails with a 5xx;
  504 when it times out; its 4xx answers pass through, and 429 and 503 keep `Retry-After`. A stream that breaks off
  after it started ends with an `error` event.

## Security

- **Keys give full access to every scope.** Call the server from your backend, never from a browser or a mobile app.
  Map your own users to `user_id` on the server side. The `/v1/memories/{id}` routes take any id, whatever its scope.
- **Keys are compared in constant time** and must be at least 16 characters. `--new-key` prints a random 43-character
  key.
- **Without a key, web pages can't use the server.** Any page the user opens can send requests to
  `http://127.0.0.1:8080`, and through DNS rebinding (a hostname that resolves first to the attacker, then to
  127.0.0.1) it can read the answers too. So a keyless server answers only requests whose `Host` names this machine
  (or a host given with `--allowed-host`), and refuses with a 403 any request whose `Origin` is another site.
  Clients that send no `Origin` (curl, SDKs, the TypeScript client) are not affected. With keys, a browser can't
  attach the key to a cross-site request, and every `Host` is accepted unless you pin names with `--allowed-host`.
- **Requests are capped:** bodies at 1 MB (413), search and fit budgets at 100,000 tokens, list pages at 1,000 items.
- **Hostile text stays cheap.** Content detection, sentence splitting and code-span handling take time linear in the
  input, so a crafted 1 MB body can't hold a worker for minutes, and `fit` holds its budget for any text: when
  compression can't get under it (one long code block, say), the result is cut to the longest head that fits.
- **Put TLS in front.** The server speaks plain HTTP. Run it behind a reverse proxy or a load balancer that terminates
  TLS.
- **Access logs.** Uvicorn's access log shows paths and query strings, including scope ids, but never bodies or keys.
- **The chat endpoint** has its own [trust model](#trust-model): the upstream is fixed by the server, the upstream's
  key never reaches clients or logs, and recalled text is framed as data.

## From Python

```python
from llmslim.memory import Memory
from llmslim.server import create_app

app = create_app(Memory("memory.db"), api_keys=["<a key of 16+ characters>"])  # any ASGI server can run it
```
