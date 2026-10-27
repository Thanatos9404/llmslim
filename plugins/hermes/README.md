# LLMSlim context engine for Hermes Agent

When a conversation gets close to the model's context window, Hermes compacts it. The built-in compressor asks a
model to summarize the older turns. This plugin replaces that step with
[LLMSlim](https://github.com/Thanatos9404/llmslim), which compresses the older tool output and turns locally instead:

- **No LLM call.** Compaction runs on your machine and spends no tokens.
- **Deterministic.** The same conversation always compacts to the same messages.
- **Cache friendly.** The system prompt, the first messages and earlier compacted history are sent byte for byte the
  same, so the provider's prompt cache keeps matching the start of the prompt.

## Install

```bash
hermes plugins install llmslim --enable
hermes config set context.engine llmslim
```

Restart Hermes (CLI, gateway or desktop app). To go back to the built-in compressor:
`hermes config set context.engine compressor`.

The install asks before it adds the plugin's one Python dependency, `llmslim==0.12.0` from PyPI, which brings numpy,
scikit-learn and jsonschema with it. The plugin needs Hermes 0.21.7 or newer.

`hermes plugins install llmslim` installs the commit reviewed for the Hermes plugin catalog.
`hermes plugins install Thanatos9404/llmslim/plugins/hermes --enable` installs the latest one from this repository.

## What it does

- **When.** Compaction starts once the prompt reaches `threshold_percent` (75%) of the context window, using the token
  counts Hermes reports after each response.
- **What stays the same.** The system prompt, the first `protect_first_n` messages after it, and the user and assistant
  messages among the last `protect_last_n` are kept as they are. System messages and multimodal content are never
  rewritten.
- **What is compressed.** The text of the messages in between (tool results, user and assistant text) is compressed
  until the prompt is about `target_percent` (50%) of the window. If that is not enough, the oldest of them are
  replaced by a one-line placeholder, and as a last resort tool results among the last `protect_last_n` are compressed
  too. No message is removed, so every tool call keeps its result, and `tool_calls` and `tool_call_id` are untouched.
- **Prompt caching.** On the next compaction, messages that are exactly what the previous compaction returned are left
  alone as long as compressing the newer ones is enough.
- **Focus.** `/compress <topic>` keeps the parts of each message about that topic first.
- **Claude thinking.** On Claude models with preserved thinking, a signed thinking block is bound to everything before
  it. The engine removes the signed thinking of the first changed message and of every later assistant message, so
  Anthropic does not reject the request, and keeps the thinking before the first change.

## Settings

Set these under `plugins.entries.llmslim.settings` in `config.yaml`, or on the plugin's page under **Settings →
Plugins** in the desktop app:

| Setting | Default | Meaning |
| :--- | :--- | :--- |
| `threshold_percent` | `0.75` | Compress when the prompt reaches this share of the context window. |
| `target_percent` | `0.5` | Compress to about this share of the window. Must be below `threshold_percent`. |
| `protect_first_n` | `3` | Messages after the system prompt that are always kept word for word. |
| `protect_last_n` | `6` | Most recent messages kept word for word (tool results among them only as a last resort). |
| `min_tokens` | `200` | Messages with at most this many tokens are left as they are. |

```yaml
plugins:
  entries:
    llmslim:
      settings:
        target_percent: 0.4
        protect_last_n: 8
context:
  engine: llmslim
```

Two more settings, `relevance` and `additional_compress_kwargs`, are described in the
[full Hermes guide](../../docs/integrations/HERMES.md#options).

## What the plugin does and does not do

- It registers one context engine, `llmslim`, and nothing else: no tools, hooks, middleware or slash commands.
- It makes no network calls, starts no processes, runs no shell commands, needs no credentials or environment
  variables, and writes no files. It sends no telemetry.
- It reads its settings from `config.yaml` through Hermes's own config loader.
- It counts tokens with a character estimate (about four characters per token, close to Hermes's own estimate) and
  logs once that `tiktoken` is not installed. If `tiktoken` is present in Hermes's environment, LLMSlim uses it
  instead; `tiktoken` downloads its encoding file the first time it runs unless it is already cached.

## Long-term memory

LLMSlim also has an MCP server with long-term memory (`llmslim mcp`). It is separate from this plugin. To use it with
Hermes, add it under `mcp_servers` in `config.yaml` (this runs it with [uv](https://docs.astral.sh/uv/)):

```yaml
mcp_servers:
  llmslim:
    command: uvx
    args: ["--from", "llmslim[mcp]==0.12.0", "llmslim", "mcp"]
    connect_timeout: 120  # the first start downloads LLMSlim
```

The memory is a local SQLite file (`~/.llmslim/memory.db`). See [docs/MCP.md](../../docs/MCP.md) for its tools and
options.

## Links

- [Full guide, with a worked example](../../docs/integrations/HERMES.md)
- [Engine source](../../llmslim/integrations/hermes.py)
- [LLMSlim on PyPI](https://pypi.org/project/llmslim/)
- License: MIT
