# LLMSlim Memory

Long-term memory for agent mode in VS Code. This extension adds the [LLMSlim](https://www.llmslim.app) MCP server to
VS Code's MCP support, so GitHub Copilot's agent mode, and any other chat that uses VS Code's MCP servers, can store
what you tell it and recall it in later chats.

The server keeps each message word for word in a SQLite file on your machine (`~/.llmslim/memory.db`) and picks what
to return when the agent asks. There is no LLM call inside it.

## What the agent gets

| Tool | What it does |
|---|---|
| `remember` | Stores a message word for word and returns its id. |
| `recall` | Returns the stored messages that answer a question, under their dates and whole where they fit, within a token budget. |
| `list_memories` | Lists recent messages with their ids, newest first. |
| `forget` | Deletes one message. It can't be undone. |
| `fit_context` | Shrinks a long text to a token budget, keeping what answers the query, in order. |

The tools carry MCP annotations: the read tools are marked read-only and `forget` destructive, so the editor can ask
before `forget` runs. `recall` labels what it returns as data, not instructions.

## Requirements

- **VS Code 1.101 or newer**, or another editor that supports VS Code's MCP extension API. In an editor without it, the
  extension shows the server config once, to add in that editor's own MCP settings.
- **[uv](https://docs.astral.sh/uv/)**. The extension starts the server with
  `uvx --from "llmslim[mcp]==0.11.1" llmslim mcp`, which needs Python 3.10 or newer; uv uses one you have or downloads
  one.
- **Or, without uv:** run `pip install "llmslim[mcp]"` (Python 3.10 or newer) and set **LLMSlim: Command** to
  `llmslim`, or to the full path of the `llmslim` executable. The server then starts as `llmslim mcp`.

If `uvx` can't be found when the server starts, the extension says so and links to uv's install guide and to the
setting.

## Use it

1. Install the extension and uv.
2. Run **MCP: List Servers** from the Command Palette: **LLMSlim Memory** is listed there, where you can start, stop
   or restart it. In Chat, its tools appear in agent mode's tools list.
3. Tell the agent something worth keeping, then ask about it in a new chat.

The first start takes longer while uvx downloads the package. Later starts use uv's cache.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `llmslim.command` | empty | The `llmslim` executable to run instead of `uvx`. The extension starts it as `<command> mcp`. Empty runs the pinned release with `uvx`. |
| `llmslim.memoryPath` | empty | The SQLite file that holds the memory, passed to the server as `LLMSLIM_MEMORY_DB`. Empty uses `~/.llmslim/memory.db`. |

Both are machine settings: VS Code reads them from your user (or remote) settings, never from a workspace's settings,
so an opened folder can't change which program starts.

## Privacy

- **The extension** sends no telemetry and makes no network requests. It looks for `uvx` (or your `llmslim.command`)
  and hands VS Code the command that starts the server.
- **The memory** stays on your machine, in the SQLite file above. The server makes no network calls of its own.
- **What reaches the network:** `uvx` downloading the `llmslim` package from PyPI the first time (and a Python build,
  if it finds no Python 3.10 or newer), and the tokenizer downloading one file the first time and caching it.
- **Your chat model** receives what `recall` returns, like any other tool result, so recalled messages go wherever
  your chat sends its requests.

To delete one memory, ask the agent to use `forget`. To delete all of it, delete the SQLite file.

## More

- [MCP server guide](https://github.com/Thanatos9404/llmslim/blob/main/docs/MCP.md): options, security and other
  clients.
- [Source and issues](https://github.com/Thanatos9404/llmslim). LLMSlim is MIT licensed.
