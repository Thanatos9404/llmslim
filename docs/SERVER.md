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
| `--db` (a SQLite path, or a `postgresql://`, `mongodb://` or `mongodb+srv://` URL) | `LLMSLIM_MEMORY_DB` | `~/.llmslim/memory.db` (`/data/memory.db` in the image) |
| `--api-key` (repeatable) | `LLMSLIM_API_KEYS` (comma-separated) | none |
| `--allowed-host` (repeatable; `*` for any) | `LLMSLIM_ALLOWED_HOSTS` (comma-separated) | none: loopback names only without a key, any name with keys |
| `--budget` | | `2000` tokens for search |

To run several server processes or machines on one memory, point `--db` at Postgres or MongoDB. Postgres needs `pip install "llmslim[server,postgres]"`, MongoDB `pip install "llmslim[server,mongodb]"`:

```bash
LLMSLIM_MEMORY_DB="postgresql://llmslim:<password>@db.example.com:5432/llmslim" llmslim serve --host 0.0.0.0
LLMSLIM_MEMORY_DB="mongodb+srv://llmslim:<password>@cluster0.example.mongodb.net/llmslim" llmslim serve --host 0.0.0.0
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
| `POST /v1/memories/search` | `query`, the scope, optional `budget`, `relevance` (`"lexical"` or `"semantic"`), `since`, `until` | `{"text", "tokens", "budget", "history_tokens", "sessions_total", "sessions_kept", "turns": [...]}` |
| `POST /v1/context/fit` | `text`, `budget` (default 2000), optional `query` | `{"text", "tokens", "original_tokens"}`, within the budget for any text |
| `GET /v1/info` | | name, version and budgets |
| `GET /healthz` | | `{"status": "ok"}`, without a key |

The fields mean what they mean in Python (see [MEMORY.md](MEMORY.md)):
- `since` and `until` are ISO 8601 times.
- Messages are stored word for word.
- `search` returns all of a scope's history when it fits the budget, and otherwise the turns that answer the query.

```bash
curl -s localhost:8080/v1/memories -H 'content-type: application/json' \
  -d '{"user_id": "asha", "messages": [{"role": "user", "content": "I moved to Pune last month."}]}'

curl -s localhost:8080/v1/memories/search -H 'content-type: application/json' \
  -d '{"user_id": "asha", "query": "Where did I move to?", "budget": 1500}'
```

Put `text` from a search into your prompt as **data, not instructions**. Add it to the new user turn rather than
rewriting earlier turns or a system prompt (see [MEMORY.md](MEMORY.md#where-to-put-the-context-never-re-render-earlier-turns)).

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

## From Python

```python
from llmslim.memory import Memory
from llmslim.server import create_app

app = create_app(Memory("memory.db"), api_keys=["<a key of 16+ characters>"])  # any ASGI server can run it
```
