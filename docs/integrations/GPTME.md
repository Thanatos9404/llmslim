# gptme

[gptme](https://gptme.org) compacts a conversation when it grows too large, and
lets a pip package supply the compaction strategy through its
[context provider interface](https://gptme.org/docs/context-compression.html).
`LLMSlimContextProvider` is such a provider: it keeps the system prompt, the
first messages, pinned messages, tool calls and the latest turns exactly as
they are, and compresses older tool output and history with LLMSlim until the
conversation fits gptme's limit. Tool output keeps its failures, tracebacks and
line structure instead of being replaced by a stub. It runs locally, with no
model call.

```bash
pip install "llmslim[gptme]"   # gptme 0.34 or newer, Python 3.10+
```

gptme pins `mcp<2`, while LLMSlim's MCP catalog support (`llmslim[mcp]`,
`llmslim[agents]`) needs `mcp>=2`, so the two cannot share an environment. That
is also why `llmslim[all]` does not include gptme.

Installing llmslim registers two gptme entry points, so there is nothing to
import or register yourself:

- `gptme.context_providers` → `llmslim`: `get_context_provider("llmslim")` and
  `list_providers()` find the provider.
- `gptme.plugins` → `llmslim`: makes LLMSlim the provider gptme's own
  compaction uses, when you ask for it.

## Use it for gptme's compaction

gptme's automatic compaction and `/compact trim` always ask for the provider
named `"default"` (gptme's development branch also uses it for
context-overflow recovery). Turn LLMSlim on in
`~/.config/gptme/config.toml` (or in a project's `gptme.toml`, which overrides
the user file key by key):

```toml
[plugin.llmslim]
compaction = true
# Optional:
keep_recent = 6      # most recent messages kept verbatim (tool output in them is still capped)
min_tokens = 200     # shorter messages are never compressed
```

Without `compaction = true` the plugin does nothing and gptme's own compaction
is unchanged. `/compact summarize` is not affected; it still asks the model for
a summary.

gptme imports the plugins of all installed packages at startup unless you keep
a `[plugins] enabled = [...]` allowlist, so with llmslim installed gptme also
imports llmslim (and NumPy and scikit-learn) when it starts.

## Example

```python
from gptme.message import Message
from gptme.tools.autocompact.context_provider import CompressionConfig, get_context_provider

from llmslim import count_tokens

# 300 lines of test output with one failure, as gptme's shell tool would return it.
lines = [f"tests/test_api.py::test_case_{i} PASSED" for i in range(300)]
lines.insert(200, "tests/test_refund.py::test_rounding FAILED - AssertionError: 10.05 != 10.04")
test_output = "Ran command: `pytest -q`\n" + "\n".join(lines)

log = [
    Message("system", "You are gptme, a coding agent.", pinned=True),
    Message("user", "Fix the failing refund test."),
    Message("assistant", "Running the tests.\n```shell\npytest -q\n```"),
    Message("system", test_output),
    Message("assistant", "One test fails: test_rounding. Reading refund.py next."),
    Message("user", "Go ahead."),
]

provider = get_context_provider("llmslim")  # found through llmslim's entry point
result = provider.compress(log, CompressionConfig(limit=1000, keep_head=2))

for before, after in zip(log, result.messages):
    print(f"{before.role:9} {count_tokens(before.content):5} -> {count_tokens(after.content):4} tokens")
print(result.limitations[0])
print()
print(result.messages[3].content)
```

Output (Python 3.12, gptme 0.34.0, token counts from tiktoken):

```text
system       10 ->   10 tokens
user          6 ->    6 tokens
assistant    12 ->   12 tokens
system     3631 ->   91 tokens
assistant    13 ->   13 tokens
user          3 ->    3 tokens
LLMSlim extractive compression: 3,675 -> 135 tokens; budget 1,000; 1 compressed, 0 dropped

Ran command: `pytest -q`
tests/test_api.py::test_case_0 PASSED
... [198 similar lines]
tests/test_api.py::test_case_199 PASSED
tests/test_refund.py::test_rounding FAILED - AssertionError: 10.05 != 10.04
tests/test_api.py::test_case_200 PASSED
... [98 similar lines]
tests/test_api.py::test_case_299 PASSED
```

gptme stores tool output as system messages. The test output is over gptme's
2,000-token limit for a single tool result, so it is compressed even though it
is recent: the failure and its neighbours stay, and the runs of passing tests
collapse into a count. This output is a favourable case, because near-identical
lines compress very well; prose is compressed only as far as the budget
requires. The tool call that produced the output is kept as it is, so the
model still sees which command ran.

## What it does

`compress(messages, config)` returns gptme's `CompactionResult`:

- Kept exactly as they are: the leading system messages (the system prompt),
  the first `config.keep_head` messages (pinned in the result, as gptme's own
  compaction does), pinned messages, assistant messages that contain a tool
  call or a code block, and the user and assistant messages among the last
  `keep_recent`.
- Tool output longer than `config.max_tool_result_tokens` (2,000 by default) is
  compressed to that size.
- If the conversation is still over `config.limit` (80% of the model's context
  when gptme passes no limit, the same default as gptme's compaction), the
  older messages are compressed by one shared ratio. If that is not enough,
  the oldest are replaced by a one-line placeholder such as
  `[3,631 tokens of earlier tool output omitted by LLMSlim]`, and as a last
  resort recent tool output is compressed below its cap.
- Messages are never removed or reordered; role, timestamp, `call_id` and the
  other fields are kept. `source_digest` is computed the way gptme computes it,
  and `covered_through` is the last message.
- Claude thinking, which gptme stores inline as `<think>` blocks with a
  `think-sig` signature, is never compressed as text: only the visible text of
  an assistant message is counted and compressed. On Claude models with
  preserved thinking (Haiku 5.5, Sonnet 5.5, Opus 5.5, Fable 5.1) a signed block
  is bound to everything before it, and Anthropic rejects it once an earlier
  message changes (HTTP 400 for accounts created on or after 2026-08-31). So
  from the first changed message on, signed thinking is removed, and
  `limitations` says so; the thinking before it is kept. While a tool round is
  unfinished and its assistant messages have signed thinking, only the tool
  output after the round's last thinking is shortened, if that fits the limit;
  the earlier history is compacted after the next user message instead.

Token counts use `llmslim.count_tokens` (tiktoken when installed).

## Options

Set them in `[plugin.llmslim]`, as keyword arguments, or with
`LLMSlimContextProvider.configured(...)`, which returns a class for
`register_provider`.

| Option | Default | Meaning |
| :--- | :--- | :--- |
| `keep_recent` | `6` | Most recent messages kept verbatim (their tool output is still capped). |
| `min_tokens` | `200` | Messages with at most this many tokens are not compressed. |
| `relevance` | `"lexical"` | `"lexical"`, `"semantic"` (needs `llmslim[semantic]`) or a callable `scorer(query, texts) -> scores`. |
| `additional_compress_kwargs` | `None` | Other `llmslim.ContextCompressor` options, for example `mode`. |
